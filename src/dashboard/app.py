import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from sqlalchemy import func
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import SessionLocal, engine, Base
from src.models.models import (
    VentaHistorico, CompraHistorico, Producto, ContabilidadHistorico,
    ClienteFinal, SyncLog, ReporteGenerado, ObumaApiEndpoint
)
from src.etl.sync_service import SyncService
from src.etl.obuma_client import ObumaClient
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }
    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }
    .subtitle {
        font-size: 0.95rem;
        color: #6b7280;
        margin-bottom: 1.5rem;
    }
    .metric-container {
        background: white;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s;
    }
    .metric-container:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #1a1a2e;
        margin: 0;
    }
    .metric-label {
        font-size: 0.8rem;
        font-weight: 500;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0;
    }
    .metric-green { color: #059669 !important; }
    .metric-red { color: #dc2626 !important; }
    .metric-blue { color: #2563eb !important; }
    .metric-amber { color: #d97706 !important; }

    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #374151;
        margin: 1.5rem 0 0.8rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e5e7eb;
    }
    .card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .sync-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-ok { background: #d1fae5; color: #065f46; }
    .badge-error { background: #fee2e2; color: #991b1b; }
    .badge-warning { background: #fef3c7; color: #92400e; }

    .sidebar .sidebar-content {
        background: #f8fafc;
    }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    div[data-testid="stSidebar"] .stMarkdown p,
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 {
        color: white;
    }
    div[data-testid="stSidebar"] .stRadio label {
        color: #e2e8f0 !important;
    }
    div[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.1);
    }

    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
    }
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }

    .status-anulada { color: #dc2626; font-weight: 600; }
    .status-vigente { color: #059669; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


def get_db():
    return SessionLocal()


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def format_clp(value):
    if value is None:
        return "$0"
    return f"${value:,.0f}".replace(",", ".")


st.sidebar.markdown("### 📊 BI Platform")
st.sidebar.markdown("**Gabriel Hoyos**")
st.sidebar.caption("Centro de Mando Empresarial")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navegacion",
    ["Dashboard", "Ventas", "Clientes", "Contabilidad", "API Obuma", "Reportes", "Sincronizacion", "Auditoria"],
    index=0,
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.caption("v1.0 | Powered by Obuma ERP")

if page == "Dashboard":
    st.markdown('<p class="main-title">Centro de Mando</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Vista consolidada del rendimiento de todas las cuentas</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        total_ventas = db.query(func.sum(VentaHistorico.total)).scalar() or 0
        total_compras = db.query(func.sum(CompraHistorico.total)).scalar() or 0
        total_margen = db.query(func.sum(VentaHistorico.margen_neto)).scalar() or 0
        n_clientes = db.query(ClienteFinal).filter(ClienteFinal.activo == True).count()
        n_productos = db.query(Producto).filter(Producto.activo == True).count()
        n_ventas = db.query(VentaHistorico).count()
        ventas_anuladas = db.query(VentaHistorico).filter(VentaHistorico.anulada == True).count()
        ventas_vigentes = n_ventas - ventas_anuladas
        total_pagado = db.query(func.sum(VentaHistorico.total_pagado)).scalar() or 0
        total_por_pagar = db.query(func.sum(VentaHistorico.total_por_pagar)).scalar() or 0
        alertas_stock = db.query(Producto).filter(
            Producto.stock_actual <= Producto.stock_minimo,
            Producto.activo == True
        ).count()
        margen_pct = (total_margen / total_ventas * 100) if total_ventas else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Ventas Totales", format_clp(total_ventas))
        col2.metric("Compras Totales", format_clp(total_compras))
        col3.metric("Margen Neto", format_clp(total_margen))
        col4.metric("Margen %", f"{margen_pct:.1f}%")

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("Clientes", n_clientes)
        col6.metric("Documentos", n_ventas)
        col7.metric("Vigentes", ventas_vigentes)
        col8.metric("Anuladas", ventas_anuladas)

        if total_pagado or total_por_pagar:
            st.markdown("---")
            cp1, cp2, cp3 = st.columns(3)
            cp1.metric("Total Pagado", format_clp(total_pagado))
            cp2.metric("Por Pagar", format_clp(total_por_pagar))
            cp3.metric("Productos", n_productos)

        st.markdown("---")
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown('<p class="section-header">Ventas por Fecha</p>', unsafe_allow_html=True)
            ventas_data = db.query(
                func.date(VentaHistorico.fecha).label("fecha"),
                func.sum(VentaHistorico.total).label("total"),
                func.sum(VentaHistorico.margen_neto).label("margen"),
                func.count(VentaHistorico.id).label("cantidad")
            ).filter(
                VentaHistorico.fecha.isnot(None)
            ).group_by(
                func.date(VentaHistorico.fecha)
            ).order_by(
                func.date(VentaHistorico.fecha)
            ).all()

            if ventas_data:
                df_ventas = pd.DataFrame([
                    {"Fecha": str(v.fecha), "Ventas": v.total or 0, "Margen": v.margen or 0, "Docs": v.cantidad}
                    for v in ventas_data
                ])
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_ventas["Fecha"], y=df_ventas["Ventas"],
                                     name="Ventas", marker_color="#2563eb"))
                fig.add_trace(go.Bar(x=df_ventas["Fecha"], y=df_ventas["Margen"],
                                     name="Margen", marker_color="#059669"))
                fig.update_layout(
                    barmode="group", height=320,
                    margin=dict(t=10, b=30, l=10, r=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter"),
                )
                fig.update_xaxes(showgrid=False)
                fig.update_yaxes(showgrid=True, gridcolor="#f3f4f6")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sin datos de ventas. Use la seccion Sincronizacion para cargar datos desde Obuma.")

        with col_right:
            st.markdown('<p class="section-header">Ingresos vs Egresos</p>', unsafe_allow_html=True)
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
                                          line=dict(color="#059669", width=2.5),
                                          marker=dict(size=6)))
                fig2.add_trace(go.Scatter(x=df_contab["Fecha"], y=df_contab["Egresos"],
                                          mode="lines+markers", name="Egresos",
                                          line=dict(color="#dc2626", width=2.5),
                                          marker=dict(size=6)))
                fig2.update_layout(
                    height=320,
                    margin=dict(t=10, b=30, l=10, r=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter"),
                )
                fig2.update_xaxes(showgrid=False)
                fig2.update_yaxes(showgrid=True, gridcolor="#f3f4f6")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sin datos de contabilidad. Sincronice con Obuma primero.")

        st.markdown("---")

        col_tbl1, col_tbl2 = st.columns(2)

        with col_tbl1:
            st.markdown('<p class="section-header">Ultimas Transacciones</p>', unsafe_allow_html=True)
            recent_ventas = db.query(VentaHistorico).order_by(VentaHistorico.fecha.desc()).limit(10).all()
            if recent_ventas:
                data = []
                for v in recent_ventas:
                    cliente_nombre = ""
                    if v.cliente_id:
                        cliente = db.query(ClienteFinal).filter(ClienteFinal.id == v.cliente_id).first()
                        cliente_nombre = cliente.nombre if cliente else ""
                    estado = "Anulada" if v.anulada else "Vigente"
                    data.append({
                        "Fecha": str(v.fecha)[:10] if v.fecha else "-",
                        "Tipo": v.tipo_documento or "-",
                        "Folio": v.folio or "-",
                        "Total": format_clp(v.total),
                        "Estado": estado,
                    })
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("Sin transacciones recientes.")

        with col_tbl2:
            st.markdown('<p class="section-header">Top Clientes</p>', unsafe_allow_html=True)
            top_clientes = db.query(
                ClienteFinal.nombre,
                ClienteFinal.rut,
                func.sum(VentaHistorico.total).label("total"),
                func.count(VentaHistorico.id).label("transacciones")
            ).join(
                VentaHistorico, VentaHistorico.cliente_id == ClienteFinal.id
            ).group_by(
                ClienteFinal.nombre, ClienteFinal.rut
            ).order_by(
                func.sum(VentaHistorico.total).desc()
            ).limit(10).all()

            if top_clientes:
                df_top = pd.DataFrame([
                    {"Cliente": c.nombre, "RUT": c.rut or "-",
                     "Total": format_clp(c.total), "Docs": c.transacciones}
                    for c in top_clientes
                ])
                st.dataframe(df_top, use_container_width=True, hide_index=True)
            else:
                clientes_list = db.query(ClienteFinal).filter(ClienteFinal.activo == True).all()
                if clientes_list:
                    df_cl = pd.DataFrame([
                        {"Cliente": c.nombre, "RUT": c.rut or "-", "Email": c.email or "-"}
                        for c in clientes_list
                    ])
                    st.dataframe(df_cl, use_container_width=True, hide_index=True)
                else:
                    st.info("Sin datos de clientes.")

    finally:
        db.close()


elif page == "Ventas":
    st.markdown('<p class="main-title">Gestion de Ventas</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Detalle de documentos de venta con filtros avanzados</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_desde = st.date_input("Desde", value=date.today() - timedelta(days=90))
        with col2:
            fecha_hasta = st.date_input("Hasta", value=date.today())
        with col3:
            filtro_estado = st.selectbox("Estado", ["Todos", "Vigentes", "Anuladas"])

        query = db.query(VentaHistorico)
        if fecha_desde:
            query = query.filter(func.date(VentaHistorico.fecha) >= fecha_desde)
        if fecha_hasta:
            query = query.filter(func.date(VentaHistorico.fecha) <= fecha_hasta)
        if filtro_estado == "Vigentes":
            query = query.filter(VentaHistorico.anulada == False)
        elif filtro_estado == "Anuladas":
            query = query.filter(VentaHistorico.anulada == True)

        ventas = query.order_by(VentaHistorico.fecha.desc()).all()

        if ventas:
            total_neto = sum(v.subtotal or 0 for v in ventas)
            total_total = sum(v.total or 0 for v in ventas)
            total_margen = sum(v.margen_neto or 0 for v in ventas)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Documentos", len(ventas))
            m2.metric("Total Neto", format_clp(total_neto))
            m3.metric("Total Bruto", format_clp(total_total))
            m4.metric("Margen", format_clp(total_margen))

            st.markdown("---")

            data = []
            for v in ventas:
                cliente_nombre = ""
                if v.cliente_id:
                    cliente = db.query(ClienteFinal).filter(ClienteFinal.id == v.cliente_id).first()
                    cliente_nombre = cliente.nombre if cliente else ""
                data.append({
                    "Fecha": str(v.fecha)[:10] if v.fecha else "-",
                    "Tipo": v.tipo_documento or "-",
                    "Folio": v.folio or "-",
                    "Cliente": cliente_nombre or "-",
                    "Neto": format_clp(v.subtotal),
                    "IVA": format_clp(v.impuestos),
                    "Total": format_clp(v.total),
                    "Costo": format_clp(v.costo_total),
                    "Margen": format_clp(v.margen_neto),
                    "Estado": "Anulada" if v.anulada else "Vigente",
                    "Obs.": (v.observacion or "")[:50],
                })

            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)
        else:
            st.info("No hay ventas en el rango seleccionado. Pruebe ampliando las fechas o sincronice datos desde Obuma.")
    finally:
        db.close()


elif page == "Clientes":
    st.markdown('<p class="main-title">Gestion de Clientes</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Clientes registrados desde Obuma ERP</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        clientes = db.query(ClienteFinal).filter(ClienteFinal.activo == True).all()

        if clientes:
            st.metric("Total Clientes", len(clientes))
            st.markdown("---")

            data = []
            for c in clientes:
                n_ventas = db.query(VentaHistorico).filter(VentaHistorico.cliente_id == c.id).count()
                total = db.query(func.sum(VentaHistorico.total)).filter(VentaHistorico.cliente_id == c.id).scalar() or 0
                data.append({
                    "Nombre": c.nombre,
                    "RUT": c.rut or "-",
                    "Email": c.email or "-",
                    "Telefono": c.telefono or "-",
                    "Direccion": (c.direccion or "-")[:40],
                    "Ventas": n_ventas,
                    "Total Facturado": format_clp(total),
                })

            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        else:
            st.info("No hay clientes registrados. Sincronice con Obuma para cargar los clientes.")
    finally:
        db.close()


elif page == "Contabilidad":
    st.markdown('<p class="main-title">Contabilidad</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Registros contables del libro diario</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        total_debe = db.query(func.sum(ContabilidadHistorico.debe)).scalar() or 0
        total_haber = db.query(func.sum(ContabilidadHistorico.haber)).scalar() or 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ingresos (Haber)", format_clp(total_haber))
        col2.metric("Total Egresos (Debe)", format_clp(total_debe))
        col3.metric("Balance", format_clp(total_haber - total_debe))

        st.markdown("---")

        entries = db.query(ContabilidadHistorico).order_by(
            ContabilidadHistorico.fecha.desc()
        ).limit(200).all()

        if entries:
            df = pd.DataFrame([{
                "Fecha": str(e.fecha) if e.fecha else "-",
                "Cuenta": e.cuenta or "-",
                "Descripcion": (e.descripcion or "-")[:60],
                "Debe": format_clp(e.debe),
                "Haber": format_clp(e.haber),
            } for e in entries])
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)
        else:
            st.info("No hay registros de contabilidad. Sincronice con Obuma primero.")
    finally:
        db.close()


elif page == "API Obuma":
    st.markdown('<p class="main-title">Catalogo API Obuma</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Registro completo de endpoints de la API de Obuma ERP para automatizaciones</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        endpoints = db.query(ObumaApiEndpoint).order_by(
            ObumaApiEndpoint.categoria_orden,
            ObumaApiEndpoint.id
        ).all()

        total_eps = len(endpoints)
        implementados = sum(1 for e in endpoints if e.implementado)
        sync_activos = sum(1 for e in endpoints if e.sync_habilitado)

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Endpoints", total_eps)
        m2.metric("Implementados", implementados)
        m3.metric("Sync Activos", sync_activos)

        st.markdown("---")

        categorias_vistas = []
        for ep in endpoints:
            if ep.categoria not in categorias_vistas:
                categorias_vistas.append(ep.categoria)
                st.markdown(f'<p class="section-header">{ep.categoria_orden}.- {ep.categoria}</p>', unsafe_allow_html=True)

            col_status = ""
            if ep.implementado and ep.sync_habilitado:
                col_status = '<span style="background:#d1fae5;color:#065f46;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">SYNC ACTIVO</span>'
            elif ep.implementado:
                col_status = '<span style="background:#dbeafe;color:#1e40af;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">IMPLEMENTADO</span>'
            elif ep.endpoint_url:
                col_status = '<span style="background:#fef3c7;color:#92400e;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">DISPONIBLE</span>'
            else:
                col_status = '<span style="background:#f3f4f6;color:#6b7280;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">REFERENCIA</span>'

            metodo_color = {"GET": "#059669", "POST": "#d97706", "-": "#9ca3af"}.get(ep.metodo_http, "#6b7280")

            sync_info = ""
            if ep.sync_habilitado and ep.registros_sync > 0:
                sync_info = f' | <strong>{ep.registros_sync}</strong> registros sincronizados'
            if ep.ultima_sync:
                sync_info += f' | Ultima sync: {str(ep.ultima_sync)[:16]}'

            endpoint_display = f'<code style="background:#f1f5f9;padding:2px 8px;border-radius:4px;font-size:0.8rem;">{ep.endpoint_url}</code>' if ep.endpoint_url else '<span style="color:#9ca3af;font-size:0.8rem;">Sin endpoint directo</span>'

            doc_link = f'<a href="{ep.doc_url}" target="_blank" style="color:#2563eb;text-decoration:none;font-size:0.8rem;">Ver documentacion</a>' if ep.doc_url else ""

            st.markdown(f"""
            <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:1rem 1.2rem;margin:0.4rem 0;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                    <div style="display:flex;align-items:center;gap:0.6rem;">
                        <span style="background:{metodo_color};color:white;padding:2px 8px;border-radius:4px;font-size:0.7rem;font-weight:700;">{ep.metodo_http}</span>
                        <strong style="font-size:0.95rem;color:#1a1a2e;">{ep.nombre}</strong>
                    </div>
                    {col_status}
                </div>
                <div style="margin:0.3rem 0;">{endpoint_display}</div>
                <div style="font-size:0.82rem;color:#6b7280;margin:0.3rem 0;">{ep.descripcion or ''}</div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.4rem;">
                    <span style="font-size:0.75rem;color:#9ca3af;">{doc_link}{sync_info}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        st.markdown('<p class="section-header">Probar Endpoint</p>', unsafe_allow_html=True)
        ep_options = [e for e in endpoints if e.endpoint_url and "{" not in (e.endpoint_url or "")]
        if ep_options:
            selected_ep = st.selectbox(
                "Seleccionar endpoint",
                options=ep_options,
                format_func=lambda e: f"{e.categoria} > {e.nombre} ({e.endpoint_url})"
            )
            if st.button("Probar Conexion", type="primary"):
                with st.spinner(f"Consultando {selected_ep.endpoint_url}..."):
                    client = ObumaClient()
                    result = run_async(client.test_endpoint(selected_ep.endpoint_url))
                    if "error" in result:
                        st.error(f"Error: {result.get('error', '')[:200]}")
                    else:
                        total_items = result.get("data-total-items", result.get("data-actual-total", "?"))
                        data_list = result.get("data", [])
                        st.success(f"Conexion exitosa. Total registros: {total_items}")
                        if data_list and len(data_list) > 0:
                            st.json(data_list[:3])

    finally:
        db.close()


elif page == "Reportes":
    st.markdown('<p class="main-title">Reportes Excel</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Generacion y descarga de reportes profesionales</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        st.markdown('<p class="section-header">Generar Nuevo Reporte</p>', unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        with col1:
            fecha_reporte = st.date_input("Fecha del reporte", value=date.today())
        with col2:
            st.write("")
            st.write("")
            if st.button("Generar Reporte", type="primary", use_container_width=True):
                with st.spinner("Generando reporte Excel..."):
                    filepath = generate_daily_report(db, fecha_reporte)
                    st.success("Reporte generado exitosamente")
                    with open(filepath, "rb") as f:
                        st.download_button(
                            label="Descargar Reporte",
                            data=f.read(),
                            file_name=os.path.basename(filepath),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )

        st.markdown("---")
        st.markdown('<p class="section-header">Reportes Historicos</p>', unsafe_allow_html=True)

        reportes = db.query(ReporteGenerado).order_by(ReporteGenerado.generado_at.desc()).all()
        if reportes:
            for r in reportes:
                col1, col2, col3 = st.columns([4, 3, 1])
                col1.write(f"**{r.nombre_archivo}**")
                col2.write(f"{str(r.generado_at)[:16]}")
                if r.ruta_archivo and os.path.exists(r.ruta_archivo):
                    with open(r.ruta_archivo, "rb") as f:
                        col3.download_button(
                            label="Descargar",
                            data=f.read(),
                            file_name=r.nombre_archivo,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_{r.id}"
                        )
                else:
                    col3.write("N/A")
        else:
            st.info("No se han generado reportes aun. Use el boton de arriba para crear uno.")
    finally:
        db.close()


elif page == "Sincronizacion":
    st.markdown('<p class="main-title">Sincronizacion con Obuma</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Importe datos desde el ERP Obuma a la base de datos local</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sincronizar Todo", type="primary", use_container_width=True):
                with st.spinner("Conectando con Obuma y sincronizando todos los modulos..."):
                    service = SyncService(db)
                    results = run_async(service.sync_all())
                    st.success("Sincronizacion completada exitosamente")

                    for module, result in results.items():
                        if isinstance(result, dict) and "error" not in result:
                            st.markdown(f"""
                            <div style="background:#f0fdf4; border-left:4px solid #059669; padding:0.8rem 1rem; border-radius:0 8px 8px 0; margin:0.3rem 0;">
                                <strong>{module.title()}</strong>: {result.get('synced', 0)} registros sincronizados
                                (API: {result.get('total_api', 0)} | BD: {result.get('total_db', 0)})
                            </div>
                            """, unsafe_allow_html=True)
                        elif isinstance(result, dict) and "error" in result:
                            st.markdown(f"""
                            <div style="background:#fef2f2; border-left:4px solid #dc2626; padding:0.8rem 1rem; border-radius:0 8px 8px 0; margin:0.3rem 0;">
                                <strong>{module.title()}</strong>: Error - {str(result.get('error', ''))[:100]}
                            </div>
                            """, unsafe_allow_html=True)

        with col2:
            endpoint = st.selectbox("Modulo especifico", ["clientes", "ventas", "productos", "compras", "contabilidad"])
            if st.button("Sincronizar Modulo", use_container_width=True):
                with st.spinner(f"Sincronizando {endpoint}..."):
                    service = SyncService(db)
                    method_map = {
                        "clientes": service.sync_clientes,
                        "ventas": service.sync_ventas,
                        "productos": service.sync_productos,
                        "compras": service.sync_compras,
                        "contabilidad": service.sync_contabilidad,
                    }
                    result = run_async(method_map[endpoint]())
                    if isinstance(result, dict) and "error" not in result:
                        st.success(f"{endpoint.title()} sincronizado: {result.get('synced', 0)} registros")
                    else:
                        st.warning(f"Sin datos nuevos para {endpoint}")
                    st.json(result)

        st.markdown("---")
        st.markdown('<p class="section-header">Historial de Sincronizacion</p>', unsafe_allow_html=True)

        logs = db.query(SyncLog).order_by(SyncLog.ejecutado_at.desc()).limit(20).all()
        if logs:
            data = []
            for l in logs:
                estado_badge = "badge-ok" if l.estado == "ok" else "badge-error"
                data.append({
                    "Fecha": str(l.ejecutado_at)[:16],
                    "Modulo": l.endpoint,
                    "Registros API": l.registros_api,
                    "Registros BD": l.registros_db,
                    "Estado": l.estado.upper(),
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        else:
            st.info("Sin historial de sincronizacion. Presione 'Sincronizar Todo' para comenzar.")
    finally:
        db.close()


elif page == "Auditoria":
    st.markdown('<p class="main-title">Auditoria de Cifras</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Comparacion de datos entre la API de Obuma y la base de datos local</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        service = SyncService(db)
        audit = service.audit_totals()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<p class="section-header">Ventas</p>', unsafe_allow_html=True)

            v = audit["ventas"]
            st.metric("Total en Base de Datos", format_clp(v["total_db"]))
            st.metric("Registros en BD", v["registros_db"])
            st.metric("Ultima Sync - Total API", format_clp(v["ultima_sync_api_total"]))
            st.metric("Ultima Sync - Registros API", v["ultima_sync_api_registros"])

            discrepancia = v["discrepancia_total"]
            if discrepancia > 0:
                st.error(f"Discrepancia detectada: {format_clp(discrepancia)}")
            else:
                st.success("Sin discrepancias en ventas")

        with col2:
            st.markdown('<p class="section-header">Compras</p>', unsafe_allow_html=True)

            c = audit["compras"]
            st.metric("Total en Base de Datos", format_clp(c["total_db"]))
            st.metric("Registros en BD", c["registros_db"])
            st.metric("Ultima Sync - Registros API", c["ultima_sync_api_registros"])

        st.markdown("---")
        st.markdown('<p class="section-header">Log de Auditorias</p>', unsafe_allow_html=True)

        logs = db.query(SyncLog).order_by(SyncLog.ejecutado_at.desc()).limit(10).all()
        if logs:
            data = [{
                "Fecha": str(l.ejecutado_at)[:16],
                "Modulo": l.endpoint,
                "Total API": format_clp(l.total_api),
                "Total BD": format_clp(l.total_db),
                "Discrepancias": l.discrepancias,
                "Estado": l.estado.upper(),
            } for l in logs]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    finally:
        db.close()
