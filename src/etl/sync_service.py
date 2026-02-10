import logging
import json
from datetime import datetime
from sqlalchemy.orm import Session
from src.etl.obuma_client import ObumaClient
from src.models.models import (
    VentaHistorico, CompraHistorico, Producto, ContabilidadHistorico,
    CostoHistorico, ClienteFinal, SyncLog, Tenant, ObumaApiEndpoint,
    Proveedor, ClienteContacto, ClienteDireccion, Empleado, Remuneracion,
    VentaItem, VentaCotizacion, VentaCobro, VentaDte,
    CompraOC, CompraPago, CompraDteRecibido, GastoMenor, CrmLead,
    ProductoCategoria, ProductoSubCategoria, ProductoFabricante, ProductoPrecio
)

logger = logging.getLogger(__name__)

TIPO_DCTO_MAP = {
    "33": "Factura Electr.",
    "34": "Factura Exenta",
    "39": "Boleta Electr.",
    "41": "Boleta Exenta",
    "43": "Liquidacion Fact.",
    "46": "Factura Compra",
    "52": "Guia Despacho",
    "56": "Nota Debito",
    "61": "Nota Credito",
    "110": "Factura Export.",
    "111": "Nota Debito Exp.",
    "112": "Nota Credito Exp.",
}

ENDPOINT_MAP = {
    "clientes": "API : Clientes",
    "clientes_contactos": "API : Clientes Contactos",
    "clientes_direcciones": "API : Clientes Direcciones",
    "proveedores": "API : Proveedores",
    "productos": "API : Productos",
    "producto_categorias": "API : Productos",
    "producto_subcategorias": "API : Productos",
    "producto_fabricantes": "API : Productos",
    "producto_precios": "API : Productos",
    "empleados": "API : Empleados",
    "remuneraciones": "API : Remuneraciones",
    "ventas": "API : Ventas",
    "ventas_items": "API : Ventas",
    "ventas_cotizaciones": "API : Ventas > Cotizaciones",
    "ventas_cobros": "API : Ventas > Cobros",
    "ventas_dte": "API : Ventas > Consultar DTE emitidos",
    "compras": "API : Compras",
    "compras_oc": "API : Compras OC",
    "compras_pagos": "API : Compras > Pagos",
    "compras_dte_recibidos": "API : Compras DTE recibidos",
    "contabilidad": "API : Contabilidad",
    "gastos_menores": "API : Compras GASTOS menores",
    "crm_leads": "CRM manejo de leads por API",
}


