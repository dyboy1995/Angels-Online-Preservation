"""Regression coverage for native ShadowBlade 30 versus Mantle 32."""
import json
import pathlib
import sqlite3
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))

import app
import arena_premios_compat
import clases
import combate
import farm_mecanicas
import inventario
import login
import ramas
import skills


class TestBranchIdentity(unittest.TestCase):
    def test_all_names_match_current_client_table(self):
        source = json.loads((ROOT / 'server/plantillas/client_tables.json').read_text(encoding='utf-8'))
        self.assertEqual(ramas.NOMBRES, {int(key): value for key, value in source['skill_names'].items()})
        self.assertIs(clases.NOMBRE_RAMA, skills.NOMBRE_RAMA)

    def test_native_xml_confirms_weapon_armor_and_class_points(self):
        rows = {int(row.get('編號')): row.attrib for row in ET.fromstring(skills._xml_de_habilidades())
                if (row.get('編號') or '').isdigit()}
        self.assertEqual(rows[30]['名稱'], 'ShadowBlade')
        self.assertEqual(rows[30]['pt14'], '10')
        self.assertEqual(rows[32]['名稱'], 'Mantle')
        self.assertEqual(rows[32]['防禦'], '3')
        self.assertEqual(rows[32]['負重'], '60')
        self.assertEqual({sid: row['名稱'] for sid, row in rows.items()}, ramas.NOMBRES)

    def test_only_shadowblade_receives_starter_spells(self):
        expected = {5401, 5406, 5411}
        self.assertEqual({mid for mid, _ in clases.hechizos_iniciales([30])}, expected)
        self.assertEqual(clases.hechizos_iniciales([32]), [])
        self.assertFalse(expected & {mid for mid, _ in clases.hechizos_iniciales([17, 15, 16, 18, 19, 32])})

    def test_spell_and_scroll_requirements_agree(self):
        self.assertEqual(skills.skill_de_magia(5402), 30)
        self.assertEqual(skills.info_pergamino(13949)['req_skills'], [30])
        self.assertEqual(skills.skill_de_magia(5401), 30)

    def test_every_shadow_spell_and_weapon_uses_branch_30(self):
        with sqlite3.connect(skills.DB_PATH.resolve().as_uri() + '?mode=ro', uri=True) as connection:
            spells = connection.execute('SELECT id FROM magic WHERE 技能限制1=?', ('影刃技能',)).fetchall()
            self.assertGreater(len(spells), 400)
            for identifier, in spells:
                self.assertEqual(skills.skill_de_magia(int(identifier)), 30)
            weapons = []
            for suffix in ('', '2', '3', '4', '5', '6', '7', '8', '9'):
                weapons.extend(connection.execute(f'SELECT id FROM item{suffix} WHERE 物品類別=?', ('影刃',)).fetchall())
            self.assertGreater(len(weapons), 1000)
            for identifier, in weapons:
                self.assertEqual(clases.skill_de_item(int(identifier)), 30)

    def test_gm_learning_uses_shadowblade_not_light_armor(self):
        self.assertTrue(skills.hechizos_de_ramas_activas([30], solo_maximo=False, nivel_tope=100))
        self.assertEqual(skills.hechizos_de_ramas_activas([32], solo_maximo=False, incluir_comunes=True), [])

    def test_shadowblade_aliases_and_legacy_alchemy_rejection(self):
        for name in ('ShadowBlade', 'Shadow Blade', '30'):
            self.assertEqual(skills.numero_de_rama(name), 30)
            self.assertEqual(app._gm_parsear('/rama add ' + name)[0], 'rama')
        self.assertEqual(skills.numero_de_rama('Mantle'), 32)
        self.assertEqual(skills.numero_de_rama('Alchemy'), 0)

    def test_assassin_class_normal_and_fallback(self):
        assassin = [30, 12, 13, 35, 36, 32]
        self.assertEqual(skills.calcular_class_id(assassin), 14)
        with patch.object(skills, '_PUNTOS_CLASE', {}):
            self.assertEqual(skills.calcular_class_id(assassin), 14)
            self.assertNotEqual(skills.calcular_class_id([32]), 14)
        self.assertEqual(skills.calcular_class_id([17, 15, 16, 18, 19, 32]), 9)

    def test_no_shadowblade_producer_class_or_extra_slot_filler(self):
        self.assertNotIn(30, ramas.PRODUCCION)
        self.assertNotIn(14, ramas.CLASES_PRODUCCION)
        self.assertNotIn(30, skills.RAMAS_RELLENO)
        self.assertTrue(set(skills.RAMAS_RELLENO) <= ramas.PRODUCCION)
        self.assertEqual(ramas.tope_nivel(30, 20), 20)
        self.assertEqual(ramas.tope_nivel(32, 20), 20)
        self.assertEqual(ramas.tope_nivel(31, 20), 31)

    def test_tutorial_weapon_and_no_robot_for_assassin(self):
        assassin = [30, 12, 13, 35, 36, 32]
        self.assertEqual(dict(clases.regalo(assassin)), {3: 19856})
        self.assertNotIn(10, dict(clases.premio_final(assassin)))
        self.assertEqual(clases.cajas_de(assassin), clases.CAJAS_GUERRERO)
        self.assertEqual(clases.regalo([32]), [])
        self.assertEqual(dict(clases.regalo([31, 20, 21, 24, 25, 32]))[10], 19814)

    def test_shadowblade_equipment_is_one_handed_but_not_dual(self):
        self.assertEqual(clases.skill_de_item(19856), 30)
        self.assertFalse(clases.es_dos_manos(19856))
        self.assertEqual(inventario.ranura_equipo_de(19856), 3)
        self.assertFalse(inventario.es_arma_dual(19856))
        self.assertFalse(clases.lleva_duales({3: 19856, 4: 19820}))
        self.assertEqual(combate.golpe_de_arma(19856), combate.GOLPE_POR_SKILL[30])

    def test_melee_trains_shadowblade_only_with_its_weapon(self):
        self.assertIn(30, clases.skills_que_suben('melee', {30}))
        self.assertIn(32, clases.skills_que_suben('melee', {30}))
        self.assertNotIn(30, clases.skills_que_suben('melee', {9}))
        self.assertNotIn(30, clases.skills_que_suben('producir'))
        self.assertNotIn(30, clases.skills_que_suben('recolectar'))
        self.assertNotIn(30, clases.skills_que_suben('producir', {30}))
        self.assertNotIn(30, clases.skills_que_suben('recolectar', {30}))
        self.assertTrue({35, 36} <= clases.skills_que_suben('distancia', {17}))

    def test_shadowblade_attribute_growth_requires_shadow_weapon(self):
        branches = [(30, 10, 0), (35, 10, 0), (36, 10, 0)]
        bare = inventario.bonos_de_habilidades(branches)
        armed = inventario.bonos_de_habilidades(branches, {3: 19856})
        sword = inventario.bonos_de_habilidades(branches, {3: 10})
        self.assertEqual((bare['atk'], bare['agi'], bare['rigor']), (2, 8, 2))
        self.assertEqual((armed['atk'], armed['agi'], armed['rigor']), (11, 26, 11))
        self.assertEqual(sword, bare)
        self.assertEqual(armed['carga'], 2000)

    def test_light_armor_keeps_defense_load_and_never_shadow_attack(self):
        bonus = inventario.bonos_de_habilidades([(32, 10, 0)], {3: 19856})
        self.assertEqual((bonus['def'], bonus['agi'], bonus['carga'], bonus['atk']), (3, 1, 2600, 0))

    def test_existing_spell_records_do_not_authorize_wrong_branch(self):
        self.assertTrue(skills.permite_magia_de_sombra(5401, [(30, 1, 0)]))
        self.assertFalse(skills.permite_magia_de_sombra(5401, [(32, 100, 0)]))
        self.assertTrue(skills.permite_magia_de_sombra(601, [(9, 1, 0)]))

    def test_old_spell_is_rejected_before_combat_dispatch(self):
        packets = []
        character = login.Personaje(habilidades=[(32, 1, 0)], stage=41)
        session = SimpleNamespace(personaje=character, rol='mundo', enviar=lambda *values: packets.extend(values))
        with patch.object(combate, 'parsear_ataque', return_value=(5401, 100)):
            app.Servidor.manejar(None, session, 0x0006, None, None, ('test', 0), b'nonempty')
        self.assertTrue(any(b'ShadowBlade' in packet for packet in packets))

    def test_panel_keeps_30_and_32_separate(self):
        original = [(30, 10, 12), (32, 9, 7), (35, 8, 0), (36, 7, 0), (12, 6, 0), (13, 5, 0)]
        before = list(original)
        packet = clases.arbol(original)
        offset = 2 + len(clases._arbol()['cabecera'])
        records = {packet[position]: packet[position:position + 14]
                   for position in range(offset, len(packet), 14)}
        self.assertEqual(struct.unpack_from('<H', records[30], 1)[0], 10)
        self.assertEqual(struct.unpack_from('<H', records[32], 1)[0], 9)
        self.assertEqual(original, before)

    def test_shadowblade_arena_reward_not_confused_with_armor(self):
        result = arena_premios_compat.plan(
            {'stage': 240, 'clasificacion': [1], 'fin': 100}, 1, {'nivel': 410},
            {'habilidades': [(30, 410, 0), (32, 410, 0)], 'inventario': {3: 19856}},
            {'habilitado': True},
        )
        self.assertEqual(result['weapon_skill'], 30)
        self.assertEqual(result['armor_skill'], 32)
        self.assertEqual(result['items'][0]['id'], 66303)


