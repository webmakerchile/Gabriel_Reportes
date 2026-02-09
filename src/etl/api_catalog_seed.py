import logging
from src.models.models import ObumaApiEndpoint

logger = logging.getLogger(__name__)

API_CATALOG = [
    {
        "categoria": "Clientes",
        "categoria_orden": 2,
        "endpoints": [
            {
                "nombre": "API : Clientes",
                "endpoint_url": "/clientes.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar, buscar, crear y actualizar clientes. Endpoints: list, findById, findByRut, findByExtranjeroId, create, update, updateClave",
                "parametros": "id, cliente_rut, cliente_extranjero, cliente_razon_social, cliente_email, estado",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/156/api--clientes",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "API : Clientes Contactos",
                "endpoint_url": "/clientesContactos.listAll.json",
                "metodo_http": "GET",
                "descripcion": "Listar contactos por cliente, listar todos los contactos, obtener contacto por ID. Endpoints: list/{id}, listAll, findById/{id}",
                "parametros": "RecursoId (ID del cliente)",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/592/api--clientes-contactos",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "API : Clientes Direcciones",
                "endpoint_url": "/clientesDirecciones.listAll.json",
                "metodo_http": "GET",
                "descripcion": "Listar direcciones por cliente, listar todas las direcciones, obtener direccion por ID. Endpoints: list/{id}, listAll, findById/{id}",
                "parametros": "RecursoId (ID del cliente)",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/593/api--clientes-direcciones",
                "implementado": True,
                "sync_habilitado": True,
            },
        ]
    },
    {
        "categoria": "Proveedores",
        "categoria_orden": 3,
        "endpoints": [
            {
                "nombre": "API : Proveedores",
                "endpoint_url": "/proveedores.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar, buscar por ID/RUT, crear y actualizar proveedores. Endpoints: list, findById/{id}, findByRut/{rut}, create, update",
                "parametros": "Sin parametros requeridos para listar",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/157/api--proveedores",
                "implementado": True,
                "sync_habilitado": True,
            },
        ]
    },
    {
        "categoria": "Productos",
        "categoria_orden": 4,
        "endpoints": [
            {
                "nombre": "API : Productos",
                "endpoint_url": "/productos.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar productos con categorias, subcategorias, fabricantes, precios. Sub-endpoints: productosCategorias, productosSubCategorias, productosFabricantes, productosImagenes, productosConsultaPrecios",
                "parametros": "id, tipo, codigo_sku, codigo_barra, categoria, subcategoria, fabricante, activo",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/13/api--productos",
                "implementado": True,
                "sync_habilitado": True,
                "notas": "Sync incluye: productos, categorias, subcategorias, fabricantes, precios",
            },
        ]
    },
    {
        "categoria": "Empleados",
        "categoria_orden": 5,
        "endpoints": [
            {
                "nombre": "API : Empleados",
                "endpoint_url": "/empleados.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar todos los empleados, activos, inactivos, usuarios activos. Buscar por ID o RUT. Endpoints: list, listActivos, listInactivos, listUsuarios, findById/{id}, findByRut/{rut}",
                "parametros": "Sin parametros requeridos para listar",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/158/api--empleados",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "API : Remuneraciones",
                "endpoint_url": "/remuneraciones.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar remuneraciones de empleados",
                "parametros": "Consultar documentacion",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/741/api--remuneraciones",
                "implementado": True,
                "sync_habilitado": True,
            },
        ]
    },
    {
        "categoria": "Ventas",
        "categoria_orden": 6,
        "endpoints": [
            {
                "nombre": "API : Ventas",
                "endpoint_url": "/ventas.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar ventas con filtros avanzados, items, referencias. Sync incluye ventas + items detallados",
                "parametros": "id_dcto_desde, tipo_dcto, folio_dcto, external_id, mes, ano, fecha, fecha_desde, fecha_hasta, total, total_pagado, total_por_pagar, cliente, cliente_rut, sucursal, bodega, usuario, vendedor",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/160/api--ventas",
                "implementado": True,
                "sync_habilitado": True,
                "notas": "Sync incluye: ventas + ventas items detallados",
            },
            {
                "nombre": "API : Ventas > Cotizaciones",
                "endpoint_url": "/ventasCotizaciones.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar cotizaciones, items, ultimo folio, buscar por ID. Crear, actualizar, eliminar, enviar email, actualizar estado",
                "parametros": "id_dcto_desde, folio_dcto, external_id, mes, ano, fecha, fecha_desde, fecha_hasta, total, cliente, cliente_rut, sucursal, usuario",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/332/api--ventas--cotizaciones",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "API : Ventas > Cobros",
                "endpoint_url": "/ventasCobros.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar cobros registrados, crear nuevos cobros para documentos de venta",
                "parametros": "mes, ano, fecha_ingreso_desde, fecha_ingreso_hasta, origen, compra_id",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/333/api--ventas--cobros",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "API : Ventas > Enviar Ventas a OBUMA via API",
                "endpoint_url": "/ventas.create.json",
                "metodo_http": "POST",
                "descripcion": "Crear documentos de venta en Obuma via API. Permite enviar facturas, boletas y otros DTE directamente",
                "parametros": "Datos completos del documento de venta en JSON",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/141/api--ventas--enviar-ventas-a-obuma-via-api",
                "implementado": True,
                "sync_habilitado": False,
                "notas": "Endpoint de escritura - no requiere sync",
            },
            {
                "nombre": "API : Ventas > Consultar Boletas electronicas emitidas",
                "endpoint_url": "/ventas.list.json?tipo_dcto=39",
                "metodo_http": "GET",
                "descripcion": "Consultar boletas electronicas emitidas filtrando por tipo documento 39",
                "parametros": "tipo_dcto=39, mas filtros de ventas.list",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/142/api--ventas--consultar-boletas-electronicas-emitidas",
                "implementado": True,
                "sync_habilitado": False,
                "notas": "Incluido en sync de ventas con filtro tipo_dcto",
            },
            {
                "nombre": "API : Ventas > Consultar ventas por RUT cliente",
                "endpoint_url": "/ventas.listByCustomerRut.json",
                "metodo_http": "POST",
                "descripcion": "Consultar ventas emitidas filtradas por RUT del cliente",
                "parametros": "rutCliente, tipoBusqueda (all/periodo/folio), mes, ano, folio",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/143/api--ventas--consultar-ventas-emitidas-en-obuma-por-rut-del-cliente",
                "implementado": True,
                "sync_habilitado": False,
                "notas": "Consulta bajo demanda - datos incluidos en sync ventas",
            },
            {
                "nombre": "API : Ventas > Consultar DTE emitidos",
                "endpoint_url": "/ventas.listDte.json",
                "metodo_http": "GET",
                "descripcion": "Consultar documentos tributarios electronicos (DTE) emitidos",
                "parametros": "Filtros de DTE emitidos",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/591/api--ventas--consultar-dte-emitidos",
                "implementado": True,
                "sync_habilitado": True,
            },
        ]
    },
    {
        "categoria": "Compras",
        "categoria_orden": 7,
        "endpoints": [
            {
                "nombre": "API : Compras",
                "endpoint_url": "/compras.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar compras con filtros avanzados, crear y actualizar compras con detalle de items",
                "parametros": "id_dcto_desde, tipo_dcto, folio_dcto, mes_contable, ano_contable, fecha, fecha_desde, fecha_hasta, total, total_pagado, total_por_pagar, proveedor, proveedor_rut, sucursal, bodega",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/159/api--compras",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "API : Compras > Pagos",
                "endpoint_url": "/comprasPagos.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar pagos de compras con filtros. Origenes: compras, boletas-honorarios, pago-iva, remuneraciones, anticipos-proveedores, pago-imposiciones",
                "parametros": "mes, ano, fecha_ingreso_desde, fecha_ingreso_hasta, origen, compra_id. Limite 500 registros",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/596/api--compras--pagos",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "API : Compras OC",
                "endpoint_url": "/comprasOc.list.json",
                "metodo_http": "GET",
                "descripcion": "Ordenes de compra: listar, items, ultimo folio, buscar por ID, crear, actualizar",
                "parametros": "id_dcto_desde, folio_dcto, mes, ano, fecha, fecha_desde, fecha_hasta, total, proveedor, sucursal, bodega, estado, forma_pago, metodo_despacho, moneda, centro_costo, concepto_gasto",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/331/api--compras-oc",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "API : Compras DTE recibidos",
                "endpoint_url": "/comprasDteRecibidos.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar documentos tributarios electronicos (DTE) recibidos de proveedores",
                "parametros": "Filtros de DTE recibidos",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/589/api--compras-dte-recibidos",
                "implementado": True,
                "sync_habilitado": True,
            },
        ]
    },
    {
        "categoria": "Contabilidad",
        "categoria_orden": 8,
        "endpoints": [
            {
                "nombre": "API : Contabilidad",
                "endpoint_url": "/contabilidad.listDiario.json",
                "metodo_http": "GET",
                "descripcion": "Consultar libro diario de contabilidad con detalle de asientos contables",
                "parametros": "mostrar_detalle=1, fecha_desde",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/418/api--contabilidad",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "API : Compras GASTOS menores",
                "endpoint_url": "/comprasGastosMenores.list.json",
                "metodo_http": "GET",
                "descripcion": "Listar gastos menores registrados en el modulo de compras",
                "parametros": "Consultar documentacion",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/590/api--compras-gastos-menores",
                "implementado": True,
                "sync_habilitado": True,
            },
        ]
    },
    {
        "categoria": "Otros",
        "categoria_orden": 9,
        "endpoints": [
            {
                "nombre": "Varios",
                "endpoint_url": None,
                "metodo_http": "-",
                "descripcion": "Endpoints varios y utilidades de la API de Obuma",
                "parametros": None,
                "doc_url": "https://www.obuma.cl/ayuda/articulo/334/varios",
                "implementado": False,
                "sync_habilitado": False,
            },
            {
                "nombre": "General",
                "endpoint_url": None,
                "metodo_http": "-",
                "descripcion": "Configuraciones generales de la API",
                "parametros": None,
                "doc_url": "https://www.obuma.cl/ayuda/articulo/671/general",
                "implementado": False,
                "sync_habilitado": False,
            },
            {
                "nombre": "CRM manejo de leads por API",
                "endpoint_url": "/crm.list.json",
                "metodo_http": "GET",
                "descripcion": "Gestion de leads y oportunidades de venta via API del CRM de Obuma",
                "parametros": "Consultar documentacion",
                "doc_url": "https://www.obuma.cl/ayuda/articulo/545/crm-manejo-de-leads-por-api",
                "implementado": True,
                "sync_habilitado": True,
            },
            {
                "nombre": "Conectar OBUMA ERP con POWER BI",
                "endpoint_url": None,
                "metodo_http": "-",
                "descripcion": "Guia para conectar Obuma con Microsoft Power BI para visualizacion de datos",
                "parametros": None,
                "doc_url": "https://www.obuma.cl/ayuda/articulo/547/conectar-obuma-erp-con-power-bi",
                "implementado": False,
                "sync_habilitado": False,
                "notas": "Referencia / Documentacion",
            },
            {
                "nombre": "SAT - Modulo produccion",
                "endpoint_url": None,
                "metodo_http": "-",
                "descripcion": "API para el modulo SAT de produccion",
                "parametros": None,
                "doc_url": "https://www.obuma.cl/ayuda/articulo/586/sat--modulo-produccion",
                "implementado": False,
                "sync_habilitado": False,
            },
            {
                "nombre": "Proyectos - Modulo de proyectos",
                "endpoint_url": None,
                "metodo_http": "-",
                "descripcion": "API para el modulo de gestion de proyectos",
                "parametros": None,
                "doc_url": "https://www.obuma.cl/ayuda/articulo/587/proyectos--modulo-de-proyectos",
                "implementado": False,
                "sync_habilitado": False,
            },
            {
                "nombre": "SAT - Modulo OT SAT",
                "endpoint_url": None,
                "metodo_http": "-",
                "descripcion": "API para el modulo de ordenes de trabajo SAT",
                "parametros": None,
                "doc_url": "https://www.obuma.cl/ayuda/articulo/588/sat--modulo-ot-sat",
                "implementado": False,
                "sync_habilitado": False,
            },
        ]
    },
    {
        "categoria": "Webhooks",
        "categoria_orden": 10,
        "endpoints": [
            {
                "nombre": "Introduccion a los webhooks en OBUMA ERP",
                "endpoint_url": None,
                "metodo_http": "-",
                "descripcion": "Guia introductoria sobre webhooks en Obuma: recibir notificaciones en tiempo real de eventos del ERP",
                "parametros": None,
                "doc_url": "https://www.obuma.cl/ayuda/articulo/708/introduccion-a-los-webhooks-en-obuma-erp",
                "implementado": False,
                "sync_habilitado": False,
                "notas": "Referencia / Documentacion",
            },
            {
                "nombre": "Como crear un webhook en OBUMA ERP",
                "endpoint_url": None,
                "metodo_http": "-",
                "descripcion": "Tutorial paso a paso para configurar webhooks y recibir eventos en tu aplicacion",
                "parametros": None,
                "doc_url": "https://www.obuma.cl/ayuda/articulo/709/como-crear-un-webhook-en-obuma-erp",
                "implementado": False,
                "sync_habilitado": False,
                "notas": "Referencia / Documentacion",
            },
            {
                "nombre": "Listado de eventos disponibles",
                "endpoint_url": None,
                "metodo_http": "-",
                "descripcion": "Catalogo completo de eventos que pueden disparar webhooks: ventas, compras, clientes, productos, etc.",
                "parametros": None,
                "doc_url": "https://www.obuma.cl/ayuda/articulo/710/listado-de-eventos-disponibles",
                "implementado": False,
                "sync_habilitado": False,
                "notas": "Referencia / Documentacion",
            },
        ]
    },
]


