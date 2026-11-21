"""Verify display translation while preserving protocol, progression and player input."""
import copy
import json
import pathlib
import sqlite3
import struct
import xml.etree.ElementTree as ET

import pytest

from test_competiciones import world, stored
import app
import clases
import competicion_logros
import localizacion
import logros
import totem_war
import build_zh_cn_catalog as builder
from audit_zh_cn_notices import literals
from mensajes_zh_cn import MENSAJES_ZH_CN, PLANTILLAS_ZH_CN


@pytest.fixture
def translated_catalog(tmp_path, monkeypatch):
    path = tmp_path / 'zh_CN.json'
    path.write_text(json.dumps({
        'locale': 'zh_CN',
        'achievement': {'741': 'MP界限突破 5000', '1955': '就是没定性 2'},
        'crown': {'49': '天使统帅'},
        'string': {'1891': '你太无礼了，让你见识我的力量！'},
        'aliases': {'Copper Sword': '铜剑', 'Slarm': '史莱姆', 'Quest for test': '测试用任务',
                    'Max MP - 5,000': 'MP界限突破 5000', 'Swindle World': '诈欺世界'},
    }), encoding='utf-8')
    monkeypatch.setenv('AO_LOCALE', 'zh_CN')
    monkeypatch.setenv('AO_LOCALE_FILE', str(path))
    localizacion._leer_catalogo.cache_clear()
    yield
    localizacion._leer_catalogo.cache_clear()


@pytest.mark.parametrize('english,chinese', [
    ('Achievement completed: [Max MP - 5,000] (+2 points)', '成就达成：【MP界限突破 5000】（+2点成就积分）'),
    ('Achievement completed: [就是没定性 2] (+2 points)', '成就达成：【就是没定性 2】（+2点成就积分）'),
    ('Level Up! Reached Level 37!', '升级了！已达到37级！'),
    ('Quest [Quest for test] Completed!', '任务【测试用任务】已完成！'),
    ('Quest [Quest for test]: Missing items (1/10)', '任务【测试用任务】：物品不足（1/10）'),
    ('Quest [Quest for test]: Defeated Slarm (5/5)! Report to Unknown NPC', '任务【测试用任务】：已击败史莱姆（5/5）！请向Unknown NPC报告。'),
    ('Defeated Slarm (2/5)', '已击败史莱姆（2/5）'),
    ('Sold 3x Copper Sword for 120 Gold.', '已出售铜剑×3，获得120金币。'),
    ('10 Gold', '10金币'),
    ('You need 3 free slots to open this.', '开启此物品需要3个背包空位。'),
    ('Capture successful! You obtained Rare-Slarm (Copper Sword).', '捕捉成功！获得稀有-史莱姆（铜剑）。'),
    ('[Daily Event] Swindle World battle has begun!', '【每日活动】诈欺世界开始了！'),
    ('Angel Arena 401..9999: registration open for 15 minutes. Enter via Sign-up Office.', '战天使擂台（401至9999级）开放报名15分钟，请从报名处入场。'),
    ('Friend invitation sent to Copper Sword.', '已向Copper Sword发送好友邀请。'),
    ("Congratulations! League 'Slarm' has been founded!", '恭喜！公会“Slarm”已成立！'),
    ('Unknown message: Copper Sword', 'Unknown message: Copper Sword'),
])
def test_dynamic_notices(translated_catalog, english, chinese):
    packet = clases.aviso(english, tipo=0)
    assert packet[:5] == struct.pack('<HHB', 0x000D, clases.MSG_TEXTO, 0)
    assert packet[5:] == chinese.encode('gbk') + bytes(3)
    assert localizacion.traducir(chinese) == chinese


def test_all_literal_player_notices_are_covered(translated_catalog):
    missing = [message for message in literals() if localizacion.traducir(message) == message]
    assert not missing


