# BI Platform - Gabriel Hoyos

## Overview
Plataforma de Business Intelligence para Gabriel Hoyos, quien gestiona multiples clientes a traves del ERP Obuma. El sistema permite auditar y reportar la rentabilidad de operaciones.

## Architecture
- **Backend**: FastAPI (puerto 8000) - API RESTful con todos los endpoints de negocio
- **Frontend**: Streamlit (puerto 5000) - Dashboard interactivo de control
- **Database**: PostgreSQL - Single Source of Truth con tablas historicas y datos completos de Obuma
- **ETL**: Modulo Python para consumir API de Obuma (23 endpoints sincronizados automaticamente)
- **Scheduler**: APScheduler - Generacion automatica de reportes Excel a las 23:50 hora Chile
- **Reports**: openpyxl - Generacion de reportes Excel profesionales
- **API Catalog**: Registro completo de 30 endpoints de Obuma en base de datos para automatizaciones

## Project Structure
```
main.py                     # Entry point - inicia FastAPI + Streamlit + seed DB
src/
  config.py                 # Configuracion y variables de entorno
  database.py               # Conexion SQLAlchemy a PostgreSQL
  scheduler.py              # Tarea programada diaria 23:50
  models/
    models.py               # Modelos SQLAlchemy (26 modelos multi-tenant)
  etl/
    obuma_client.py          # Cliente HTTP para API Obuma (30+ metodos)
    sync_service.py          # Servicio de sincronizacion completa (23 syncs)
    api_catalog_seed.py      # Seed de catalogo API Obuma (30 endpoints)
  api/
    main.py                 # Endpoints FastAPI
  reports/
    excel_generator.py       # Generador de reportes Excel
  dashboard/
    app.py                  # Dashboard Streamlit (8 secciones)
reports/                    # Directorio de reportes generados
```

## Database Models (26 tablas)
### Core
- **Tenant**: Multi-tenant support
- **SyncLog**: Log de sincronizaciones con API
- **ReporteGenerado**: Reportes Excel generados
- **ObumaApiEndpoint**: Catalogo completo de endpoints API Obuma (30 registros)

### Clientes
- **ClienteFinal**: Clientes sincronizados desde Obuma (rut, nombre, email, telefono)
- **ClienteContacto**: Contactos de clientes (nombre, email, telefono, cargo)
- **ClienteDireccion**: Direcciones de clientes (calle, ciudad, comuna, region)

### Proveedores
- **Proveedor**: Proveedores (rut, razon_social, email, telefono, direccion)

### Productos
- **Producto**: Productos con SKU, precios, costos, stock
- **ProductoCategoria**: Categorias de productos
- **ProductoSubCategoria**: Subcategorias de productos
- **ProductoFabricante**: Fabricantes de productos
- **ProductoPrecio**: Listas de precios por producto
- **CostoHistorico**: Historial de costos por producto

### Ventas
- **VentaHistorico**: Ventas con neto, IVA, total, costo, margen, pagado, por pagar, anulada
- **VentaItem**: Items detallados de cada venta (producto, cantidad, precio, total)
- **VentaCotizacion**: Cotizaciones (folio, fecha, cliente, total, estado)
- **VentaCobro**: Cobros recibidos (fecha, monto, forma de pago)
- **VentaDte**: Documentos tributarios electronicos emitidos

### Compras
- **CompraHistorico**: Compras con proveedor, folio, total
- **CompraOC**: Ordenes de compra (folio, proveedor, total, estado)
- **CompraPago**: Pagos a proveedores (fecha, monto, forma pago, origen)
- **CompraDteRecibido**: DTE recibidos de proveedores

### Contabilidad
- **ContabilidadHistorico**: Libro diario (debe/haber)
- **GastoMenor**: Gastos menores (fecha, descripcion, monto, categoria)

### Otros
- **Empleado**: Empleados (rut, nombre, email, cargo, activo)
- **Remuneracion**: Remuneraciones (empleado, periodo, haberes, descuentos, liquido)
- **CrmLead**: Leads CRM (nombre, empresa, email, estado, monto estimado)

