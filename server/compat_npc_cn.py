"""Wire-only NPC prototypes for services absent from the CN 8.6.5.7 tables."""
import os
import struct

import localizacion


def paquete(packet):
    if (os.environ.get('AO_CLIENT_PROTOCOL') != 'cn-8.6.5.7'
            or len(packet) < 49 or packet[:2] != b'\x08\x00'):
        return packet
    kind = struct.unpack_from('<I', packet, 42)[0]
    prototype = struct.unpack_from('<H', packet, 47)[0]
    sprite = struct.unpack_from('<I', packet, 36)[0]
    if kind not in (199, 200, 400, 500) or prototype != 24801 or sprite != 40002:
        return packet
    names = localizacion.catalogo().get('npc', {})
    if '24801' in names or '14231' not in names:
        return packet
    result = bytearray(packet)
    struct.pack_into('<H', result, 47, 14231)
    result[18:35] = '补发天使'.encode('gbk').ljust(17, b'\x00')
    return bytes(result)


def paquetes(packets, role):
    if role != 'mundo':
        return packets
    return tuple(paquete(packet) for packet in packets)