def seed_api_catalog(db):
    existing = db.query(ObumaApiEndpoint).count()
    if existing > 0:
        for cat in API_CATALOG:
            for ep in cat["endpoints"]:
                entry = db.query(ObumaApiEndpoint).filter(
                    ObumaApiEndpoint.nombre == ep["nombre"]
                ).first()
                if entry:
                    entry.implementado = ep.get("implementado", False)
                    entry.sync_habilitado = ep.get("sync_habilitado", False)
                    entry.endpoint_url = ep.get("endpoint_url") or entry.endpoint_url
                    entry.notas = ep.get("notas") or entry.notas
                    if ep.get("implementado") and not entry.estado.startswith("sincronizado"):
                        entry.estado = "implementado"
                else:
                    entry = ObumaApiEndpoint(
                        categoria=cat["categoria"],
                        categoria_orden=cat["categoria_orden"],
                        nombre=ep["nombre"],
                        endpoint_url=ep.get("endpoint_url"),
                        metodo_http=ep.get("metodo_http", "GET"),
                        descripcion=ep.get("descripcion"),
                        parametros=ep.get("parametros"),
                        doc_url=ep.get("doc_url"),
                        implementado=ep.get("implementado", False),
                        sync_habilitado=ep.get("sync_habilitado", False),
                        estado="implementado" if ep.get("implementado") else "disponible",
                        notas=ep.get("notas"),
                    )
                    db.add(entry)
        db.commit()
        logger.info(f"API catalog updated ({existing} entries)")
        return existing

    count = 0
    for cat in API_CATALOG:
        for ep in cat["endpoints"]:
            entry = ObumaApiEndpoint(
                categoria=cat["categoria"],
                categoria_orden=cat["categoria_orden"],
                nombre=ep["nombre"],
                endpoint_url=ep.get("endpoint_url"),
                metodo_http=ep.get("metodo_http", "GET"),
                descripcion=ep.get("descripcion"),
                parametros=ep.get("parametros"),
                doc_url=ep.get("doc_url"),
                implementado=ep.get("implementado", False),
                sync_habilitado=ep.get("sync_habilitado", False),
                estado="implementado" if ep.get("implementado") else "disponible",
                notas=ep.get("notas"),
            )
            db.add(entry)
            count += 1

    db.commit()
    logger.info(f"Seeded {count} API catalog entries")
    return count
