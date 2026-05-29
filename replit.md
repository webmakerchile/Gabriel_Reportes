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
- **Scheduler**: APScheduler for daily light syncs and automated report deliveries. Ensures immediate synchronization before report generation and aborts if sync fails. An internal health check runs every 5 minutes. Jobs configurados (todos zona horaria America/Santiago, todos con sync inmediato + abort-on-failure):
- `daily_sync` — diario 18:30 (sync ligero, sin envío de reportes).
- `daily_weekday_reports` — Lun-Jue 23:00 (reporte diario por vendedor, omite viernes).
- `weekly_friday_reports` — Vie 23:00 (reporte semanal por vendedor).
- `weekend_morning_reports` — Sab/Dom 09:00 (reporte fin de semana por vendedor).
- `weekly_monday_cobranza_reports` — **Lun 06:30 (Cartera por Cobrar por Vendedor, entrega ~09:00)**: cumple la spec del módulo "Reporte semanal de cobranza por vendedor". Llama `generate_all_cartera_cobranza_reports(do_sync=True)` y envía cada Excel personalizado a los emails configurados en `ReporteProgramado.emails_destino`. Si un vendedor no tiene saldo pendiente, se omite (no se envía correo vacío). El cron se gatilla a las 06:30 (no 09:00) porque el sync inmediato con Obuma + la generación de los 5 Excels (~1.500 docs en total) tarda ~2.5h en producción; de este modo el correo LLEGA cerca de las 09:00 como pidió el cliente.
- `check_scheduled_reports` — cada 15 min (verificación de reportes programados ad-hoc).
- `internal_health_check` — cada 5 min (monitor de salud interno).

**Reports**: Generated via `src/reports/excel_generator.py` (using openpyxl) and sent via email using `src/reports/email_service.py`. Excel reports use specific styling (yellow for zero cells, green for ABC segments, blue/white headers).

**Dashboard**: Features global filters (dates, salesperson), KPIs, and charts for sales, profitability, collections, and top products.

**Dashboard Performance (Fase 1 + Fase 2 + Fase 3)**:
- *Fase 1 (cache):* La pestaña "Dashboard" usa helpers cacheados (`_cached_load_empleados`, `_cached_dashboard_kpis`, `_cached_dashboard_charts`, `_cached_dashboard_recent_and_top`) en `src/dashboard/app.py` con `@st.cache_data(ttl=300, show_spinner=False)`. Cada helper abre su propia `SessionLocal()` y devuelve primitivos (no objetos ORM). El `vendor_ids` cache key viaja como tuple ordenado. `Base.metadata.create_all` está envuelto en `@st.cache_resource _ensure_schema_once()`. El botón "Ver Dashboard Actualizado" llama `st.cache_data.clear()` post-sync.
- *Fase 2 (N+1 + indexes):* La pestaña "Vendedores" tenía 4 patrones N+1 reescritos a queries `GROUP BY` batch — Tab 1 "Rendimiento vs Metas" (5 GROUP BY por vendedor: metas, neto, maquinaria, cartera, atendidos con `HAVING net > 0`), Tab 2 "Cartera de Clientes" (1 GROUP BY por cliente_id con short-circuit si la lista está vacía), Tab 3 "Cruce Cartera vs Ventas" (1 GROUP BY ventas + 1 GROUP BY max(fecha) solo sobre `no_compraron_ids`), y mini-loop "Clientes por Vendedor" (1 GROUP BY por empleado_obuma_id).
- *Indexes Postgres* creados idempotentemente en `src/api/main.py::_ensure_perf_indexes()` (llamada desde `_heavy_init()` antes de `seed_api_catalog`, usa `Index().create(bind=engine, checkfirst=True)`). Cada arranque loggea `Performance indexes ensured (10/10)`. Los 10 índices: `ix_ventas_vendedor_fecha`, `ix_ventas_cliente_fecha`, `ix_ventas_fecha`, `ix_ventas_anulada_tipo`, `ix_venta_items_venta_id_obuma`, `ix_ventas_obuma_id` (acelera join VentaItem→VentaHistorico), `ix_compras_fecha`, `ix_vendedor_cartera_emp_activo`, **`ix_clientes_tenant_obuma`** (Fase 4 sync N+1), **`ix_compras_obuma_id`** (Fase 4 sync N+1).
- *Fase 3 (range predicates):* Todos los filtros `extract('year'/'month', fecha) == valor` y `func.date(fecha) >= / <= ...` migrados a rangos sobre la columna pura (`fecha >= start AND fecha < end_excl`) usando los helpers de `src/utils/date_filters.py` (`date_range_filters(col, df, dt)` y `year_month_range(year, month=None)`). Sin esto, los `ix_*_fecha` de Fase 2 no se usaban porque el planner descartaba el btree al aplicar funciones sobre la columna. EXPLAIN ANALYZE confirma cambio de plan: `Bitmap Heap Scan + Filter (extract)` → `Index Scan using ix_ventas_fecha (Index Cond: fecha >= ... AND fecha < ...)`. Mejora medida: ~2955ms → ~26ms (≈113x) en query de neto por vendedor del periodo. El borde superior `<= date_to` se traduce a `< day_after_to` (00:00) para incluir todo el día `date_to` cuando la columna es DateTime con hora. Aplicado en 7 zonas de `src/dashboard/app.py` (helper `_apply_dash_filters_q`, KPI compras, monthly compras, Tab 1 Rendimiento con `_period_start/_period_end`, Tab 2 cartera 12 meses, Tab 3 Cruce con `_cruce_start/_cruce_end`, Ventas tab), 2 endpoints de `src/api/main.py` (`/api/v1/ventas`, `/api/v1/margen-bruto`) y 4 queries de `src/reports/excel_generator.py`.
- *Casos `extract()` legítimos preservados:* `extract('year/month', fecha).label(...)` en `SELECT` para agrupar mensualmente (Dashboard ventas/compras chart) y `count(distinct(extract('month', fecha)))` para contar meses únicos. No estorban al planner porque NO están en `WHERE`.
- *Semántica preservada en Fases 2 y 3:* NC resta vía `sql_case(NC_DOC_TYPES_G)`, ND/Facturas suman, filtro `VALID_DOC_TYPES_G`, exclusión de dummies `OBU-*` sin nombre en metas, regla "atendido = HAVING net > 0", `VendedorCartera.activo == True`. 82/82 tests pasan tras Fases 2, 3 y 4.

