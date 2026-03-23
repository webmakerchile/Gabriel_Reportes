import asyncio
import logging
import time as _time
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text as sa_text

from src.database import get_db, engine, Base, SessionLocal
from src.models.models import (
    VentaHistorico, CompraHistorico, Producto, ContabilidadHistorico,
    ClienteFinal, SyncLog, ReporteGenerado
)
from src.etl.sync_service import SyncService
from src.reports.excel_generator import generate_all_vendedor_reports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_sync_state = {
    "running": False,
    "done": False,
    "step": 0,
    "total": 0,
    "label": "",
    "results": [],
    "ts": 0,
}
_SYNC_STALE_SECONDS = 600

app = FastAPI(
    title="BI Platform - Gabriel Hoyos",
    description="Plataforma de Business Intelligence para gestión de clientes Obuma",
    version="1.0.0",
)


VENDEDOR_METAS_DEFAULT = {
    "28856": {"rep": 58_900_000, "maq": 2_000_000},
    "28886": {"rep": 89_900_000, "maq": 4_000_000},
    "28887": {"rep": 58_900_000, "maq": 4_000_000},
    "28891": {"rep": 36_900_000, "maq": 2_000_000},
    "28892": {"rep": 36_900_000, "maq": 2_000_000},
}


def _seed_vendedor_metas(db):
    from src.models.models import VendedorMeta
    today = date.today()
    start_year = 2025
    start_month = 3
    for vid, vals in VENDEDOR_METAS_DEFAULT.items():
        y, m = start_year, start_month
        while (y, m) <= (today.year, today.month):
            exists = db.query(VendedorMeta).filter(
                VendedorMeta.empleado_obuma_id == vid,
                VendedorMeta.anio == y,
                VendedorMeta.mes == m
            ).first()
            if not exists:
                db.add(VendedorMeta(
                    empleado_obuma_id=vid, anio=y, mes=m,
                    meta_repuestos=vals["rep"], meta_maquinaria=vals["maq"]
                ))
            m += 1
            if m > 12:
                m = 1
                y += 1
    db.commit()
    logger.info("Vendedor metas seeded/verified")


def _backfill_venta_items(db):
    from sqlalchemy import text
    try:
        needs_sku = db.execute(text(
            "SELECT COUNT(*) FROM ventas_items WHERE (producto_sku IS NULL OR producto_sku = '') AND data_json IS NOT NULL"
        )).scalar()
        needs_total = db.execute(text(
            "SELECT COUNT(*) FROM ventas_items WHERE (total = 0 OR total IS NULL) AND data_json IS NOT NULL"
        )).scalar()

        if needs_sku > 0:
            db.execute(text("""
                UPDATE ventas_items 
                SET producto_sku = data_json::json->>'codigo_comercial'
                WHERE (producto_sku IS NULL OR producto_sku = '')
                AND data_json IS NOT NULL 
                AND data_json::json->>'codigo_comercial' IS NOT NULL
            """))
            db.commit()
            logger.info(f"Backfilled producto_sku for {needs_sku} items")

        if needs_total > 0:
            db.execute(text("""
                UPDATE ventas_items 
                SET total = COALESCE((data_json::json->>'subtotal')::float, 0)
                WHERE (total = 0 OR total IS NULL)
                AND data_json IS NOT NULL
            """))
            db.commit()
            logger.info(f"Backfilled total for {needs_total} items")

        if needs_sku == 0 and needs_total == 0:
            logger.info("VentaItem backfill: no updates needed")
    except Exception as e:
        logger.error(f"Error in VentaItem backfill: {e}")


