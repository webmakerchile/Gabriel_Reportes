from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, Date, BigInteger, Index, UniqueConstraint
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
    giro = Column(String(255), nullable=True)
    comuna = Column(String(100), nullable=True)
    ciudad = Column(String(100), nullable=True)
    activo = Column(Boolean, default=True)
    obuma_id = Column(String(50), nullable=True)
    data_json = Column(Text, nullable=True)
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
    vendedor_id = Column(String(50), nullable=True)
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
    total_pagado = Column(Float, default=0)
    total_por_pagar = Column(Float, default=0)
    anulada = Column(Boolean, default=False)
    observacion = Column(Text, nullable=True)
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


class Proveedor(Base):
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    rut = Column(String(20), nullable=True)
    razon_social = Column(String(255), nullable=True)
    nombre_fantasia = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    direccion = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_proveedores_tenant_obuma", "tenant_id", "obuma_id", unique=True),
    )


class ClienteContacto(Base):
    __tablename__ = "clientes_contactos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    cliente_id_obuma = Column(String(50), nullable=True)
    nombre = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    cargo = Column(String(255), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class ClienteDireccion(Base):
    __tablename__ = "clientes_direcciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    cliente_id_obuma = Column(String(50), nullable=True)
    direccion = Column(Text, nullable=True)
    ciudad = Column(String(255), nullable=True)
    comuna = Column(String(255), nullable=True)
    region = Column(String(255), nullable=True)
    tipo = Column(String(50), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class Empleado(Base):
    __tablename__ = "empleados"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    rut = Column(String(20), nullable=True)
    nombre = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    cargo = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_empleados_tenant_obuma", "tenant_id", "obuma_id", unique=True),
    )


class Remuneracion(Base):
    __tablename__ = "remuneraciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    empleado_rut = Column(String(20), nullable=True)
    periodo = Column(String(20), nullable=True)
    total_haberes = Column(Float, default=0)
    total_descuentos = Column(Float, default=0)
    liquido = Column(Float, default=0)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class VentaItem(Base):
    __tablename__ = "ventas_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    venta_id_obuma = Column(String(50), nullable=True)
    producto_nombre = Column(String(255), nullable=True)
    producto_sku = Column(String(100), nullable=True)
    cantidad = Column(Float, default=0)
    precio_unitario = Column(Float, default=0)
    descuento = Column(Float, default=0)
    total = Column(Float, default=0)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class VentaCotizacion(Base):
    __tablename__ = "ventas_cotizaciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    folio = Column(String(50), nullable=True)
    fecha = Column(DateTime, nullable=True)
    cliente_rut = Column(String(20), nullable=True)
    cliente_nombre = Column(String(255), nullable=True)
    total = Column(Float, default=0)
    estado = Column(String(50), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class VentaCobro(Base):
    __tablename__ = "ventas_cobros"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    venta_id_obuma = Column(String(50), nullable=True)
    fecha = Column(DateTime, nullable=True)
    monto = Column(Float, default=0)
    forma_pago = Column(String(100), nullable=True)
    estado = Column(String(50), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class VentaDte(Base):
    __tablename__ = "ventas_dte"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    tipo_dcto = Column(String(50), nullable=True)
    folio = Column(String(50), nullable=True)
    fecha = Column(DateTime, nullable=True)
    rut_receptor = Column(String(20), nullable=True)
    razon_social = Column(String(255), nullable=True)
    monto_total = Column(Float, default=0)
    estado_sii = Column(String(100), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class CompraOC(Base):
    __tablename__ = "compras_oc"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    folio = Column(String(50), nullable=True)
    fecha = Column(DateTime, nullable=True)
    proveedor = Column(String(255), nullable=True)
    proveedor_rut = Column(String(20), nullable=True)
    total = Column(Float, default=0)
    estado = Column(String(50), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class CompraPago(Base):
    __tablename__ = "compras_pagos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    compra_id_obuma = Column(String(50), nullable=True)
    fecha = Column(DateTime, nullable=True)
    monto = Column(Float, default=0)
    forma_pago = Column(String(100), nullable=True)
    origen = Column(String(100), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class CompraDteRecibido(Base):
    __tablename__ = "compras_dte_recibidos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    tipo_dcto = Column(String(50), nullable=True)
    folio = Column(String(50), nullable=True)
    fecha = Column(DateTime, nullable=True)
    rut_emisor = Column(String(20), nullable=True)
    razon_social = Column(String(255), nullable=True)
    monto_total = Column(Float, default=0)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class GastoMenor(Base):
    __tablename__ = "gastos_menores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    fecha = Column(DateTime, nullable=True)
    descripcion = Column(Text, nullable=True)
    monto = Column(Float, default=0)
    categoria = Column(String(255), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class CrmLead(Base):
    __tablename__ = "crm_leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    nombre = Column(String(255), nullable=True)
    empresa = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    estado = Column(String(50), nullable=True)
    origen = Column(String(100), nullable=True)
    monto_estimado = Column(Float, default=0)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class ProductoCategoria(Base):
    __tablename__ = "producto_categorias"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    nombre = Column(String(255), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class ProductoSubCategoria(Base):
    __tablename__ = "producto_subcategorias"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    nombre = Column(String(255), nullable=True)
    categoria_id_obuma = Column(String(50), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class ProductoFabricante(Base):
    __tablename__ = "producto_fabricantes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    nombre = Column(String(255), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class ProductoPrecio(Base):
    __tablename__ = "producto_precios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    obuma_id = Column(String(50), nullable=True)
    producto_id_obuma = Column(String(50), nullable=True)
    producto_nombre = Column(String(255), nullable=True)
    precio = Column(Float, default=0)
    lista_precio = Column(String(100), nullable=True)
    data_json = Column(Text, nullable=True)
    sincronizado_at = Column(DateTime, server_default=func.now())


class ObumaApiEndpoint(Base):
    __tablename__ = "obuma_api_endpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    categoria = Column(String(100), nullable=False)
    categoria_orden = Column(Integer, default=0)
    nombre = Column(String(255), nullable=False)
    endpoint_url = Column(String(500), nullable=True)
    metodo_http = Column(String(10), default="GET")
    descripcion = Column(Text, nullable=True)
    parametros = Column(Text, nullable=True)
    doc_url = Column(String(500), nullable=True)
    implementado = Column(Boolean, default=False)
    sync_habilitado = Column(Boolean, default=False)
    ultima_sync = Column(DateTime, nullable=True)
    registros_sync = Column(Integer, default=0)
    estado = Column(String(50), default="disponible")
    notas = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class VendedorMeta(Base):
    __tablename__ = "vendedor_metas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    empleado_obuma_id = Column(String(50), nullable=False)
    anio = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)
    meta_repuestos = Column(Float, default=0)
    meta_maquinaria = Column(Float, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "empleado_obuma_id", "anio", "mes", name="uq_vendedor_meta_tenant_empleado_anio_mes"),
    )


class VendedorCartera(Base):
    __tablename__ = "vendedor_carteras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    empleado_obuma_id = Column(String(50), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes_finales.id"), nullable=False)
    fecha_asignacion = Column(Date, nullable=True)
    fecha_baja = Column(Date, nullable=True)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "empleado_obuma_id", "cliente_id", name="uq_vendedor_cartera_tenant_empleado_cliente"),
    )