## Sync Coverage (23 endpoints activos)
| Categoria | Endpoint | Tabla DB | Estado |
|-----------|----------|----------|--------|
| Clientes | clientes.list.json | clientes_finales | OK |
| Clientes | clientesContactos.listAll.json | clientes_contactos | OK |
| Clientes | clientesDirecciones.listAll.json | clientes_direcciones | OK |
| Proveedores | proveedores.list.json | proveedores | OK |
| Productos | productos.list.json | productos | OK |
| Productos | productosCategorias.list.json | producto_categorias | OK |
| Productos | productosSubCategorias.list.json | producto_subcategorias | OK |
| Productos | productosFabricantes.list.json | producto_fabricantes | OK |
| Productos | productosConsultaPrecios.list.json | producto_precios | OK |
| Empleados | empleados.list.json | empleados | OK |
| Empleados | remuneraciones.list.json | remuneraciones | OK |
| Ventas | ventas.list.json | ventas_historico | OK |
| Ventas | ventas.listItems.json | ventas_items | OK |
| Ventas | ventasCotizaciones.list.json | ventas_cotizaciones | OK |
| Ventas | ventasCobros.list.json | ventas_cobros | OK |
| Ventas | ventas.listDte.json | ventas_dte | OK |
| Compras | compras.list.json | compras_historico | OK |
| Compras | comprasOc.list.json | compras_oc | OK |
| Compras | comprasPagos.list.json | compras_pagos | OK |
| Compras | comprasDteRecibidos.list.json | compras_dte_recibidos | 404 |
| Contabilidad | contabilidad.listDiario.json | contabilidad_historico | OK |
| Contabilidad | comprasGastosMenores.list.json | gastos_menores | 404 |
| CRM | crm.list.json | crm_leads | OK |

## Key Features
1. **ETL Completo**: Sincronizacion de 23 endpoints Obuma (clientes, contactos, direcciones, proveedores, productos, categorias, subcategorias, fabricantes, precios, empleados, remuneraciones, ventas, items, cotizaciones, cobros, DTE, compras, OC, pagos, contabilidad, gastos menores, CRM)
2. **Tablas Historicas**: ventas_historico, costos_historico, compras_historico
3. **Multi-Tenant**: Tabla clientes_finales con relaciones a transacciones
4. **Calculo Margen Neto**: Cruce ventas vs costos de adquisicion
5. **Auditoria**: Comparacion totales API vs PostgreSQL
6. **Reportes Excel**: Generacion automatica diaria a las 23:50 Chile
7. **Dashboard**: 8 secciones - Dashboard, Ventas, Clientes, Contabilidad, API Obuma, Reportes, Sincronizacion, Auditoria
8. **Catalogo API**: 30 endpoints Obuma registrados con estado (sincronizado, implementado, disponible, referencia, error)
9. **Data JSON**: Cada modelo almacena data_json con respuesta cruda completa de API para futuras automatizaciones

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection
- `OBUMA_API_KEY` - API key for Obuma ERP (ff5bfe7710dd17ac298f60bd469b7b9b)
- `OBUMA_BASE_URL` - Base URL for Obuma API (https://api.obuma.cl/v1.0)
- `TZ` - Timezone (America/Santiago)

## Running
- `python main.py` starts both FastAPI (port 8000) and Streamlit (port 5000)
- Database tables and API catalog are auto-seeded on startup

## Obuma API Technical Notes
- Authentication: Header `access-token: YOUR_TOKEN`
- Rate limit: 1,000 calls/day per endpoint
- Max 1,000 items per response
- Base URL: https://api.obuma.cl/v1.0/
- Venta fields use venta_* prefix (venta_id, venta_neto, venta_iva, venta_total, venta_costo, venta_utilidad, venta_anulada)
- Document types: 33=Factura Electr., 34=Factura Exenta, 39=Boleta Electr., 61=Nota Credito
- 2 endpoints return 404: comprasDteRecibidos.list.json, comprasGastosMenores.list.json (posiblemente no habilitados en la cuenta)
