# BI Platform - Gabriel Hoyos

## Overview
This project is a Business Intelligence platform designed for Gabriel Hoyos (VLSur), who manages multiple clients within the Obuma ERP. Its primary purpose is to audit and report on profitability, sales, costs, and performance for five tracked salespeople. The platform automates Excel report generation and provides a web-based dashboard. The business vision is to provide comprehensive insights into sales and financial performance, enabling better decision-making and optimizing operations for VLSur's clients.

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
- **Scheduler**: APScheduler for daily light syncs and automated report deliveries. It ensures immediate synchronization before report generation and aborts if sync fails, preventing partial data delivery. An internal health check runs every 5 minutes, alerting admins if the system is degraded.

**Reports**: Generated via `src/reports/excel_generator.py` (using openpyxl) and sent via email using `src/reports/email_service.py` (Resend). Excel reports utilize specific styling (yellow for zero cells, green for ABC segments, blue/white headers).

**Dashboard**: Features global filters (dates, salesperson), KPIs, and charts for sales, profitability, collections, and top products.

**Dashboard Cache Layer (Fase 1 perf):** El bloque `if page == "Dashboard":` consume helpers cacheados en `src/dashboard/app.py` (`_cached_load_empleados`, `_cached_dashboard_kpis`, `_cached_dashboard_charts`, `_cached_dashboard_recent_and_top`). Todos usan `@st.cache_data(ttl=300, show_spinner=False)`, abren su propia `SessionLocal()` y devuelven primitivos (no objetos ORM). El `vendor_ids` cache key viaja como tuple ordenado y `Base.metadata.create_all` se envuelve en `@st.cache_resource _ensure_schema_once()` (antes corría en cada rerun). El botón "📊 Ver Dashboard Actualizado" (post-sync manual) llama `st.cache_data.clear()` para que los datos frescos se vean inmediatamente sin esperar al TTL. Fase 2 (índices + N+1 en Vendedores/Cruce Cartera) queda pendiente.

**Critical Handling of Credit/Debit Notes**:
- **Sales/Margin/Dashboard Reports**: Credit Notes (NC) are subtracted from sales totals, and Debit Notes (ND) are added as positive charges. This logic is implemented in `excel_generator.py` and `dashboard/app.py`.
- **Collections/Accounts Receivable Reports**: Both NC and ND are shown as positive values in the "Amount Due" column, mirroring Obuma's display. NCs are styled with italic red font, NDs with bold dark blue font, and other documents in normal black.

**Critical Immediate Sync + Abort-on-Failure**:
- All automatic report dispatches (daily, weekly, scheduled) perform an immediate, blocking sync (`sync_for_report`). If any part of the sync fails, the report dispatch is aborted, an error is logged, and an administrative alert is sent. This prevents partial or outdated reports from being sent.
- Admin alerts for sync failures are sent to `ADMIN_ALERT_EMAILS` with anti-spam cooldowns.

**Critical Accounts Receivable Report**:
- Includes checks for data staleness.
- Filters by `vendedor_id`, valid document types, positive amounts due, and non-cancelled documents.
- Excel structure includes a **SUMMARY** (total outstanding, overdue, non-overdue, no due date), **DISTRIBUTION BY DUE DAYS** (ranges with quantity, amount, %), and a detailed **DETAIL** section (11 columns, grouped by client with subtotals). Row colors in the detail section indicate days since emission (green for 30-45 days, orange for 46-60, red for 61+).

