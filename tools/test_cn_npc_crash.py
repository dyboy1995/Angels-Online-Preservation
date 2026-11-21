"""Reissue Angel 24801 is absent from the installed CN NPC table."""
import copy
import struct

import pytest

from test_competiciones import world, stored
import app
import compat_npc_cn
import localizacion
import login
from session import Session
from framing import decode_header, submessages


@pytest.fixture
def cn(monkeypatch):
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', 'cn-8.6.5.7')
    monkeypatch.setenv('AO_LOCALE', 'zh_CN')
    monkeypatch.setattr(localizacion, 'catalogo', lambda: {'npc': {'14231': '补偿天使'}})


def spawn(prototype=24801, kind=200, sprite=40002):
    return login._npc_spawn(71410008, prototype, 'Reissue Angel', (194, 91), sprite=sprite, klass=kind)


def test_only_missing_client_prototype_and_display_name_change(cn):
    original = spawn()
    changed = compat_npc_cn.paquete(original)
    assert changed[:18] == original[:18]
    assert changed[35:47] == original[35:47]
    assert changed[49:] == original[49:]
    assert len(changed) == len(original)
    assert struct.unpack_from('<H', changed, 47)[0] == 14231
    assert struct.unpack_from('<I', changed, 2)[0] == 71410008
    assert changed[18:35].split(b'\0')[0].decode('gbk') == '补发天使'
    assert compat_npc_cn.paquete(changed) == changed


@pytest.mark.parametrize('packet', [spawn(1506), spawn(kind=1), spawn(kind=38), spawn(sprite=40005), b'\x08\x00'])
def test_unrelated_spawns_and_short_packets_unchanged(cn, packet):
    assert compat_npc_cn.paquete(packet) == packet


def test_other_profile_and_catalog_support_are_preserved(cn, monkeypatch):
    packet = spawn()
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', 'igg')
    assert compat_npc_cn.paquete(packet) == packet
    monkeypatch.setenv('AO_CLIENT_PROTOCOL', 'cn-8.6.5.7')
    monkeypatch.setattr(localizacion, 'catalogo', lambda: {'npc': {'24801': '补发天使', '14231': '补偿天使'}})
    assert compat_npc_cn.paquete(packet) == packet
    monkeypatch.setattr(localizacion, 'catalogo', lambda: {})
    assert compat_npc_cn.paquete(packet) == packet


@pytest.mark.parametrize('method', ['enviar', 'enviar_sin_espejo', 'enviar_inmediato'])
def test_all_outbound_paths_use_the_compatible_prototype(cn, method):
    session = Session(('test', 0))
    session.volcar = lambda: None
    getattr(session, method)(spawn())
    wire = session.drenar()
    header = decode_header(wire)
    messages, consumed = submessages(wire[6:6 + header['length']])
    packet = struct.pack('<H', messages[0][0]) + messages[0][1]
    assert packet == compat_npc_cn.paquete(spawn())


def test_npc_click_keeps_original_reissue_dialogue_and_character_data(world, cn):
    session = world.player(level=1)
    session.personaje.stage = 41
    session.personaje.tile_x, session.personaje.tile_y = 194, 91
    before = copy.deepcopy(stored(world, session))
    router = app.Servidor.__new__(app.Servidor)
    router.mundos = world.players
    router.manejar(session, 5, None, None, 'test', struct.pack('<IH', 71410008, 0))
    assert any(packet[:2] == b'\x12\x00' and struct.unpack_from('<I', packet, 2)[0] == 516960
               for packet in session.packets)
    assert stored(world, session) == before
