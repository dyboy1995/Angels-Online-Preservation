"""Translate permanent-stat notices without changing consumption or saved bonuses."""
import struct

import pytest

from test_competiciones import world, stored
import app
import clases


@pytest.mark.parametrize('identifier,bonus', [(40268, {'hp_bonus': 5000}), (40269, {'mp_bonus': 4000})])
def test_source_item_notice_is_chinese_and_effect_persists(world, monkeypatch, identifier, bonus):
    monkeypatch.setenv('AO_LOCALE', 'zh_CN')
    session = world.player(level=1, items={20: identifier, 21: 66})
    monkeypatch.setattr(app, '_stats_ses', lambda session: b'')
    router = app.Servidor.__new__(app.Servidor)
    router.mundos = world.players
    router.manejar(session, 0x002E, None, None, 'test', struct.pack('<II', 20, 0))
    expected = struct.pack('<HHB', 0x000D, clases.MSG_TEXTO, 7) + '你的属性已永久提升。'.encode('gbk') + bytes(3)
    assert expected in session.packets
    assert session.personaje.stats_permanentes == bonus
    assert stored(world, session)['permanentes'] == bonus
    assert session.inventario == {21: 66}
    assert stored(world, session)['custom_field'] == 'preserve me'