**Sync ETL Performance (Fase 4 — hot fix)**:
- *Síntoma:* En producción (autoreportes.cl) el sync de clientes tardaba ~29 min para 8015 items y la UI mostraba "Clientes y Cartera de Vendedores: Timeout (900s)". El backend completaba pero el polling del frontend caducaba a los 15 min.
- *Causa raíz (preexistente, no relacionada con Fase 3):* `sync_clientes()` (línea 170 de `src/etl/sync_service.py`) y `sync_compras()` (línea 950) hacen un `SELECT WHERE obuma_id = X` por cada item del API. Las tablas `clientes.obuma_id` y `compras_historico.obuma_id` no tenían índice, por lo que cada lookup era seq scan completo. Con 8015 clientes: 8015 × seq scan de 8015 = O(n²) ≈ 64M comparaciones.
- *Fix (mínimamente invasivo):* Se agregaron 2 índices defensivos a `_ensure_perf_indexes()` sin tocar la lógica de sync:
  - `ix_clientes_tenant_obuma` (composite `tenant_id, obuma_id`) — cura el N+1 de `sync_clientes`.
  - `ix_compras_obuma_id` — cura el N+1 de `sync_compras` (la query original no filtra por tenant_id).
- *Mejora esperada:* O(n²) → O(n log n). El sync de 8015 clientes pasa de ~29 min a ~1-2 min. El overhead de mantener un índice extra en INSERT es despreciable comparado con eliminar 64M comparaciones por seq scan.
- *Lo que NO se tocó (en Fase 4):* La precarga ORM de `sync_ventas` ya evitaba N+1 con un cache en memoria. Ver Fase 5 para la optimización posterior cuando ese sync sí se volvió el cuello de botella.

**Sync ETL Performance (Fase 5 — bulk upsert de ventas)**:
- *Síntoma:* En producción el sync inmediato que dispara los reportes programados (`sync_for_report` → `sync_ventas`) tardaba ~2-3h para ~57.500 ventas. Los logs mostraban `Ventas sync progress: 26000/57506` tras ~1.5h y el job `check_scheduled_reports` (cada 15 min) se saltaba repetidamente con `WARNING ... skipped: maximum number of running instances reached (1)`. Resultado para el cliente: los reportes programados llegaban con horas de retraso o no llegaban (el tick siguiente nunca arrancaba porque el anterior seguía corriendo).
- *Causa raíz:* `sync_ventas` (1) precargaba TODAS las filas de `VentaHistorico` como objetos ORM completos (incluido el `Text` `detalle` con el JSON crudo de cada venta) a la identity map, y (2) hacía dirty-checking objeto-por-objeto en el loop (unit-of-work del ORM emite un UPDATE por objeto). Con ~57.500 filas eran ~57.500 UPDATEs vía ORM (~464 filas/min medido).
- *Fix:* (a) la precarga ahora trae solo `(obuma_id, id)` en vez de objetos completos; (b) el loop acumula `update_mappings`/`insert_mappings` y los vuelca con `bulk_update_mappings`/`bulk_insert_mappings` cada `batch_size=2000` (mismo punto de commit/log de progreso que antes). Semántica idéntica: mismos campos, misma regla de stale-delete (`existing_cache.keys() - api_obuma_ids`), mismos defaults (`sincronizado_at` server_default y `anulada` se preservan). 82/82 tests pasan.
- *Mejora esperada:* de ~2-3h a unos pocos minutos. Al terminar rápido, el sync ya no solapa con el tick de 15 min y desaparecen los `maximum running instances reached`.
- *Si en el futuro hace falta más:* `sync_ventas_items_incremental` y `sync_ventas_cobros` siguen con patrón ORM; si crecen lo suficiente, aplicar el mismo enfoque bulk.

**Critical Handling of Credit/Debit Notes**:
- **Sales/Margin/Dashboard Reports**: Credit Notes (NC) are subtracted from sales, Debit Notes (ND) are added.
- **Collections/Accounts Receivable Reports**: NCs are shown as **NEGATIVE** values in the POR PAGAR column (italic red font) so they subtract from the customer's outstanding balance — matching how Obuma's "Facturas por Cobrar" computes "Total ventas a cobrar". NDs remain positive (bold dark blue font). All downstream sums (per-client subtotal, TOTAL GENERAL, RESUMEN CARTERA totals, distribution by due-date ranges) are direct sums of POR PAGAR and therefore self-adjust correctly via the NC sign. Historical note: prior to commit fixing this, NCs were shown positive and inflated the total by 2× the NC amount per occurrence (e.g. an NC of $273.688 made the total differ by +$547.376 vs. Obuma).

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