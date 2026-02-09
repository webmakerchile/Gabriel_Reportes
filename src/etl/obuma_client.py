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

    async def get_ventas(self, params: dict = None) -> dict:
        return await self._get("ventas.list.json", params)

    async def get_productos(self, params: dict = None) -> dict:
        return await self._get("productos.list.json", params)

    async def get_compras(self, params: dict = None) -> dict:
        return await self._get("comprasOc.list.json", params)

    async def get_contabilidad(self, fecha_desde: str = None) -> dict:
        params = {"mostrar_detalle": 1}
        if fecha_desde:
            params["fecha_desde"] = fecha_desde
        return await self._get("contabilidad.listDiario.json", params)

    async def get_clientes(self, params: dict = None) -> dict:
        return await self._get("clientes.list.json", params)

    async def get_categorias_productos(self) -> dict:
        return await self._get("productosCategorias.list.json")
