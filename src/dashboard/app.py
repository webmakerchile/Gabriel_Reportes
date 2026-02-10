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
    ClienteFinal, SyncLog, ReporteGenerado, ObumaApiEndpoint,
    Proveedor, ClienteContacto, ClienteDireccion, Empleado, Remuneracion,
    VentaItem, VentaCotizacion, VentaCobro, VentaDte, CompraOC, CompraPago,
    CompraDteRecibido, GastoMenor, CrmLead, ProductoCategoria,
    ProductoSubCategoria, ProductoFabricante, ProductoPrecio, CostoHistorico
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

DARK_BG = "#0e1117"
CARD_BG = "#1a1f2e"
CARD_BORDER = "#2d3548"
TEXT_PRIMARY = "#e2e8f0"
TEXT_SECONDARY = "#94a3b8"
ACCENT_BLUE = "#3b82f6"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_AMBER = "#f59e0b"
ACCENT_PURPLE = "#8b5cf6"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {{
        font-family: 'Inter', sans-serif;
    }}

    div[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }}
    div[data-testid="stSidebar"] .stMarkdown p,
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 {{
        color: #e2e8f0;
    }}
    div[data-testid="stSidebar"] .stRadio label {{
        color: #cbd5e1 !important;
    }}
    div[data-testid="stSidebar"] .stRadio label:hover {{
        color: #ffffff !important;
    }}
    div[data-testid="stSidebar"] hr {{
        border-color: rgba(255,255,255,0.08);
    }}

    div[data-testid="stMetric"] {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
    }}
    div[data-testid="stMetric"] label {{
        color: {TEXT_SECONDARY} !important;
    }}
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
        color: {TEXT_PRIMARY} !important;
    }}

    .metric-card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
        transition: all 0.2s ease;
    }}
    .metric-card:hover {{
        border-color: {ACCENT_BLUE};
        box-shadow: 0 8px 15px -3px rgba(59,130,246,0.15);
    }}
    .metric-value {{
        font-size: 1.8rem;
        font-weight: 700;
        color: {TEXT_PRIMARY};
        margin: 0;
        line-height: 1.2;
    }}
    .metric-label {{
        font-size: 0.78rem;
        font-weight: 500;
        color: {TEXT_SECONDARY};
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin: 0 0 0.4rem 0;
    }}
    .metric-icon {{
        font-size: 1.5rem;
        margin-bottom: 0.3rem;
    }}

    .section-header {{
        font-size: 1.1rem;
        font-weight: 600;
        color: {TEXT_PRIMARY};
        margin: 1.5rem 0 0.8rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid {CARD_BORDER};
    }}

    .page-title {{
        font-size: 1.8rem;
        font-weight: 700;
        color: {TEXT_PRIMARY};
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }}
    .page-subtitle {{
        font-size: 0.95rem;
        color: {TEXT_SECONDARY};
        margin-bottom: 1.5rem;
    }}

    .data-card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
    }}

    .status-badge {{
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }}
    .badge-ok {{ background: rgba(16,185,129,0.15); color: #34d399; }}
    .badge-error {{ background: rgba(239,68,68,0.15); color: #f87171; }}
    .badge-warning {{ background: rgba(245,158,11,0.15); color: #fbbf24; }}
    .badge-info {{ background: rgba(59,130,246,0.15); color: #60a5fa; }}

    .stDataFrame {{
        border-radius: 8px;
        overflow: hidden;
    }}
    .stDataFrame [data-testid="stDataFrameResizable"] {{
        border: 1px solid {CARD_BORDER};
        border-radius: 8px;
    }}

    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {ACCENT_BLUE}, #2563eb);
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        color: white;
    }}
    .stButton > button {{
        border-radius: 8px;
        font-weight: 500;
        border-color: {CARD_BORDER};
    }}

    .sync-result-ok {{
        background: rgba(16,185,129,0.1);
        border-left: 4px solid {ACCENT_GREEN};
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.3rem 0;
        color: {TEXT_PRIMARY};
    }}
    .sync-result-error {{
        background: rgba(239,68,68,0.1);
        border-left: 4px solid {ACCENT_RED};
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.3rem 0;
        color: {TEXT_PRIMARY};
    }}

    .api-card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin: 0.4rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }}

    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px;
        padding: 8px 16px;
    }}

    div.stAlert {{
        border-radius: 8px;
    }}
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


def render_metric(label, value, icon="", color=TEXT_PRIMARY):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">{icon}</div>
        <p class="metric-label">{label}</p>
        <p class="metric-value" style="color:{color};">{value}</p>
    </div>
    """, unsafe_allow_html=True)


def chart_layout(height=340):
    return dict(
        height=height,
        margin=dict(t=20, b=40, l=50, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(color=TEXT_SECONDARY)),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=TEXT_SECONDARY),
        xaxis=dict(showgrid=False, color=TEXT_SECONDARY),
        yaxis=dict(showgrid=True, gridcolor="rgba(45,53,72,0.5)", color=TEXT_SECONDARY),
    )


st.sidebar.markdown("### 📊 BI Platform")
st.sidebar.markdown("**Gabriel Hoyos**")
st.sidebar.caption("Centro de Mando Empresarial")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navegacion",
    ["Dashboard", "Ventas", "Clientes", "Proveedores", "Productos",
     "Empleados", "Compras", "Contabilidad", "CRM",
     "API Obuma", "Reportes", "Sincronizacion", "Auditoria"],
    index=0,
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.caption("v2.0 | Powered by Obuma ERP")


# ============================================================
# DASHBOARD
# ============================================================
if page == "Dashboard":
    st.markdown('<p class="page-title">Centro de Mando</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Vista consolidada del rendimiento de todas las cuentas</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        total_ventas = db.query(func.sum(VentaHistorico.total)).scalar() or 0
        total_compras = db.query(func.sum(CompraHistorico.total)).scalar() or 0
        total_margen = db.query(func.sum(VentaHistorico.margen_neto)).scalar() or 0
        n_clientes = db.query(ClienteFinal).filter(ClienteFinal.activo == True).count()
        n_productos = db.query(Producto).filter(Producto.activo == True).count()
        n_proveedores = db.query(Proveedor).filter(Proveedor.activo == True).count()
        n_empleados = db.query(Empleado).filter(Empleado.activo == True).count()
        n_ventas = db.query(VentaHistorico).count()
        ventas_anuladas = db.query(VentaHistorico).filter(VentaHistorico.anulada == True).count()
        ventas_vigentes = n_ventas - ventas_anuladas
        total_pagado = db.query(func.sum(VentaHistorico.total_pagado)).scalar() or 0
        total_por_pagar = db.query(func.sum(VentaHistorico.total_por_pagar)).scalar() or 0
        margen_pct = (total_margen / total_ventas * 100) if total_ventas else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric("Ventas Totales", format_clp(total_ventas), "💰", ACCENT_GREEN)
        with c2:
            render_metric("Compras Totales", format_clp(total_compras), "🛒", ACCENT_AMBER)
        with c3:
            render_metric("Margen Neto", format_clp(total_margen), "📈", ACCENT_BLUE)
        with c4:
            render_metric("Margen %", f"{margen_pct:.1f}%", "📊", ACCENT_PURPLE)

        st.markdown("")

        c5, c6, c7, c8 = st.columns(4)
        with c5:
            render_metric("Clientes", str(n_clientes), "👥")
        with c6:
            render_metric("Documentos", str(n_ventas), "📄")
        with c7:
            render_metric("Empleados", str(n_empleados), "👷")
        with c8:
            render_metric("Proveedores", str(n_proveedores), "🏭")

        if total_pagado or total_por_pagar:
            st.markdown("")
            cp1, cp2, cp3, cp4 = st.columns(4)
            with cp1:
                render_metric("Pagado", format_clp(total_pagado), "✅", ACCENT_GREEN)
            with cp2:
                render_metric("Por Pagar", format_clp(total_por_pagar), "⏳", ACCENT_RED)
            with cp3:
                render_metric("Productos", str(n_productos), "📦")
            with cp4:
                render_metric("Vigentes / Anuladas", f"{ventas_vigentes} / {ventas_anuladas}", "📋")

        st.markdown("---")
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown('<p class="section-header">Ventas por Fecha</p>', unsafe_allow_html=True)
            ventas_data = db.query(
                func.date(VentaHistorico.fecha).label("fecha"),
                func.sum(VentaHistorico.total).label("total"),
                func.sum(VentaHistorico.margen_neto).label("margen"),
                func.count(VentaHistorico.id).label("cantidad")
            ).filter(VentaHistorico.fecha.isnot(None)).group_by(
                func.date(VentaHistorico.fecha)
            ).order_by(func.date(VentaHistorico.fecha)).all()

            if ventas_data:
                df_ventas = pd.DataFrame([
                    {"Fecha": str(v.fecha), "Ventas": v.total or 0, "Margen": v.margen or 0}
                    for v in ventas_data
                ])
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_ventas["Fecha"], y=df_ventas["Ventas"],
                                     name="Ventas", marker_color=ACCENT_BLUE))
                fig.add_trace(go.Bar(x=df_ventas["Fecha"], y=df_ventas["Margen"],
                                     name="Margen", marker_color=ACCENT_GREEN))
                fig.update_layout(barmode="group", **chart_layout())
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sin datos de ventas. Sincronice con Obuma primero.")

        with col_right:
            st.markdown('<p class="section-header">Ingresos vs Egresos</p>', unsafe_allow_html=True)
            contab_data = db.query(
                func.date(ContabilidadHistorico.fecha).label("fecha"),
                func.sum(ContabilidadHistorico.haber).label("ingresos"),
                func.sum(ContabilidadHistorico.debe).label("egresos")
            ).filter(ContabilidadHistorico.fecha.isnot(None)).group_by(
                func.date(ContabilidadHistorico.fecha)
            ).order_by(func.date(ContabilidadHistorico.fecha)).all()

            if contab_data:
                df_contab = pd.DataFrame([
                    {"Fecha": str(c.fecha), "Ingresos": c.ingresos or 0, "Egresos": c.egresos or 0}
                    for c in contab_data
                ])
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df_contab["Fecha"], y=df_contab["Ingresos"],
                                          mode="lines+markers", name="Ingresos",
                                          line=dict(color=ACCENT_GREEN, width=2.5),
                                          marker=dict(size=6)))
                fig2.add_trace(go.Scatter(x=df_contab["Fecha"], y=df_contab["Egresos"],
                                          mode="lines+markers", name="Egresos",
                                          line=dict(color=ACCENT_RED, width=2.5),
                                          marker=dict(size=6)))
                fig2.update_layout(**chart_layout())
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
                    data.append({
                        "Fecha": str(v.fecha)[:10] if v.fecha else "-",
                        "Folio": v.folio or "-",
                        "Total": format_clp(v.total),
                        "Estado": "Anulada" if v.anulada else "Vigente",
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
            ).join(VentaHistorico, VentaHistorico.cliente_id == ClienteFinal.id
            ).group_by(ClienteFinal.nombre, ClienteFinal.rut
            ).order_by(func.sum(VentaHistorico.total).desc()).limit(10).all()

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


# ============================================================
# VENTAS
# ============================================================
elif page == "Ventas":
    st.markdown('<p class="page-title">Gestion de Ventas</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Documentos de venta, items, cotizaciones, cobros y DTE</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        tab_docs, tab_items, tab_cotiz, tab_cobros, tab_dte = st.tabs([
            "Documentos", "Items de Venta", "Cotizaciones", "Cobros", "DTE"
        ])

        with tab_docs:
            col1, col2, col3 = st.columns(3)
            with col1:
                fecha_desde = st.date_input("Desde", value=date.today() - timedelta(days=365), key="vd1")
            with col2:
                fecha_hasta = st.date_input("Hasta", value=date.today(), key="vd2")
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
                with m1:
                    render_metric("Documentos", str(len(ventas)), "📄")
                with m2:
                    render_metric("Total Neto", format_clp(total_neto), "💵", ACCENT_BLUE)
                with m3:
                    render_metric("Total Bruto", format_clp(total_total), "💰", ACCENT_GREEN)
                with m4:
                    render_metric("Margen", format_clp(total_margen), "📈", ACCENT_PURPLE)

                st.markdown("")
                data = []
                for v in ventas:
                    data.append({
                        "Fecha": str(v.fecha)[:10] if v.fecha else "-",
                        "Tipo": v.tipo_documento or "-",
                        "Folio": v.folio or "-",
                        "Neto": format_clp(v.subtotal),
                        "IVA": format_clp(v.impuestos),
                        "Total": format_clp(v.total),
                        "Costo": format_clp(v.costo_total),
                        "Margen": format_clp(v.margen_neto),
                        "Estado": "Anulada" if v.anulada else "Vigente",
                    })
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("No hay ventas en el rango seleccionado.")

        with tab_items:
            items = db.query(VentaItem).order_by(VentaItem.id.desc()).limit(500).all()
            if items:
                st.metric("Total Items", len(items))
                data = [{
                    "Venta ID": i.venta_id_obuma or "-",
                    "Producto": i.producto_nombre or "-",
                    "SKU": i.producto_sku or "-",
                    "Cantidad": i.cantidad or 0,
                    "Precio Unit.": format_clp(i.precio_unitario),
                    "Total": format_clp(i.total),
                } for i in items]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin items de venta. Sincronice con Obuma.")

        with tab_cotiz:
            cotizaciones = db.query(VentaCotizacion).order_by(VentaCotizacion.id.desc()).limit(200).all()
            if cotizaciones:
                st.metric("Total Cotizaciones", len(cotizaciones))
                data = [{
                    "Folio": c.folio or "-",
                    "Fecha": str(c.fecha)[:10] if c.fecha else "-",
                    "Cliente": c.cliente_nombre or "-",
                    "Total": format_clp(c.total),
                    "Estado": c.estado or "-",
                } for c in cotizaciones]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin cotizaciones. Sincronice con Obuma.")

        with tab_cobros:
            cobros = db.query(VentaCobro).order_by(VentaCobro.id.desc()).limit(200).all()
            if cobros:
                total_cobros = sum(c.monto or 0 for c in cobros)
                c1, c2 = st.columns(2)
                with c1:
                    render_metric("Total Cobros", str(len(cobros)), "🧾")
                with c2:
                    render_metric("Monto Total", format_clp(total_cobros), "💵", ACCENT_GREEN)
                st.markdown("")
                data = [{
                    "Fecha": str(c.fecha)[:10] if c.fecha else "-",
                    "Monto": format_clp(c.monto),
                    "Forma Pago": c.forma_pago or "-",
                    "Estado": c.estado or "-",
                } for c in cobros]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin cobros registrados. Sincronice con Obuma.")

        with tab_dte:
            dtes = db.query(VentaDte).order_by(VentaDte.id.desc()).limit(200).all()
            if dtes:
                st.metric("Total DTE Emitidos", len(dtes))
                data = [{
                    "Tipo DTE": d.tipo_dcto or "-",
                    "Folio": d.folio or "-",
                    "Fecha": str(d.fecha)[:10] if d.fecha else "-",
                    "Total": format_clp(d.monto_total),
                    "Estado SII": d.estado_sii or "-",
                } for d in dtes]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin DTE emitidos. Sincronice con Obuma.")
    finally:
        db.close()


# ============================================================
# CLIENTES
# ============================================================
elif page == "Clientes":
    st.markdown('<p class="page-title">Gestion de Clientes</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Clientes, contactos y direcciones desde Obuma ERP</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        tab_clientes, tab_contactos, tab_direcciones = st.tabs([
            "Clientes", "Contactos", "Direcciones"
        ])

        with tab_clientes:
            clientes = db.query(ClienteFinal).filter(ClienteFinal.activo == True).all()
            if clientes:
                render_metric("Total Clientes Activos", str(len(clientes)), "👥", ACCENT_BLUE)
                st.markdown("")
                data = []
                for c in clientes:
                    n_ventas = db.query(VentaHistorico).filter(VentaHistorico.cliente_id == c.id).count()
                    total = db.query(func.sum(VentaHistorico.total)).filter(VentaHistorico.cliente_id == c.id).scalar() or 0
                    data.append({
                        "Nombre": c.nombre,
                        "RUT": c.rut or "-",
                        "Email": c.email or "-",
                        "Telefono": c.telefono or "-",
                        "Ventas": n_ventas,
                        "Total Facturado": format_clp(total),
                    })
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("No hay clientes. Sincronice con Obuma.")

        with tab_contactos:
            contactos = db.query(ClienteContacto).all()
            if contactos:
                st.metric("Total Contactos", len(contactos))
                data = [{
                    "Nombre": c.nombre or "-",
                    "Email": c.email or "-",
                    "Telefono": c.telefono or "-",
                    "Cargo": c.cargo or "-",
                    "Cliente ID": c.cliente_id_obuma or "-",
                } for c in contactos]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("Sin contactos de clientes. Sincronice con Obuma.")

        with tab_direcciones:
            direcciones = db.query(ClienteDireccion).all()
            if direcciones:
                st.metric("Total Direcciones", len(direcciones))
                data = [{
                    "Direccion": d.direccion or "-",
                    "Ciudad": d.ciudad or "-",
                    "Comuna": d.comuna or "-",
                    "Region": d.region or "-",
                    "Cliente ID": d.cliente_id_obuma or "-",
                } for d in direcciones]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("Sin direcciones de clientes. Sincronice con Obuma.")
    finally:
        db.close()


# ============================================================
# PROVEEDORES
# ============================================================
elif page == "Proveedores":
    st.markdown('<p class="page-title">Proveedores</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Proveedores registrados desde Obuma ERP</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        proveedores = db.query(Proveedor).filter(Proveedor.activo == True).all()
        total_prov = len(proveedores)

        render_metric("Total Proveedores", str(total_prov), "🏭", ACCENT_BLUE)
        st.markdown("")

        if proveedores:
            data = [{
                "Razon Social": p.razon_social or p.nombre_fantasia or "-",
                "RUT": p.rut or "-",
                "Email": p.email or "-",
                "Telefono": p.telefono or "-",
                "Direccion": (p.direccion or "-")[:60],
            } for p in proveedores]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        else:
            st.info("Sin proveedores registrados. Sincronice con Obuma.")
    finally:
        db.close()


# ============================================================
# PRODUCTOS
# ============================================================
elif page == "Productos":
    st.markdown('<p class="page-title">Productos</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Productos, categorias, precios y fabricantes</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        tab_prod, tab_cat, tab_subcat, tab_fab, tab_precios = st.tabs([
            "Productos", "Categorias", "Subcategorias", "Fabricantes", "Precios"
        ])

        with tab_prod:
            productos = db.query(Producto).all()
            activos = [p for p in productos if p.activo]
            c1, c2, c3 = st.columns(3)
            with c1:
                render_metric("Total Productos", str(len(productos)), "📦")
            with c2:
                render_metric("Activos", str(len(activos)), "✅", ACCENT_GREEN)
            with c3:
                alertas = [p for p in activos if p.stock_actual <= p.stock_minimo]
                render_metric("Alerta Stock", str(len(alertas)), "⚠️", ACCENT_RED)

            st.markdown("")
            if productos:
                data = [{
                    "Nombre": p.nombre,
                    "SKU": p.sku or "-",
                    "Categoria": p.categoria or "-",
                    "Precio Venta": format_clp(p.precio_venta),
                    "Costo": format_clp(p.costo),
                    "Stock": p.stock_actual or 0,
                    "Activo": "Si" if p.activo else "No",
                } for p in productos]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin productos. Sincronice con Obuma.")

        with tab_cat:
            categorias = db.query(ProductoCategoria).all()
            if categorias:
                st.metric("Total Categorias", len(categorias))
                data = [{
                    "ID": c.obuma_id or "-",
                    "Nombre": c.nombre or "-",
                } for c in categorias]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("Sin categorias. Sincronice con Obuma.")

        with tab_subcat:
            subcategorias = db.query(ProductoSubCategoria).all()
            if subcategorias:
                st.metric("Total Subcategorias", len(subcategorias))
                data = [{
                    "ID": s.obuma_id or "-",
                    "Nombre": s.nombre or "-",
                    "Categoria ID": s.categoria_id_obuma or "-",
                } for s in subcategorias]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("Sin subcategorias. Sincronice con Obuma.")

        with tab_fab:
            fabricantes = db.query(ProductoFabricante).all()
            if fabricantes:
                st.metric("Total Fabricantes", len(fabricantes))
                data = [{
                    "ID": f.obuma_id or "-",
                    "Nombre": f.nombre or "-",
                } for f in fabricantes]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("Sin fabricantes. Sincronice con Obuma.")

        with tab_precios:
            precios = db.query(ProductoPrecio).all()
            if precios:
                st.metric("Total Listas de Precios", len(precios))
                data = [{
                    "Producto ID": p.producto_id_obuma or "-",
                    "Producto": p.producto_nombre or "-",
                    "Lista": p.lista_precio or "-",
                    "Precio": format_clp(p.precio),
                } for p in precios]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin listas de precios. Sincronice con Obuma.")
    finally:
        db.close()


# ============================================================
# EMPLEADOS
# ============================================================
elif page == "Empleados":
    st.markdown('<p class="page-title">Empleados</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Empleados y remuneraciones desde Obuma ERP</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        tab_emp, tab_rem = st.tabs(["Empleados", "Remuneraciones"])

        with tab_emp:
            empleados = db.query(Empleado).all()
            activos = [e for e in empleados if e.activo]
            c1, c2 = st.columns(2)
            with c1:
                render_metric("Total Empleados", str(len(empleados)), "👷")
            with c2:
                render_metric("Activos", str(len(activos)), "✅", ACCENT_GREEN)

            st.markdown("")
            if empleados:
                data = [{
                    "Nombre": e.nombre or "-",
                    "RUT": e.rut or "-",
                    "Email": e.email or "-",
                    "Cargo": e.cargo or "-",
                    "Activo": "Si" if e.activo else "No",
                } for e in empleados]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("Sin empleados. Sincronice con Obuma.")

        with tab_rem:
            remuneraciones = db.query(Remuneracion).order_by(Remuneracion.id.desc()).limit(200).all()
            if remuneraciones:
                total_haberes = sum(r.total_haberes or 0 for r in remuneraciones)
                total_liquido = sum(r.liquido or 0 for r in remuneraciones)
                c1, c2, c3 = st.columns(3)
                with c1:
                    render_metric("Registros", str(len(remuneraciones)), "📋")
                with c2:
                    render_metric("Total Haberes", format_clp(total_haberes), "💵", ACCENT_BLUE)
                with c3:
                    render_metric("Total Liquido", format_clp(total_liquido), "💰", ACCENT_GREEN)

                st.markdown("")
                data = [{
                    "Empleado RUT": r.empleado_rut or "-",
                    "Periodo": r.periodo or "-",
                    "Haberes": format_clp(r.total_haberes),
                    "Descuentos": format_clp(r.total_descuentos),
                    "Liquido": format_clp(r.liquido),
                } for r in remuneraciones]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin remuneraciones. Sincronice con Obuma.")
    finally:
        db.close()


# ============================================================
# COMPRAS
# ============================================================
elif page == "Compras":
    st.markdown('<p class="page-title">Compras</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Compras, ordenes de compra, pagos y DTE recibidos</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        tab_compras, tab_oc, tab_pagos, tab_dte_rec, tab_gastos = st.tabs([
            "Compras", "Ordenes de Compra", "Pagos", "DTE Recibidos", "Gastos Menores"
        ])

        with tab_compras:
            compras = db.query(CompraHistorico).order_by(CompraHistorico.fecha.desc()).all()
            if compras:
                total_compras = sum(c.total or 0 for c in compras)
                c1, c2 = st.columns(2)
                with c1:
                    render_metric("Total Compras", str(len(compras)), "🛒")
                with c2:
                    render_metric("Monto Total", format_clp(total_compras), "💵", ACCENT_AMBER)

                st.markdown("")
                data = [{
                    "Fecha": str(c.fecha)[:10] if c.fecha else "-",
                    "Proveedor": c.proveedor or "-",
                    "Folio": c.folio or "-",
                    "Total": format_clp(c.total),
                    "Estado": c.estado or "-",
                } for c in compras]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin compras registradas. Sincronice con Obuma.")

        with tab_oc:
            ocs = db.query(CompraOC).order_by(CompraOC.id.desc()).limit(200).all()
            if ocs:
                st.metric("Total OC", len(ocs))
                data = [{
                    "Folio": o.folio or "-",
                    "Fecha": str(o.fecha)[:10] if o.fecha else "-",
                    "Proveedor": o.proveedor or "-",
                    "Total": format_clp(o.total),
                    "Estado": o.estado or "-",
                } for o in ocs]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin ordenes de compra. Sincronice con Obuma.")

        with tab_pagos:
            pagos = db.query(CompraPago).order_by(CompraPago.id.desc()).limit(200).all()
            if pagos:
                total_pagos = sum(p.monto or 0 for p in pagos)
                c1, c2 = st.columns(2)
                with c1:
                    render_metric("Total Pagos", str(len(pagos)), "💳")
                with c2:
                    render_metric("Monto Total", format_clp(total_pagos), "💵", ACCENT_RED)

                st.markdown("")
                data = [{
                    "Fecha": str(p.fecha)[:10] if p.fecha else "-",
                    "Monto": format_clp(p.monto),
                    "Forma Pago": p.forma_pago or "-",
                    "Origen": p.origen or "-",
                } for p in pagos]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin pagos a proveedores. Sincronice con Obuma.")

        with tab_dte_rec:
            dtes = db.query(CompraDteRecibido).order_by(CompraDteRecibido.id.desc()).limit(200).all()
            if dtes:
                st.metric("Total DTE Recibidos", len(dtes))
                data = [{
                    "Tipo DTE": d.tipo_dcto or "-",
                    "Folio": d.folio or "-",
                    "Emisor": d.razon_social or "-",
                    "Fecha": str(d.fecha)[:10] if d.fecha else "-",
                    "Total": format_clp(d.monto_total),
                } for d in dtes]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin DTE recibidos. Este endpoint puede no estar disponible en su cuenta Obuma.")

        with tab_gastos:
            gastos = db.query(GastoMenor).order_by(GastoMenor.id.desc()).limit(200).all()
            if gastos:
                total_gastos = sum(g.monto or 0 for g in gastos)
                c1, c2 = st.columns(2)
                with c1:
                    render_metric("Total Gastos", str(len(gastos)), "📝")
                with c2:
                    render_metric("Monto Total", format_clp(total_gastos), "💵", ACCENT_AMBER)

                st.markdown("")
                data = [{
                    "Fecha": str(g.fecha)[:10] if g.fecha else "-",
                    "Descripcion": g.descripcion or "-",
                    "Monto": format_clp(g.monto),
                    "Categoria": g.categoria or "-",
                } for g in gastos]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin gastos menores. Este endpoint puede no estar disponible en su cuenta Obuma.")
    finally:
        db.close()


# ============================================================
# CONTABILIDAD
# ============================================================
elif page == "Contabilidad":
    st.markdown('<p class="page-title">Contabilidad</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Libro diario y registros contables</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        total_debe = db.query(func.sum(ContabilidadHistorico.debe)).scalar() or 0
        total_haber = db.query(func.sum(ContabilidadHistorico.haber)).scalar() or 0
        balance = total_haber - total_debe

        c1, c2, c3 = st.columns(3)
        with c1:
            render_metric("Total Ingresos (Haber)", format_clp(total_haber), "📥", ACCENT_GREEN)
        with c2:
            render_metric("Total Egresos (Debe)", format_clp(total_debe), "📤", ACCENT_RED)
        with c3:
            color = ACCENT_GREEN if balance >= 0 else ACCENT_RED
            render_metric("Balance", format_clp(balance), "⚖️", color)

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


# ============================================================
# CRM
# ============================================================
elif page == "CRM":
    st.markdown('<p class="page-title">CRM - Leads</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Oportunidades comerciales y seguimiento de leads</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        leads = db.query(CrmLead).order_by(CrmLead.id.desc()).all()

        if leads:
            total_monto = sum(l.monto_estimado or 0 for l in leads)
            c1, c2, c3 = st.columns(3)
            with c1:
                render_metric("Total Leads", str(len(leads)), "🎯")
            with c2:
                render_metric("Monto Estimado", format_clp(total_monto), "💰", ACCENT_GREEN)
            with c3:
                activos = [l for l in leads if l.estado and l.estado.lower() not in ("cerrado", "perdido")]
                render_metric("Activos", str(len(activos)), "🔥", ACCENT_AMBER)

            st.markdown("")
            data = [{
                "Nombre": l.nombre or "-",
                "Empresa": l.empresa or "-",
                "Email": l.email or "-",
                "Telefono": l.telefono or "-",
                "Estado": l.estado or "-",
                "Monto Est.": format_clp(l.monto_estimado),
            } for l in leads]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
        else:
            st.info("Sin leads CRM. Sincronice con Obuma.")
    finally:
        db.close()


# ============================================================
# API OBUMA
# ============================================================
elif page == "API Obuma":
    st.markdown('<p class="page-title">Catalogo API Obuma</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">30 endpoints registrados para automatizaciones</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        endpoints = db.query(ObumaApiEndpoint).order_by(
            ObumaApiEndpoint.categoria_orden, ObumaApiEndpoint.id
        ).all()

        total_eps = len(endpoints)
        implementados = sum(1 for e in endpoints if e.implementado)
        sync_activos = sum(1 for e in endpoints if e.sync_habilitado)
        no_disp = sum(1 for e in endpoints if e.estado == "no_disponible")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric("Total Endpoints", str(total_eps), "🔌")
        with c2:
            render_metric("Implementados", str(implementados), "✅", ACCENT_GREEN)
        with c3:
            render_metric("Sync Activos", str(sync_activos), "🔄", ACCENT_BLUE)
        with c4:
            render_metric("No Disponibles", str(no_disp), "❌", ACCENT_RED)

        st.markdown("---")

        categorias_vistas = []
        for ep in endpoints:
            if ep.categoria not in categorias_vistas:
                categorias_vistas.append(ep.categoria)
                st.markdown(f'<p class="section-header">{ep.categoria_orden}. {ep.categoria}</p>', unsafe_allow_html=True)

            if ep.estado == "no_disponible":
                badge = f'<span style="background:rgba(239,68,68,0.15);color:#f87171;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">NO DISPONIBLE</span>'
            elif ep.implementado and ep.sync_habilitado:
                badge = f'<span style="background:rgba(16,185,129,0.15);color:#34d399;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">SYNC ACTIVO</span>'
            elif ep.implementado:
                badge = f'<span style="background:rgba(59,130,246,0.15);color:#60a5fa;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">IMPLEMENTADO</span>'
            elif ep.endpoint_url:
                badge = f'<span style="background:rgba(245,158,11,0.15);color:#fbbf24;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">DISPONIBLE</span>'
            else:
                badge = f'<span style="background:rgba(148,163,184,0.15);color:#94a3b8;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">REFERENCIA</span>'

            metodo_color = {"GET": ACCENT_GREEN, "POST": ACCENT_AMBER, "-": TEXT_SECONDARY}.get(ep.metodo_http, TEXT_SECONDARY)
            endpoint_display = f'<code style="background:rgba(59,130,246,0.1);color:#60a5fa;padding:2px 8px;border-radius:4px;font-size:0.8rem;">{ep.endpoint_url}</code>' if ep.endpoint_url else '<span style="color:#64748b;font-size:0.8rem;">Sin endpoint directo</span>'

            sync_info = ""
            if ep.sync_habilitado and ep.registros_sync and ep.registros_sync > 0:
                sync_info = f' | <strong style="color:{ACCENT_GREEN};">{ep.registros_sync}</strong> registros'
            if ep.ultima_sync:
                sync_info += f' | Sync: {str(ep.ultima_sync)[:16]}'

            st.markdown(f"""
            <div class="api-card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                    <div style="display:flex;align-items:center;gap:0.6rem;">
                        <span style="background:{metodo_color};color:white;padding:2px 8px;border-radius:4px;font-size:0.7rem;font-weight:700;">{ep.metodo_http}</span>
                        <strong style="font-size:0.95rem;color:{TEXT_PRIMARY};">{ep.nombre}</strong>
                    </div>
                    {badge}
                </div>
                <div style="margin:0.3rem 0;">{endpoint_display}</div>
                <div style="font-size:0.82rem;color:{TEXT_SECONDARY};margin:0.3rem 0;">{ep.descripcion or ''}</div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:0.4rem;">{sync_info}</div>
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


# ============================================================
# REPORTES
# ============================================================
elif page == "Reportes":
    st.markdown('<p class="page-title">Reportes Excel</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Generacion y descarga de reportes profesionales</p>', unsafe_allow_html=True)

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
            st.info("No se han generado reportes aun.")
    finally:
        db.close()


# ============================================================
# SINCRONIZACION
# ============================================================
elif page == "Sincronizacion":
    st.markdown('<p class="page-title">Sincronizacion con Obuma</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Importe datos desde el ERP Obuma a la base de datos local</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sincronizar Todo", type="primary", use_container_width=True):
                with st.spinner("Conectando con Obuma y sincronizando todos los modulos..."):
                    service = SyncService(db)
                    results = run_async(service.sync_all())
                    st.success("Sincronizacion completada")

                    for module, result in results.items():
                        if isinstance(result, dict) and "error" not in result:
                            st.markdown(f"""
                            <div class="sync-result-ok">
                                <strong>{module.replace('_', ' ').title()}</strong>: {result.get('synced', 0)} registros
                                (API: {result.get('total_api', 0)} | BD: {result.get('total_db', 0)})
                            </div>
                            """, unsafe_allow_html=True)
                        elif isinstance(result, dict) and "error" in result:
                            st.markdown(f"""
                            <div class="sync-result-error">
                                <strong>{module.replace('_', ' ').title()}</strong>: {str(result.get('error', ''))[:100]}
                            </div>
                            """, unsafe_allow_html=True)

        with col2:
            all_modules = [
                "clientes", "clientes_contactos", "clientes_direcciones",
                "proveedores", "productos", "producto_categorias", "producto_subcategorias",
                "producto_fabricantes", "producto_precios", "empleados", "remuneraciones",
                "ventas", "ventas_items", "ventas_cotizaciones", "ventas_cobros", "ventas_dte",
                "compras", "compras_oc", "compras_pagos",
                "contabilidad", "crm_leads"
            ]
            endpoint = st.selectbox("Modulo especifico", all_modules)
            if st.button("Sincronizar Modulo", use_container_width=True):
                with st.spinner(f"Sincronizando {endpoint}..."):
                    service = SyncService(db)
                    method_name = f"sync_{endpoint}"
                    method = getattr(service, method_name, None)
                    if method:
                        result = run_async(method())
                        if isinstance(result, dict) and "error" not in result:
                            st.success(f"{endpoint.title()}: {result.get('synced', 0)} registros sincronizados")
                        else:
                            st.warning(f"Resultado: {result}")
                    else:
                        st.error(f"Metodo sync_{endpoint} no encontrado")

        st.markdown("---")
        st.markdown('<p class="section-header">Historial de Sincronizacion</p>', unsafe_allow_html=True)

        logs = db.query(SyncLog).order_by(SyncLog.ejecutado_at.desc()).limit(30).all()
        if logs:
            data = [{
                "Fecha": str(l.ejecutado_at)[:16],
                "Modulo": l.endpoint,
                "Registros API": l.registros_api,
                "Registros BD": l.registros_db,
                "Estado": l.estado.upper(),
            } for l in logs]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        else:
            st.info("Sin historial de sincronizacion.")
    finally:
        db.close()


# ============================================================
# AUDITORIA
# ============================================================
elif page == "Auditoria":
    st.markdown('<p class="page-title">Auditoria de Cifras</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Comparacion de datos entre la API de Obuma y la base de datos local</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        service = SyncService(db)
        audit = service.audit_totals()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<p class="section-header">Ventas</p>', unsafe_allow_html=True)

            v = audit["ventas"]
            c1, c2 = st.columns(2)
            with c1:
                render_metric("Total BD", format_clp(v["total_db"]), "🗄️", ACCENT_BLUE)
            with c2:
                render_metric("Registros BD", str(v["registros_db"]), "📊")

            st.markdown("")
            c3, c4 = st.columns(2)
            with c3:
                render_metric("Total API (Sync)", format_clp(v["ultima_sync_api_total"]), "🌐", ACCENT_AMBER)
            with c4:
                render_metric("Registros API", str(v["ultima_sync_api_registros"]), "📡")

            discrepancia = v["discrepancia_total"]
            if discrepancia > 0:
                st.error(f"Discrepancia detectada: {format_clp(discrepancia)}")
            else:
                st.success("Sin discrepancias en ventas")

        with col2:
            st.markdown('<p class="section-header">Compras</p>', unsafe_allow_html=True)

            c = audit["compras"]
            c1, c2 = st.columns(2)
            with c1:
                render_metric("Total BD", format_clp(c["total_db"]), "🗄️", ACCENT_BLUE)
            with c2:
                render_metric("Registros BD", str(c["registros_db"]), "📊")
            st.markdown("")
            render_metric("Registros API (Sync)", str(c["ultima_sync_api_registros"]), "📡", ACCENT_AMBER)

        st.markdown("---")

        st.markdown('<p class="section-header">Resumen de Tablas</p>', unsafe_allow_html=True)
        table_counts = [
            ("Clientes", db.query(ClienteFinal).count()),
            ("Contactos", db.query(ClienteContacto).count()),
            ("Direcciones", db.query(ClienteDireccion).count()),
            ("Proveedores", db.query(Proveedor).count()),
            ("Productos", db.query(Producto).count()),
            ("Categorias", db.query(ProductoCategoria).count()),
            ("Subcategorias", db.query(ProductoSubCategoria).count()),
            ("Fabricantes", db.query(ProductoFabricante).count()),
            ("Precios", db.query(ProductoPrecio).count()),
            ("Empleados", db.query(Empleado).count()),
            ("Remuneraciones", db.query(Remuneracion).count()),
            ("Ventas", db.query(VentaHistorico).count()),
            ("Items Venta", db.query(VentaItem).count()),
            ("Cotizaciones", db.query(VentaCotizacion).count()),
            ("Cobros", db.query(VentaCobro).count()),
            ("DTE Emitidos", db.query(VentaDte).count()),
            ("Compras", db.query(CompraHistorico).count()),
            ("Ordenes Compra", db.query(CompraOC).count()),
            ("Pagos Proveedores", db.query(CompraPago).count()),
            ("DTE Recibidos", db.query(CompraDteRecibido).count()),
            ("Contabilidad", db.query(ContabilidadHistorico).count()),
            ("Gastos Menores", db.query(GastoMenor).count()),
            ("CRM Leads", db.query(CrmLead).count()),
            ("Costos Historicos", db.query(CostoHistorico).count()),
        ]
        df_tables = pd.DataFrame(table_counts, columns=["Tabla", "Registros"])
        st.dataframe(df_tables, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown('<p class="section-header">Log de Auditorias</p>', unsafe_allow_html=True)

        logs = db.query(SyncLog).order_by(SyncLog.ejecutado_at.desc()).limit(15).all()
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
