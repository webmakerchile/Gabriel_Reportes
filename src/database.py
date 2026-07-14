from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,
    pool_timeout=30,
    # values_plus_batch: los UPDATE/DELETE en executemany (p.ej.
    # bulk_update_mappings de los syncs) se agrupan con
    # psycopg2.extras.execute_batch en paginas, en vez de UN viaje de red
    # POR FILA. Con la DB remota de produccion (~70ms RTT) esto era el
    # cuello de botella real: 62.932 updates de ventas = ~80 min; en lotes
    # de 500 quedan ~126 viajes = un par de minutos.
    executemany_mode="values_plus_batch",
    executemany_batch_page_size=500,
    connect_args={
        "options": "-c statement_timeout=120000",
        # TCP keepalives: evita que NAT/proxies maten en silencio la
        # conexion mientras un sync pasa varios minutos descargando
        # paginas del API de Obuma sin tocar la DB (causa del
        # "SSL connection has been closed unexpectedly" del 14/07/2026).
        "keepalives": 1,
        "keepalives_idle": 60,
        "keepalives_interval": 20,
        "keepalives_count": 5,
    },
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
