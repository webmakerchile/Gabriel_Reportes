"""Tests del sync BULK de clientes (Fase 6) y del barrido batch de cartera.

Blindan la reescritura de sync_clientes / _sync_cartera_from_clientes que
elimino el patron fila-por-fila (N+1). Corren contra sqlite in-memory con el
esquema real (Base.metadata.create_all) y el cliente Obuma mockeado; ningun
test toca la red ni Postgres.

Semantica que DEBE preservarse (identica a la version fila-por-fila):
  - Colision de RUT -> rut sintetico OBU-{obuma_id} (el primero en llegar se
    queda con el rut real).
  - Campos vacios del API NO pisan valores existentes en DB.
  - RUT invalido en update -> se mantiene el rut existente.
  - `activo` viene del campo cliente_activo del API.
  - Fallback fila-por-fila ante IntegrityError en un lote (concurrencia).
  - Cartera: desactiva asignaciones de otros vendedores / clientes inactivos,
    crea la del vendedor correcto, y RESPETA desactivaciones manuales.
"""
import asyncio
import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.models import ClienteFinal, VendedorCartera
from src.etl.sync_service import SyncService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    """Sesion sqlite in-memory con soporte real de SAVEPOINT (begin_nested).

    pysqlite no soporta savepoints con la configuracion por defecto; se aplica
    la receta oficial de SQLAlchemy (isolation_level=None + BEGIN explicito).
    """
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _do_connect(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _do_begin(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def service(db):
    """SyncService con tenant default creado y cliente Obuma mockeado."""
    svc = SyncService(db)  # crea el tenant default via _get_default_tenant_id
    svc.client = MagicMock()
    return svc


def _mock_api(service, items):
    async def _coro(*_a, **_k):
        return {"data": items}

    service.client.get_clientes_all_pages = _coro


def _run(service):
    return asyncio.run(service.sync_clientes())


def _item(obuma_id, rut="", nombre="Cliente Test", activo="1", **extra):
    base = {
        "cliente_id": obuma_id,
        "cliente_rut": rut,
        "cliente_razon_social": nombre,
        "cliente_activo": activo,
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# sync_clientes: inserts
# ---------------------------------------------------------------------------

def test_insert_nuevos_clientes_con_rut_valido(service, db):
    _mock_api(service, [
        _item("101", rut="11.111.111-1", nombre="Alfa"),
        _item("102", rut="22.222.222-2", nombre="Beta"),
        _item("103", rut="33.333.333-3", nombre="Gamma", activo="0"),
    ])
    result = _run(service)

    assert result["synced"] == 3
    assert result["skipped"] == 0
    rows = {c.obuma_id: c for c in db.query(ClienteFinal).all()}
    assert rows["101"].rut == "11.111.111-1"
    assert rows["102"].nombre == "Beta"
    assert rows["103"].activo is False  # cliente_activo=0 respetado
    assert rows["101"].activo is True


def test_rut_duplicado_en_lote_gana_el_primero(service, db):
    """Obuma a veces trae el mismo rut en dos clientes distintos: el primero
    se queda con el rut real, el segundo recibe OBU-{id}. Nadie se omite."""
    _mock_api(service, [
        _item("201", rut="11.111.111-1", nombre="Original"),
        _item("202", rut="11.111.111-1", nombre="Duplicado"),
    ])
    result = _run(service)

    assert result["synced"] == 2
    assert result["skipped"] == 0
    rows = {c.obuma_id: c for c in db.query(ClienteFinal).all()}
    assert rows["201"].rut == "11.111.111-1"
    assert rows["202"].rut == "OBU-202"


def test_nuevo_cliente_rut_invalido_recibe_obu(service, db):
    _mock_api(service, [_item("301", rut="12345678-9", nombre="Sin formato")])
    _run(service)
    row = db.query(ClienteFinal).filter_by(obuma_id="301").one()
    assert row.rut == "OBU-301"  # rut sin puntos = invalido -> sintetico


# ---------------------------------------------------------------------------
# sync_clientes: updates
# ---------------------------------------------------------------------------

def test_update_preserva_campos_vacios_del_api(service, db):
    db.add(ClienteFinal(
        tenant_id=service.tenant_id, obuma_id="401", rut="11.111.111-1",
        nombre="Nombre Viejo", email="viejo@mail.cl", telefono="+56911111111",
    ))
    db.commit()

    _mock_api(service, [_item(
        "401", rut="11.111.111-1", nombre="Nombre Nuevo",
        cliente_email="",  # vacio -> NO debe pisar el email existente
    )])
    result = _run(service)

    assert result["synced"] == 1
    row = db.query(ClienteFinal).filter_by(obuma_id="401").one()
    assert row.nombre == "Nombre Nuevo"
    assert row.email == "viejo@mail.cl"       # preservado
    assert row.telefono == "+56911111111"     # preservado


def test_update_cambio_de_rut_a_uno_ocupado_usa_obu(service, db):
    db.add_all([
        ClienteFinal(tenant_id=service.tenant_id, obuma_id="501",
                     rut="11.111.111-1", nombre="Dueno del rut"),
        ClienteFinal(tenant_id=service.tenant_id, obuma_id="502",
                     rut="22.222.222-2", nombre="El que cambia"),
    ])
    db.commit()

    # El API ahora dice que 502 tiene el rut de 501 -> colision -> OBU-502.
    _mock_api(service, [
        _item("501", rut="11.111.111-1", nombre="Dueno del rut"),
        _item("502", rut="11.111.111-1", nombre="El que cambia"),
    ])
    result = _run(service)

    assert result["skipped"] == 0
    rows = {c.obuma_id: c for c in db.query(ClienteFinal).all()}
    assert rows["501"].rut == "11.111.111-1"
    assert rows["502"].rut == "OBU-502"


def test_update_rut_invalido_mantiene_rut_existente(service, db):
    db.add(ClienteFinal(tenant_id=service.tenant_id, obuma_id="601",
                        rut="11.111.111-1", nombre="Cliente"))
    db.commit()

    _mock_api(service, [_item("601", rut="basura", nombre="Cliente")])
    _run(service)

    row = db.query(ClienteFinal).filter_by(obuma_id="601").one()
    assert row.rut == "11.111.111-1"


def test_update_actualiza_activo_y_data_json(service, db):
    db.add(ClienteFinal(tenant_id=service.tenant_id, obuma_id="701",
                        rut="11.111.111-1", nombre="Cliente", activo=True))
    db.commit()

    _mock_api(service, [_item("701", rut="11.111.111-1", nombre="Cliente", activo="0")])
    _run(service)

    row = db.query(ClienteFinal).filter_by(obuma_id="701").one()
    assert row.activo is False
    assert json.loads(row.data_json)["cliente_id"] == "701"


def test_rut_liberado_en_la_misma_corrida_queda_disponible(service, db):
    """Si un cliente cambia de rut, el rut viejo queda libre y otro cliente
    del mismo lote puede tomarlo (replica el flush-por-item anterior)."""
    db.add(ClienteFinal(tenant_id=service.tenant_id, obuma_id="801",
                        rut="11.111.111-1", nombre="Libera"))
    db.commit()

    _mock_api(service, [
        _item("801", rut="99.999.999-9", nombre="Libera"),      # deja libre 11.111.111-1
        _item("802", rut="11.111.111-1", nombre="Toma"),        # lo toma
    ])
    result = _run(service)

    assert result["skipped"] == 0
    rows = {c.obuma_id: c for c in db.query(ClienteFinal).all()}
    assert rows["801"].rut == "99.999.999-9"
    assert rows["802"].rut == "11.111.111-1"


# ---------------------------------------------------------------------------
# Fallback fila-por-fila (colisiones que el mapa en memoria no pudo ver,
# p.ej. otra conexion escribiendo en paralelo)
# ---------------------------------------------------------------------------

def test_flush_fallback_reintenta_con_obu(service, db):
    db.add(ClienteFinal(tenant_id=service.tenant_id, obuma_id="901",
                        rut="11.111.111-1", nombre="Ya existe"))
    db.commit()

    # Insert que colisiona con el rut existente (simula carrera concurrente).
    mappings = [{
        "tenant_id": service.tenant_id, "rut": "11.111.111-1",
        "nombre": "Concurrente", "email": "", "telefono": "", "direccion": "",
        "giro": "", "comuna": "", "ciudad": "", "obuma_id": "902",
        "activo": True, "data_json": "{}",
    }]
    skipped = service._flush_clientes_mappings([], mappings)
    db.commit()

    assert skipped == 0
    row = db.query(ClienteFinal).filter_by(obuma_id="902").one()
    assert row.rut == "OBU-902"  # reintento con rut sintetico


def test_flush_fallback_omite_si_tambien_falla_obu(service, db):
    db.add_all([
        ClienteFinal(tenant_id=service.tenant_id, obuma_id="911",
                     rut="11.111.111-1", nombre="Dueno rut"),
        ClienteFinal(tenant_id=service.tenant_id, obuma_id="912",
                     rut="OBU-913", nombre="Dueno OBU"),
    ])
    db.commit()

    mappings = [{
        "tenant_id": service.tenant_id, "rut": "11.111.111-1",
        "nombre": "Imposible", "email": "", "telefono": "", "direccion": "",
        "giro": "", "comuna": "", "ciudad": "", "obuma_id": "913",
        "activo": True, "data_json": "{}",
    }]
    skipped = service._flush_clientes_mappings([], mappings)
    db.commit()

    assert skipped == 1
    assert db.query(ClienteFinal).filter_by(obuma_id="913").first() is None


# ---------------------------------------------------------------------------
# _sync_cartera_from_clientes (barrido batch)
# ---------------------------------------------------------------------------

def _cliente_con_vendedor(service, obuma_id, rut, rel_usuario_id, cliente_activo="1"):
    return ClienteFinal(
        tenant_id=service.tenant_id, obuma_id=obuma_id, rut=rut,
        nombre=f"Cliente {obuma_id}", activo=(cliente_activo == "1"),
        data_json=json.dumps({
            "cliente_id": obuma_id,
            "rel_usuario_id": rel_usuario_id,
            "cliente_activo": cliente_activo,
        }),
    )


def test_cartera_asigna_vendedor_tracked(service, db):
    db.add(_cliente_con_vendedor(service, "1001", "11.111.111-1", "28856"))
    db.commit()

    result = service._sync_cartera_from_clientes()

    assert result == {"added": 1, "deactivated": 0}
    vc = db.query(VendedorCartera).one()
    assert vc.empleado_obuma_id == "28856"
    assert vc.activo is True
    assert vc.fecha_asignacion is not None


def test_cartera_desactiva_asignacion_de_otro_vendedor(service, db):
    cli = _cliente_con_vendedor(service, "1002", "22.222.222-2", "28856")
    db.add(cli)
    db.flush()
    db.add(VendedorCartera(tenant_id=service.tenant_id, empleado_obuma_id="28886",
                           cliente_id=cli.id, activo=True))
    db.commit()

    result = service._sync_cartera_from_clientes()

    assert result == {"added": 1, "deactivated": 1}
    vieja = db.query(VendedorCartera).filter_by(empleado_obuma_id="28886").one()
    assert vieja.activo is False
    assert vieja.fecha_baja is not None
    nueva = db.query(VendedorCartera).filter_by(empleado_obuma_id="28856").one()
    assert nueva.activo is True


def test_cartera_respeta_desactivacion_manual(service, db):
    """Si Gabriel desactivo manualmente la asignacion del vendedor correcto,
    el sync NO la reactiva ni crea una duplicada."""
    cli = _cliente_con_vendedor(service, "1003", "33.333.333-3", "28856")
    db.add(cli)
    db.flush()
    db.add(VendedorCartera(tenant_id=service.tenant_id, empleado_obuma_id="28856",
                           cliente_id=cli.id, activo=False))
    db.commit()

    result = service._sync_cartera_from_clientes()

    assert result == {"added": 0, "deactivated": 0}
    vc = db.query(VendedorCartera).one()
    assert vc.activo is False  # sigue desactivada


def test_cartera_desactiva_cliente_inactivo_o_no_tracked(service, db):
    cli_inactivo = _cliente_con_vendedor(service, "1004", "44.444.444-4",
                                         "28856", cliente_activo="0")
    cli_no_tracked = _cliente_con_vendedor(service, "1005", "55.555.555-5", "99999")
    db.add_all([cli_inactivo, cli_no_tracked])
    db.flush()
    db.add_all([
        VendedorCartera(tenant_id=service.tenant_id, empleado_obuma_id="28856",
                        cliente_id=cli_inactivo.id, activo=True),
        VendedorCartera(tenant_id=service.tenant_id, empleado_obuma_id="28886",
                        cliente_id=cli_no_tracked.id, activo=True),
    ])
    db.commit()

    result = service._sync_cartera_from_clientes()

    assert result == {"added": 0, "deactivated": 2}
    assert db.query(VendedorCartera).filter_by(activo=True).count() == 0


def test_cartera_corre_dentro_de_sync_clientes(service, db):
    """Integracion: sync_clientes completo asigna cartera desde el data_json."""
    _mock_api(service, [_item(
        "1101", rut="66.666.666-6", nombre="Full flow",
        rel_usuario_id="28892",
    )])
    result = _run(service)

    assert result["synced"] == 1
    assert result["cartera"] == {"added": 1, "deactivated": 0}
    vc = db.query(VendedorCartera).one()
    assert vc.empleado_obuma_id == "28892"


# ---------------------------------------------------------------------------
# Volumen: el flujo bulk parte los lotes correctamente
# ---------------------------------------------------------------------------

def test_bulk_maneja_mas_de_un_lote(service, db):
    """2.500 clientes nuevos (>2 lotes de 1000) + re-sync como updates."""
    items = [_item(str(10000 + i), rut="", nombre=f"Masivo {i}") for i in range(2500)]
    _mock_api(service, items)
    result = _run(service)
    assert result["synced"] == 2500
    assert db.query(ClienteFinal).count() == 2500

    # Segunda corrida: todos son updates ahora.
    result2 = _run(service)
    assert result2["synced"] == 2500
    assert result2["skipped"] == 0
    assert db.query(ClienteFinal).count() == 2500


# ---------------------------------------------------------------------------
# Marcado de inactivos: clientes que ya no vienen del API
# ---------------------------------------------------------------------------

def test_clientes_ausentes_del_api_se_marcan_inactivos(service, db):
    """Cliente en DB que Obuma ya no devuelve -> activo=False. Los presentes
    y los que no tienen obuma_id (creados desde ventas) no se tocan."""
    db.add_all([
        ClienteFinal(tenant_id=service.tenant_id, obuma_id="801",
                     rut="11.111.111-1", nombre="Presente", activo=True),
        ClienteFinal(tenant_id=service.tenant_id, obuma_id="802",
                     rut="22.222.222-2", nombre="Ausente", activo=True),
        ClienteFinal(tenant_id=service.tenant_id, obuma_id=None,
                     rut="33.333.333-3", nombre="Sin obuma id", activo=True),
    ])
    db.commit()

    _mock_api(service, [_item("801", rut="11.111.111-1", nombre="Presente")])
    result = _run(service)

    assert result["synced"] == 1
    assert result["skipped"] == 0
    assert result["inactivados"] == 1
    rows = {c.nombre: c for c in db.query(ClienteFinal).all()}
    assert rows["Presente"].activo is True
    assert rows["Ausente"].activo is False        # ausente -> inactivo
    assert rows["Sin obuma id"].activo is True    # sin obuma_id: intocable


def test_payload_vacio_no_desactiva_nada(service, db):
    """Guardia anti-catastrofe: si Obuma devuelve payload vacio/malformado,
    NO se marca inactivo a nadie (evita apagar el padron completo)."""
    db.add(ClienteFinal(tenant_id=service.tenant_id, obuma_id="901",
                        rut="11.111.111-1", nombre="Intacto", activo=True))
    db.commit()

    _mock_api(service, [])
    result = _run(service)

    assert result["synced"] == 0
    assert result["inactivados"] == 0
    assert db.query(ClienteFinal).filter_by(obuma_id="901").one().activo is True


def test_ausente_ya_inactivo_no_se_recuenta(service, db):
    """Un ausente que ya estaba inactivo no infla el contador (update
    filtra activo=True), y sigue inactivo."""
    db.add_all([
        ClienteFinal(tenant_id=service.tenant_id, obuma_id="911",
                     rut="11.111.111-1", nombre="Presente", activo=True),
        ClienteFinal(tenant_id=service.tenant_id, obuma_id="912",
                     rut="22.222.222-2", nombre="Ya inactivo", activo=False),
    ])
    db.commit()

    _mock_api(service, [_item("911", rut="11.111.111-1", nombre="Presente")])
    result = _run(service)

    assert result["inactivados"] == 0
    assert db.query(ClienteFinal).filter_by(obuma_id="912").one().activo is False


def test_ausente_presente_en_api_aunque_sea_saltado_no_se_desactiva(service, db):
    """Item del API sin nombre ni rut se salta del upsert, pero SI cuenta como
    presente (su obuma_id viene en el payload) -> no se marca inactivo."""
    db.add(ClienteFinal(tenant_id=service.tenant_id, obuma_id="921",
                        rut="11.111.111-1", nombre="Presente raro", activo=True))
    db.commit()

    _mock_api(service, [_item("921", rut="", nombre="")])
    result = _run(service)

    assert result["inactivados"] == 0
    assert db.query(ClienteFinal).filter_by(obuma_id="921").one().activo is True
