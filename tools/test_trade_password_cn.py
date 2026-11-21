"""Trade PIN state and trash confirmation use isolated characters only."""
import copy
import struct

import pytest

from test_competiciones import world, stored
import app
import cuentas
import login
import seguridad_comercio as security


@pytest.fixture(autouse=True)
def cn_profile(monkeypatch):
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', security.CN_PROFILE)


def test_cn_character_packet_covers_native_fields_and_preserves_payload():
    original = b'\x02\x00' + b'\x55' * 4118
    result = security.ajustar_ficha(original, stage=3)
    assert len(result) == security.CN_CHARACTER_PACKET_SIZE
    assert result[:len(original)] == original
    assert result[security.CN_PASSWORD_FLAG_OFFSET] == 0
    assert result[security.CN_STAGE_OFFSET:security.CN_STAGE_OFFSET + 4] == struct.pack('<I', 3)
    assert len(result) > 0x1818
    assert security.ajustar_ficha(result) == result


def test_cn_existing_flag_is_cleared_without_truncating_later_fields():
    original = bytearray(b'\x02\x00' + bytes(security.CN_CHARACTER_PACKET_SIZE - 2))
    original[security.CN_PASSWORD_FLAG_OFFSET] = 1
    original[0x1818] = 77
    result = security.ajustar_ficha(bytes(original), stage=41)
    assert result[security.CN_PASSWORD_FLAG_OFFSET] == 0
    assert result[0x1818] == 77
    assert result[security.CN_STAGE_OFFSET:security.CN_STAGE_OFFSET + 4] == struct.pack('<I', 41)
    assert len(result) == len(original)


def test_other_profiles_and_packet_types_are_not_changed(monkeypatch):
    original = b'\x02\x00' + b'\x55' * 4118
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', 'igg')
    assert security.ajustar_ficha(original) == original
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', security.CN_PROFILE)
    other = b'\x14\x00' + bytes(11)
    assert security.ajustar_ficha(other) == other


def test_scene_and_character_refresh_initialize_the_same_disabled_pin(world):
    cuentas._init_db()
    session = world.player(level=1)
    session.personaje.stage = 41
    refresh = login.ficha_actual(session.personaje)
    scene = next(packet for packet in login.secuencia(session.personaje) if packet[:2] == b'\x02\x00')
    assert refresh[security.CN_PASSWORD_FLAG_OFFSET] == scene[security.CN_PASSWORD_FLAG_OFFSET] == 0
    assert refresh[security.CN_STAGE_OFFSET:security.CN_STAGE_OFFSET + 4] == struct.pack('<I', 41)
    assert scene[security.CN_STAGE_OFFSET:security.CN_STAGE_OFFSET + 4] == struct.pack('<I', 41)
    assert len(refresh) == len(scene) == security.CN_CHARACTER_PACKET_SIZE


def test_pin_request_clears_stale_ui_without_deleting_or_changing_password(world):
    session = world.player(items={20: 72056})
    before = copy.deepcopy(stored(world, session))
    body = struct.pack('<I', 6) + bytes(132)
    app.Servidor.manejar(None, session, 0x0049, None, None, 'test', body)
    assert session.packets == [struct.pack('<HHB', 0x000D, 906, 0) + bytes(3)]
    assert stored(world, session) == before
    assert session.inventario == {20: 72056}


@pytest.mark.parametrize('body', [b'', bytes(135), bytes(137)])
def test_malformed_pin_requests_do_not_unlock_or_mutate_items(world, body):
    session = world.player(items={20: 72056})
    before = copy.deepcopy(stored(world, session))
    assert security.procesar(session, 0x0049, body)
    assert not session.packets and stored(world, session) == before


def test_no_pin_response_for_unauthenticated_or_other_profile(world, monkeypatch):
    session = world.player()
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', 'igg')
    assert not security.procesar(session, 0x0049, bytes(136))
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', security.CN_PROFILE)
    session.personaje = None
    assert not security.procesar(session, 0x0049, bytes(136))
    assert not session.packets


def test_actual_delete_still_requires_matching_slot_and_item(world):
    session = world.player(items={20: 72056, 21: 72057})
    before = copy.deepcopy(stored(world, session))
    app.Servidor.manejar(None, session, 0x0013, None, None, 'test', struct.pack('<HI', 20, 72057))
    assert stored(world, session) == before
    app.Servidor.manejar(None, session, 0x0013, None, None, 'test', struct.pack('<HI', 20, 72056))
    assert session.inventario == {21: 72057}
    assert stored(world, session)['inventario'] == {'21': 72057}
    assert any(packet[:2] == b'\x1b\x00' for packet in session.packets)