class SyncService:
    def __init__(self, db: Session, tenant_id: int = None):
        self.db = db
        self.client = ObumaClient()
        self.tenant_id = tenant_id or self._get_default_tenant_id()

    def _get_default_tenant_id(self) -> int:
        tenant = self.db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(nombre="Gabriel Hoyos", rut_empresa="default")
            self.db.add(tenant)
            self.db.commit()
            self.db.refresh(tenant)
        return tenant.id

    def _extract_items(self, data, *keys):
        if data is None:
            return []
        if isinstance(data, list):
            return data
        result = data.get("data")
        if result is not None and isinstance(result, list):
            return result
        for key in keys:
            val = data.get(key)
            if val is not None and isinstance(val, list):
                return val
        return []

    def _safe_float(self, val):
        try:
            return float(val or 0)
        except (ValueError, TypeError):
            return 0.0

    def _safe_int(self, val):
        try:
            return int(float(val or 0))
        except (ValueError, TypeError):
            return 0

    def _safe_str(self, val, default=""):
        if val is None:
            return default
        return str(val).strip()

    def _parse_date(self, date_str):
        if not date_str or date_str in ("0000-00-00", "0000-00-00 00:00:00"):
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y"):
            try:
                return datetime.strptime(str(date_str).strip()[:19], fmt)
            except (ValueError, TypeError):
                continue
        return None

    def _to_json(self, item):
        return json.dumps(item, default=str, ensure_ascii=False)

    def _get_obuma_id(self, item, *keys):
        for key in keys:
            val = item.get(key)
            if val and str(val) != "0":
                return str(val)
        return str(id(item))

    def _get_or_create_cliente(self, rut: str = None, nombre: str = "Sin nombre") -> int:
        if not rut or rut == "0":
            return None
        cliente = self.db.query(ClienteFinal).filter(
            ClienteFinal.rut == rut,
            ClienteFinal.tenant_id == self.tenant_id
        ).first()
        if not cliente:
            cliente = ClienteFinal(rut=rut, nombre=nombre, tenant_id=self.tenant_id)
            self.db.add(cliente)
            self.db.flush()
        return cliente.id

    async def sync_clientes(self) -> dict:
        data = await self.client.get_clientes()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("clientes", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "clientes")
        count = 0
        for item in items:
            rut = item.get("cliente_rut", "")
            if not rut or rut == "0":
                continue

            existing = self.db.query(ClienteFinal).filter(
                ClienteFinal.rut == rut,
                ClienteFinal.tenant_id == self.tenant_id
            ).first()

            nombre = item.get("cliente_razon_social", item.get("cliente_nombre_fantasia", ""))
            email = item.get("cliente_email", "")
            telefono = item.get("cliente_telefono", item.get("cliente_celular", ""))
            direccion = item.get("cliente_direccion_facturacion", "")
            giro = item.get("cliente_giro", "")
            comuna = item.get("cliente_comuna", "")
            ciudad = item.get("cliente_ciudad", "")
            obuma_id = self._safe_str(item.get("cliente_id", item.get("id", "")))

            if existing:
                existing.nombre = nombre or existing.nombre
                existing.email = email or existing.email
                existing.telefono = telefono or existing.telefono
                existing.direccion = direccion or existing.direccion
                existing.giro = giro or existing.giro
                existing.comuna = comuna or existing.comuna
                existing.ciudad = ciudad or existing.ciudad
                existing.obuma_id = obuma_id or existing.obuma_id
                existing.data_json = self._to_json(item)
            else:
                cliente = ClienteFinal(
                    tenant_id=self.tenant_id,
                    rut=rut,
                    nombre=nombre or "Sin nombre",
                    email=email,
                    telefono=telefono,
                    direccion=direccion,
                    giro=giro,
                    comuna=comuna,
                    ciudad=ciudad,
                    obuma_id=obuma_id,
                    data_json=self._to_json(item),
                )
                self.db.add(cliente)
            count += 1

        self.db.commit()
        db_count = self.db.query(ClienteFinal).filter(ClienteFinal.tenant_id == self.tenant_id).count()
        self._log_sync("clientes", len(items), db_count, 0)
        return {"synced": count, "total_api": len(items), "total_db": db_count}

    async def sync_clientes_contactos(self) -> dict:
        data = await self.client.get_clientes_contactos_all()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("clientes_contactos", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "contactos", "clientes_contactos")
        self.db.query(ClienteContacto).filter(ClienteContacto.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            contacto = ClienteContacto(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("contacto_id", item.get("id"))),
                cliente_id_obuma=self._safe_str(item.get("rel_cliente_id", item.get("cliente_id"))),
                nombre=self._safe_str(item.get("contacto_nombre", item.get("nombre"))),
                email=self._safe_str(item.get("contacto_email", item.get("email"))),
                telefono=self._safe_str(item.get("contacto_telefono", item.get("telefono"))),
                cargo=self._safe_str(item.get("contacto_cargo", item.get("cargo"))),
                data_json=self._to_json(item),
            )
            self.db.add(contacto)
            count += 1

        self.db.commit()
        self._log_sync("clientes_contactos", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_clientes_direcciones(self) -> dict:
        data = await self.client.get_clientes_direcciones_all()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("clientes_direcciones", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "direcciones", "clientes_direcciones")
        self.db.query(ClienteDireccion).filter(ClienteDireccion.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            direccion = ClienteDireccion(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("direccion_id", item.get("id"))),
                cliente_id_obuma=self._safe_str(item.get("rel_cliente_id", item.get("cliente_id"))),
                direccion=self._safe_str(item.get("direccion_calle", item.get("direccion"))),
                ciudad=self._safe_str(item.get("direccion_ciudad", item.get("ciudad"))),
                comuna=self._safe_str(item.get("direccion_comuna", item.get("comuna"))),
                region=self._safe_str(item.get("direccion_region", item.get("region"))),
                tipo=self._safe_str(item.get("direccion_tipo", item.get("tipo"))),
                data_json=self._to_json(item),
            )
            self.db.add(direccion)
            count += 1

        self.db.commit()
        self._log_sync("clientes_direcciones", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_proveedores(self) -> dict:
        data = await self.client.get_proveedores()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("proveedores", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "proveedores")
        count = 0
        for item in items:
            obuma_id = self._safe_str(item.get("proveedor_id", item.get("id")))
            if not obuma_id or obuma_id == "0":
                continue

            existing = self.db.query(Proveedor).filter(
                Proveedor.obuma_id == obuma_id,
                Proveedor.tenant_id == self.tenant_id
            ).first()

            if existing:
                existing.rut = self._safe_str(item.get("proveedor_rut", item.get("rut"))) or existing.rut
                existing.razon_social = self._safe_str(item.get("proveedor_razon_social", item.get("razon_social"))) or existing.razon_social
                existing.nombre_fantasia = self._safe_str(item.get("proveedor_nombre_fantasia"))
                existing.email = self._safe_str(item.get("proveedor_email", item.get("email")))
                existing.telefono = self._safe_str(item.get("proveedor_telefono", item.get("telefono")))
                existing.direccion = self._safe_str(item.get("proveedor_direccion", item.get("direccion")))
                existing.data_json = self._to_json(item)
            else:
                prov = Proveedor(
                    tenant_id=self.tenant_id,
                    obuma_id=obuma_id,
                    rut=self._safe_str(item.get("proveedor_rut", item.get("rut"))),
                    razon_social=self._safe_str(item.get("proveedor_razon_social", item.get("razon_social"))) or "Sin nombre",
                    nombre_fantasia=self._safe_str(item.get("proveedor_nombre_fantasia")),
                    email=self._safe_str(item.get("proveedor_email", item.get("email"))),
                    telefono=self._safe_str(item.get("proveedor_telefono", item.get("telefono"))),
                    direccion=self._safe_str(item.get("proveedor_direccion", item.get("direccion"))),
                    data_json=self._to_json(item),
                )
                self.db.add(prov)
            count += 1

        self.db.commit()
        db_count = self.db.query(Proveedor).filter(Proveedor.tenant_id == self.tenant_id).count()
        self._log_sync("proveedores", len(items), db_count, 0)
        return {"synced": count, "total_api": len(items), "total_db": db_count}

    async def sync_productos(self) -> dict:
        data = await self.client.get_productos()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("productos", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "productos")
        count = 0
        for item in items:
            obuma_id = str(item.get("producto_id", item.get("id", "")))
            existing = self.db.query(Producto).filter(
                Producto.obuma_id == obuma_id,
                Producto.tenant_id == self.tenant_id
            ).first()

            nombre = item.get("producto_nombre", item.get("nombre", ""))
            sku = item.get("producto_sku", item.get("sku", ""))
            categoria = item.get("producto_categoria", item.get("categoria", ""))
            precio_venta = self._safe_float(item.get("producto_precio_venta", item.get("precio_venta", 0)))
            costo = self._safe_float(item.get("producto_costo", item.get("costo", 0)))
            stock = self._safe_int(item.get("producto_stock", item.get("stock", 0)))

            if existing:
                old_costo = existing.costo
                existing.nombre = nombre or existing.nombre
                existing.sku = sku or existing.sku
                existing.categoria = categoria or existing.categoria
                existing.precio_venta = precio_venta
                existing.costo = costo
                existing.stock_actual = stock

                if costo and costo != old_costo:
                    costo_hist = CostoHistorico(
                        tenant_id=self.tenant_id,
                        producto_id=existing.id,
                        costo_unitario=costo,
                        cantidad=stock,
                        costo_total=costo * stock,
                        fecha=datetime.now(),
                        fuente="obuma",
                    )
                    self.db.add(costo_hist)
            else:
                producto = Producto(
                    tenant_id=self.tenant_id,
                    obuma_id=obuma_id,
                    nombre=nombre or "Sin nombre",
                    sku=sku,
                    categoria=categoria,
                    precio_venta=precio_venta,
                    costo=costo,
                    stock_actual=stock,
                )
                self.db.add(producto)
                self.db.flush()

                if costo:
                    costo_hist = CostoHistorico(
                        tenant_id=self.tenant_id,
                        producto_id=producto.id,
                        costo_unitario=costo,
                        cantidad=stock,
                        costo_total=costo * stock,
                        fecha=datetime.now(),
                        fuente="obuma",
                    )
                    self.db.add(costo_hist)
            count += 1

        self.db.commit()
        db_count = self.db.query(Producto).filter(Producto.tenant_id == self.tenant_id).count()
        self._log_sync("productos", len(items), db_count, abs(len(items) - db_count))
        return {"synced": count, "total_api": len(items), "total_db": db_count}

    async def sync_producto_categorias(self) -> dict:
        data = await self.client.get_categorias_productos()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("producto_categorias", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "categorias", "productosCategorias")
        self.db.query(ProductoCategoria).filter(ProductoCategoria.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            cat = ProductoCategoria(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("categoria_id", item.get("id"))),
                nombre=self._safe_str(item.get("categoria_nombre", item.get("nombre"))),
                data_json=self._to_json(item),
            )
            self.db.add(cat)
            count += 1

        self.db.commit()
        self._log_sync("producto_categorias", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_producto_subcategorias(self) -> dict:
        data = await self.client.get_subcategorias_productos()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("producto_subcategorias", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "subcategorias", "productosSubCategorias")
        self.db.query(ProductoSubCategoria).filter(ProductoSubCategoria.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            subcat = ProductoSubCategoria(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("subcategoria_id", item.get("id"))),
                nombre=self._safe_str(item.get("subcategoria_nombre", item.get("nombre"))),
                categoria_id_obuma=self._safe_str(item.get("rel_categoria_id", item.get("categoria_id"))),
                data_json=self._to_json(item),
            )
            self.db.add(subcat)
            count += 1

        self.db.commit()
        self._log_sync("producto_subcategorias", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_producto_fabricantes(self) -> dict:
        data = await self.client.get_fabricantes_productos()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("producto_fabricantes", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "fabricantes", "productosFabricantes")
        self.db.query(ProductoFabricante).filter(ProductoFabricante.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            fab = ProductoFabricante(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("fabricante_id", item.get("id"))),
                nombre=self._safe_str(item.get("fabricante_nombre", item.get("nombre"))),
                data_json=self._to_json(item),
            )
            self.db.add(fab)
            count += 1

        self.db.commit()
        self._log_sync("producto_fabricantes", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_producto_precios(self) -> dict:
        data = await self.client.get_productos_precios()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("producto_precios", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "precios", "productosConsultaPrecios")
        self.db.query(ProductoPrecio).filter(ProductoPrecio.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            precio = ProductoPrecio(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("id")),
                producto_id_obuma=self._safe_str(item.get("rel_producto_id", item.get("producto_id"))),
                producto_nombre=self._safe_str(item.get("producto_nombre", item.get("nombre"))),
                precio=self._safe_float(item.get("precio", item.get("precio_venta", 0))),
                lista_precio=self._safe_str(item.get("lista_precio", item.get("nombre_lista"))),
                data_json=self._to_json(item),
            )
            self.db.add(precio)
            count += 1

        self.db.commit()
        self._log_sync("producto_precios", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_empleados(self) -> dict:
        data = await self.client.get_empleados()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("empleados", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "empleados")
        count = 0
        for item in items:
            obuma_id = self._safe_str(item.get("empleado_id", item.get("id")))
            if not obuma_id or obuma_id == "0":
                continue

            existing = self.db.query(Empleado).filter(
                Empleado.obuma_id == obuma_id,
                Empleado.tenant_id == self.tenant_id
            ).first()

            nombres = self._safe_str(item.get("empleado_nombres", item.get("empleado_nombre", "")))
            apellido_p = self._safe_str(item.get("empleado_apellido_p", ""))
            apellido_m = self._safe_str(item.get("empleado_apellido_m", ""))
            nombre_completo = " ".join(filter(None, [nombres, apellido_p, apellido_m])).strip() or "Sin nombre"
            email = self._safe_str(item.get("empleado_email", item.get("empleado_email_personal", "")))
            cargo_val = self._safe_str(item.get("empleado_cargo", ""))
            if cargo_val == "0":
                cargo_val = self._safe_str(item.get("empleado_codigo", ""))

            if existing:
                existing.rut = self._safe_str(item.get("empleado_rut", item.get("rut"))) or existing.rut
                existing.nombre = nombre_completo
                existing.email = email
                existing.cargo = cargo_val
                existing.activo = str(item.get("empleado_activo", "1")) != "0"
                existing.data_json = self._to_json(item)
            else:
                emp = Empleado(
                    tenant_id=self.tenant_id,
                    obuma_id=obuma_id,
                    rut=self._safe_str(item.get("empleado_rut", item.get("rut"))),
                    nombre=nombre_completo,
                    email=email,
                    cargo=cargo_val,
                    activo=str(item.get("empleado_activo", "1")) != "0",
                    data_json=self._to_json(item),
                )
                self.db.add(emp)
            count += 1

        self.db.commit()
        db_count = self.db.query(Empleado).filter(Empleado.tenant_id == self.tenant_id).count()
        self._log_sync("empleados", len(items), db_count, 0)
        return {"synced": count, "total_api": len(items), "total_db": db_count}

    async def sync_remuneraciones(self) -> dict:
        data = await self.client.get_remuneraciones()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("remuneraciones", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "remuneraciones")
        self.db.query(Remuneracion).filter(Remuneracion.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            rem = Remuneracion(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("remuneracion_id", item.get("id"))),
                empleado_rut=self._safe_str(item.get("empleado_rut", item.get("rut"))),
                periodo=self._safe_str(item.get("periodo", item.get("remuneracion_periodo"))),
                total_haberes=self._safe_float(item.get("total_haberes", item.get("remuneracion_haberes", 0))),
                total_descuentos=self._safe_float(item.get("total_descuentos", item.get("remuneracion_descuentos", 0))),
                liquido=self._safe_float(item.get("liquido", item.get("remuneracion_liquido", 0))),
                data_json=self._to_json(item),
            )
            self.db.add(rem)
            count += 1

        self.db.commit()
        self._log_sync("remuneraciones", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_ventas(self) -> dict:
        data = await self.client.get_ventas()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("ventas", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "ventas")
        count = 0
        total_api = 0.0
        for item in items:
            obuma_id = str(item.get("venta_id", item.get("id", "")))

            existing = self.db.query(VentaHistorico).filter(VentaHistorico.obuma_id == obuma_id).first()
            if existing:
                neto = self._safe_float(item.get("venta_neto", 0))
                iva = self._safe_float(item.get("venta_iva", 0))
                total = self._safe_float(item.get("venta_total", 0))
                costo = self._safe_float(item.get("venta_costo", 0))
                utilidad = self._safe_float(item.get("venta_utilidad", 0))
                total_api += total

                existing.subtotal = neto
                existing.impuestos = iva
                existing.total = total
                existing.costo_total = costo
                existing.margen_neto = utilidad if utilidad else (neto - costo)
                existing.total_pagado = self._safe_float(item.get("venta_total_pagado", 0))
                existing.total_por_pagar = self._safe_float(item.get("venta_total_por_pagar", 0))
                existing.anulada = str(item.get("venta_anulada", "0")) == "1"
                existing.detalle = self._to_json(item)
                count += 1
                continue

            fecha = self._parse_date(item.get("venta_fecha_ingreso", item.get("fecha", None)))
            tipo_dcto_code = str(item.get("venta_tipo_dcto", item.get("tipo_documento", "")))
            tipo_dcto = TIPO_DCTO_MAP.get(tipo_dcto_code, f"Tipo {tipo_dcto_code}")

            neto = self._safe_float(item.get("venta_neto", item.get("neto", 0)))
            iva = self._safe_float(item.get("venta_iva", item.get("iva", 0)))
            total = self._safe_float(item.get("venta_total", item.get("total", 0)))
            costo = self._safe_float(item.get("venta_costo", item.get("costo_total", 0)))
            utilidad = self._safe_float(item.get("venta_utilidad", 0))
            total_api += total

            cliente_rut = item.get("cliente_rut", item.get("rut", None))
            cliente_nombre = item.get("cliente_razon_social", item.get("cliente_nombre", ""))
            cliente_id = self._get_or_create_cliente(cliente_rut, cliente_nombre)

            folio = str(item.get("venta_nro_dcto", item.get("folio", "")))
            anulada = str(item.get("venta_anulada", "0")) == "1"
            estado = "Anulada" if anulada else item.get("venta_estado", "Vigente")

            venta = VentaHistorico(
                tenant_id=self.tenant_id,
                obuma_id=obuma_id,
                cliente_id=cliente_id,
                fecha=fecha,
                tipo_documento=tipo_dcto,
                folio=folio,
                subtotal=neto,
                impuestos=iva,
                total=total,
                estado=estado,
                detalle=self._to_json(item),
                costo_total=costo,
                margen_neto=utilidad if utilidad else (neto - costo),
                total_pagado=self._safe_float(item.get("venta_total_pagado", 0)),
                total_por_pagar=self._safe_float(item.get("venta_total_por_pagar", 0)),
                anulada=anulada,
                observacion=item.get("venta_observacion", ""),
            )
            self.db.add(venta)
            count += 1

        self.db.commit()
        db_count = self.db.query(VentaHistorico).count()
        total_db_sum = self.db.query(VentaHistorico).with_entities(VentaHistorico.total).all()
        total_db_val = sum(v[0] for v in total_db_sum if v[0])

        self._log_sync("ventas", len(items), db_count,
                        abs(len(items) - count),
                        total_api=total_api, total_db=total_db_val)
        return {"synced": count, "total_api": len(items), "total_db": db_count}

    async def sync_ventas_items(self) -> dict:
        data = await self.client.get_ventas_items()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("ventas_items", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "items", "ventas_items")
        self.db.query(VentaItem).filter(VentaItem.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            vi = VentaItem(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("item_id", item.get("id"))),
                venta_id_obuma=self._safe_str(item.get("rel_venta_id", item.get("venta_id"))),
                producto_nombre=self._safe_str(item.get("item_nombre", item.get("producto_nombre", item.get("nombre")))),
                producto_sku=self._safe_str(item.get("item_sku", item.get("producto_sku", item.get("sku")))),
                cantidad=self._safe_float(item.get("item_cantidad", item.get("cantidad", 0))),
                precio_unitario=self._safe_float(item.get("item_precio", item.get("precio_unitario", 0))),
                descuento=self._safe_float(item.get("item_descuento", item.get("descuento", 0))),
                total=self._safe_float(item.get("item_total", item.get("total", 0))),
                data_json=self._to_json(item),
            )
            self.db.add(vi)
            count += 1

        self.db.commit()
        self._log_sync("ventas_items", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_ventas_cotizaciones(self) -> dict:
        data = await self.client.get_ventas_cotizaciones()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("ventas_cotizaciones", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "cotizaciones", "ventasCotizaciones")
        self.db.query(VentaCotizacion).filter(VentaCotizacion.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            cot = VentaCotizacion(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("cotizacion_id", item.get("id"))),
                folio=self._safe_str(item.get("cotizacion_folio", item.get("folio"))),
                fecha=self._parse_date(item.get("cotizacion_fecha", item.get("fecha"))),
                cliente_rut=self._safe_str(item.get("cliente_rut")),
                cliente_nombre=self._safe_str(item.get("cliente_razon_social", item.get("cliente_nombre"))),
                total=self._safe_float(item.get("cotizacion_total", item.get("total", 0))),
                estado=self._safe_str(item.get("cotizacion_estado", item.get("estado"))),
                data_json=self._to_json(item),
            )
            self.db.add(cot)
            count += 1

        self.db.commit()
        self._log_sync("ventas_cotizaciones", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_ventas_cobros(self) -> dict:
        data = await self.client.get_ventas_cobros()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("ventas_cobros", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "cobros", "ventasCobros")
        self.db.query(VentaCobro).filter(VentaCobro.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            cobro = VentaCobro(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("cobro_id", item.get("id"))),
                venta_id_obuma=self._safe_str(item.get("rel_venta_id", item.get("venta_id"))),
                fecha=self._parse_date(item.get("cobro_fecha", item.get("fecha"))),
                monto=self._safe_float(item.get("cobro_monto", item.get("monto", 0))),
                forma_pago=self._safe_str(item.get("cobro_forma_pago", item.get("forma_pago"))),
                estado=self._safe_str(item.get("cobro_estado", item.get("estado"))),
                data_json=self._to_json(item),
            )
            self.db.add(cobro)
            count += 1

        self.db.commit()
        self._log_sync("ventas_cobros", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_ventas_dte(self) -> dict:
        data = await self.client.get_ventas_dte()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("ventas_dte", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "dte", "ventas_dte")
        self.db.query(VentaDte).filter(VentaDte.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            dte = VentaDte(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("dte_id", item.get("id"))),
                tipo_dcto=self._safe_str(item.get("dte_tipo_dcto", item.get("tipo_dcto"))),
                folio=self._safe_str(item.get("dte_folio", item.get("folio"))),
                fecha=self._parse_date(item.get("dte_fecha", item.get("fecha"))),
                rut_receptor=self._safe_str(item.get("dte_rut_receptor", item.get("rut_receptor"))),
                razon_social=self._safe_str(item.get("dte_razon_social", item.get("razon_social"))),
                monto_total=self._safe_float(item.get("dte_monto_total", item.get("monto_total", 0))),
                estado_sii=self._safe_str(item.get("dte_estado_sii", item.get("estado_sii"))),
                data_json=self._to_json(item),
            )
            self.db.add(dte)
            count += 1

        self.db.commit()
        self._log_sync("ventas_dte", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_compras(self) -> dict:
        data = await self.client.get_compras()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("compras", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "compras")
        count = 0
        for item in items:
            obuma_id = str(item.get("compra_id", item.get("id", item.get("folio_dcto", ""))))
            existing = self.db.query(CompraHistorico).filter(CompraHistorico.obuma_id == obuma_id).first()
            if existing:
                continue

            fecha = self._parse_date(item.get("compra_fecha", item.get("fecha", None)))

            compra = CompraHistorico(
                tenant_id=self.tenant_id,
                obuma_id=obuma_id,
                fecha=fecha,
                proveedor=item.get("proveedor", item.get("compra_proveedor", "")),
                folio=str(item.get("folio_dcto", item.get("compra_folio", ""))),
                total=self._safe_float(item.get("total", item.get("compra_total", 0))),
                estado=item.get("estado", item.get("compra_estado", "")),
                detalle=self._to_json(item),
            )
            self.db.add(compra)
            count += 1

        self.db.commit()
        db_count = self.db.query(CompraHistorico).count()
        self._log_sync("compras", len(items), db_count, abs(len(items) - count))
        return {"synced": count, "total_api": len(items), "total_db": db_count}

    async def sync_compras_oc(self) -> dict:
        data = await self.client.get_compras_oc()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("compras_oc", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "compras_oc", "comprasOc")
        self.db.query(CompraOC).filter(CompraOC.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            oc = CompraOC(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("oc_id", item.get("id"))),
                folio=self._safe_str(item.get("oc_folio", item.get("folio"))),
                fecha=self._parse_date(item.get("oc_fecha", item.get("fecha"))),
                proveedor=self._safe_str(item.get("proveedor_razon_social", item.get("proveedor"))),
                proveedor_rut=self._safe_str(item.get("proveedor_rut")),
                total=self._safe_float(item.get("oc_total", item.get("total", 0))),
                estado=self._safe_str(item.get("oc_estado", item.get("estado"))),
                data_json=self._to_json(item),
            )
            self.db.add(oc)
            count += 1

        self.db.commit()
        self._log_sync("compras_oc", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_compras_pagos(self) -> dict:
        data = await self.client.get_compras_pagos()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("compras_pagos", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "pagos", "comprasPagos")
        self.db.query(CompraPago).filter(CompraPago.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            pago = CompraPago(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("pago_id", item.get("id"))),
                compra_id_obuma=self._safe_str(item.get("rel_compra_id", item.get("compra_id"))),
                fecha=self._parse_date(item.get("pago_fecha", item.get("fecha"))),
                monto=self._safe_float(item.get("pago_monto", item.get("monto", 0))),
                forma_pago=self._safe_str(item.get("pago_forma_pago", item.get("forma_pago"))),
                origen=self._safe_str(item.get("pago_origen", item.get("origen"))),
                data_json=self._to_json(item),
            )
            self.db.add(pago)
            count += 1

        self.db.commit()
        self._log_sync("compras_pagos", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_compras_dte_recibidos(self) -> dict:
        data = await self.client.get_compras_dte_recibidos()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("compras_dte_recibidos", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "dte", "compras_dte_recibidos")
        self.db.query(CompraDteRecibido).filter(CompraDteRecibido.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            dte = CompraDteRecibido(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("dte_id", item.get("id"))),
                tipo_dcto=self._safe_str(item.get("dte_tipo_dcto", item.get("tipo_dcto"))),
                folio=self._safe_str(item.get("dte_folio", item.get("folio"))),
                fecha=self._parse_date(item.get("dte_fecha", item.get("fecha"))),
                rut_emisor=self._safe_str(item.get("dte_rut_emisor", item.get("rut_emisor"))),
                razon_social=self._safe_str(item.get("dte_razon_social", item.get("razon_social"))),
                monto_total=self._safe_float(item.get("dte_monto_total", item.get("monto_total", 0))),
                data_json=self._to_json(item),
            )
            self.db.add(dte)
            count += 1

        self.db.commit()
        self._log_sync("compras_dte_recibidos", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_contabilidad(self, fecha_desde: str = None) -> dict:
        data = await self.client.get_contabilidad(fecha_desde)
        if isinstance(data, dict) and "error" in data:
            self._log_sync("contabilidad", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "asientos")
        count = 0
        for item in items:
            fecha = self._parse_date(item.get("fecha", item.get("contabilidad_fecha", None)))

            entry = ContabilidadHistorico(
                tenant_id=self.tenant_id,
                fecha=fecha.date() if fecha else None,
                cuenta=item.get("cuenta", item.get("contabilidad_cuenta", item.get("codigo_cuenta", ""))),
                descripcion=item.get("descripcion", item.get("contabilidad_glosa", item.get("glosa", ""))),
                debe=self._safe_float(item.get("debe", item.get("contabilidad_debe", 0))),
                haber=self._safe_float(item.get("haber", item.get("contabilidad_haber", 0))),
                tipo=item.get("tipo", item.get("contabilidad_tipo", "")),
            )
            self.db.add(entry)
            count += 1

        self.db.commit()
        db_count = self.db.query(ContabilidadHistorico).count()
        self._log_sync("contabilidad", len(items), db_count, 0)
        return {"synced": count, "total_api": len(items), "total_db": db_count}

    async def sync_gastos_menores(self) -> dict:
        data = await self.client.get_gastos_menores()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("gastos_menores", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "gastos", "gastos_menores", "comprasGastosMenores")
        self.db.query(GastoMenor).filter(GastoMenor.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            gasto = GastoMenor(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("gasto_id", item.get("id"))),
                fecha=self._parse_date(item.get("gasto_fecha", item.get("fecha"))),
                descripcion=self._safe_str(item.get("gasto_descripcion", item.get("descripcion"))),
                monto=self._safe_float(item.get("gasto_monto", item.get("monto", 0))),
                categoria=self._safe_str(item.get("gasto_categoria", item.get("categoria"))),
                data_json=self._to_json(item),
            )
            self.db.add(gasto)
            count += 1

        self.db.commit()
        self._log_sync("gastos_menores", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_crm_leads(self) -> dict:
        data = await self.client.get_crm_leads()
        if isinstance(data, dict) and "error" in data:
            self._log_sync("crm_leads", 0, 0, 0, estado="error", detalle=str(data.get("error")))
            return data

        items = self._extract_items(data, "leads", "crm")
        self.db.query(CrmLead).filter(CrmLead.tenant_id == self.tenant_id).delete()
        count = 0
        for item in items:
            lead = CrmLead(
                tenant_id=self.tenant_id,
                obuma_id=self._safe_str(item.get("lead_id", item.get("id"))),
                nombre=self._safe_str(item.get("lead_nombre", item.get("nombre"))),
                empresa=self._safe_str(item.get("lead_empresa", item.get("empresa"))),
                email=self._safe_str(item.get("lead_email", item.get("email"))),
                telefono=self._safe_str(item.get("lead_telefono", item.get("telefono"))),
                estado=self._safe_str(item.get("lead_estado", item.get("estado"))),
                origen=self._safe_str(item.get("lead_origen", item.get("origen"))),
                monto_estimado=self._safe_float(item.get("lead_monto", item.get("monto_estimado", 0))),
                data_json=self._to_json(item),
            )
            self.db.add(lead)
            count += 1

        self.db.commit()
        self._log_sync("crm_leads", len(items), count, 0)
        return {"synced": count, "total_api": len(items), "total_db": count}

    async def sync_all(self) -> dict:
        results = {}
        results["clientes"] = await self.sync_clientes()
        results["clientes_contactos"] = await self.sync_clientes_contactos()
        results["clientes_direcciones"] = await self.sync_clientes_direcciones()
        results["proveedores"] = await self.sync_proveedores()
        results["productos"] = await self.sync_productos()
        results["producto_categorias"] = await self.sync_producto_categorias()
        results["producto_subcategorias"] = await self.sync_producto_subcategorias()
        results["producto_fabricantes"] = await self.sync_producto_fabricantes()
        results["producto_precios"] = await self.sync_producto_precios()
        results["empleados"] = await self.sync_empleados()
        results["remuneraciones"] = await self.sync_remuneraciones()
        results["ventas"] = await self.sync_ventas()
        results["ventas_items"] = await self.sync_ventas_items()
        results["ventas_cotizaciones"] = await self.sync_ventas_cotizaciones()
        results["ventas_cobros"] = await self.sync_ventas_cobros()
        results["ventas_dte"] = await self.sync_ventas_dte()
        results["compras"] = await self.sync_compras()
        results["compras_oc"] = await self.sync_compras_oc()
        results["compras_pagos"] = await self.sync_compras_pagos()
        results["compras_dte_recibidos"] = await self.sync_compras_dte_recibidos()
        results["contabilidad"] = await self.sync_contabilidad()
        results["gastos_menores"] = await self.sync_gastos_menores()
        results["crm_leads"] = await self.sync_crm_leads()
        return results

    def _log_sync(self, endpoint, registros_api, registros_db, discrepancias,
                  total_api=0, total_db=0, estado="ok", detalle=None):
        log = SyncLog(
            tenant_id=self.tenant_id,
            endpoint=endpoint,
            registros_api=registros_api,
            registros_db=registros_db,
            discrepancias=discrepancias,
            total_api=total_api,
            total_db=total_db,
            estado=estado,
            detalle=detalle,
        )
        self.db.add(log)
        self.db.commit()

        api_name = ENDPOINT_MAP.get(endpoint)
        if api_name:
            catalog_entry = self.db.query(ObumaApiEndpoint).filter(
                ObumaApiEndpoint.nombre == api_name
            ).first()
            if catalog_entry:
                catalog_entry.ultima_sync = datetime.now()
                catalog_entry.registros_sync = registros_db
                catalog_entry.implementado = True
                if estado == "ok":
                    catalog_entry.estado = "sincronizado"
                    catalog_entry.sync_habilitado = True
                elif detalle and "404" in str(detalle):
                    catalog_entry.estado = "no_disponible"
                    catalog_entry.sync_habilitado = False
                    catalog_entry.notas = "Endpoint no disponible en esta cuenta (404)"
                else:
                    catalog_entry.estado = "error"
                    catalog_entry.sync_habilitado = True
                self.db.commit()

    def audit_totals(self) -> dict:
        results = {}

        ventas_db = self.db.query(VentaHistorico).all()
        total_ventas_db = sum(v.total for v in ventas_db if v.total)
        count_ventas_db = len(ventas_db)

        compras_db = self.db.query(CompraHistorico).all()
        total_compras_db = sum(c.total for c in compras_db if c.total)
        count_compras_db = len(compras_db)

        last_sync_ventas = self.db.query(SyncLog).filter(
            SyncLog.endpoint == "ventas"
        ).order_by(SyncLog.ejecutado_at.desc()).first()

        last_sync_compras = self.db.query(SyncLog).filter(
            SyncLog.endpoint == "compras"
        ).order_by(SyncLog.ejecutado_at.desc()).first()

        results["ventas"] = {
            "total_db": total_ventas_db,
            "registros_db": count_ventas_db,
            "ultima_sync_api_total": last_sync_ventas.total_api if last_sync_ventas else 0,
            "ultima_sync_api_registros": last_sync_ventas.registros_api if last_sync_ventas else 0,
            "discrepancia_total": abs(total_ventas_db - (last_sync_ventas.total_api if last_sync_ventas else 0)),
        }
        results["compras"] = {
            "total_db": total_compras_db,
            "registros_db": count_compras_db,
            "ultima_sync_api_registros": last_sync_compras.registros_api if last_sync_compras else 0,
        }
        return results
