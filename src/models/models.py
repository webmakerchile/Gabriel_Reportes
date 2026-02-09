from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, Date, BigInteger, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(255), nullable=False)
    rut_empresa = Column(String(20), unique=True, nullable=True)
    email = Column(String(255), nullable=True)
    api_key = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    clientes = relationship("ClienteFinal", back_populates="tenant")
    productos = relationship("Producto", back_populates="tenant")
    ventas = relationship("VentaHistorico", back_populates="tenant")
    compras = relationship("CompraHistorico", back_populates="tenant")
    contabilidad = relationship("ContabilidadHistorico", back_populates="tenant")


class ClienteFinal(Base):
    __tablename__ = "clientes_finales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    rut = Column(String(20), nullable=True)
    nombre = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    direccion = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_clientes_tenant_rut", "tenant_id", "rut", unique=True),
    )

    tenant = relationship("Tenant", back_populates="clientes")
    ventas = relationship("VentaHistorico", back_populates="cliente")
    compras = relationship("CompraHistorico", back_populates="cliente")


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    nombre = Column(String(255), nullable=False)
    sku = Column(String(100), nullable=True)
    categoria = Column(String(255), nullable=True)
    precio_venta = Column(Float, default=0)
    costo = Column(Float, default=0)
    stock_actual = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=0)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_productos_tenant_obuma", "tenant_id", "obuma_id", unique=True),
    )

    tenant = relationship("Tenant", back_populates="productos")
    costos = relationship("CostoHistorico", back_populates="producto")


class VentaHistorico(Base):
    __tablename__ = "ventas_historico"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    cliente_id = Column(Integer, ForeignKey("clientes_finales.id"), nullable=True)
    fecha = Column(DateTime, nullable=True)
    tipo_documento = Column(String(50), nullable=True)
    folio = Column(String(50), nullable=True)
    subtotal = Column(Float, default=0)
    impuestos = Column(Float, default=0)
    total = Column(Float, default=0)
    estado = Column(String(50), nullable=True)
    detalle = Column(Text, nullable=True)
    costo_total = Column(Float, default=0)
    margen_neto = Column(Float, default=0)
    sincronizado_at = Column(DateTime, server_default=func.now())

    tenant = relationship("Tenant", back_populates="ventas")
    cliente = relationship("ClienteFinal", back_populates="ventas")


class CompraHistorico(Base):
    __tablename__ = "compras_historico"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    cliente_id = Column(Integer, ForeignKey("clientes_finales.id"), nullable=True)
    fecha = Column(DateTime, nullable=True)
    proveedor = Column(String(255), nullable=True)
    folio = Column(String(50), nullable=True)
    total = Column(Float, default=0)
    estado = Column(String(50), nullable=True)
    detalle = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())

    tenant = relationship("Tenant", back_populates="compras")
    cliente = relationship("ClienteFinal", back_populates="compras")


class CostoHistorico(Base):
    __tablename__ = "costos_historico"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    costo_unitario = Column(Float, default=0)
    cantidad = Column(Integer, default=0)
    costo_total = Column(Float, default=0)
    fecha = Column(DateTime, nullable=True)
    fuente = Column(String(50), default="obuma")
    sincronizado_at = Column(DateTime, server_default=func.now())

    producto = relationship("Producto", back_populates="costos")


class ContabilidadHistorico(Base):
    __tablename__ = "contabilidad_historico"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    fecha = Column(Date, nullable=True)
    cuenta = Column(String(255), nullable=True)
    descripcion = Column(Text, nullable=True)
    debe = Column(Float, default=0)
    haber = Column(Float, default=0)
    tipo = Column(String(50), nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())

    tenant = relationship("Tenant", back_populates="contabilidad")


class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    endpoint = Column(String(100), nullable=False)
    registros_api = Column(Integer, default=0)
    registros_db = Column(Integer, default=0)
    discrepancias = Column(Integer, default=0)
    total_api = Column(Float, default=0)
    total_db = Column(Float, default=0)
    estado = Column(String(50), default="ok")
    detalle = Column(Text, nullable=True)
    ejecutado_at = Column(DateTime, server_default=func.now())


class ReporteGenerado(Base):
    __tablename__ = "reportes_generados"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    nombre_archivo = Column(String(255), nullable=False)
    tipo = Column(String(50), default="diario")
    fecha_reporte = Column(Date, nullable=True)
    archivo_datos = Column(Text, nullable=True)
    ruta_archivo = Column(String(500), nullable=True)
    generado_at = Column(DateTime, server_default=func.now())
