import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from sqlalchemy import func, text
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import SessionLocal, engine, Base
from src.models.models import (
    VentaHistorico, CompraHistorico, Producto, ContabilidadHistorico,
    ClienteFinal, SyncLog, ReporteGenerado
)
from src.etl.sync_service import SyncService
from src.reports.excel_generator import generate_daily_report

Base.metadata.create_all(bind=engine)

st.set_page_config(
    page_title="BI Platform - Gabriel Hoyos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; color: #2F5496; margin-bottom: 0.5rem; }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.2rem; border-radius: 12px; color: white; text-align: center;
    }
    .stMetric { background-color: #f8f9fa; padding: 1rem; border-radius: 8px; border-left: 4px solid #2F5496; }
</style>
""", unsafe_allow_html=True)


def get_db():
    return SessionLocal()


st.sidebar.markdown("## 📊 BI Platform")
st.sidebar.markdown("**Gabriel Hoyos**")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navegación",
    ["Dashboard", "Ventas", "Contabilidad", "Reportes", "Sincronización", "Auditoría"],
    index=0
)

if page == "Dashboard":
    st.markdown('<p class="main-header">Centro de Mando</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        total_ventas = db.query(func.sum(VentaHistorico.total)).scalar() or 0
        total_compras = db.query(func.sum(CompraHistorico.total)).scalar() or 0
        total_margen = db.query(func.sum(VentaHistorico.margen_neto)).scalar() or 0
        n_clientes = db.query(ClienteFinal).filter(ClienteFinal.activo == True).count()
        n_productos = db.query(Producto).filter(Producto.activo == True).count()
        n_ventas = db.query(VentaHistorico).count()
        alertas_stock = db.query(Producto).filter(
            Producto.stock_actual <= Producto.stock_minimo,
            Producto.activo == True
        ).count()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Ventas", f"${total_ventas:,.0f}")
        col2.metric("Total Compras", f"${total_compras:,.0f}")
        col3.metric("Margen Neto", f"${total_margen:,.0f}")
        col4.metric("Clientes Activos", n_clientes)

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("Productos", n_productos)
        col6.metric("Transacciones", n_ventas)
        col7.metric("Alertas Stock", alertas_stock)
        margen_pct = (total_margen / total_ventas * 100) if total_ventas else 0
        col8.metric("Margen %", f"{margen_pct:.1f}%")

        st.markdown("---")

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Ventas por Fecha")
            ventas_data = db.query(
                func.date(VentaHistorico.fecha).label("fecha"),
                func.sum(VentaHistorico.total).label("total"),
                func.sum(VentaHistorico.margen_neto).label("margen")
            ).filter(
                VentaHistorico.fecha.isnot(None)
            ).group_by(
                func.date(VentaHistorico.fecha)
            ).order_by(
                func.date(VentaHistorico.fecha)
            ).all()

            if ventas_data:
                df_ventas = pd.DataFrame([
                    {"Fecha": str(v.fecha), "Ventas": v.total or 0, "Margen": v.margen or 0}
                    for v in ventas_data
                ])
                fig = px.bar(df_ventas, x="Fecha", y=["Ventas", "Margen"],
                            barmode="group", color_discrete_sequence=["#2F5496", "#4CAF50"])
                fig.update_layout(height=350, margin=dict(t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de ventas disponibles. Sincronice con Obuma primero.")

        with col_right:
            st.subheader("Ingresos vs Egresos")
            contab_data = db.query(
                func.date(ContabilidadHistorico.fecha).label("fecha"),
                func.sum(ContabilidadHistorico.haber).label("ingresos"),
                func.sum(ContabilidadHistorico.debe).label("egresos")
            ).filter(
                ContabilidadHistorico.fecha.isnot(None)
            ).group_by(
                func.date(ContabilidadHistorico.fecha)
            ).order_by(
                func.date(ContabilidadHistorico.fecha)
            ).all()

            if contab_data:
                df_contab = pd.DataFrame([
                    {"Fecha": str(c.fecha), "Ingresos": c.ingresos or 0, "Egresos": c.egresos or 0}
                    for c in contab_data
                ])
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df_contab["Fecha"], y=df_contab["Ingresos"],
                                          mode="lines+markers", name="Ingresos",
                                          line=dict(color="#4CAF50", width=2)))
                fig2.add_trace(go.Scatter(x=df_contab["Fecha"], y=df_contab["Egresos"],
                                          mode="lines+markers", name="Egresos",
                                          line=dict(color="#F44336", width=2)))
                fig2.update_layout(height=350, margin=dict(t=20, b=20))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No hay datos de contabilidad disponibles. Sincronice con Obuma primero.")

        st.markdown("---")
        st.subheader("Top Clientes por Ventas")
        top_clientes = db.query(
            ClienteFinal.nombre,
            func.sum(VentaHistorico.total).label("total"),
            func.count(VentaHistorico.id).label("transacciones")
        ).join(
            VentaHistorico, VentaHistorico.cliente_id == ClienteFinal.id
        ).group_by(
            ClienteFinal.nombre
        ).order_by(
            func.sum(VentaHistorico.total).desc()
        ).limit(10).all()

        if top_clientes:
            df_top = pd.DataFrame([
                {"Cliente": c.nombre, "Total Ventas": c.total or 0, "Transacciones": c.transacciones}
                for c in top_clientes
            ])
            st.dataframe(df_top, use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos de clientes disponibles.")

    finally:
        db.close()


elif page == "Ventas":
    st.markdown('<p class="main-header">Gestión de Ventas</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        col1, col2 = st.columns(2)
        with col1:
            fecha_desde = st.date_input("Fecha desde", value=date.today() - timedelta(days=30))
        with col2:
            fecha_hasta = st.date_input("Fecha hasta", value=date.today())

        query = db.query(VentaHistorico)
        if fecha_desde:
            query = query.filter(func.date(VentaHistorico.fecha) >= fecha_desde)
        if fecha_hasta:
            query = query.filter(func.date(VentaHistorico.fecha) <= fecha_hasta)

        ventas = query.order_by(VentaHistorico.fecha.desc()).all()

        if ventas:
            data = []
            for v in ventas:
                cliente_nombre = ""
                if v.cliente_id:
                    cliente = db.query(ClienteFinal).filter(ClienteFinal.id == v.cliente_id).first()
                    cliente_nombre = cliente.nombre if cliente else ""
                data.append({
                    "Fecha": str(v.fecha)[:10] if v.fecha else "",
                    "Cliente": cliente_nombre,
                    "Folio": v.folio,
                    "Tipo": v.tipo_documento,
                    "Neto": v.subtotal or 0,
                    "IVA": v.impuestos or 0,
                    "Total": v.total or 0,
                    "Costo": v.costo_total or 0,
                    "Margen": v.margen_neto or 0,
                })

            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Neto", f"${df['Neto'].sum():,.0f}")
            col2.metric("Total", f"${df['Total'].sum():,.0f}")
            col3.metric("Margen Total", f"${df['Margen'].sum():,.0f}")
        else:
            st.info("No hay ventas en el rango seleccionado.")
    finally:
        db.close()


elif page == "Contabilidad":
    st.markdown('<p class="main-header">Contabilidad</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        total_debe = db.query(func.sum(ContabilidadHistorico.debe)).scalar() or 0
        total_haber = db.query(func.sum(ContabilidadHistorico.haber)).scalar() or 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ingresos (Haber)", f"${total_haber:,.0f}")
        col2.metric("Total Egresos (Debe)", f"${total_debe:,.0f}")
        col3.metric("Diferencia", f"${total_haber - total_debe:,.0f}")

        st.markdown("---")

        entries = db.query(ContabilidadHistorico).order_by(
            ContabilidadHistorico.fecha.desc()
        ).limit(200).all()

        if entries:
            df = pd.DataFrame([{
                "Fecha": str(e.fecha) if e.fecha else "",
                "Cuenta": e.cuenta,
                "Descripción": e.descripcion,
                "Debe": e.debe or 0,
                "Haber": e.haber or 0,
            } for e in entries])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros de contabilidad. Sincronice con Obuma primero.")
    finally:
        db.close()


elif page == "Reportes":
    st.markdown('<p class="main-header">Gestión de Reportes Excel</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        st.subheader("Generar Nuevo Reporte")
        col1, col2 = st.columns([2, 1])
        with col1:
            fecha_reporte = st.date_input("Fecha del reporte", value=date.today())
        with col2:
            st.write("")
            st.write("")
            if st.button("Generar Reporte Diario", type="primary"):
                with st.spinner("Generando reporte..."):
                    filepath = generate_daily_report(db, fecha_reporte)
                    st.success(f"Reporte generado exitosamente")

                    with open(filepath, "rb") as f:
                        st.download_button(
                            label="Descargar Reporte",
                            data=f.read(),
                            file_name=os.path.basename(filepath),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

        st.markdown("---")
        st.subheader("Reportes Históricos")

        reportes = db.query(ReporteGenerado).order_by(ReporteGenerado.generado_at.desc()).all()
        if reportes:
            for r in reportes:
                col1, col2, col3 = st.columns([3, 2, 1])
                col1.write(f"**{r.nombre_archivo}**")
                col2.write(f"Generado: {str(r.generado_at)[:16]}")
                if r.ruta_archivo and os.path.exists(r.ruta_archivo):
                    with open(r.ruta_archivo, "rb") as f:
                        col3.download_button(
                            label="Descargar",
                            data=f.read(),
                            file_name=r.nombre_archivo,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"download_{r.id}"
                        )
                else:
                    col3.write("Archivo no disponible")
        else:
            st.info("No hay reportes generados aún.")
    finally:
        db.close()


elif page == "Sincronización":
    st.markdown('<p class="main-header">Sincronización con Obuma</p>', unsafe_allow_html=True)

    import asyncio

    db = get_db()
    try:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sincronizar Todo", type="primary"):
                with st.spinner("Sincronizando todos los datos desde Obuma..."):
                    service = SyncService(db)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(service.sync_all())
                    loop.close()
                    st.success("Sincronización completada")
                    st.json(results)

        with col2:
            endpoint = st.selectbox("Sincronizar módulo específico",
                                     ["ventas", "productos", "compras", "contabilidad"])
            if st.button("Sincronizar Módulo"):
                with st.spinner(f"Sincronizando {endpoint}..."):
                    service = SyncService(db)
                    method_map = {
                        "ventas": service.sync_ventas,
                        "productos": service.sync_productos,
                        "compras": service.sync_compras,
                        "contabilidad": service.sync_contabilidad,
                    }
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(method_map[endpoint]())
                    loop.close()
                    st.success(f"{endpoint} sincronizado")
                    st.json(result)

        st.markdown("---")
        st.subheader("Historial de Sincronización")

        logs = db.query(SyncLog).order_by(SyncLog.ejecutado_at.desc()).limit(20).all()
        if logs:
            df = pd.DataFrame([{
                "Fecha": str(l.ejecutado_at)[:16],
                "Endpoint": l.endpoint,
                "Registros API": l.registros_api,
                "Registros DB": l.registros_db,
                "Discrepancias": l.discrepancias,
                "Estado": l.estado,
            } for l in logs])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros de sincronización.")
    finally:
        db.close()


elif page == "Auditoría":
    st.markdown('<p class="main-header">Auditoría de Cifras</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        service = SyncService(db)
        audit = service.audit_totals()

        st.subheader("Comparación API vs Base de Datos")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Ventas")
            st.metric("Total en BD", f"${audit['ventas']['total_db']:,.0f}")
            st.metric("Registros en BD", audit['ventas']['registros_db'])
            st.metric("Última Sync - Total API", f"${audit['ventas']['ultima_sync_api_total']:,.0f}")
            st.metric("Última Sync - Registros API", audit['ventas']['ultima_sync_api_registros'])
            discrepancia = audit['ventas']['discrepancia_total']
            if discrepancia > 0:
                st.error(f"Discrepancia detectada: ${discrepancia:,.0f}")
            else:
                st.success("Sin discrepancias en totales de ventas")

        with col2:
            st.markdown("### Compras")
            st.metric("Total en BD", f"${audit['compras']['total_db']:,.0f}")
            st.metric("Registros en BD", audit['compras']['registros_db'])
            st.metric("Última Sync - Registros API", audit['compras']['ultima_sync_api_registros'])
    finally:
        db.close()