def test_translation_keys_are_unique_and_values_gbk_safe():
    import ast
    tree = ast.parse(pathlib.Path(__file__).resolve().parents[1].joinpath('server/mensajes_zh_cn.py').read_text('utf-8'))
    dictionary = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                      and any(getattr(target, 'id', '') == 'MENSAJES_ZH_CN' for target in node.targets))
    keys = [key.value for key in dictionary.keys]
    assert len(keys) == len(set(keys))
    for translation in MENSAJES_ZH_CN.values():
        assert translation.encode('gbk').decode('gbk') == translation
    for pattern, translation, names in PLANTILLAS_ZH_CN:
        assert max(names, default=-1) < pattern.groups
        translation.format(*['测试'] * pattern.groups).encode('gbk')


@pytest.mark.parametrize('mode', ['manual', 'automatic', 'competition'])
def test_achievement_routes_keep_ids_points_and_other_state(world, monkeypatch, translated_catalog, mode):
    session = world.player(level=1, items={20: 66})
    session.personaje.logros = []
    before = copy.deepcopy(logros.de_id(741))
    original_gold = session.oro
    monkeypatch.setattr(app, '_stats_ses', lambda session: b'')
    monkeypatch.setattr(logros, 'comprobar_ranking', lambda *args: [])
    monkeypatch.setattr(app, '_listas_ranking', lambda *args: {})
    monkeypatch.setattr(app, '_logros_ctx', lambda *args: {})
    monkeypatch.setattr(app, '_logros_stats', lambda *args: {'mp_max': 5000})
    monkeypatch.setattr(logros, 'comprobar_extra', lambda *args: [])
    if mode == 'manual':
        monkeypatch.setattr(app, '_logros_actualizar', lambda *args, **kwargs: None)
        assert app._logros_dar(session, 'test', 741)
    elif mode == 'automatic':
        app._logros_actualizar(session)
    else:
        competicion_logros.publicar([(session.usuario, session.personaje.char_id, {}, [741], [741])])
    expected = clases.aviso('成就达成：【MP界限突破 5000】（+2点成就积分）', tipo=0)
    assert expected in session.packets
    assert 741 in session.personaje.logros
    assert logros.de_id(741) == before
    assert session.oro == original_gold
    assert session.inventario == {20: 66}
    assert stored(world, session)['custom_field'] == 'preserve me'


def test_title_broadcast_is_gbk_without_rewriting_player_chat(translated_catalog, monkeypatch):
    player_name = 'Copper Sword'
    message = logros.aviso_titulo(player_name, 49)
    packet = clases.chat_super_broadcast(0, player_name, message, 1, sistema=True)
    assert packet[:7] == struct.pack('<HIB', 0x0128, 0, 11)
    assert packet[7:24] == player_name.encode('ascii').ljust(17, b'\0')
    assert packet[24:] == b'1' + 'Copper Sword获得了称号【天使统帅】！'.encode('gbk') + b'\0'
    long_packet = clases.chat_super_broadcast(0, '中' * 20, '中' * 1000, sistema=True)
    assert len(long_packet[7:24]) == 17
    assert long_packet[7:24].split(b'\0')[0].decode('gbk') == '中' * 8
    assert len(long_packet[25:-1]) <= 999
    long_packet[25:-1].decode('gbk')
    player_message = 'Your backpack is full.'
    ordinary = clases.chat_super_broadcast(123, player_name, player_message)
    assert ordinary[24:] == b'0' + player_message.encode('ascii') + b'\0'
    monkeypatch.setenv('AO_LOCALE', '')
    monkeypatch.setattr(logros, 'nombre_titulo', lambda identifier: 'Angel Marshal')
    assert logros.aviso_titulo(player_name, 49) == 'Copper Sword has obtained the title [Angel Marshal]!'
    assert localizacion.traducir('Achievement completed: [Max MP - 5,000] (+2 points)') == 'Achievement completed: [Max MP - 5,000] (+2 points)'


