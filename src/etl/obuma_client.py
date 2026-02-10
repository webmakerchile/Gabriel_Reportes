import asyncio
import httpx
import logging
from src.config import OBUMA_API_KEY, OBUMA_BASE_URL

logger = logging.getLogger(__name__)

class ObumaClient:
    def __init__(self):
        self.base_url = OBUMA_BASE_URL
        self.headers = {"access-token": OBUMA_API_KEY}
        self.timeout = 30.0

    async def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                result = response.json()
                if result is None:
                    return {"data": [], "data-total-items": 0}
                return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} on {endpoint}: {e}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error fetching {endpoint}: {e}")
            return {"error": str(e)}

    async def _post(self, endpoint: str, data: dict = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers={**self.headers, "Content-Type": "application/json"}, json=data)
                response.raise_for_status()
                result = response.json()
                if result is None:
                    return {"data": [], "data-total-items": 0}
                return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} on {endpoint}: {e}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error posting {endpoint}: {e}")
            return {"error": str(e)}

    async def _get_all_pages(self, endpoint: str, params: dict = None) -> dict:
        merged_params = dict(params or {})
        merged_params["page"] = 1
        first_page = await self._get(endpoint, merged_params)
        if isinstance(first_page, dict) and "error" in first_page:
            return first_page
        all_items = list(first_page.get("data", []) if isinstance(first_page, dict) else [])
        total_pages = int(first_page.get("data-total-pages", 1)) if isinstance(first_page, dict) else 1
        total_items = int(first_page.get("data-total-items", len(all_items))) if isinstance(first_page, dict) else len(all_items)
        logger.info(f"Pagination: {endpoint} - page 1/{total_pages}, total items: {total_items}")
        for page in range(2, total_pages + 1):
            await asyncio.sleep(0.1)
            merged_params["page"] = page
            page_data = await self._get(endpoint, merged_params)
            if isinstance(page_data, dict) and "error" in page_data:
                logger.error(f"Error fetching {endpoint} page {page}: {page_data}")
                continue
            page_items = page_data.get("data", []) if isinstance(page_data, dict) else []
            all_items.extend(page_items)
            if page % 10 == 0:
                logger.info(f"Pagination: {endpoint} - page {page}/{total_pages}, accumulated {len(all_items)} items")
        logger.info(f"Pagination complete: {endpoint} - {len(all_items)} total items fetched across {total_pages} pages")
        return {"data": all_items, "data-total-items": total_items}

    async def get_clientes(self, params: dict = None) -> dict:
        return await self._get("clientes.list.json", params)

    async def get_cliente_by_id(self, recurso_id: str) -> dict:
        return await self._get(f"clientes.findById.json/{recurso_id}")

    async def get_cliente_by_rut(self, rut: str) -> dict:
        return await self._get(f"clientes.findByRut.json/{rut}")

    async def get_clientes_contactos(self, cliente_id: str) -> dict:
        return await self._get(f"clientesContactos.list.json/{cliente_id}")

    async def get_clientes_contactos_all(self) -> dict:
        return await self._get("clientesContactos.listAll.json")

    async def get_clientes_direcciones(self, cliente_id: str) -> dict:
        return await self._get(f"clientesDirecciones.list.json/{cliente_id}")

    async def get_clientes_direcciones_all(self) -> dict:
        return await self._get("clientesDirecciones.listAll.json")

    async def get_proveedores(self, params: dict = None) -> dict:
        return await self._get("proveedores.list.json", params)

    async def get_proveedor_by_id(self, recurso_id: str) -> dict:
        return await self._get(f"proveedores.findById.json/{recurso_id}")

    async def get_proveedor_by_rut(self, rut: str) -> dict:
        return await self._get(f"proveedores.findByRut.json/{rut}")

    async def get_productos(self, params: dict = None) -> dict:
        return await self._get("productos.list.json", params)

    async def get_producto_by_id(self, recurso_id: str) -> dict:
        return await self._get(f"productos.findById.json/{recurso_id}")

    async def get_productos_precios(self, params: dict = None) -> dict:
        return await self._get("productosConsultaPrecios.list.json", params)

    async def get_categorias_productos(self) -> dict:
        return await self._get("productosCategorias.list.json")

    async def get_subcategorias_productos(self) -> dict:
        return await self._get("productosSubCategorias.list.json")

    async def get_fabricantes_productos(self) -> dict:
        return await self._get("productosFabricantes.list.json")

    async def get_empleados(self, params: dict = None) -> dict:
        return await self._get("empleados.list.json", params)

    async def get_empleados_activos(self) -> dict:
        return await self._get("empleados.listActivos.json")

    async def get_empleado_by_id(self, recurso_id: str) -> dict:
        return await self._get(f"empleados.findById.json/{recurso_id}")

    async def get_empleado_by_rut(self, rut: str) -> dict:
        return await self._get(f"empleados.findByRut.json/{rut}")

    async def get_remuneraciones(self, params: dict = None) -> dict:
        return await self._get("remuneraciones.list.json", params)

    async def get_ventas(self, params: dict = None) -> dict:
        return await self._get("ventas.list.json", params)

    async def get_venta_by_id(self, recurso_id: str) -> dict:
        return await self._get(f"ventas.findById.json/{recurso_id}")

    async def get_ventas_items(self, params: dict = None) -> dict:
        return await self._get("ventas.listItems.json", params)

    async def get_ventas_referencias(self, params: dict = None) -> dict:
        return await self._get("ventas.listReferencias.json", params)

    async def get_ventas_cotizaciones(self, params: dict = None) -> dict:
        return await self._get("ventasCotizaciones.list.json", params)

    async def get_ventas_cobros(self, params: dict = None) -> dict:
        return await self._get("ventasCobros.list.json", params)

    async def get_ventas_by_customer_rut(self, rut: str, tipo: str = "all") -> dict:
        return await self._post("ventas.listByCustomerRut.json", {"rutCliente": rut, "tipoBusqueda": tipo})

    async def get_ventas_dte(self, params: dict = None) -> dict:
        return await self._get("ventas.listDte.json", params)

    async def get_ventas_all_pages(self, params: dict = None) -> dict:
        return await self._get_all_pages("ventas.list.json", params)

    async def get_ventas_items_all_pages(self, params: dict = None) -> dict:
        return await self._get_all_pages("ventas.listItems.json", params)

    async def get_ventas_cobros_all_pages(self, params: dict = None) -> dict:
        return await self._get_all_pages("ventasCobros.list.json", params)

    async def get_ventas_cotizaciones_all_pages(self, params: dict = None) -> dict:
        return await self._get_all_pages("ventasCotizaciones.list.json", params)

    async def get_ventas_dte_all_pages(self, params: dict = None) -> dict:
        return await self._get_all_pages("ventas.listDte.json", params)

    async def get_boletas_electronicas(self, params: dict = None) -> dict:
        p = params or {}
        p["tipo_dcto"] = 39
        return await self._get("ventas.list.json", p)

    async def get_compras(self, params: dict = None) -> dict:
        return await self._get("compras.list.json", params)

    async def get_compras_oc(self, params: dict = None) -> dict:
        return await self._get("comprasOc.list.json", params)

    async def get_compras_pagos(self, params: dict = None) -> dict:
        return await self._get("comprasPagos.list.json", params)

    async def get_compras_dte_recibidos(self, params: dict = None) -> dict:
        return await self._get("comprasDteRecibidos.list.json", params)

    async def get_contabilidad(self, fecha_desde: str = None) -> dict:
        params = {"mostrar_detalle": 1}
        if fecha_desde:
            params["fecha_desde"] = fecha_desde
        return await self._get("contabilidad.listDiario.json", params)

    async def get_gastos_menores(self, params: dict = None) -> dict:
        return await self._get("comprasGastosMenores.list.json", params)

    async def get_crm_leads(self, params: dict = None) -> dict:
        return await self._get("crm.list.json", params)

    async def test_endpoint(self, endpoint_url: str) -> dict:
        if endpoint_url and not endpoint_url.startswith("/"):
            endpoint_url = "/" + endpoint_url
        clean = endpoint_url.lstrip("/") if endpoint_url else ""
        if "{" in clean:
            clean = clean.split("{")[0].rstrip("/")
        if not clean:
            return {"error": "No endpoint URL configured"}
        return await self._get(clean)
