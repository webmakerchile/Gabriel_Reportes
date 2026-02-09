import logging
import json
from datetime import datetime
from sqlalchemy.orm import Session
from src.etl.obuma_client import ObumaClient
from src.models.models import (
    VentaHistorico, CompraHistorico, Producto, ContabilidadHistorico,
    CostoHistorico, ClienteFinal, SyncLog, Tenant, ObumaApiEndpoint
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

    def _parse_date(self, date_str):
        if not date_str or date_str in ("0000-00-00", "0000-00-00 00:00:00"):
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y"):
            try:
                return datetime.strptime(str(date_str).strip()[:19], fmt)
            except (ValueError, TypeError):
                continue
        return None

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

            if existing:
                existing.nombre = nombre or existing.nombre
                existing.email = email or existing.email
                existing.telefono = telefono or existing.telefono
                existing.direccion = direccion or existing.direccion
            else:
                cliente = ClienteFinal(
                    tenant_id=self.tenant_id,
                    rut=rut,
                    nombre=nombre or "Sin nombre",
                    email=email,
                    telefono=telefono,
                    direccion=direccion,
                )
                self.db.add(cliente)
            count += 1

        self.db.commit()
        db_count = self.db.query(ClienteFinal).filter(ClienteFinal.tenant_id == self.tenant_id).count()
        self._log_sync("clientes", len(items), db_count, 0)
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
                existing.detalle = json.dumps(item, default=str, ensure_ascii=False)
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

            cliente_id_obuma = item.get("rel_cliente_id", item.get("cliente_id", "0"))
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
                detalle=json.dumps(item, default=str, ensure_ascii=False),
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
                detalle=json.dumps(item, default=str, ensure_ascii=False),
            )
            self.db.add(compra)
            count += 1

        self.db.commit()
        db_count = self.db.query(CompraHistorico).count()
        self._log_sync("compras", len(items), db_count, abs(len(items) - count))
        return {"synced": count, "total_api": len(items), "total_db": db_count}

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

    async def sync_all(self) -> dict:
        results = {}
        results["clientes"] = await self.sync_clientes()
        results["productos"] = await self.sync_productos()
        results["ventas"] = await self.sync_ventas()
        results["compras"] = await self.sync_compras()
        results["contabilidad"] = await self.sync_contabilidad()
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

        endpoint_map = {
            "clientes": "API : Clientes",
            "productos": "API : Productos",
            "ventas": "API : Ventas",
            "compras": "API : Compras",
            "contabilidad": "API : Contabilidad",
        }
        api_name = endpoint_map.get(endpoint)
        if api_name:
            catalog_entry = self.db.query(ObumaApiEndpoint).filter(
                ObumaApiEndpoint.nombre == api_name
            ).first()
            if catalog_entry:
                catalog_entry.ultima_sync = datetime.now()
                catalog_entry.registros_sync = registros_db
                catalog_entry.estado = "sincronizado" if estado == "ok" else "error"
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