class TestExperiencePaths(unittest.TestCase):
    def make_session(self):
        character = login.Personaje(nivel=20, habilidades=[(30, 20, 0), (31, 20, 0), (32, 20, 0)])
        return SimpleNamespace(personaje=character, usuario=None, inventario={3: 19856}, sp=0, enviar=lambda *packets: None)

    def test_combat_and_production_have_different_caps(self):
        session = self.make_session()
        with patch.object(clases, 'exp_requerida_skill', return_value=10):
            app._otorgar_skill_exp(session, session.personaje, 1001, skills_forzadas={30, 31, 32}, prob_override=1)
        levels = {sid: level for sid, level, _ in session.personaje.habilidades}
        self.assertEqual(levels[30], 20)
        self.assertEqual(levels[32], 20)
        self.assertGreater(levels[31], 20)

    def test_skill_voucher_cap(self):
        session = self.make_session()
        with patch.object(clases, 'exp_requerida_skill', return_value=10):
            app._dar_exp_habilidad(session, 30, 100)
            app._dar_exp_habilidad(session, 31, 100)
        self.assertEqual(session.personaje.habilidades[0][1], 20)
        self.assertGreater(session.personaje.habilidades[1][1], 20)

    def test_farm_reward_cap(self):
        session = self.make_session()
        with patch.object(clases, 'exp_requerida_skill', return_value=10):
            farm_mecanicas._experiencia(session, skill=10)
        levels = {sid: level for sid, level, _ in session.personaje.habilidades}
        self.assertEqual(levels[30], 20)
        self.assertEqual(levels[32], 20)
        self.assertGreater(levels[31], 20)


if __name__ == '__main__':
    unittest.main()
