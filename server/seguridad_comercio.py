"""Local Simplified Chinese character-packet compatibility fields."""
import os
import struct

CN_PROFILE = 'cn-8.6.5.7'
CN_CHARACTER_PACKET_SIZE = 0x1819
CN_PASSWORD_FLAG_OFFSET = 0x1761
CN_STAGE_OFFSET = 0x1773
PASSWORD_CLEARED_MESSAGE = 906


def ajustar_ficha(packet, stage=None):
    if os.environ.get('AO_CLIENT_PROTOCOL', 'igg') != CN_PROFILE:
        return packet
    if packet[:2] != b'\x02\x00':
        return packet
    result = bytearray(packet)
    if len(result) < CN_CHARACTER_PACKET_SIZE:
        result.extend(bytes(CN_CHARACTER_PACKET_SIZE - len(result)))
    result[CN_PASSWORD_FLAG_OFFSET] = 0
    if stage is not None:
        struct.pack_into('<I', result, CN_STAGE_OFFSET, int(stage) & 0xFFFFFFFF)
    return bytes(result)


def procesar(session, opcode, body):
    if (opcode != 0x0049 or os.environ.get('AO_CLIENT_PROTOCOL', 'igg') != CN_PROFILE
            or session.rol != 'mundo' or not getattr(session, 'personaje', None)):
        return False
    if len(body) != 136:
        return True
    session.enviar(struct.pack('<HHB', 0x000D, PASSWORD_CLEARED_MESSAGE, 0) + bytes(3))
    return True
