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
- Historical tables for sales, costs, and purchases.
- Net margin calculation by cross-referencing sales and acquisition costs.
- Audit functionality comparing API totals with PostgreSQL data.
- 30 API endpoints registered for automated processes.
- Raw JSON data stored in a `data_json` field for each model.

## External Dependencies
- **Obuma ERP API**: `OBUMA_API_KEY`, `OBUMA_BASE_URL`.
- **PostgreSQL**: Primary database.
- **Resend**: Email sending service (`RESEND_API_KEY`, `EMAIL_FROM=reportes@autoreportes.cl`).
- **Health Endpoint**: `GET /api/health` (FastAPI, port 8000). Provides system status (ok/degraded) including email configuration and scheduler status.
- **`ADMIN_ALERT_EMAILS`**: (Optional, recommended in production) CSV list of admin emails for sync failure alerts.