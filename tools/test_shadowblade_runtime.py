"""Exercise ShadowBlade/Mantle packets and persistence using temporary SQLite."""
import struct

import pytest

from test_competiciones import world, stored
import app
import clases
import combate
import competiciones
import competicion_premios
import cuentas
import daily_events
import daily_experience
import elementary
import presencia
import skills


def spell_packets(session):
    result = set()
    for packet in session.packets:
        if len(packet) < 7 or packet[:2] != b'\x1d\0' or len(packet) != 7 + 9 * packet[6]:
            continue
        for offset in range(7, len(packet), 9):
            if packet[offset] == clases.KIND_HECHIZO:
                result.add(struct.unpack_from('<I', packet, offset + 1)[0])
    return result


def reload_character(world, session):
    saved = stored(world, session)
    saved.update(char_id=session.personaje.char_id, ranura=0)
    for key in ('barra', 'quests'):
        saved.setdefault(key, [])
    return cuentas.personaje_de({'personajes': [saved]})


@pytest.mark.parametrize('branches,weapon,class_id,starters', [
    ([30, 12, 13, 35, 36, 32], 19856, 14, {5401, 5406, 5411}),
    ([17, 15, 16, 18, 19, 32], 19844, 9, {901, 902, 903}),
])
def test_profession_packet_grants_correct_starters_and_survives_reload(
        world, monkeypatch, branches, weapon, class_id, starters):
    session = world.player(level=1)
    monkeypatch.setattr(presencia, 'notificar_equipo', lambda *args: None)
    monkeypatch.setattr(app, '_apariencia', lambda *args: [])
    app.Servidor.manejar(None, session, 0x003A, None, None, 'test', bytes(branches))
    assert spell_packets(session) == starters
    assert session.inventario[3] == weapon and 10 not in session.inventario
    loaded = reload_character(world, session)
    assert [sid for sid, _, _ in loaded.habilidades] == branches
    assert loaded.class_id == class_id
    assert set(loaded.barra) == starters
    assert stored(world, session)['custom_field'] == 'preserve me'


def test_skill_angel_roundtrip_preserves_separate_levels_bank_and_learned_spells(world, monkeypatch):
    session = world.player(level=20)
    session.personaje.habilidades = [(32, 9, 7), (12, 10, 1), (13, 10, 2)]
    session.personaje.banco_habilidades = {30: [8, 6]}
    world.save(session)
    cuentas.guardar_hechizos(session.usuario, session.personaje.char_id, {5402})
    monkeypatch.setattr(app, '_logros_contar', lambda *args, **kwargs: None)
    app.Servidor.manejar(None, session, 0x002F, None, None, 'test', struct.pack('<BII', 10, 32, 30))
    assert spell_packets(session) == {5401, 5406, 5411}
    loaded = reload_character(world, session)
    assert loaded.habilidades[0] == (30, 8, 6)
    assert loaded.banco_habilidades[32] == [9, 7]
    assert loaded.hechizos_aprendidos == {5402}
    session.personaje = loaded
    session.packets.clear()
    app.Servidor.manejar(None, session, 0x002F, None, None, 'test', struct.pack('<BII', 10, 30, 32))
    assert not spell_packets(session)
    loaded = reload_character(world, session)
    assert loaded.habilidades[0] == (32, 9, 7)
    assert loaded.banco_habilidades[30] == [8, 6]
    assert loaded.hechizos_aprendidos == {5402}
    assert not skills.permite_magia_de_sombra(5402, loaded.habilidades)
    assert stored(world, session)['custom_field'] == 'preserve me'


@pytest.mark.parametrize('item,shadow_gains', [(19856, True), (10, False), (19844, False)])
def test_real_equipped_weapon_routes_shadow_skill_experience(world, monkeypatch, item, shadow_gains):
    session = world.player(level=20, items={3: item})
    session.personaje.habilidades = [(30, 1, 0), (32, 1, 0), (35, 1, 0), (36, 1, 0)]
    monkeypatch.setattr(clases, 'exp_requerida_skill', lambda *args: 1000000)
    app._otorgar_skill_exp(session, session.personaje, session.personaje.entity_id, prob_override=1)
    experience = {sid: points for sid, _, points in session.personaje.habilidades}
    assert (experience[30] > 0) == shadow_gains
    assert experience[32] > 0 and experience[35] > 0 and experience[36] > 0


@pytest.mark.parametrize('source', ['daily', 'quiz', 'holy'])
def test_activity_reward_caps_and_sql_persistence(world, monkeypatch, source):
    level = 410 if source == 'daily' else 20
    session = world.player(level=level, items={20: 8537})
    session.personaje.habilidades = [(30, level, 0), (31, level, 0), (32, level, 0)]
    world.save(session)
    monkeypatch.setattr(clases, 'exp_requerida_skill', lambda *args: 10)
    monkeypatch.setattr(combate, 'exp_para_nivel', lambda rank: 0 if rank <= level else 10**18)
    monkeypatch.setattr(app, '_stats_ses', lambda *args: b'')
    if source == 'daily':
        daily_events.iniciar(374, registration=0)
        daily_events.entrar(session, 374)
        current = daily_events.actual(374)
        assert daily_experience._award(session, current, current['start'] + 10, 10)
        assert not daily_experience._award(session, current, current['start'] + 10, 10)
    elif source == 'quiz':
        from test_elementary import enrol, answer_body, request
        monkeypatch.setattr(elementary, '_ROUND', None)
        monkeypatch.setattr(elementary, '_LOADED', False)
        router = app.Servidor.__new__(app.Servidor)
        router.mundos = world.players
        current = enrol(world, router, session)
        request(router, session, 0x153, answer_body(current, current['questions'][0]['correct']))
        elementary._finish(elementary.current())
        elementary._award(session)
    else:
        competiciones.iniciar(112, 60, 0)
        competiciones.entrada(session, 112)
        competiciones.entrada(world.player(level=level, items={20: 8537}), 112)
        current = competiciones.ronda(112)
        current['puntos']['1'] = 1
        current['miembros'][str(session.personaje.char_id)]['score'] = 500
        competiciones._guardar(current)
        competiciones.terminar(112, 'time limit')
        assert competicion_premios.entregar(session) == 0
    levels = {sid: level for sid, level, _ in session.personaje.habilidades}
    assert levels[30] == level and levels[32] == level
    assert level < levels[31] <= level + 11
    assert stored(world, session)['habilidades'] == [list(row) for row in session.personaje.habilidades]