def _seed_reportes_programados(db):
    from src.models.models import ReporteProgramado
    from datetime import datetime, timedelta

    REPORTES_CONFIG = [
        {"nombre": "Reporte Semanal - Gabriel Hoyos",       "vendedor_obuma_id": "28856", "email_principal": "gabrielhoyos@vlsur.cl"},
        {"nombre": "Reporte Semanal - Ernesto Quintiliani", "vendedor_obuma_id": "28887", "email_principal": "ventas.ernesto.q@gmail.com"},
        {"nombre": "Reporte Semanal - Jhonatan Ruiz",       "vendedor_obuma_id": "28886", "email_principal": "ventas.jhonatan.ruiz@gmail.com"},
        {"nombre": "Reporte Semanal - Pablo Pinto",         "vendedor_obuma_id": "28891", "email_principal": "vicentepinto@vlsur.cl"},
        {"nombre": "Reporte Semanal - Jesus Gonzalez",      "vendedor_obuma_id": "28892", "email_principal": "jesusgonzalez@vlsur.cl"},
    ]
    GABRIEL_EMAIL = "gabrielhoyos@vlsur.cl"

    now = datetime.now()
    days_until_friday = (4 - now.weekday()) % 7
    if days_until_friday == 0 and now.hour >= 18:
        days_until_friday = 7
    next_friday = (now + timedelta(days=max(days_until_friday, 1))).replace(hour=18, minute=30, second=0, microsecond=0)

    for cfg in REPORTES_CONFIG:
        existing = db.query(ReporteProgramado).filter(
            ReporteProgramado.vendedor_obuma_id == cfg["vendedor_obuma_id"],
            ReporteProgramado.frecuencia == "semanal",
            ReporteProgramado.tenant_id == 1
        ).first()
        if cfg['email_principal'] == GABRIEL_EMAIL:
            emails = GABRIEL_EMAIL
        else:
            emails = f"{cfg['email_principal']},\n{GABRIEL_EMAIL}"
        if not existing:
            db.add(ReporteProgramado(
                tenant_id=1,
                nombre=cfg["nombre"],
                tipo_reporte="individual",
                vendedor_obuma_id=cfg["vendedor_obuma_id"],
                frecuencia="semanal",
                dia_semana=4,
                hora=18,
                minuto=30,
                emails_destino=emails,
                filtro_fecha_tipo="mes_actual",
                activo=True,
                total_enviados=0,
                proxima_ejecucion=next_friday,
            ))
        else:
            if GABRIEL_EMAIL not in (existing.emails_destino or ""):
                existing.emails_destino = emails
    db.commit()
    logger.info("Reportes programados seeded/verified (5 semanales viernes 18:30)")


def _auto_sync_current_month_items():
    """If the current month has no VentaItem records, run incremental sync automatically."""
    import asyncio
    from datetime import date
    from sqlalchemy import text as sa_text
    try:
        db = SessionLocal()
        today = date.today()
        fecha_desde = today.replace(day=1).strftime("%Y-%m-%d")
        fecha_hasta = today.strftime("%Y-%m-%d")

        # Count items for current month via join
        count = db.execute(sa_text("""
            SELECT COUNT(vi.id) FROM ventas_items vi
            JOIN ventas_historico vh ON vh.obuma_id = vi.venta_id_obuma
            WHERE EXTRACT(year FROM vh.fecha) = :yr AND EXTRACT(month FROM vh.fecha) = :mo
        """), {"yr": today.year, "mo": today.month}).scalar() or 0

        if count == 0:
            logger.info(f"Auto-sync: no items found for {today.year}-{today.month:02d}, syncing now ({fecha_desde} to {fecha_hasta})...")
            from src.etl.sync_service import SyncService
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                svc = SyncService(db)
                result = loop.run_until_complete(
                    svc.sync_ventas_items_incremental(fecha_desde, fecha_hasta)
                )
                logger.info(f"Auto-sync items complete: {result}")
                # Backfill after sync
                _backfill_venta_items(db)
            finally:
                loop.close()
        else:
            logger.info(f"Auto-sync items: {count} items already exist for {today.year}-{today.month:02d}, skipping")
        db.close()
    except Exception as e:
        logger.error(f"Error in auto-sync current month items: {e}")


def _fix_cartera_orphans():
    """Deactivate cartera entries for clients no longer assigned to tracked vendedores."""
    try:
        from src.etl.sync_service import SyncService
        db = SessionLocal()
        svc = SyncService(db)
        result = svc._sync_cartera_from_clientes()
        logger.info(f"Cartera fix on startup: {result}")
        db.close()
    except Exception as e:
        logger.error(f"Error fixing cartera orphans: {e}")


def _heavy_init():
    try:
        Base.metadata.create_all(bind=engine)
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('ventas_historico')]
        if 'vendedor_id' not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE ventas_historico ADD COLUMN vendedor_id VARCHAR(50)"))
                conn.commit()
        from src.etl.api_catalog_seed import seed_api_catalog
        from src.scheduler import start_scheduler
        db = SessionLocal()
        try:
            seed_api_catalog(db)
            _seed_vendedor_metas(db)
            _backfill_venta_items(db)
            _seed_reportes_programados(db)
        finally:
            db.close()
        start_scheduler()
        logger.info("Background startup complete: DB seeded, scheduler started")
        # Auto-repair: sync missing items + fix cartera (non-blocking, runs after startup)
        _fix_cartera_orphans()
        _auto_sync_current_month_items()
    except Exception as e:
        logger.error(f"Error in background startup: {e}")


