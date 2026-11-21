import unittest
import struct
import sys
import pathlib
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'server'))
import login

class TestSceneMap(unittest.TestCase):
    def test_cn_map_state_covers_native_lighting_preset_read(self):
        with patch.object(login, '_mapas_sin_minimapa', return_value=set()):
            packet = login.flags_de_mapa(41, perfil='cn-8.6.5.7')
        self.assertEqual(len(packet), 13)
        self.assertEqual(struct.unpack_from('<I', packet, 2)[0], 0x0205)
        self.assertEqual(packet[6:9], bytes((12, 0, 0)))
        self.assertEqual(struct.unpack_from('<i', packet, 9)[0], -1)

    def test_cn_map_state_keeps_instance_minimap_flag(self):
        with patch.object(login, '_mapas_sin_minimapa', return_value={112}):
            packet = login.flags_de_mapa(112, perfil='cn-8.6.5.7')
        self.assertEqual(struct.unpack_from('<I', packet, 2)[0], 0x0225)

    def test_cn_map_state_profile_applies_with_and_without_template(self):
        captured = bytes.fromhex('05020000ff0000')
        with patch.dict('os.environ', {'AO_CLIENT_PROTOCOL': 'cn-8.6.5.7'}):
            with patch.object(login, '_mapas_sin_minimapa', return_value=set()):
                self.assertEqual(login.flags_de_mapa(41, captured), login.flags_de_mapa(41))
                self.assertEqual(len(login.flags_de_mapa(41)), 13)

    def test_legacy_map_state_stays_byte_identical(self):
        captured = bytes.fromhex('05020000ff0000')
        with patch.object(login, '_mapas_sin_minimapa', return_value=set()):
            packet = login.flags_de_mapa(41, captured, perfil='igg')
        self.assertEqual(packet, b'\x14\x00' + captured)

    def test_opcode_0014_map_flags_bit20(self):
        """Verifica que el opcode 0x0014 conserve los flags de mapa oficiales (0x0205)

        y NO tenga el bit 0x20 encendido, ya que Angel.exe lo interpreta como 'desactivar mapa'.
        """
        p = login.Personaje(entity_id=1003, stage=41)
        submsgs = login.secuencia(p)
        
        op14_found = False
        for sub in submsgs:
            op = struct.unpack_from('<H', sub, 0)[0]
            if op == 0x0014:
                op14_found = True
                flags = struct.unpack_from('<I', sub, 2)[0]
                self.assertEqual(flags & 0x20, 0, f"Bit 0x20 no debe estar encendido en flags de mapa (flags={flags:08x})")
                self.assertEqual(flags, 0x0205, f"Flags de mapa esperados 0x0205, se obtuvo {flags:08x}")
                break
        
        self.assertTrue(op14_found, "No se encontro el sub-mensaje 0x0014 en la secuencia")

    def test_poblar_stage_41_contains_npcs_and_resources(self):
        """Verifica que en el stage 41 se envien los spawns de NPC (0x0008) y recursos (0x000E)."""
        p = login.Personaje(entity_id=1001, stage=41)
        submsgs = login.secuencia(p)
        ops = [struct.unpack_from('<H', sub, 0)[0] for sub in submsgs]
        
        self.assertIn(0x0008, ops, "Debe enviar 0x0008 (NPC spawns) para poblar el mapa")
        self.assertIn(0x000E, ops, "Debe enviar 0x000E (recursos) para poblar el mapa")

if __name__ == '__main__':
    unittest.main()

