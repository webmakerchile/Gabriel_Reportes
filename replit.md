# BI Platform - Gabriel Hoyos

## Overview
Plataforma de Business Intelligence para Gabriel Hoyos (VLSur), administrador de múltiples clientes en el ERP Obuma. Audita y reporta rentabilidad, ventas, costos y desempeño de los 5 vendedores trackeados, generando reportes Excel automatizados y un dashboard web.

## User Preferences
- Priorizar la **exactitud y puntualidad de los reportes Excel**.
- Para reportes de **cartera/cobranza** se exige sincronización inmediata antes de generar (los datos del día deben estar incluidos).
- **Manejo de "Nota Crédito" depende del tipo de reporte** (ver sección CRITICAL más abajo). NO aplicar una sola regla universal.
- **Excluir documentos "Tipo 4"** (pre-facturas) de todo análisis de ventas. Solo se aceptan los `VALID_DOC_TYPES` definidos en `src/reports/excel_generator.py`: `BILLING_DOC_TYPES = ["Factura Electr.", "Factura Exenta", "Boleta Electr."]` + `NC_DOC_TYPES = ["Nota Credito"]` + `ND_DOC_TYPES = ["Nota Debito"]`.

## System Architecture

**Stack**
- **Backend**: FastAPI (puerto 8000)
- **Frontend**: Streamlit (puerto 5000)
- **DB**: PostgreSQL (single source of truth, 28 modelos, multi-tenant)
- **ETL**: módulo Python que consume API Obuma (21 endpoints sincronizando)
- **Scheduler**: APScheduler — sync ligero diario 18:30 hora Chile + envíos automáticos:
  - **Lun-Jue 23:00**: reportes diarios por vendedor (sync inmediato + abort-on-failure)
  - **Viernes 23:00**: reporte semanal por vendedor (sync inmediato + abort-on-failure)
  - **Sáb-Dom 09:00**: reportes de fin de semana (sync inmediato + abort-on-failure)
  - **Cada 15 min**: `process_scheduled_reports` chequea schedules custom; si hay alguno due hace UN solo sync inmediato + abort y luego envía todos los due en ese tick.
- **Reports**: `src/reports/excel_generator.py` (openpyxl) + `src/reports/email_service.py` (Resend, `EMAIL_FROM=reportes@autoreportes.cl`)

**Estilos Excel**: amarillo en celdas en cero, verde en segmento ABC, encabezados azul/blanco.

**Dashboard**: filtros globales (fechas, vendedor), KPIs, gráficos de ventas/rentabilidad/cobranza/top productos.

## CRITICAL: Manejo de Nota Crédito (NC) y Nota Débito (ND) por tipo de reporte

**Las NC se tratan distinto según el reporte. Esto NO es contradicción — refleja cómo Obuma las muestra en cada pantalla. Las ND, en cambio, se tratan SIEMPRE como cargo positivo (igual que una Factura) en todos los reportes.**

### En reportes de VENTAS / MARGEN / DASHBOARD (vendedor mensual, top productos, KPIs)
- Las **NC se restan** de los totales de venta (representan devoluciones / anulaciones de ingresos).
- Las **ND suman positivo** (representan cargos adicionales al cliente: intereses, recargos, ajustes a favor de la empresa).
- Implementado en `excel_generator.py` (reportes de vendedor) y `dashboard/app.py` filtrando por `VALID_DOC_TYPES` y aplicando signo negativo solo a NC. ND quedan en la rama positiva por defecto del `case`.

### En reporte CARTERA / COBRANZA (Facturas por Cobrar)
- Tanto **NC como ND** se muestran POSITIVAS en la columna POR PAGAR, exactamente como aparecen en la pantalla "Facturas por Cobrar" de Obuma.
- Para **NC**: el campo `total_por_pagar` que devuelve Obuma ya representa el saldo a favor del cliente; restarla sería doble conteo.
- Para **ND**: es deuda real adicional del cliente, igual que una factura.
- El TOTAL GENERAL del reporte = suma directa de la columna POR PAGAR (sin negar nada).
- Visualmente:
  - NCs: font italic rojo (`NC_FONT`) — saldo a favor del cliente.
  - NDs: font azul oscuro bold (`ND_FONT`) — cargo adicional al cliente.
  - Facturas/Boletas: font normal negro.

## CRITICAL: Sync inmediato + abort-on-failure (TODOS los envíos automáticos)

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

## Feature Specifications
- ETL completo: 21 endpoints activos de Obuma.
- Tablas históricas: `ventas_historico`, `costos_historico`, `compras_historico`.
- Cálculo de margen neto: cruce ventas × costos de adquisición.
- Auditoría: comparación totales API vs PostgreSQL.
- Catálogo API: 30 endpoints registrados en `ObumaApiEndpoint` para procesos automatizados.
- Almacenamiento JSON crudo: campo `data_json` en cada modelo.

## External Dependencies
- **Obuma ERP API**: `OBUMA_API_KEY`, `OBUMA_BASE_URL`.
- **PostgreSQL**: BD primaria.
- **Resend**: envío de correos (`RESEND_API_KEY`, `EMAIL_FROM=reportes@autoreportes.cl`).
- **`ADMIN_ALERT_EMAILS`** (opcional, recomendado en producción): lista CSV de correos de admins (ej. `gabriel@vlsur.cl,otro@vlsur.cl`) que reciben aviso cuando un envío automático se aborta por fallo de sync con Obuma. Si está vacía, el sistema sigue funcionando pero la alerta sólo queda en logs (ver sección CRITICAL más arriba). **Define esta variable en el entorno de producción** para no perder el aviso si Obuma cae fuera de horario.
