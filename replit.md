# BI Platform - Gabriel Hoyos

## Overview
This project is a Business Intelligence platform for Gabriel Hoyos (VLSur), designed to audit and report on profitability, sales, costs, and performance for five tracked salespeople within the Obuma ERP. It automates Excel report generation and provides a web-based dashboard. The platform aims to provide comprehensive insights into sales and financial performance, enabling better decision-making and optimizing operations for VLSur's clients.

## User Preferences
- Priorizar la **exactitud y puntualidad de los reportes Excel**.
- Para reportes de **cartera/cobranza** se exige sincronización inmediata antes de generar (los datos del día deben estar incluidos).
- **Manejo de "Nota Crédito" depende del tipo de reporte** (ver sección CRITICAL más abajo). NO aplicar una sola regla universal.
- **Excluir documentos "Tipo 4"** (pre-facturas) de todo análisis de ventas. Solo se aceptan los `VALID_DOC_TYPES` definidos en `src/reports/excel_generator.py`: `BILLING_DOC_TYPES = ["Factura Electr.", "Factura Exenta", "Boleta Electr."]` + `NC_DOC_TYPES = ["Nota Credito"]` + `ND_DOC_TYPES = ["Nota Debito"]`.

## System Architecture

**Stack**
- **Backend**: FastAPI (port 8000)
- **Frontend**: Streamlit (port 5000)
- **Database**: PostgreSQL (single source of truth, multi-tenant)
- **ETL**: Python module consuming Obuma API (21 endpoints for synchronization)
- **Scheduler**: APScheduler for daily light syncs and automated report deliveries. Ensures immediate synchronization before report generation and aborts if sync fails. An internal health check runs every 5 minutes.

**Reports**: Generated via `src/reports/excel_generator.py` (using openpyxl) and sent via email using `src/reports/email_service.py`. Excel reports use specific styling (yellow for zero cells, green for ABC segments, blue/white headers).

**Dashboard**: Features global filters (dates, salesperson), KPIs, and charts for sales, profitability, collections, and top products.

**Dashboard Performance (Fase 1 + Fase 2)**:
- *Fase 1 (cache):* La pestaña "Dashboard" usa helpers cacheados (`_cached_load_empleados`, `_cached_dashboard_kpis`, `_cached_dashboard_charts`, `_cached_dashboard_recent_and_top`) en `src/dashboard/app.py` con `@st.cache_data(ttl=300, show_spinner=False)`. Cada helper abre su propia `SessionLocal()` y devuelve primitivos (no objetos ORM). El `vendor_ids` cache key viaja como tuple ordenado. `Base.metadata.create_all` está envuelto en `@st.cache_resource _ensure_schema_once()`. El botón "Ver Dashboard Actualizado" llama `st.cache_data.clear()` post-sync.
- *Fase 2 (N+1 + indexes):* La pestaña "Vendedores" tenía 4 patrones N+1 reescritos a queries `GROUP BY` batch — Tab 1 "Rendimiento vs Metas" (5 GROUP BY por vendedor: metas, neto, maquinaria, cartera, atendidos con `HAVING net > 0`), Tab 2 "Cartera de Clientes" (1 GROUP BY por cliente_id con short-circuit si la lista está vacía), Tab 3 "Cruce Cartera vs Ventas" (1 GROUP BY ventas + 1 GROUP BY max(fecha) solo sobre `no_compraron_ids`), y mini-loop "Clientes por Vendedor" (1 GROUP BY por empleado_obuma_id).
- *Indexes Postgres* creados idempotentemente en `src/api/main.py::_ensure_perf_indexes()` (llamada desde `_heavy_init()` antes de `seed_api_catalog`, usa `Index().create(bind=engine, checkfirst=True)`). Cada arranque loggea `Performance indexes ensured (8/8)`. Los 8 índices: `ix_ventas_vendedor_fecha`, `ix_ventas_cliente_fecha`, `ix_ventas_fecha`, `ix_ventas_anulada_tipo`, `ix_venta_items_venta_id_obuma`, `ix_ventas_obuma_id` (acelera join VentaItem→VentaHistorico), `ix_compras_fecha`, `ix_vendedor_cartera_emp_activo`.
- *Semántica preservada en Fase 2:* NC resta vía `sql_case(NC_DOC_TYPES_G)`, ND/Facturas suman, filtro `VALID_DOC_TYPES_G`, exclusión de dummies `OBU-*` sin nombre en metas, regla "atendido = HAVING net > 0", `VendedorCartera.activo == True`. 52/52 tests pasan.
- *Pendiente para Fase 3 (sugerido por code review):* migrar predicados `extract('year'/'month', fecha)` a rangos `fecha >= start AND fecha < end` para que el planner aproveche mejor los índices de fecha.

**Critical Handling of Credit/Debit Notes**:
- **Sales/Margin/Dashboard Reports**: Credit Notes (NC) are subtracted from sales, Debit Notes (ND) are added.
- **Collections/Accounts Receivable Reports**: Both NC and ND are shown as positive values, with specific styling (italic red for NC, bold dark blue for ND).

**Critical Immediate Sync + Abort-on-Failure**:
- All automatic report dispatches perform an immediate, blocking sync. If any part of the sync fails, report dispatch is aborted, an error is logged, and an administrative alert is sent (with anti-spam cooldowns).

**Critical Accounts Receivable Report**:
- Includes staleness checks, filters by salesperson, valid document types, positive amounts due, and non-cancelled documents.
- Excel structure includes a **SUMMARY**, **DISTRIBUTION BY DUE DAYS**, and a detailed **DETAIL** section (11 columns, grouped by client with subtotals). Row colors in the detail section indicate days since emission (green for 30-45 days, orange for 46-60, red for 61+).

**Salesperson Mapping**:
- For **accounts receivable (client assignment)**: `ClienteFinal.data_json.rel_usuario_id`.
- For **individual sales (invoices, receipts, NCs)**: `VentaHistorico.vendedor_id` (from Obuma's raw JSON `detalle.rel_vendedor_id`). This tracks the actual salesperson for the document.

**Tracked Salespeople (5)**: Gabriel, Jhonatan, Ernesto, Pablo, Jesús. Product classification (Machinery vs. Spare Parts) is based on SKU prefixes.

**Feature Specifications**:
- Complete ETL with 21 active Obuma endpoints.
- Historical tables for sales, costs, and purchases.
- Net margin calculation by cross-referencing sales and acquisition costs.
- Audit functionality comparing API totals with PostgreSQL data.
- 30 API endpoints registered for automated processes.
- Raw JSON data stored in a `data_json` field for each model.

## External Dependencies
- **Obuma ERP API**: `OBUMA_API_KEY`, `OBUMA_BASE_URL`.
- **PostgreSQL**: Primary database.
- **Resend**: Email sending service (`RESEND_API_KEY`, `EMAIL_FROM=reportes@autoreportes.cl`).
- **Health Endpoint**: `GET /api/health` (FastAPI, port 8000).
- **`ADMIN_ALERT_EMAILS`**: (Optional) CSV list of admin emails for sync failure alerts.