@app.on_event("startup")
async def on_startup():
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _heavy_init)
    logger.info("FastAPI started - heavy init running in separate thread")


@app.get("/")
def root():
    return {"status": "alive"}


def _run_sync_step_blocking(step_key: str):
    """Run a single sync step in a blocking fashion (called from thread pool)."""
    db = SessionLocal()
    try:
        service = SyncService(db)
        loop = asyncio.new_event_loop()
        try:
            if step_key == "ventas_items_inc":
                fecha_desde = (date.today() - timedelta(days=45)).strftime("%Y-%m-%d")
                fecha_hasta = date.today().strftime("%Y-%m-%d")
                result = loop.run_until_complete(
                    service.sync_ventas_items_incremental(fecha_desde, fecha_hasta)
                )
                db.close()
                db = SessionLocal()
                db.execute(sa_text("""
                    UPDATE ventas_items SET producto_sku = data_json::json->>'codigo_comercial'
                    WHERE (producto_sku IS NULL OR producto_sku = '') AND data_json IS NOT NULL
                      AND data_json::json->>'codigo_comercial' IS NOT NULL
                """))
                db.execute(sa_text("""
                    UPDATE ventas_items SET total = COALESCE((data_json::json->>'subtotal')::float, 0)
                    WHERE (total = 0 OR total IS NULL) AND data_json IS NOT NULL
                """))
                db.commit()
            elif step_key == "clientes":
                result = loop.run_until_complete(service.sync_clientes())
            elif step_key == "ventas":
                result = loop.run_until_complete(service.sync_ventas())
            elif step_key == "ventas_cobros":
                result = loop.run_until_complete(service.sync_ventas_cobros())
            elif step_key == "productos":
                result = loop.run_until_complete(service.sync_productos())
            elif step_key == "compras":
                result = loop.run_until_complete(service.sync_compras())
            elif step_key == "contabilidad":
                result = loop.run_until_complete(service.sync_contabilidad())
            elif step_key == "empleados":
                result = loop.run_until_complete(service.sync_empleados())
            else:
                result = {}
        finally:
            loop.close()
        return result
    finally:
        try:
            db.close()
        except Exception:
            pass


async def _run_background_sync():
    """Background coroutine that runs sync steps in thread pool to avoid blocking event loop."""
    global _sync_state
    SYNC_STEPS = [
        ("clientes",         "Clientes y Cartera de Vendedores"),
        ("ventas",           "Ventas y Documentos Tributarios"),
        ("ventas_items_inc", "Items de Ventas (ultimos 45 dias)"),
        ("ventas_cobros",    "Cobros Recibidos"),
        ("productos",        "Productos y Catalogo"),
        ("compras",          "Compras y Ordenes"),
        ("contabilidad",     "Contabilidad y Libro Diario"),
        ("empleados",        "Empleados y Remuneraciones"),
    ]
    total = len(SYNC_STEPS)
    results = []

    try:
        for i, (step_key, step_label) in enumerate(SYNC_STEPS):
            _sync_state.update({
                "running": True, "done": False,
                "step": i, "total": total, "label": step_label,
                "results": list(results), "ts": _time.time(),
            })

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_run_sync_step_blocking, step_key),
                    timeout=300
                )
                synced = result.get("synced", 0) if isinstance(result, dict) else 0
                results.append({"label": step_label, "ok": True, "synced": synced})
            except asyncio.TimeoutError:
                results.append({"label": step_label, "ok": False, "error": "Timeout (300s)"})
            except Exception as e:
                results.append({"label": step_label, "ok": False, "error": str(e)[:120]})
    except Exception as e:
        results.append({"label": "Error general", "ok": False, "error": str(e)[:120]})
    finally:
        _sync_state.update({
            "running": False, "done": True,
            "step": total, "total": total, "label": "Completado",
            "results": list(results), "ts": _time.time(),
        })


@app.post("/api/sync/start")
async def sync_start():
    global _sync_state
    if _sync_state["running"]:
        age = _time.time() - _sync_state.get("ts", 0)
        if age < _SYNC_STALE_SECONDS:
            return {"status": "already_running", "step": _sync_state["step"], "total": _sync_state["total"]}
    _sync_state.update({
        "running": True, "done": False,
        "step": 0, "total": 8, "label": "Iniciando...",
        "results": [], "ts": _time.time(),
    })
    asyncio.create_task(_run_background_sync())
    return {"status": "started"}


