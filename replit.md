# BI Platform - Gabriel Hoyos

## Overview
Plataforma de Business Intelligence para Gabriel Hoyos (VLSur), administrador de múltiples clientes en el ERP Obuma. Audita y reporta rentabilidad, ventas, costos y desempeño de los 5 vendedores trackeados, generando reportes Excel automatizados y un dashboard web.

## User Preferences
- Priorizar la **exactitud y puntualidad de los reportes Excel**.
- Para reportes de **cartera/cobranza** se exige sincronización inmediata antes de generar (los datos del día deben estar incluidos).
- **Manejo de "Nota Crédito" depende del tipo de reporte** (ver sección CRITICAL más abajo). NO aplicar una sola regla universal.
- **Excluir documentos "Tipo 4"** (pre-facturas) de todo análisis de ventas. Solo se aceptan los `VALID_DOC_TYPES`: Factura Electr., Boleta Electr., Nota Crédito.

## System Architecture

**Stack**
- **Backend**: FastAPI (puerto 8000)
- **Frontend**: Streamlit (puerto 5000)
- **DB**: PostgreSQL (single source of truth, 28 modelos, multi-tenant)
- **ETL**: módulo Python que consume API Obuma (21 endpoints sincronizando)
- **Scheduler**: APScheduler — sync diario 18:30 hora Chile + reportes automáticos (lunes-jueves 20:30, viernes 23:00)
- **Reports**: `src/reports/excel_generator.py` (openpyxl) + `src/reports/email_service.py` (Resend, `EMAIL_FROM=reportes@autoreportes.cl`)

**Estilos Excel**: amarillo en celdas en cero, verde en segmento ABC, encabezados azul/blanco.

**Dashboard**: filtros globales (fechas, vendedor), KPIs, gráficos de ventas/rentabilidad/cobranza/top productos.

## CRITICAL: Manejo de Nota Crédito (NC) por tipo de reporte

**Las NC se tratan distinto según el reporte. Esto NO es contradicción — refleja cómo Obuma las muestra en cada pantalla.**

### En reportes de VENTAS / MARGEN / DASHBOARD (vendedor mensual, top productos, KPIs)
- Las NC **se restan** de los totales de venta (representan devoluciones / anulaciones de ingresos).
- Implementado en `excel_generator.py` (reportes de vendedor) y `dashboard/app.py` filtrando por `VALID_DOC_TYPES` y aplicando signo negativo a NC.

### En reporte CARTERA / COBRANZA (Facturas por Cobrar)
- Las NC **se muestran POSITIVAS** en la columna POR PAGAR, exactamente como aparecen en la pantalla "Facturas por Cobrar" de Obuma.
- Razón: el campo `total_por_pagar` que devuelve Obuma para una NC pendiente ya representa el saldo a favor del cliente; restarla de nuevo sería doble conteo.
- El TOTAL GENERAL del reporte = suma directa de la columna POR PAGAR (sin negar NCs).
- Visualmente las NCs se distinguen con font italic rojo (NC_FONT) en la fila para que el usuario las identifique sin confundir el valor.

## CRITICAL: Reporte Cartera/Cobranza

- **Sync inmediato antes de generar** (`generate_all_cartera_cobranza_reports(db, do_sync=True)`):
  - Ejecuta sync de `clientes` + `ventas` + `ventas_items_incremental(YYYY-01-01..hoy)` ANTES de generar cualquier Excel.
  - Si el sync falla → ABORTA la generación (return `[]`) para no enviar datos viejos.
  - Tras el sync, registra en logs el cuadre de los 5 vendedores trackeados (totales y % vencido) para auditar contra Obuma.
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
