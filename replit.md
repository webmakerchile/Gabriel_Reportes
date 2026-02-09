# BI Platform - Gabriel Hoyos

## Overview
Plataforma de Business Intelligence para Gabriel Hoyos, quien gestiona multiples clientes a traves del ERP Obuma. El sistema permite auditar y reportar la rentabilidad de operaciones.

## Architecture
- **Backend**: FastAPI (puerto 8000) - API RESTful con todos los endpoints de negocio
- **Frontend**: Streamlit (puerto 5000) - Dashboard interactivo de control
- **Database**: PostgreSQL - Single Source of Truth con tablas historicas
- **ETL**: Modulo Python para consumir API de Obuma (ventas, productos, compras, contabilidad, clientes)
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
    models.py               # Modelos SQLAlchemy (multi-tenant + API catalog)
  etl/
    obuma_client.py          # Cliente HTTP para API Obuma (30+ metodos)
    sync_service.py          # Servicio de sincronizacion y auditoria
    api_catalog_seed.py      # Seed de catalogo API Obuma (30 endpoints)
  api/
    main.py                 # Endpoints FastAPI
  reports/
    excel_generator.py       # Generador de reportes Excel
  dashboard/
    app.py                  # Dashboard Streamlit (8 secciones)
reports/                    # Directorio de reportes generados
```

## Database Models
- **Tenant**: Multi-tenant support
- **ClienteFinal**: Clientes sincronizados desde Obuma
- **Producto**: Productos con SKU, precios, costos, stock
- **VentaHistorico**: Ventas con neto, IVA, total, costo, margen, pagado, por pagar, anulada
- **CompraHistorico**: Compras con proveedor, folio, total
- **CostoHistorico**: Historial de costos por producto
- **ContabilidadHistorico**: Libro diario (debe/haber)
- **SyncLog**: Log de sincronizaciones con API
- **ReporteGenerado**: Reportes Excel generados
- **ObumaApiEndpoint**: Catalogo completo de endpoints API Obuma (30 registros)

## Key Features
1. **ETL Obuma**: Sincronizacion de ventas, productos, compras, contabilidad, clientes
2. **Tablas Historicas**: ventas_historico, costos_historico, compras_historico
3. **Multi-Tenant**: Tabla clientes_finales con relaciones a transacciones
4. **Calculo Margen Neto**: Cruce ventas vs costos de adquisicion
5. **Auditoria**: Comparacion totales API vs PostgreSQL
6. **Reportes Excel**: Generacion automatica diaria a las 23:50 Chile
7. **Dashboard**: 8 secciones - Dashboard, Ventas, Clientes, Contabilidad, API Obuma, Reportes, Sincronizacion, Auditoria
8. **Catalogo API**: 30 endpoints Obuma registrados con estado (implementado, sync activo, disponible, referencia)
9. **Obuma Client**: 30+ metodos HTTP para todos los endpoints conocidos de Obuma

## API Obuma Categories (30 endpoints)
- Clientes: list, contactos, direcciones
- Proveedores: list, findById, findByRut
- Productos: list, categorias, subcategorias, fabricantes, precios, imagenes
- Empleados: list, activos, remuneraciones
- Ventas: list, items, cotizaciones, cobros, DTE, boletas, por RUT
- Compras: list, pagos, OC, DTE recibidos
- Contabilidad: libro diario, gastos menores
- Otros: CRM leads, Power BI, SAT, Proyectos
- Webhooks: introduccion, crear webhook, eventos

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
