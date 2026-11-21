"""CN client compatibility for the native Angels GO! transport."""
import struct

from test_competiciones import world, stored
import app


def _use(session, destination):
    app.Servidor.__new__(app.Servidor).manejar(
        session, 0x0151, None, None, 'test', struct.pack('<I', destination))


def _character(world):
    session = world.player(level=79, items={83: app.ITEM_SUPERWING})
    session.cantidades[83] = 10
    session.personaje.faction = 'Heaven'
    session.personaje.stage = 41
    session.personaje.tile_x, session.personaje.tile_y = 176, 87
    world.save(session)
    return session


def test_cn_client_allows_angels_go_before_faction_selection(world, monkeypatch):
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', 'cn-8.6.5.7')
    session = _character(world)
    _use(session, 1)
    assert (session.personaje.stage, session.personaje.tile_x, session.personaje.tile_y) == (41, 152, 74)
    assert session.cantidades[83] == 9
    assert session.packets[0][:2] == struct.pack('<H', 0x0012)
    assert session.packets[-1][:2] == struct.pack('<H', 0x0003)
    assert stored(world, session)['stage_id'] == 41


def test_original_profile_keeps_the_measured_faction_requirement(world, monkeypatch):
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', 'igg')
    session = _character(world)
    before = (session.personaje.stage, session.personaje.tile_x, session.personaje.tile_y)
    _use(session, 1)
    assert (session.personaje.stage, session.personaje.tile_x, session.personaje.tile_y) == before
    assert session.cantidades[83] == 10
    assert session.packets == []