**Salesperson Mapping**:
- For **accounts receivable (client assignment)**: `ClienteFinal.data_json.rel_usuario_id`.
- For **individual sales (invoices, receipts, NCs)**: `VentaHistorico.vendedor_id` (mapping to `detalle.rel_vendedor_id` from Obuma's raw JSON). This ensures the actual salesperson for the document is tracked.

**Tracked Salespeople (5)**: Gabriel, Jhonatan, Ernesto, Pablo, Jesús. Product classification (Machinery vs. Spare Parts) is based on SKU prefixes.

**Feature Specifications**:
- Complete ETL with 21 active Obuma endpoints.
- Historical tables for sales, costs, and purchases (`ventas_historico`, `costos_historico`, `compras_historico`).
- Net margin calculation by cross-referencing sales and acquisition costs.
- Audit functionality comparing API totals with PostgreSQL data.
- 30 API endpoints registered for automated processes in `ObumaApiEndpoint`.
- Raw JSON data stored in a `data_json` field for each model.

Política unificada para que Gabriel nunca reciba un correo con datos parciales o desactualizados:

- **Helpers compartidos en `src/reports/excel_generator.py`**:
  - `sync_for_report(db, scope)`: ejecuta `sync_clientes` → `sync_ventas` → `sync_ventas_items_incremental(YYYY-01-01..hoy)` → `sync_ventas_cobros`. Los 4 son **bloqueantes**: si cualquiera falla levanta `RuntimeError` y los flujos llamadores abortan el envío sin mandar correo.
  - `log_reconciliation_per_vendor(db, today, scope)`: loguea totales de cartera por vendedor trackeado vs `OBUMA_REFERENCE_TOTALS`.
  - `_sync_for_cartera_report(db)`: compat wrapper que llama a ambos.
- **Aplicado en todos los flujos del scheduler** (`src/scheduler.py`):
  - `_generate_and_send_individual_reports` (usado por `daily_weekday_reports`, `weekly_friday_reports`, `weekend_morning_reports`): sync inmediato al inicio; si falla, **NO se envía ningún correo**, se loguea ERROR y se dispara alerta admin (ver abajo).
  - `process_scheduled_reports`: chequea schedules due primero; si hay alguno, hace UN solo sync inmediato + reconciliación, y solo si pasa procede con los envíos. Si falla, ABORTA todos los schedules due en ese tick y dispara alerta admin.
  - `generate_all_cartera_cobranza_reports(db, do_sync=True)`: igual comportamiento (return `[]` si sync falla).
- **Alerta admin por correo cuando un envío se aborta** (`src/scheduler.py::_send_sync_failure_alert`):
  - Cuando `sync_for_report` lanza, además del log ERROR se manda un correo corto (sin attachments, plantilla `build_admin_alert_html` en `email_service.py`) a la lista definida por la variable de entorno **`ADMIN_ALERT_EMAILS`** (separada por coma, ej. `gabriel@vlsur.cl,otro@vlsur.cl`).
  - Si `ADMIN_ALERT_EMAILS` no está configurada, la alerta se omite silenciosamente (solo log WARN). El sistema sigue siendo funcional sin la alerta.
  - **Anti-spam**: máximo 1 alerta por scope (`Reporte Diario Lun-Jue`, `Reporte Semanal Viernes`, `Reporte Fin de Semana`, `Reportes Programados`) cada `ALERT_COOLDOWN_HOURS = 1.0` horas. Evita inundar la bandeja si Obuma está caído por horas.
  - El helper de alerta nunca lanza excepción — si falla el envío de la alerta, solo se loguea (el flujo de aborto del envío principal ya está en marcha).
  - **Aviso de configuración al arrancar** (`src/api/main.py::on_startup` → `email_service.log_admin_alert_config_status`): cada vez que arranca FastAPI, se loguea una línea explícita con el estado de `ADMIN_ALERT_EMAILS` (`INFO` si está configurada con la lista de destinatarios; `WARNING` muy visible si no lo está). El helper de chequeo es `email_service.check_admin_alert_config()` y devuelve `{configured, emails, reason}`.
  - **Aviso simétrico del proveedor de correo al arrancar** (`src/api/main.py::on_startup` → `email_service.log_email_config_status`, justo después del log de admin alerts): loguea una línea explícita con el estado del proveedor de correo y el remitente actual: `INFO "EMAIL: Resend OK / SendGrid OK / SMTP OK (remitente: ...)"` cuando hay proveedor y `EMAIL_FROM` apunta a un dominio propio; `WARNING "EMAIL: NO CONFIGURADO ..."` si no hay `RESEND_API_KEY`/`SENDGRID_API_KEY`/SMTP — sin esto no se mandan reportes NI alertas a admin; `WARNING "EMAIL: Resend OK pero EMAIL_FROM=onboarding@resend.dev en modo sandbox: ..."` si el remitente quedó en el sandbox de Resend (solo puede enviar al dueño de la cuenta y rebota cualquier otro destinatario). El helper de chequeo es `email_service.check_email_config()` y devuelve `{configured, method, detail, sandbox, from_email}`.
  - **Indicador visible en el dashboard**: el sidebar de Streamlit (`src/dashboard/app.py`) muestra una badge "Alertas admin: ON" (verde, con cantidad de destinatarios) o "Alertas admin: OFF" (rojo, con instrucción para definir `ADMIN_ALERT_EMAILS`) en cada vista. La pestaña "Configuracion de Email" repite el mismo estado con más detalle.

## CRITICAL: Reporte Cartera/Cobranza
- **Detección de staleness en path por-vendedor** (`generate_cartera_cobranza_report`):
  - Si la última sincronización de `Ventas` en `ObumaApiEndpoint.ultima_sync` tiene > 2 horas, emite WARNING en logs (la entrada batch normal hace sync inmediato; este check solo cubre llamadas directas que pudieran bypassear el batch).
- **Filtros**: `vendedor_id`, `tipo_documento ∈ VALID_DOC_TYPES`, `total_por_pagar > 0`, `anulada == False`.
- **Estructura Excel**:
  1. **RESUMEN**: total a cobrar (#docs), total vencido (con %), total no vencido (con %), sin vencimiento.
  2. **DISTRIBUCIÓN POR DÍAS DE VENCIMIENTO**: rangos Vencido >90 / 61-90 / 31-60 / 1-30, Vence hoy, Por vencer 1-30 / 31-60 / 61-90 / >90, Sin vencimiento. Cada fila: cantidad, monto, % del total. Coloreado por criticidad.
  3. **DETALLE** (11 columnas): DOCUMENTO, FOLIO, FECHA, FECHA VCTO, ESTADO (Vencido/Por vencer/Sin vencimiento), FECHA HOY, DÍAS ATRASO, CLIENTE, CLIENTE RUT, VENDEDOR, POR PAGAR. Agrupado por cliente con subtotal gris + TOTAL GENERAL final.
- **Semáforo del DETALLE** (color de fila): días desde **EMISIÓN**. <30 sin color, 30-45 verde, 46-60 naranja, 61+ rojo. (Gabriel pidió mantener este criterio aunque el ESTADO se calcule por vencimiento.)

## CRITICAL: Mapeo de vendedor (regla central)
- **Para CARTERA (asignación de cliente)**: usar `ClienteFinal.data_json.rel_usuario_id`. Auto-poblado en `VendedorCartera` durante `sync_clientes` para los 5 vendedores trackeados.
- **Para VENTAS individuales (facturas, boletas, NCs)**: usar `VentaHistorico.vendedor_id` (columna BD), que mapea a `detalle.rel_vendedor_id` en el JSON crudo de Obuma. Es el vendedor REAL del documento (NO `rel_usuario_id`, que es quien creó el documento — cajero/operador).
- Verificación: 30 registros aleatorios → coincidencia 30/30.

## Vendedores trackeados (5)
| Obuma ID | Nombre   | Metas mensuales (Repuestos / Maquinaria) |
|----------|----------|------------------------------------------|
| 28856    | Gabriel  | configuradas en `VendedorMeta`           |
| 28886    | Jhonatan | configuradas en `VendedorMeta`           |
| 28887    | Ernesto  | configuradas en `VendedorMeta`           |
| 28891    | Pablo    | configuradas en `VendedorMeta`           |
| 28892    | Jesús    | configuradas en `VendedorMeta`           |

Clasificación de producto (Maquinaria vs Repuestos): por prefijo de SKU.

## External Dependencies
- **Obuma ERP API**: `OBUMA_API_KEY`, `OBUMA_BASE_URL`.
- **PostgreSQL**: Primary database.
- **Resend**: Email sending service (`RESEND_API_KEY`, `EMAIL_FROM=reportes@autoreportes.cl`).
- **Health Endpoint**: `GET /api/health` (FastAPI, port 8000). Provides system status (ok/degraded) including email configuration and scheduler status.
- **`ADMIN_ALERT_EMAILS`**: (Optional, recommended in production) CSV list of admin emails for sync failure alerts.