def test_banner_preserves_header_limit_and_locale(translated_catalog, monkeypatch):
    original = '[Daily Event] Swindle World battle has begun!'
    packet = totem_war.cartel_deslizante(original)
    assert packet[:24] == struct.pack('<HIB17s', 0x0128, 0, 0, bytes(17))
    assert packet[24:-1].decode('gbk') == '【每日活动】诈欺世界开始了！'
    long_packet = totem_war.cartel_deslizante('A' + '中' * 1000)
    assert len(long_packet[24:-1]) <= 900
    long_packet[24:-1].decode('gbk')
    monkeypatch.setenv('AO_LOCALE', '')
    assert totem_war.cartel_deslizante(original)[24:-1] == original.encode('ascii')


def test_system_speech_is_translated_without_touching_player_chat(translated_catalog, monkeypatch):
    system = app._decir(7, 'Slarm', 'Feel the elemental power!', sistema=True)
    assert system[:6] == struct.pack('<HI', 0x0017, 7)
    assert system[6:23] == b'Slarm'.ljust(17, b'\0')
    assert system[23:] == '感受元素之力吧！'.encode('gbk') + b'\0'
    player = app._decir(7, 'Slarm', 'Feel the elemental power!')
    assert player[23:] == b'Feel the elemental power!\0'
    monkeypatch.setattr(app, '_STRINGS', {1891: 'You are impolite. Let me show you my power!'})
    assert app._texto_string(1891) == '你太无礼了，让你见识我的力量！'
    monkeypatch.setenv('AO_LOCALE', '')
    assert app._texto_string(1891) == 'You are impolite. Let me show you my power!'


def test_catalog_adds_id_names_without_modifying_source(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    templates = root / 'server' / 'plantillas'
    templates.mkdir(parents=True)
    (templates / 'logros.json').write_text(json.dumps({'filas': [{'id': 741, 'nombre': 'Max MP - 5,000'}]}), 'utf-8')
    (templates / 'misiones.json').write_text(json.dumps({'filas': [{'id': 1, 'nombre': 'Quest for test'}]}), 'utf-8')
    database = root / 'content.db'
    with sqlite3.connect(database) as connection:
        for table in ('npc', 'monster'):
            connection.execute(f'CREATE TABLE {table}(id INTEGER, name TEXT)')
            connection.execute(f'INSERT INTO {table} VALUES (1, ?)', ('English name',))
        connection.execute('CREATE TABLE quest(id INTEGER, "任務名稱" TEXT)')
        connection.execute('INSERT INTO quest VALUES (1, ?)', ('Quest for test',))
    tables = [
        ('npc', '<rows><row 編號="1" 名稱="天使"/></rows>'),
        ('monster', '<rows><row 編號="1" 名稱="史莱姆"/></rows>'),
        ('achievement', '<rows><row 編號="741" 名稱="MP界限突破 5000"/></rows>'),
        ('crown', '<rows><row 編號="49" 封號="天使统帅"/></rows>'),
        ('quest', '<rows><row 編號="1" 任務名稱="测试用任务"/></rows>'),
        ('string', '<rows><row 編號="3076" 文字="诈欺世界Ⅰ"/></rows>'),
    ]
    monkeypatch.setattr(builder, 'ROOT', root)
    monkeypatch.setattr(builder, 'client_tables', lambda client: ((table, ET.fromstring(xml), 'test.pak') for table, xml in tables))
    before = database.read_bytes()
    result = builder.build(root, database)
    assert result['achievement']['741'] == 'MP界限突破 5000'
    assert result['crown']['49'] == '天使统帅'
    assert result['aliases']['Max MP - 5,000'] == 'MP界限突破 5000'
    assert result['aliases']['Quest for test'] == '测试用任务'
    assert result['aliases']['Swindle World'] == '诈欺世界'
    assert 'English name' not in result['aliases']
    assert database.read_bytes() == before
