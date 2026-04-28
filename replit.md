# BI Platform - Gabriel Hoyos

## Overview
This project is a Business Intelligence platform designed for Gabriel Hoyos, who manages multiple clients using the Obuma ERP system. The platform's primary purpose is to audit and report on the profitability of operations. It aims to provide comprehensive insights into sales, costs, and client performance, enabling better decision-making and operational efficiency.

## User Preferences
I prefer that the agent prioritize the creation and refinement of Excel reports, especially ensuring their accuracy and timely generation. The system should guarantee that all data used for reporting, particularly for cartera/cobranza reports, is up-to-date by performing an immediate synchronization before report generation. I expect "Nota Credito" amounts to be handled specifically by being subtracted from totals in all calculations and reports, not added. I also require strict adherence to document type filtering to exclude "Tipo 4" documents (pre-invoices) from all sales analyses.

## System Architecture
The platform features a multi-tenant architecture with a clear separation of concerns.

**UI/UX Decisions:**
- The frontend is built with Streamlit, providing an interactive dashboard experience.
- Excel reports are generated using `openpyxl`, ensuring a professional and consistent format with specific styling guidelines (e.g., yellow fill for zero cells, green fill for ABC segments, blue/white headers).
- Dashboard sections include a global filter for dates and vendors, displaying KPIs, interactive charts for sales, profitability, collections, and top products.

**Technical Implementations:**
- **Backend:** FastAPI handles all business logic and API endpoints.
- **Frontend:** Streamlit serves as the interactive dashboard.
- **Database:** PostgreSQL acts as the single source of truth, storing historical data and comprehensive Obuma information across 28 models, including multi-tenant support via the `Tenant` model.
- **ETL:** A Python module is responsible for consuming the Obuma API, synchronizing 23 endpoints automatically.
- **Scheduler:** APScheduler manages daily data synchronization at 18:30 (Chile time) for core entities (clients, sales, etc.) and automated report generation (daily Mon-Thu 20:30, weekly Fri 23:00 Chile time).
- **Reports:** `excel_generator.py` module is dedicated to creating professional Excel reports, including specialized vendor reports with ABC segmentation, risk levels, and custom date ranges.
- **Document Type Filtering:** A critical system-wide rule mandates filtering sales data to include only `VALID_DOC_TYPES` (e.g., 'Factura Electr.', 'Boleta Electr.', 'Nota Credito') and exclude 'Tipo 4'. 'Nota Credito' amounts are always subtracted. This is enforced in `excel_generator.py` and `dashboard/app.py`.
- **Vendedor Mapping:** For client assignment (cartera), `ClienteFinal.data_json.rel_usuario_id` is used. For individual sales, `VentaHistorico.vendedor_id` is used, which maps to `detalle.rel_vendedor_id` from the raw Obuma JSON.
- **Cartera Auto-Population:** `VendedorCartera` is automatically populated from `ClienteFinal.data_json.rel_usuario_id` during client synchronization, focusing on specific tracked vendors.
- **Reporte Cartera/Cobranza Logic:** Reports trigger an immediate sync of `clientes`, `ventas`, and `ventas_items_incremental` to ensure data freshness. `NCs` are handled by displaying `total_por_pagar` as positive, matching Obuma's display. Filters applied include `vendedor_id`, `tipo_documento`, `total_por_pagar > 0`, and `anulada == False`. Reports include summary blocks, distribution by due days, and detailed breakdowns with traffic light indicators based on emission date.
- **Vendedor Tracking:** Support for tracking 5 specific vendors, including their monthly targets for 'Repuestos' and 'Maquinaria'. Product classification (Maquinaria vs. Repuestos) is based on SKU prefixes.

**Feature Specifications:**
- **Complete ETL:** Synchronization of 21 active Obuma endpoints.
- **Historical Tables:** `ventas_historico`, `costos_historico`, `compras_historico`.
- **Net Margin Calculation:** Cross-referencing sales with acquisition costs.
- **Audit Capabilities:** Comparison of API totals versus PostgreSQL data.
- **API Catalog:** A database record of 30 Obuma API endpoints for automated processes.
- **Data JSON Storage:** Raw API responses are stored in `data_json` for each model.

## External Dependencies
- **Obuma ERP API:** The core data source, accessed via `OBUMA_API_KEY` and `OBUMA_BASE_URL`.
- **PostgreSQL:** The primary database for all stored data.
- **Resend:** Email service for sending automated reports, configured with `RESEND_API_KEY` and a verified `EMAIL_FROM` address (`reportes@autoreportes.cl`).