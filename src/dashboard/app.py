import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from sqlalchemy import func, extract, distinct
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
    CrmLead, ProductoCategoria,
    ProductoSubCategoria, ProductoFabricante, ProductoPrecio, CostoHistorico
)
from src.etl.sync_service import SyncService
from src.etl.obuma_client import ObumaClient
from src.reports.excel_generator import generate_vendedor_report, generate_all_vendedor_reports

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
    .metric-delta {{
        font-size: 0.8rem;
        font-weight: 600;
        margin-top: 0.3rem;
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


def render_metric(label, value, icon="", color=TEXT_PRIMARY, delta=None, delta_color=None):
    delta_html = ""
    if delta is not None:
        dc = delta_color or (ACCENT_GREEN if str(delta).startswith("+") or (isinstance(delta, (int, float)) and delta > 0) else ACCENT_RED)
        delta_html = f'<p class="metric-delta" style="color:{dc};">{delta}</p>'
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">{icon}</div>
        <p class="metric-label">{label}</p>
        <p class="metric-value" style="color:{color};">{value}</p>
        {delta_html}
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


MONTH_LABELS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
CHART_COLORS = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_AMBER, ACCENT_RED, ACCENT_PURPLE,
                "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1"]


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
    st.markdown('<p class="page-subtitle">Vista consolidada del rendimiento empresarial</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        st.markdown('<p class="section-header">Filtros Globales</p>', unsafe_allow_html=True)
        fc1, fc2, fc3 = st.columns([2, 2, 3])
        with fc1:
            dash_date_from = st.date_input("Desde", value=date.today() - timedelta(days=365), key="dash_from")
        with fc2:
            dash_date_to = st.date_input("Hasta", value=date.today(), key="dash_to")
        with fc3:
            empleados_list = db.query(Empleado).filter(Empleado.activo == True).order_by(Empleado.nombre).all()
            vendedor_names = {e.obuma_id: e.nombre for e in empleados_list}
            vendedor_options_all = ["Todos"] + [f"{e.nombre} ({e.cargo or 'Sin cargo'})" for e in empleados_list]
            vendedor_sel_dash = st.multiselect("Vendedores", vendedor_options_all, default=["Todos"], key="dash_vend")

        selected_vendedor_ids = []
        if "Todos" not in vendedor_sel_dash and vendedor_sel_dash:
            for sel in vendedor_sel_dash:
                for e in empleados_list:
                    if f"{e.nombre} ({e.cargo or 'Sin cargo'})" == sel:
                        selected_vendedor_ids.append(e.obuma_id)

        def apply_dash_filters(query, model=VentaHistorico):
            if dash_date_from:
                query = query.filter(func.date(model.fecha) >= dash_date_from)
            if dash_date_to:
                query = query.filter(func.date(model.fecha) <= dash_date_to)
            if selected_vendedor_ids and model == VentaHistorico:
                query = query.filter(model.vendedor_id.in_(selected_vendedor_ids))
            return query

        st.markdown("---")

        base_ventas_q = apply_dash_filters(db.query(VentaHistorico))
        total_ventas = base_ventas_q.with_entities(func.sum(VentaHistorico.total)).scalar() or 0
        total_margen = base_ventas_q.with_entities(func.sum(VentaHistorico.margen_neto)).scalar() or 0
        n_ventas = base_ventas_q.count()
        ventas_anuladas = apply_dash_filters(db.query(VentaHistorico).filter(VentaHistorico.anulada == True)).count()
        total_pagado = base_ventas_q.with_entities(func.sum(VentaHistorico.total_pagado)).scalar() or 0
        total_por_pagar = base_ventas_q.with_entities(func.sum(VentaHistorico.total_por_pagar)).scalar() or 0

        compras_q = db.query(func.sum(CompraHistorico.total))
        if dash_date_from:
            compras_q = compras_q.filter(func.date(CompraHistorico.fecha) >= dash_date_from)
        if dash_date_to:
            compras_q = compras_q.filter(func.date(CompraHistorico.fecha) <= dash_date_to)
        total_compras = compras_q.scalar() or 0

        n_clientes = db.query(ClienteFinal).filter(ClienteFinal.activo == True).count()
        n_productos = db.query(Producto).filter(Producto.activo == True).count()
        margen_pct = (total_margen / total_ventas * 100) if total_ventas else 0

        total_cobros_count = base_ventas_q.with_entities(func.count(VentaHistorico.id)).filter(VentaHistorico.total_pagado > 0).scalar() or 0

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
            render_metric("Clientes Activos", str(n_clientes), "👥")
        with c6:
            render_metric("Documentos", str(n_ventas), "📄")
        with c7:
            render_metric("Productos", str(n_productos), "📦")
        with c8:
            render_metric("Cobros", str(total_cobros_count), "🧾")

        st.markdown("---")

        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown('<p class="section-header">Ventas Mensuales</p>', unsafe_allow_html=True)
            monthly_sales = apply_dash_filters(
                db.query(
                    extract('year', VentaHistorico.fecha).label("anio"),
                    extract('month', VentaHistorico.fecha).label("mes"),
                    func.sum(VentaHistorico.total).label("total")
                ).filter(VentaHistorico.fecha.isnot(None))
            ).group_by("anio", "mes").order_by("anio", "mes").all()

            if monthly_sales:
                df_ms = pd.DataFrame([{
                    "Periodo": f"{int(r.anio)}-{int(r.mes):02d}",
                    "Mes": MONTH_LABELS[int(r.mes) - 1] + f" {int(r.anio)}",
                    "Total": r.total or 0
                } for r in monthly_sales])
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_ms["Mes"], y=df_ms["Total"], name="Ventas",
                                     marker_color=ACCENT_BLUE, opacity=0.85))
                if len(df_ms) > 2:
                    fig.add_trace(go.Scatter(x=df_ms["Mes"], y=df_ms["Total"].rolling(3, min_periods=1).mean(),
                                             mode="lines", name="Tendencia",
                                             line=dict(color=ACCENT_AMBER, width=2.5, dash="dot")))
                fig.update_layout(**chart_layout())
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sin datos de ventas para el rango seleccionado.")

        with col_chart2:
            st.markdown('<p class="section-header">Top 10 Vendedores</p>', unsafe_allow_html=True)
            top_vend = apply_dash_filters(
                db.query(
                    VentaHistorico.vendedor_id,
                    func.sum(VentaHistorico.total).label("total")
                ).filter(VentaHistorico.vendedor_id.isnot(None), VentaHistorico.fecha.isnot(None))
            ).group_by(VentaHistorico.vendedor_id).order_by(func.sum(VentaHistorico.total).desc()).limit(10).all()

            if top_vend:
                df_tv = pd.DataFrame([{
                    "Vendedor": vendedor_names.get(v.vendedor_id, v.vendedor_id or "Desconocido"),
                    "Total": v.total or 0
                } for v in top_vend])
                fig2 = go.Figure(go.Bar(
                    x=df_tv["Total"], y=df_tv["Vendedor"], orientation='h',
                    marker_color=ACCENT_GREEN, text=df_tv["Total"].apply(lambda x: format_clp(x)),
                    textposition="auto"
                ))
                fig2.update_layout(**chart_layout(height=380))
                fig2.update_layout(yaxis=dict(autorange="reversed", showgrid=False))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sin datos de vendedores.")

        st.markdown("")
        col_chart3, col_chart4 = st.columns(2)

        with col_chart3:
            st.markdown('<p class="section-header">Segmentacion ABC de Clientes</p>', unsafe_allow_html=True)
            client_sales = apply_dash_filters(
                db.query(
                    VentaHistorico.cliente_id,
                    func.sum(VentaHistorico.total).label("total")
                ).filter(VentaHistorico.cliente_id.isnot(None), VentaHistorico.fecha.isnot(None))
            ).group_by(VentaHistorico.cliente_id).order_by(func.sum(VentaHistorico.total).desc()).all()

            if client_sales:
                grand_total_abc = sum(c.total or 0 for c in client_sales)
                segments = {"A": 0, "B": 0, "C": 0, "D": 0}
                cumulative = 0
                for c in client_sales:
                    val = c.total or 0
                    cumulative += val
                    pct = cumulative / grand_total_abc if grand_total_abc else 0
                    if pct <= 0.80:
                        segments["A"] += val
                    elif pct <= 0.95:
                        segments["B"] += val
                    elif pct <= 0.99:
                        segments["C"] += val
                    else:
                        segments["D"] += val

                df_abc = pd.DataFrame([{"Segmento": k, "Total": v} for k, v in segments.items() if v > 0])
                abc_colors = {"A": ACCENT_GREEN, "B": ACCENT_BLUE, "C": ACCENT_AMBER, "D": ACCENT_RED}
                fig3 = go.Figure(go.Pie(
                    labels=df_abc["Segmento"], values=df_abc["Total"],
                    hole=0.45, marker=dict(colors=[abc_colors.get(s, ACCENT_BLUE) for s in df_abc["Segmento"]]),
                    textinfo="label+percent", textfont=dict(color="white")
                ))
                fig3.update_layout(**chart_layout())
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("Sin datos de clientes para segmentacion.")

        with col_chart4:
            st.markdown('<p class="section-header">Rentabilidad por Vendedor</p>', unsafe_allow_html=True)
            rent_vend = apply_dash_filters(
                db.query(
                    VentaHistorico.vendedor_id,
                    func.sum(VentaHistorico.margen_neto).label("margen")
                ).filter(VentaHistorico.vendedor_id.isnot(None), VentaHistorico.fecha.isnot(None))
            ).group_by(VentaHistorico.vendedor_id).order_by(func.sum(VentaHistorico.margen_neto).desc()).limit(10).all()

            if rent_vend:
                df_rv = pd.DataFrame([{
                    "Vendedor": vendedor_names.get(v.vendedor_id, v.vendedor_id or "Desconocido"),
                    "Margen": v.margen or 0
                } for v in rent_vend])
                colors_rv = [ACCENT_GREEN if m >= 0 else ACCENT_RED for m in df_rv["Margen"]]
                fig4 = go.Figure(go.Bar(
                    x=df_rv["Vendedor"], y=df_rv["Margen"],
                    marker_color=colors_rv,
                    text=df_rv["Margen"].apply(lambda x: format_clp(x)),
                    textposition="auto"
                ))
                fig4.update_layout(**chart_layout())
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("Sin datos de rentabilidad.")

        st.markdown("")
        col_chart5, col_chart6 = st.columns(2)

        with col_chart5:
            st.markdown('<p class="section-header">Estado de Cobranza</p>', unsafe_allow_html=True)
            if total_pagado or total_por_pagar:
                fig5 = go.Figure(go.Pie(
                    labels=["Pagado", "Por Pagar"],
                    values=[total_pagado, total_por_pagar],
                    hole=0.5,
                    marker=dict(colors=[ACCENT_GREEN, ACCENT_RED]),
                    textinfo="label+percent+value",
                    textfont=dict(color="white"),
                    texttemplate="%{label}<br>%{percent}<br>$%{value:,.0f}"
                ))
                fig5.update_layout(**chart_layout())
                st.plotly_chart(fig5, use_container_width=True)
            else:
                st.info("Sin datos de cobranza.")

        with col_chart6:
            st.markdown('<p class="section-header">Top 15 Productos Vendidos</p>', unsafe_allow_html=True)
            top_products_q = db.query(
                VentaItem.producto_nombre,
                func.sum(VentaItem.cantidad).label("cantidad"),
                func.sum(VentaItem.total).label("total")
            ).join(VentaHistorico, VentaHistorico.obuma_id == VentaItem.venta_id_obuma
            ).filter(VentaItem.producto_nombre.isnot(None))
            top_products_q = apply_dash_filters(top_products_q, VentaHistorico)
            top_products = top_products_q.group_by(VentaItem.producto_nombre
            ).order_by(func.sum(VentaItem.total).desc()).limit(15).all()

            if top_products:
                df_tp = pd.DataFrame([{
                    "Producto": (p.producto_nombre or "")[:30],
                    "Total": p.total or 0
                } for p in top_products])
                fig6 = go.Figure(go.Bar(
                    x=df_tp["Total"], y=df_tp["Producto"], orientation='h',
                    marker_color=ACCENT_PURPLE,
                    text=df_tp["Total"].apply(lambda x: format_clp(x)),
                    textposition="auto"
                ))
                fig6.update_layout(**chart_layout(height=420))
                fig6.update_layout(yaxis=dict(autorange="reversed", showgrid=False))
                st.plotly_chart(fig6, use_container_width=True)
            else:
                st.info("Sin datos de productos vendidos.")

        st.markdown("")
        col_chart7, col_chart8 = st.columns(2)

        with col_chart7:
            st.markdown('<p class="section-header">Evolucion Ventas vs Compras</p>', unsafe_allow_html=True)
            monthly_ventas = apply_dash_filters(
                db.query(
                    extract('year', VentaHistorico.fecha).label("anio"),
                    extract('month', VentaHistorico.fecha).label("mes"),
                    func.sum(VentaHistorico.total).label("total")
                ).filter(VentaHistorico.fecha.isnot(None))
            ).group_by("anio", "mes").order_by("anio", "mes").all()

            compras_q_monthly = db.query(
                extract('year', CompraHistorico.fecha).label("anio"),
                extract('month', CompraHistorico.fecha).label("mes"),
                func.sum(CompraHistorico.total).label("total")
            ).filter(CompraHistorico.fecha.isnot(None))
            if dash_date_from:
                compras_q_monthly = compras_q_monthly.filter(func.date(CompraHistorico.fecha) >= dash_date_from)
            if dash_date_to:
                compras_q_monthly = compras_q_monthly.filter(func.date(CompraHistorico.fecha) <= dash_date_to)
            monthly_compras = compras_q_monthly.group_by("anio", "mes").order_by("anio", "mes").all()

            if monthly_ventas or monthly_compras:
                all_periods = set()
                ventas_map = {}
                compras_map = {}
                for r in monthly_ventas:
                    key = f"{int(r.anio)}-{int(r.mes):02d}"
                    all_periods.add(key)
                    ventas_map[key] = r.total or 0
                for r in monthly_compras:
                    key = f"{int(r.anio)}-{int(r.mes):02d}"
                    all_periods.add(key)
                    compras_map[key] = r.total or 0

                sorted_periods = sorted(all_periods)
                labels = [MONTH_LABELS[int(p.split("-")[1]) - 1] + f" {p.split('-')[0]}" for p in sorted_periods]

                fig7 = go.Figure()
                fig7.add_trace(go.Scatter(
                    x=labels, y=[ventas_map.get(p, 0) for p in sorted_periods],
                    mode="lines+markers", name="Ventas",
                    line=dict(color=ACCENT_GREEN, width=2.5), marker=dict(size=6)
                ))
                fig7.add_trace(go.Scatter(
                    x=labels, y=[compras_map.get(p, 0) for p in sorted_periods],
                    mode="lines+markers", name="Compras",
                    line=dict(color=ACCENT_RED, width=2.5), marker=dict(size=6)
                ))
                fig7.update_layout(**chart_layout())
                st.plotly_chart(fig7, use_container_width=True)
            else:
                st.info("Sin datos para comparacion ventas vs compras.")

        with col_chart8:
            st.markdown('<p class="section-header">Distribucion por Tipo Documento</p>', unsafe_allow_html=True)
            doc_types = apply_dash_filters(
                db.query(
                    VentaHistorico.tipo_documento,
                    func.count(VentaHistorico.id).label("cantidad"),
                    func.sum(VentaHistorico.total).label("total")
                ).filter(VentaHistorico.tipo_documento.isnot(None), VentaHistorico.fecha.isnot(None))
            ).group_by(VentaHistorico.tipo_documento).order_by(func.sum(VentaHistorico.total).desc()).all()

            if doc_types:
                df_dt = pd.DataFrame([{
                    "Tipo": d.tipo_documento or "Otro",
                    "Total": d.total or 0,
                    "Cantidad": d.cantidad or 0
                } for d in doc_types])
                fig8 = go.Figure(go.Pie(
                    labels=df_dt["Tipo"], values=df_dt["Total"],
                    hole=0.4, marker=dict(colors=CHART_COLORS[:len(df_dt)]),
                    textinfo="label+percent", textfont=dict(color="white")
                ))
                fig8.update_layout(**chart_layout())
                st.plotly_chart(fig8, use_container_width=True)
            else:
                st.info("Sin datos de tipos de documento.")

        st.markdown("---")
        col_tbl1, col_tbl2 = st.columns(2)

        with col_tbl1:
            st.markdown('<p class="section-header">Ultimas Transacciones</p>', unsafe_allow_html=True)
            recent_q = apply_dash_filters(db.query(VentaHistorico).filter(VentaHistorico.fecha.isnot(None)))
            recent_ventas = recent_q.order_by(VentaHistorico.fecha.desc()).limit(15).all()
            if recent_ventas:
                data = []
                for v in recent_ventas:
                    vend_name = vendedor_names.get(v.vendedor_id, "-") if v.vendedor_id else "-"
                    data.append({
                        "Fecha": str(v.fecha)[:10] if v.fecha else "-",
                        "Tipo": v.tipo_documento or "-",
                        "Folio": v.folio or "-",
                        "Total": format_clp(v.total),
                        "Vendedor": vend_name,
                        "Estado": "Anulada" if v.anulada else "Vigente",
                    })
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("Sin transacciones recientes.")

        with col_tbl2:
            st.markdown('<p class="section-header">Top Clientes por Ingresos</p>', unsafe_allow_html=True)
            top_clientes_q = db.query(
                ClienteFinal.nombre,
                ClienteFinal.rut,
                func.sum(VentaHistorico.total).label("total"),
                func.sum(VentaHistorico.margen_neto).label("margen"),
                func.count(VentaHistorico.id).label("transacciones")
            ).join(VentaHistorico, VentaHistorico.cliente_id == ClienteFinal.id
            ).filter(VentaHistorico.fecha.isnot(None))
            top_clientes_q = apply_dash_filters(top_clientes_q, VentaHistorico)
            top_clientes = top_clientes_q.group_by(
                ClienteFinal.nombre, ClienteFinal.rut
            ).order_by(func.sum(VentaHistorico.total).desc()).limit(15).all()

            if top_clientes:
                df_top = pd.DataFrame([{
                    "Cliente": c.nombre, "RUT": c.rut or "-",
                    "Total": format_clp(c.total), "Margen": format_clp(c.margen),
                    "Docs": c.transacciones
                } for c in top_clientes])
                st.dataframe(df_top, use_container_width=True, hide_index=True, height=400)
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
            empleados_v = db.query(Empleado).filter(Empleado.activo == True).order_by(Empleado.nombre).all()
            vend_map_v = {e.obuma_id: e.nombre for e in empleados_v}

            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
            with col1:
                fecha_desde = st.date_input("Desde", value=date.today() - timedelta(days=365), key="vd1")
            with col2:
                fecha_hasta = st.date_input("Hasta", value=date.today(), key="vd2")
            with col3:
                filtro_estado = st.selectbox("Estado", ["Todos", "Vigentes", "Anuladas"])
            with col4:
                vend_options_v = ["Todos"] + [e.nombre for e in empleados_v]
                filtro_vendedor = st.selectbox("Vendedor", vend_options_v, key="vd_vend")

            query = db.query(VentaHistorico)
            if fecha_desde:
                query = query.filter(func.date(VentaHistorico.fecha) >= fecha_desde)
            if fecha_hasta:
                query = query.filter(func.date(VentaHistorico.fecha) <= fecha_hasta)
            if filtro_estado == "Vigentes":
                query = query.filter(VentaHistorico.anulada == False)
            elif filtro_estado == "Anuladas":
                query = query.filter(VentaHistorico.anulada == True)
            if filtro_vendedor != "Todos":
                sel_emp = next((e for e in empleados_v if e.nombre == filtro_vendedor), None)
                if sel_emp:
                    query = query.filter(VentaHistorico.vendedor_id == sel_emp.obuma_id)

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

                col_vc1, col_vc2 = st.columns(2)
                with col_vc1:
                    st.markdown('<p class="section-header">Ventas Mensuales</p>', unsafe_allow_html=True)
                    df_v_all = pd.DataFrame([{
                        "fecha": v.fecha,
                        "total": v.total or 0,
                        "mes": v.fecha.month if v.fecha else None,
                        "anio": v.fecha.year if v.fecha else None
                    } for v in ventas if v.fecha])
                    if not df_v_all.empty:
                        monthly = df_v_all.groupby(["anio", "mes"])["total"].sum().reset_index()
                        monthly["label"] = monthly.apply(lambda r: f"{MONTH_LABELS[int(r['mes'])-1]} {int(r['anio'])}", axis=1)
                        fig_vm = go.Figure(go.Bar(x=monthly["label"], y=monthly["total"],
                                                   marker_color=ACCENT_BLUE))
                        fig_vm.update_layout(**chart_layout())
                        st.plotly_chart(fig_vm, use_container_width=True)

                with col_vc2:
                    st.markdown('<p class="section-header">Tipo de Documento</p>', unsafe_allow_html=True)
                    df_tipos = pd.DataFrame([{"tipo": v.tipo_documento or "Otro", "total": v.total or 0} for v in ventas])
                    if not df_tipos.empty:
                        tipos_agg = df_tipos.groupby("tipo")["total"].sum().reset_index()
                        fig_tp = go.Figure(go.Pie(
                            labels=tipos_agg["tipo"], values=tipos_agg["total"],
                            hole=0.4, marker=dict(colors=CHART_COLORS[:len(tipos_agg)]),
                            textinfo="label+percent", textfont=dict(color="white")
                        ))
                        fig_tp.update_layout(**chart_layout())
                        st.plotly_chart(fig_tp, use_container_width=True)

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
                        "Vendedor": vend_map_v.get(v.vendedor_id, "-") if v.vendedor_id else "-",
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
    st.markdown('<p class="page-subtitle">Clientes, contactos, direcciones y analisis de actividad</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        tab_clientes, tab_contactos, tab_direcciones = st.tabs([
            "Clientes", "Contactos", "Direcciones"
        ])

        with tab_clientes:
            fc1, fc2 = st.columns([3, 1])
            with fc1:
                search_term = st.text_input("Buscar por nombre o RUT", "", key="cli_search")
            with fc2:
                show_inactive = st.checkbox("Mostrar inactivos", value=False, key="cli_inactive")

            clientes_q = db.query(ClienteFinal)
            if not show_inactive:
                clientes_q = clientes_q.filter(ClienteFinal.activo == True)
            if search_term:
                clientes_q = clientes_q.filter(
                    (ClienteFinal.nombre.ilike(f"%{search_term}%")) |
                    (ClienteFinal.rut.ilike(f"%{search_term}%"))
                )
            clientes = clientes_q.order_by(ClienteFinal.nombre).all()

            if clientes:
                render_metric("Clientes Encontrados", str(len(clientes)), "👥", ACCENT_BLUE)
                st.markdown("")

                col_cc1, col_cc2 = st.columns(2)

                with col_cc1:
                    st.markdown('<p class="section-header">Top Clientes por Facturacion</p>', unsafe_allow_html=True)
                    top_cl = db.query(
                        ClienteFinal.nombre,
                        func.sum(VentaHistorico.total).label("total")
                    ).join(VentaHistorico, VentaHistorico.cliente_id == ClienteFinal.id
                    ).group_by(ClienteFinal.nombre
                    ).order_by(func.sum(VentaHistorico.total).desc()).limit(10).all()

                    if top_cl:
                        df_tcl = pd.DataFrame([{"Cliente": c.nombre, "Total": c.total or 0} for c in top_cl])
                        fig_cl = go.Figure(go.Bar(
                            x=df_tcl["Total"], y=df_tcl["Cliente"], orientation='h',
                            marker_color=ACCENT_BLUE,
                            text=df_tcl["Total"].apply(lambda x: format_clp(x)),
                            textposition="auto"
                        ))
                        fig_cl.update_layout(**chart_layout(height=350))
                        fig_cl.update_layout(yaxis=dict(autorange="reversed", showgrid=False))
                        st.plotly_chart(fig_cl, use_container_width=True)

                with col_cc2:
                    st.markdown('<p class="section-header">Actividad de Clientes (Meses con Compras)</p>', unsafe_allow_html=True)
                    activity = db.query(
                        ClienteFinal.nombre,
                        func.count(distinct(extract('month', VentaHistorico.fecha))).label("meses")
                    ).join(VentaHistorico, VentaHistorico.cliente_id == ClienteFinal.id
                    ).filter(VentaHistorico.fecha.isnot(None)
                    ).group_by(ClienteFinal.nombre
                    ).order_by(func.count(distinct(extract('month', VentaHistorico.fecha))).desc()).limit(10).all()

                    if activity:
                        df_act = pd.DataFrame([{"Cliente": a.nombre, "Meses": a.meses or 0} for a in activity])
                        fig_act = go.Figure(go.Bar(
                            x=df_act["Meses"], y=df_act["Cliente"], orientation='h',
                            marker_color=ACCENT_GREEN,
                            text=df_act["Meses"], textposition="auto"
                        ))
                        fig_act.update_layout(**chart_layout(height=350))
                        fig_act.update_layout(yaxis=dict(autorange="reversed", showgrid=False),
                                              xaxis=dict(title="Meses con compras"))
                        st.plotly_chart(fig_act, use_container_width=True)

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
                        "Activo": "Si" if c.activo else "No",
                    })
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=400)
            else:
                st.info("No hay clientes que coincidan con la busqueda.")

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
        tab_compras, tab_oc, tab_pagos = st.tabs([
            "Compras", "Ordenes de Compra", "Pagos"
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
    st.markdown('<p class="page-title">Reportes Excel - Evolucion por Vendedor</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Reportes de ventas por vendedor con segmentacion ABC y nivel de riesgo</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        vendedores = db.query(Empleado).order_by(Empleado.nombre).all()

        st.markdown('<p class="section-header">Generar Reportes por Vendedor</p>', unsafe_allow_html=True)

        tab_individual, tab_todos = st.tabs(["Reporte Individual", "Todos los Vendedores"])

        with tab_individual:
            vendedor_options = {f"{v.nombre} ({v.cargo or 'Sin cargo'})": v.obuma_id for v in vendedores}
            vendedor_sel = st.selectbox("Seleccionar Vendedor", list(vendedor_options.keys()))

            st.markdown('<p class="section-header">Rango de Fechas</p>', unsafe_allow_html=True)
            range_mode = st.radio("Modo", ["Por Ano", "Rango Personalizado"], horizontal=True, key="rng_ind")

            if range_mode == "Por Ano":
                col1, col2 = st.columns([2, 1])
                with col1:
                    year_report = st.number_input("Ano", value=date.today().year, min_value=2020, max_value=2030, key="yr_ind")
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("Generar", type="primary", use_container_width=True, key="gen_individual"):
                        vendedor_obuma_id = vendedor_options[vendedor_sel]
                        with st.spinner(f"Generando reporte para {vendedor_sel}..."):
                            try:
                                year_val = int(year_report)
                                date_from_r = date(year_val, 1, 1)
                                date_to_r = date(year_val, 12, 31)
                                filepath = generate_vendedor_report(db, vendedor_obuma_id, date_from_r, date_to_r)
                                if filepath:
                                    st.success(f"Reporte generado: {os.path.basename(filepath)}")
                                    with open(filepath, "rb") as f:
                                        st.download_button(
                                            label="Descargar Reporte",
                                            data=f.read(),
                                            file_name=os.path.basename(filepath),
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            use_container_width=True,
                                            key="dl_individual"
                                        )
                                else:
                                    st.warning("Este vendedor no tiene ventas registradas en el periodo.")
                            except Exception as e:
                                st.error(f"Error generando reporte: {str(e)}")
            else:
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    rpt_date_from = st.date_input("Desde", value=date(date.today().year, 1, 1), key="rpt_from_ind")
                with col2:
                    rpt_date_to = st.date_input("Hasta", value=date.today(), key="rpt_to_ind")
                with col3:
                    st.write("")
                    st.write("")
                    if st.button("Generar", type="primary", use_container_width=True, key="gen_individual_custom"):
                        vendedor_obuma_id = vendedor_options[vendedor_sel]
                        with st.spinner(f"Generando reporte para {vendedor_sel}..."):
                            try:
                                filepath = generate_vendedor_report(db, vendedor_obuma_id, rpt_date_from, rpt_date_to)
                                if filepath:
                                    st.success(f"Reporte generado: {os.path.basename(filepath)}")
                                    with open(filepath, "rb") as f:
                                        st.download_button(
                                            label="Descargar Reporte",
                                            data=f.read(),
                                            file_name=os.path.basename(filepath),
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            use_container_width=True,
                                            key="dl_individual_custom"
                                        )
                                else:
                                    st.warning("Este vendedor no tiene ventas registradas en el periodo.")
                            except Exception as e:
                                st.error(f"Error generando reporte: {str(e)}")

        with tab_todos:
            st.markdown('<p class="section-header">Rango de Fechas</p>', unsafe_allow_html=True)
            range_mode_all = st.radio("Modo", ["Por Ano", "Rango Personalizado"], horizontal=True, key="rng_all")

            if range_mode_all == "Por Ano":
                col1, col2 = st.columns([3, 1])
                with col1:
                    year_all = st.number_input("Ano", value=date.today().year, min_value=2020, max_value=2030, key="year_all")
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("Generar Todos", type="primary", use_container_width=True, key="gen_all"):
                        with st.spinner("Generando reportes para todos los vendedores..."):
                            try:
                                year_val_all = int(year_all)
                                date_from_all = date(year_val_all, 1, 1)
                                date_to_all = date(year_val_all, 12, 31)
                                filepaths = generate_all_vendedor_reports(db, date_from_all, date_to_all)
                                st.success(f"Se generaron {len(filepaths)} reportes")
                                for fp in filepaths:
                                    with open(fp, "rb") as f:
                                        st.download_button(
                                            label=f"Descargar {os.path.basename(fp)}",
                                            data=f.read(),
                                            file_name=os.path.basename(fp),
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            key=f"dl_all_{os.path.basename(fp)}"
                                        )
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
            else:
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    rpt_date_from_all = st.date_input("Desde", value=date(date.today().year, 1, 1), key="rpt_from_all")
                with col2:
                    rpt_date_to_all = st.date_input("Hasta", value=date.today(), key="rpt_to_all")
                with col3:
                    st.write("")
                    st.write("")
                    if st.button("Generar Todos", type="primary", use_container_width=True, key="gen_all_custom"):
                        with st.spinner("Generando reportes para todos los vendedores..."):
                            try:
                                filepaths = generate_all_vendedor_reports(db, rpt_date_from_all, rpt_date_to_all)
                                st.success(f"Se generaron {len(filepaths)} reportes")
                                for fp in filepaths:
                                    with open(fp, "rb") as f:
                                        st.download_button(
                                            label=f"Descargar {os.path.basename(fp)}",
                                            data=f.read(),
                                            file_name=os.path.basename(fp),
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            key=f"dl_allc_{os.path.basename(fp)}"
                                        )
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

        st.markdown("---")
        st.markdown('<p class="section-header">Reportes Generados</p>', unsafe_allow_html=True)

        reportes = db.query(ReporteGenerado).order_by(ReporteGenerado.generado_at.desc()).limit(50).all()
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
            st.info("No se han generado reportes aun. Use los botones de arriba para generar.")
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
    st.markdown('<p class="page-title">Auditoria de Datos</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Diagnostico completo de datos disponibles en Obuma y base de datos local</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        tab_diag, tab_tables, tab_logs = st.tabs(["Diagnostico API en Vivo", "Resumen de Tablas", "Log de Sincronizacion"])

        with tab_diag:
            st.markdown('<p class="section-header">Consultar API Obuma en Tiempo Real</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="color:{TEXT_SECONDARY};font-size:0.9rem;">Este diagnostico consulta directamente la API de Obuma para verificar cuantos registros existen en cada endpoint. Permite identificar que datos estan disponibles para importar.</p>', unsafe_allow_html=True)

            if st.button("Ejecutar Diagnostico Completo", type="primary", use_container_width=True):
                with st.spinner("Consultando todos los endpoints de la API Obuma..."):
                    client = ObumaClient()
                    endpoints_to_test = [
                        ("Clientes", "clientes.list.json"),
                        ("Contactos Clientes", "clientesContactos.listAll.json"),
                        ("Direcciones Clientes", "clientesDirecciones.listAll.json"),
                        ("Proveedores", "proveedores.list.json"),
                        ("Productos", "productos.list.json"),
                        ("Categorias Productos", "productosCategorias.list.json"),
                        ("Subcategorias Productos", "productosSubCategorias.list.json"),
                        ("Fabricantes Productos", "productosFabricantes.list.json"),
                        ("Precios Productos", "productosConsultaPrecios.list.json"),
                        ("Empleados", "empleados.list.json"),
                        ("Remuneraciones", "remuneraciones.list.json"),
                        ("Ventas", "ventas.list.json"),
                        ("Items de Venta", "ventas.listItems.json"),
                        ("Cotizaciones", "ventasCotizaciones.list.json"),
                        ("Cobros", "ventasCobros.list.json"),
                        ("DTE Emitidos", "ventas.listDte.json"),
                        ("Compras", "compras.list.json"),
                        ("Ordenes de Compra", "comprasOc.list.json"),
                        ("Pagos Proveedores", "comprasPagos.list.json"),
                        ("Contabilidad", "contabilidad.listDiario.json"),
                        ("CRM Leads", "crm.list.json"),
                    ]

                    diag_results = []
                    for name, endpoint in endpoints_to_test:
                        try:
                            result = run_async(client.test_endpoint(endpoint))
                            if "error" in result:
                                status_code = result.get("status_code", "?")
                                diag_results.append({
                                    "Endpoint": name,
                                    "API Obuma": f"Error ({status_code})",
                                    "Estado": "NO DISPONIBLE",
                                    "Detalle": str(result.get("error", ""))[:80]
                                })
                            else:
                                total = result.get("data-total-items", 0)
                                data_list = result.get("data") or []
                                actual = len(data_list) if isinstance(data_list, list) else 0
                                estado = "CON DATOS" if total and int(total) > 0 else "SIN DATOS"
                                diag_results.append({
                                    "Endpoint": name,
                                    "API Obuma": f"{total} registros",
                                    "Estado": estado,
                                    "Detalle": f"{actual} en ultima pagina"
                                })
                        except Exception as e:
                            diag_results.append({
                                "Endpoint": name,
                                "API Obuma": "Error",
                                "Estado": "ERROR",
                                "Detalle": str(e)[:80]
                            })

                    df_diag = pd.DataFrame(diag_results)

                    con_datos = sum(1 for r in diag_results if r["Estado"] == "CON DATOS")
                    sin_datos = sum(1 for r in diag_results if r["Estado"] == "SIN DATOS")
                    errores = sum(1 for r in diag_results if r["Estado"] in ("ERROR", "NO DISPONIBLE"))

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        render_metric("Con Datos", str(con_datos), "✅", ACCENT_GREEN)
                    with c2:
                        render_metric("Sin Datos", str(sin_datos), "⚠️", ACCENT_AMBER)
                    with c3:
                        render_metric("No Disponible", str(errores), "❌", ACCENT_RED)

                    st.markdown("")

                    def color_estado(val):
                        if val == "CON DATOS":
                            return f"background-color: rgba(16,185,129,0.15); color: #34d399;"
                        elif val == "SIN DATOS":
                            return f"background-color: rgba(245,158,11,0.15); color: #fbbf24;"
                        else:
                            return f"background-color: rgba(239,68,68,0.15); color: #f87171;"

                    styled_df = df_diag.style.map(color_estado, subset=["Estado"])
                    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)

                    if sin_datos > 10:
                        st.warning(f"Su cuenta Obuma tiene datos solo en {con_datos} de {len(diag_results)} endpoints. Los endpoints sin datos ({sin_datos}) no tienen registros cargados en su ERP Obuma. Para que aparezcan aqui, primero debe cargar esos datos en Obuma (productos, compras, contabilidad, etc).")

        with tab_tables:
            st.markdown('<p class="section-header">Registros en Base de Datos Local</p>', unsafe_allow_html=True)
            table_counts = [
                ("Clientes", db.query(ClienteFinal).count(), "clientes.list.json"),
                ("Contactos", db.query(ClienteContacto).count(), "clientesContactos.listAll.json"),
                ("Direcciones", db.query(ClienteDireccion).count(), "clientesDirecciones.listAll.json"),
                ("Proveedores", db.query(Proveedor).count(), "proveedores.list.json"),
                ("Productos", db.query(Producto).count(), "productos.list.json"),
                ("Categorias", db.query(ProductoCategoria).count(), "productosCategorias.list.json"),
                ("Subcategorias", db.query(ProductoSubCategoria).count(), "productosSubCategorias.list.json"),
                ("Fabricantes", db.query(ProductoFabricante).count(), "productosFabricantes.list.json"),
                ("Precios", db.query(ProductoPrecio).count(), "productosConsultaPrecios.list.json"),
                ("Empleados", db.query(Empleado).count(), "empleados.list.json"),
                ("Remuneraciones", db.query(Remuneracion).count(), "remuneraciones.list.json"),
                ("Ventas", db.query(VentaHistorico).count(), "ventas.list.json"),
                ("Items Venta", db.query(VentaItem).count(), "ventas.listItems.json"),
                ("Cotizaciones", db.query(VentaCotizacion).count(), "ventasCotizaciones.list.json"),
                ("Cobros", db.query(VentaCobro).count(), "ventasCobros.list.json"),
                ("DTE Emitidos", db.query(VentaDte).count(), "ventas.listDte.json"),
                ("Compras", db.query(CompraHistorico).count(), "compras.list.json"),
                ("Ordenes Compra", db.query(CompraOC).count(), "comprasOc.list.json"),
                ("Pagos Proveedores", db.query(CompraPago).count(), "comprasPagos.list.json"),
                ("Contabilidad", db.query(ContabilidadHistorico).count(), "contabilidad.listDiario.json"),
                ("CRM Leads", db.query(CrmLead).count(), "crm.list.json"),
                ("Costos Historicos", db.query(CostoHistorico).count(), "-"),
            ]

            total_registros = sum(t[1] for t in table_counts)
            tablas_con_datos = sum(1 for t in table_counts if t[1] > 0)

            c1, c2 = st.columns(2)
            with c1:
                render_metric("Total Registros BD", str(total_registros), "🗄️", ACCENT_BLUE)
            with c2:
                render_metric("Tablas con Datos", f"{tablas_con_datos}/{len(table_counts)}", "📊", ACCENT_GREEN)

            st.markdown("")
            df_tables = pd.DataFrame(table_counts, columns=["Tabla", "Registros", "Endpoint API"])

            def color_registros(val):
                if isinstance(val, (int, float)) and val > 0:
                    return "color: #34d399; font-weight: bold;"
                elif isinstance(val, (int, float)):
                    return "color: #64748b;"
                return ""

            styled = df_tables.style.map(color_registros, subset=["Registros"])
            st.dataframe(styled, use_container_width=True, hide_index=True, height=700)

        with tab_logs:
            st.markdown('<p class="section-header">Historial de Sincronizacion</p>', unsafe_allow_html=True)
            logs = db.query(SyncLog).order_by(SyncLog.ejecutado_at.desc()).limit(30).all()
            if logs:
                data = [{
                    "Fecha": str(l.ejecutado_at)[:16],
                    "Modulo": l.endpoint,
                    "Registros API": l.registros_api,
                    "Registros BD": l.registros_db,
                    "Discrepancias": l.discrepancias,
                    "Estado": l.estado.upper(),
                } for l in logs]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=600)
            else:
                st.info("Sin historial de sincronizacion.")
    finally:
        db.close()