@app.get("/api/sync/status")
async def sync_status():
    global _sync_state
    if _sync_state["running"] and _sync_state.get("ts"):
        age = _time.time() - _sync_state["ts"]
        if age > _SYNC_STALE_SECONDS:
            _sync_state.update({"running": False, "done": True, "results": [
                {"label": "Timeout general", "ok": False, "error": "El proceso no respondio en 10 minutos"}
            ], "ts": _time.time()})
    return dict(_sync_state)


@app.post("/api/sync/reset")
async def sync_reset():
    global _sync_state
    _sync_state.update({
        "running": False, "done": False,
        "step": 0, "total": 0, "label": "",
        "results": [], "ts": 0,
    })
    return {"status": "reset"}


@app.post("/api/sync/all")
async def sync_all(db: Session = Depends(get_db)):
    service = SyncService(db)
    results = await service.sync_all()
    return {"status": "completed", "results": results}


@app.post("/api/sync/{endpoint}")
async def sync_endpoint(endpoint: str, db: Session = Depends(get_db)):
    service = SyncService(db)
    method_map = {
        "clientes": service.sync_clientes,
        "ventas": service.sync_ventas,
        "ventas_items": service.sync_ventas_items,
        "ventas_cobros": service.sync_ventas_cobros,
        "productos": service.sync_productos,
        "compras": service.sync_compras,
        "contabilidad": service.sync_contabilidad,
        "empleados": service.sync_empleados,
    }
    if endpoint not in method_map:
        raise HTTPException(status_code=400, detail=f"Endpoint '{endpoint}' no válido")
    result = await method_map[endpoint]()
    return {"status": "completed", "endpoint": endpoint, "result": result}


