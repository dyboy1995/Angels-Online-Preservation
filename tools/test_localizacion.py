import json
import os
import pathlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import clases
import configuracion
import combate
import dialogos
import localizacion
import login
from session import Session
from framing import decode_header, submessages


class TestLocalization(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.catalog = pathlib.Path(self.directory.name) / 'zh_CN.json'
        self.catalog.write_text(json.dumps({
            'locale': 'zh_CN', 'npc': {'1894': '天使拜丘'},
            'monster': {'19': '史莱姆'}, 'item': {'73': '铜剑'},
            'skill': {'9': '剑术'}, 'aliases': {'Sword': '剑术', 'Copper Sword': '铜剑'},
        }), encoding='utf-8')
        environment = patch.dict(os.environ, {'AO_LOCALE': 'zh_CN', 'AO_LOCALE_FILE': str(self.catalog)})
        environment.start()
        self.addCleanup(environment.stop)
        self.addCleanup(localizacion._leer_catalogo.cache_clear)

    def test_spawn_only_replaces_name_and_preserves_native_layout(self):
        original = login._npc_spawn(19, 1894, 'Angel Raphael', (244, 30), sprite=40005, klass=199)
        translated = localizacion.paquete(original)
        self.assertEqual(len(translated), len(original))
        self.assertEqual(translated[:18], original[:18])
        self.assertEqual(translated[35:], original[35:])
        self.assertEqual(translated[18:35].split(b'\0')[0].decode('gbk'), '天使拜丘')
        self.assertEqual(localizacion.paquete(translated), translated)

    def test_summon_personal_name_and_unknown_types_are_preserved(self):
        for kind, type_id in ((38, 19), (199, 65535)):
            original = login._npc_spawn(91, type_id, 'My pet', (12, 14), klass=kind)
            self.assertEqual(localizacion.paquete(original), original)

    def test_monster_name_uses_monster_table(self):
        original = login._monster_spawn(101, 19, 'Slarm', (15, 17))
        translated = localizacion.paquete(original)
        self.assertEqual(translated[18:35].split(b'\0')[0].decode('gbk'), '史莱姆')

    def test_gbk_truncation_never_splits_character(self):
        result = localizacion.codificar('A' + '中' * 12, limite=16)
        self.assertEqual(len(result), 15)
        self.assertEqual(result.decode('gbk'), 'A' + '中' * 7)

    def test_resource_name_does_not_change_other_fields(self):
        original = bytearray(range(46))
        struct.pack_into('<H', original, 0, 0x000F)
        original[18:34] = b'Copper Sword'.ljust(16, b'\0')
        translated = localizacion.paquete(bytes(original))
        self.assertEqual(translated[18:34].split(b'\0')[0].decode('gbk'), '铜剑')
        self.assertEqual(translated[:18], original[:18])
        self.assertEqual(translated[34:], original[34:])

    def test_internal_item_names_remain_canonical(self):
        import app
        with patch('misiones.nombre_item', return_value='Copper Sword'):
            self.assertEqual(app._nombre_item(73), 'Copper Sword')
            self.assertIn('铜剑'.encode('gbk'), clases.aviso(app._nombre_item(73)))

    def test_outbound_paths_translate_world_only(self):
        original = login._npc_spawn(19, 1894, 'Angel Raphael', (244, 30), klass=199)
        for role in ('login', 'mundo'):
            for method in ('enviar', 'enviar_sin_espejo'):
                session = Session(('test', 0))
                session.rol = role
                getattr(session, method)(original)
                wire = session.drenar()
                header = decode_header(wire)
                packets, consumed = submessages(wire[6:6 + header['length']])
                actual = struct.pack('<H', packets[0][0]) + packets[0][1]
                expected = localizacion.paquete(original) if role == 'mundo' else original
                self.assertEqual(actual, expected)

    def test_notices_and_dialogue_parameters_keep_chinese(self):
        self.assertIn('铜剑'.encode('gbk'), clases.aviso('Copper Sword'))
        self.assertIn('剑术'.encode('gbk') + b'\0' + b'100\0', clases.aviso_doble(503, 'Sword', '100'))
        self.assertIn('铜剑'.encode('gbk'), dialogos.armar_linea(123, strings=['Copper Sword']))
        self.assertEqual(clases.nombre(9), '剑术')

    def test_disabled_locale_keeps_legacy_bytes(self):
        original = login._npc_spawn(19, 1894, 'Angel Raphael', (244, 30), klass=199)
        with patch.dict(os.environ, {'AO_LOCALE': ''}):
            self.assertEqual(localizacion.paquete(original), original)
            self.assertIn(b'Copper Sword\0', clases.aviso('Copper Sword'))

    def test_server_authored_notices_use_exact_chinese_text_and_keep_header(self):
        for english, chinese in localizacion.MENSAJES_ZH_CN.items():
            packet = clases.aviso(english, tipo=7, msg_id=clases.MSG_TEXTO)
            self.assertEqual(packet[:5], struct.pack('<HHB', 0x000D, clases.MSG_TEXTO, 7))
            self.assertEqual(packet[5:-3].decode('gbk'), chinese)
            self.assertEqual(packet[-3:], bytes(3))
            self.assertNotIn(english.encode('ascii'), packet)

    def test_custom_notices_keep_english_when_locale_disabled(self):
        with patch.dict(os.environ, {'AO_LOCALE': ''}):
            for english in localizacion.MENSAJES_ZH_CN:
                self.assertEqual(localizacion.traducir(english), english)
                self.assertIn(english.encode('ascii') + bytes(3), clases.aviso(english))

    def test_system_translation_does_not_replace_fragments_or_unknown_text(self):
        for original in ('Unknown server notice.', 'Your abilities were permanently improved. Extra text.'):
            self.assertEqual(localizacion.traducir(original), original)


class TestRequestedRates(unittest.TestCase):
    def test_base_rates_are_stable_on_all_weekdays(self):
        self.assertFalse(configuracion.EVENTO_FIN_DE_SEMANA_AUTOMATICO)
        self.assertFalse(configuracion.EVENTO_DOBLE_EXP_FORZADO)
        for day in range(7):
            with patch.object(configuracion.datetime, 'datetime') as clock:
                clock.now.return_value.weekday.return_value = day
                self.assertEqual(configuracion.multiplicador_exp(), 1.0)
                self.assertEqual(configuracion.multiplicador_skill_exp(), 100.0)
                self.assertEqual(configuracion.multiplicador_drop(), 10.0)

    def test_combat_consumes_configured_experience_rates(self):
        with patch.object(combate, '_datos', return_value={'exp': 35}):
            self.assertEqual(combate.calcular_exp(19), 35)
        self.assertEqual(combate.calcular_skill_exp(), 600)

    def test_drop_rate_preserves_existing_probability_cap(self):
        with patch.dict(combate._DROPS_CACHE, {19: [(73, 1)]}):
            with patch.object(combate, 'es_jefe', return_value=False):
                with patch.object(combate.random, 'random', return_value=0.949):
                    self.assertEqual(combate.botin_items(19), [(73, 1)])
                with patch.object(combate.random, 'random', return_value=0.951):
                    self.assertEqual(combate.botin_items(19), [])


if __name__ == '__main__':
    unittest.main()
