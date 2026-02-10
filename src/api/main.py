import asyncio
import logging
from datetime import date, datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import get_db, engine, Base, SessionLocal
from src.models.models import (
    VentaHistorico, CompraHistorico, Producto, ContabilidadHistorico,
    ClienteFinal, SyncLog, ReporteGenerado
)
from src.etl.sync_service import SyncService
from src.reports.excel_generator import generate_all_vendedor_reports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BI Platform - Gabriel Hoyos",
    description="Plataforma de Business Intelligence para gestión de clientes Obuma",
    version="1.0.0",
)


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
        finally:
            db.close()
        start_scheduler()
        logger.info("Background startup complete: DB seeded, scheduler started")
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
        "productos": service.sync_productos,
        "compras": service.sync_compras,
        "contabilidad": service.sync_contabilidad,
    }
    if endpoint not in method_map:
        raise HTTPException(status_code=400, detail=f"Endpoint '{endpoint}' no válido")
    result = await method_map[endpoint]()
    return {"status": "completed", "endpoint": endpoint, "result": result}


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
