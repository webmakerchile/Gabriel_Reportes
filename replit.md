# BI Platform - Gabriel Hoyos

## Overview
Plataforma de Business Intelligence para Gabriel Hoyos, quien gestiona múltiples clientes a través del ERP Obuma. El sistema permite auditar y reportar la rentabilidad de operaciones.

## Architecture
- **Backend**: FastAPI (puerto 8000) - API RESTful con todos los endpoints de negocio
- **Frontend**: Streamlit (puerto 5000) - Dashboard interactivo de control
- **Database**: PostgreSQL - Single Source of Truth con tablas históricas
- **ETL**: Módulo Python para consumir API de Obuma (ventas, productos, compras, contabilidad)
- **Scheduler**: APScheduler - Generación automática de reportes Excel a las 23:50 hora Chile
- **Reports**: openpyxl - Generación de reportes Excel profesionales

## Project Structure
```
main.py                     # Entry point - inicia FastAPI + Streamlit
src/
  config.py                 # Configuración y variables de entorno
  database.py               # Conexión SQLAlchemy a PostgreSQL
  scheduler.py              # Tarea programada diaria 23:50
  models/
    models.py               # Modelos SQLAlchemy (multi-tenant)
  etl/
    obuma_client.py          # Cliente HTTP para API Obuma
    sync_service.py          # Servicio de sincronización y auditoría
  api/
    main.py                 # Endpoints FastAPI
  reports/
    excel_generator.py       # Generador de reportes Excel
  dashboard/
    app.py                  # Dashboard Streamlit
reports/                    # Directorio de reportes generados
```

## Key Features
1. **ETL Obuma**: Sincronización de ventas, productos, compras, contabilidad
2. **Tablas Históricas**: ventas_historico, costos_historico, compras_historico
3. **Multi-Tenant**: Tabla clientes_finales con relaciones a transacciones
4. **Cálculo Margen Neto**: Cruce ventas vs costos de adquisición
5. **Auditoría**: Comparación totales API vs PostgreSQL
6. **Reportes Excel**: Generación automática diaria a las 23:50 Chile
7. **Dashboard**: Métricas, gráficos ingresos vs egresos, gestión de reportes

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection
- `OBUMA_API_KEY` - API key for Obuma ERP
- `OBUMA_BASE_URL` - Base URL for Obuma API
- `TZ` - Timezone (America/Santiago)

## Running
- `python main.py` starts both FastAPI (port 8000) and Streamlit (port 5000)