@app.post("/api/sync/ventas_items/incremental")
async def sync_ventas_items_incremental(
    fecha_desde: str = Query(..., description="Fecha inicio YYYY-MM-DD"),
    fecha_hasta: str = Query(..., description="Fecha fin YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    service = SyncService(db)
    result = await service.sync_ventas_items_incremental(fecha_desde, fecha_hasta)
    return {"status": "completed", "result": result}


@app.get("/api/audit")
def audit(db: Session = Depends(get_db)):
    service = SyncService(db)
    return service.audit_totals()


@app.get("/api/ventas")
def list_ventas(
    fecha_desde: date = None,
    fecha_hasta: date = None,
    cliente_id: int = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(VentaHistorico)
    if fecha_desde:
        query = query.filter(func.date(VentaHistorico.fecha) >= fecha_desde)
    if fecha_hasta:
        query = query.filter(func.date(VentaHistorico.fecha) <= fecha_hasta)
    if cliente_id:
        query = query.filter(VentaHistorico.cliente_id == cliente_id)
    total = query.count()
    ventas = query.order_by(VentaHistorico.fecha.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "data": [{
            "id": v.id, "obuma_id": v.obuma_id, "cliente_id": v.cliente_id,
            "fecha": str(v.fecha) if v.fecha else None, "folio": v.folio,
            "tipo_documento": v.tipo_documento, "subtotal": v.subtotal,
            "impuestos": v.impuestos, "total": v.total,
            "costo_total": v.costo_total, "margen_neto": v.margen_neto,
        } for v in ventas]
    }


@app.get("/api/compras")
def list_compras(
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(CompraHistorico)
    total = query.count()
    compras = query.order_by(CompraHistorico.fecha.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "data": [{
            "id": c.id, "obuma_id": c.obuma_id, "fecha": str(c.fecha) if c.fecha else None,
            "proveedor": c.proveedor, "folio": c.folio, "total": c.total,
        } for c in compras]
    }


@app.get("/api/productos")
def list_productos(
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Producto)
    total = query.count()
    productos = query.offset(offset).limit(limit).all()
    return {
        "total": total,
        "data": [{
            "id": p.id, "obuma_id": p.obuma_id, "nombre": p.nombre,
            "sku": p.sku, "categoria": p.categoria,
            "precio_venta": p.precio_venta, "costo": p.costo,
            "stock_actual": p.stock_actual,
        } for p in productos]
    }


@app.get("/api/contabilidad")
def list_contabilidad(
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(ContabilidadHistorico)
    total = query.count()
    entries = query.order_by(ContabilidadHistorico.fecha.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "data": [{
            "id": e.id, "fecha": str(e.fecha) if e.fecha else None,
            "cuenta": e.cuenta, "descripcion": e.descripcion,
            "debe": e.debe, "haber": e.haber, "tipo": e.tipo,
        } for e in entries]
    }


@app.get("/api/clientes")
def list_clientes(db: Session = Depends(get_db)):
    clientes = db.query(ClienteFinal).filter(ClienteFinal.activo == True).all()
    return [{
        "id": c.id, "rut": c.rut, "nombre": c.nombre, "email": c.email,
    } for c in clientes]


@app.get("/api/margen")
def margen_neto(
    fecha_desde: date = None,
    fecha_hasta: date = None,
    cliente_id: int = None,
    db: Session = Depends(get_db)
):
    query = db.query(VentaHistorico)
    if fecha_desde:
        query = query.filter(func.date(VentaHistorico.fecha) >= fecha_desde)
    if fecha_hasta:
        query = query.filter(func.date(VentaHistorico.fecha) <= fecha_hasta)
    if cliente_id:
        query = query.filter(VentaHistorico.cliente_id == cliente_id)

    ventas = query.all()
    total_ventas = sum(v.subtotal or 0 for v in ventas)
    total_costos = sum(v.costo_total or 0 for v in ventas)
    margen = total_ventas - total_costos
    porcentaje = (margen / total_ventas * 100) if total_ventas else 0

    return {
        "total_ventas_neto": total_ventas,
        "total_costos": total_costos,
        "margen_neto": margen,
        "margen_porcentaje": round(porcentaje, 2),
        "cantidad_transacciones": len(ventas),
    }


@app.get("/api/dashboard/resumen")
def dashboard_resumen(db: Session = Depends(get_db)):
    total_ventas = db.query(func.sum(VentaHistorico.total)).scalar() or 0
    total_compras = db.query(func.sum(CompraHistorico.total)).scalar() or 0
    total_margen = db.query(func.sum(VentaHistorico.margen_neto)).scalar() or 0
    n_clientes = db.query(ClienteFinal).filter(ClienteFinal.activo == True).count()
    n_productos = db.query(Producto).filter(Producto.activo == True).count()
    n_ventas = db.query(VentaHistorico).count()

    productos_bajo_stock = db.query(Producto).filter(
        Producto.stock_actual <= Producto.stock_minimo,
        Producto.activo == True
    ).count()

    return {
        "total_ventas": total_ventas,
        "total_compras": total_compras,
        "margen_neto_total": total_margen,
        "clientes_activos": n_clientes,
        "productos_activos": n_productos,
        "total_transacciones": n_ventas,
        "alertas_stock": productos_bajo_stock,
    }


@app.post("/api/reportes/generar")
def generar_reporte(
    year: int = None,
    db: Session = Depends(get_db)
):
    if year is None:
        year = date.today().year
    date_from = date(year, 1, 1)
    date_to = date(year, 12, 31)
    filepaths = generate_all_vendedor_reports(db, date_from, date_to)
    return {"status": "generated", "count": len(filepaths), "filepaths": filepaths}


@app.get("/api/reportes")
def list_reportes(db: Session = Depends(get_db)):
    reportes = db.query(ReporteGenerado).order_by(ReporteGenerado.generado_at.desc()).all()
    return [{
        "id": r.id,
        "nombre_archivo": r.nombre_archivo,
        "tipo": r.tipo,
        "fecha_reporte": str(r.fecha_reporte) if r.fecha_reporte else None,
        "ruta_archivo": r.ruta_archivo,
        "generado_at": str(r.generado_at),
    } for r in reportes]


@app.get("/api/reportes/descargar/{reporte_id}")
def descargar_reporte(reporte_id: int, db: Session = Depends(get_db)):
    reporte = db.query(ReporteGenerado).filter(ReporteGenerado.id == reporte_id).first()
    if not reporte or not reporte.ruta_archivo:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    import os
    if not os.path.exists(reporte.ruta_archivo):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")
    return FileResponse(
        reporte.ruta_archivo,
        filename=reporte.nombre_archivo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.get("/api/sync/log")
def sync_log(limit: int = 20, db: Session = Depends(get_db)):
    logs = db.query(SyncLog).order_by(SyncLog.ejecutado_at.desc()).limit(limit).all()
    return [{
        "id": l.id, "endpoint": l.endpoint,
        "registros_api": l.registros_api, "registros_db": l.registros_db,
        "discrepancias": l.discrepancias, "total_api": l.total_api,
        "total_db": l.total_db, "estado": l.estado,
        "detalle": l.detalle, "ejecutado_at": str(l.ejecutado_at),
    } for l in logs]


@app.get("/api/contabilidad/resumen")
def contabilidad_resumen(db: Session = Depends(get_db)):
    total_debe = db.query(func.sum(ContabilidadHistorico.debe)).scalar() or 0
    total_haber = db.query(func.sum(ContabilidadHistorico.haber)).scalar() or 0
    return {
        "total_ingresos": total_haber,
        "total_egresos": total_debe,
        "diferencia": total_haber - total_debe,
    }
