import logging
import json
from datetime import datetime
from sqlalchemy.orm import Session
from src.etl.obuma_client import ObumaClient
from src.models.models import (
    VentaHistorico, CompraHistorico, Producto, ContabilidadHistorico,
    CostoHistorico, ClienteFinal, SyncLog, Tenant
)

logger = logging.getLogger(__name__)


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

    def _get_or_create_cliente(self, rut: str = None, nombre: str = "Sin nombre") -> int:
        if not rut:
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

    async def sync_productos(self) -> dict:
        data = await self.client.get_productos()
        if "error" in data:
            self._log_sync("productos", 0, 0, 0, estado="error", detalle=str(data["error"]))
            return data

        items = data if isinstance(data, list) else data.get("data", data.get("productos", []))
        count = 0
        for item in items:
            obuma_id = str(item.get("id", ""))
            existing = self.db.query(Producto).filter(
                Producto.obuma_id == obuma_id,
                Producto.tenant_id == self.tenant_id
            ).first()

            costo = float(item.get("costo", 0) or 0)

            if existing:
                old_costo = existing.costo
                existing.nombre = item.get("nombre", existing.nombre)
                existing.sku = item.get("sku", existing.sku)
                existing.categoria = item.get("categoria", existing.categoria)
                existing.precio_venta = float(item.get("precio_venta", 0) or 0)
                existing.costo = costo
                existing.stock_actual = int(item.get("stock", 0) or 0)

                if costo and costo != old_costo:
                    costo_hist = CostoHistorico(
                        tenant_id=self.tenant_id,
                        producto_id=existing.id,
                        costo_unitario=costo,
                        cantidad=int(item.get("stock", 0) or 0),
                        costo_total=costo * int(item.get("stock", 0) or 0),
                        fecha=datetime.now(),
                        fuente="obuma",
                    )
                    self.db.add(costo_hist)
            else:
                producto = Producto(
                    tenant_id=self.tenant_id,
                    obuma_id=obuma_id,
                    nombre=item.get("nombre", ""),
                    sku=item.get("sku", ""),
                    categoria=item.get("categoria", ""),
                    precio_venta=float(item.get("precio_venta", 0) or 0),
                    costo=costo,
                    stock_actual=int(item.get("stock", 0) or 0),
                )
                self.db.add(producto)
                self.db.flush()

                if costo:
                    costo_hist = CostoHistorico(
                        tenant_id=self.tenant_id,
                        producto_id=producto.id,
                        costo_unitario=costo,
                        cantidad=int(item.get("stock", 0) or 0),
                        costo_total=costo * int(item.get("stock", 0) or 0),
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
        if "error" in data:
            self._log_sync("ventas", 0, 0, 0, estado="error", detalle=str(data["error"]))
            return data

        items = data if isinstance(data, list) else data.get("data", data.get("ventas", []))
        count = 0
        total_api = 0.0
        for item in items:
            obuma_id = str(item.get("id", ""))
            total = float(item.get("total", 0) or 0)
            total_api += total

            existing = self.db.query(VentaHistorico).filter(VentaHistorico.obuma_id == obuma_id).first()
            if existing:
                continue

            cliente_rut = item.get("cliente_rut", item.get("rut", None))
            cliente_nombre = item.get("cliente_nombre", item.get("razon_social", "Sin nombre"))
            cliente_id = self._get_or_create_cliente(cliente_rut, cliente_nombre)

            fecha_str = item.get("fecha", None)
            fecha = None
            if fecha_str:
                try:
                    fecha = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d")
                except (ValueError, TypeError):
                    try:
                        fecha = datetime.strptime(str(fecha_str)[:10], "%d-%m-%Y")
                    except (ValueError, TypeError):
                        fecha = None

            subtotal = float(item.get("subtotal", item.get("neto", 0)) or 0)
            impuestos = float(item.get("impuestos", item.get("iva", 0)) or 0)
            costo_total = float(item.get("costo_total", 0) or 0)

            venta = VentaHistorico(
                tenant_id=self.tenant_id,
                obuma_id=obuma_id,
                cliente_id=cliente_id,
                fecha=fecha,
                tipo_documento=item.get("tipo_documento", item.get("tipoDte", "")),
                folio=str(item.get("folio", "")),
                subtotal=subtotal,
                impuestos=impuestos,
                total=total,
                estado=item.get("estado", ""),
                detalle=json.dumps(item, default=str, ensure_ascii=False),
                costo_total=costo_total,
                margen_neto=subtotal - costo_total if costo_total else 0,
            )
            self.db.add(venta)
            count += 1

        self.db.commit()
        db_count = self.db.query(VentaHistorico).count()
        total_db = self.db.query(VentaHistorico).with_entities(
            VentaHistorico.total
        ).all()
        total_db_sum = sum(v[0] for v in total_db if v[0])

        self._log_sync("ventas", len(items), db_count,
                        abs(len(items) - count),
                        total_api=total_api, total_db=total_db_sum)
        return {"synced": count, "total_api": len(items), "total_db": db_count}

    async def sync_compras(self) -> dict:
        data = await self.client.get_compras()
        if "error" in data:
            self._log_sync("compras", 0, 0, 0, estado="error", detalle=str(data["error"]))
            return data

        items = data if isinstance(data, list) else data.get("data", data.get("compras", []))
        count = 0
        for item in items:
            obuma_id = str(item.get("id", item.get("folio_dcto", "")))
            existing = self.db.query(CompraHistorico).filter(CompraHistorico.obuma_id == obuma_id).first()
            if existing:
                continue

            fecha_str = item.get("fecha", None)
            fecha = None
            if fecha_str:
                try:
                    fecha = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d")
                except (ValueError, TypeError):
                    try:
                        fecha = datetime.strptime(str(fecha_str)[:10], "%d-%m-%Y")
                    except (ValueError, TypeError):
                        fecha = None

            compra = CompraHistorico(
                tenant_id=self.tenant_id,
                obuma_id=obuma_id,
                fecha=fecha,
                proveedor=item.get("proveedor", ""),
                folio=str(item.get("folio_dcto", "")),
                total=float(item.get("total", 0) or 0),
                estado=item.get("estado", ""),
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
        if "error" in data:
            self._log_sync("contabilidad", 0, 0, 0, estado="error", detalle=str(data["error"]))
            return data

        items = data if isinstance(data, list) else data.get("data", data.get("asientos", []))
        count = 0
        for item in items:
            fecha_str = item.get("fecha", None)
            fecha = None
            if fecha_str:
                try:
                    fecha = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    try:
                        fecha = datetime.strptime(str(fecha_str)[:10], "%d-%m-%Y").date()
                    except (ValueError, TypeError):
                        fecha = None

            entry = ContabilidadHistorico(
                tenant_id=self.tenant_id,
                fecha=fecha,
                cuenta=item.get("cuenta", item.get("codigo_cuenta", "")),
                descripcion=item.get("descripcion", item.get("glosa", "")),
                debe=float(item.get("debe", 0) or 0),
                haber=float(item.get("haber", 0) or 0),
                tipo=item.get("tipo", ""),
            )
            self.db.add(entry)
            count += 1

        self.db.commit()
        db_count = self.db.query(ContabilidadHistorico).count()
        self._log_sync("contabilidad", len(items), db_count, 0)
        return {"synced": count, "total_api": len(items), "total_db": db_count}

    async def sync_all(self) -> dict:
        results = {}
        results["productos"] = await self.sync_productos()
        results["ventas"] = await self.sync_ventas()
        results["compras"] = await self.sync_compras()
        results["contabilidad"] = await self.sync_contabilidad()
        return results

    def _log_sync(self, endpoint, registros_api, registros_db, discrepancias,
                  total_api=0, total_db=0, estado="ok", detalle=None):
        log = SyncLog(
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
