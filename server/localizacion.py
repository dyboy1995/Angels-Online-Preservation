"""Optional display translations from the player's own Chinese client tables."""
import functools
import json
import logging
import os
import pathlib
import struct

from mensajes_zh_cn import MENSAJES_ZH_CN, traducir_mensaje


log = logging.getLogger(__name__)
DEFAULT_CATALOG = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'localization' / 'zh_CN.json'


def activa():
    return os.environ.get('AO_LOCALE', '') == 'zh_CN'


@functools.lru_cache(maxsize=4)
def _leer_catalogo(path):
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
        if data.get('locale') != 'zh_CN':
            raise ValueError('Expected zh_CN catalog')
        return data
    except (OSError, ValueError):
        log.exception('No se pudo cargar el catalogo local %s', path)
        return {}


def catalogo():
    return _leer_catalogo(os.environ.get('AO_LOCALE_FILE') or str(DEFAULT_CATALOG))


def traducir(texto):
    if not activa():
        return texto
    original = str(texto)
    if original in MENSAJES_ZH_CN:
        return MENSAJES_ZH_CN[original]
    aliases = catalogo().get('aliases', {})
    if original in aliases:
        return aliases[original]
    return traducir_mensaje(original, lambda name: aliases.get(name, MENSAJES_ZH_CN.get(name, name)))


def codificar(texto, *, limite=None, legacy='ascii'):
    encoding = 'gbk' if activa() else legacy
    encoded = str(texto).encode(encoding, 'replace')
    if limite is not None:
        encoded = encoded[:limite]
        if encoding == 'gbk':
            encoded = encoded.decode(encoding, 'ignore').encode(encoding)
    return encoded


def texto(texto_original, *, legacy='ascii'):
    return codificar(traducir(texto_original), legacy=legacy)


def nombre(tipo, identificador, original):
    if not activa():
        return original
    return catalogo().get(tipo, {}).get(str(identificador), original)


def paquete(packet):
    if not activa() or len(packet) < 2:
        return packet
    opcode = struct.unpack_from('<H', packet)[0]
    translated = None
    width = 17
    if opcode == 0x0008 and len(packet) >= 49:
        kind = struct.unpack_from('<I', packet, 42)[0]
        type_id = struct.unpack_from('<H', packet, 47)[0]
        if kind == 1:
            table = 'monster'
        elif kind in (199, 200, 400, 500):
            table = 'npc'
        else:
            return packet
        translated = catalogo().get(table, {}).get(str(type_id))
    elif opcode == 0x000F and len(packet) == 46:
        width = 16
        original = packet[18:34].split(b'\x00', 1)[0].decode('ascii', 'ignore')
        translated = catalogo().get('aliases', {}).get(original)
    if not translated:
        return packet
    output = bytearray(packet)
    output[18:18 + width] = codificar(translated, limite=16).ljust(width, b'\x00')
    return bytes(output)


def paquetes(packets, rol):
    if rol != 'mundo' or not activa():
        return packets
    return tuple(paquete(packet) for packet in packets)
