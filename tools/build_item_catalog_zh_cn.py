"""Build a read-only offline item index using local server and CN client data."""
import argparse
import contextlib
import ctypes
import datetime
import functools
import json
import mmap
import os
import pathlib
import re
import sqlite3
import sys
import zlib
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[1]
TABLES = ('item', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8', 'item9')
sys.path.insert(0, str(ROOT / 'server'))
import paks_cliente


_PLACEHOLDER = re.compile(r'^(?:/c\$\d+)?%s(?:/c\*)?$', re.IGNORECASE)
_HAN = re.compile(r'[\u3400-\u9fff]')
_JAPANESE_OR_KOREAN = re.compile(r'[\u3040-\u30ff\uac00-\ud7af]')
_COLOR_TAG = re.compile(r'/c(?:\$\d*)?')
_UNUSABLE_DESCRIPTIONS = {'none', 'null'}
_TRADITIONAL_FIXES = str.maketrans('後隻裡髮於', '后只里发于')
_PHRASE_FIXES = (
    (
        '可重复使用的道具，使用后效果时间内，将怪物掉好宝的机率调高至平时的三倍。',
        '可重复使用。有效时间内，将从怪物身上获得稀有物品的几率提高至平时的三倍。',
    ),
    (
        '可重复使用的道具，使用后效果时间内，获得的技能经验值加倍。',
        '可重复使用。有效时间内，击败怪物获得的技能经验值加倍。',
    ),
    ('蒐集', '收集'),
    ('机率', '几率'),
    ('乾淨', '干净'),
    ('乾燥', '干燥'),
    (
        'Open it to get one of the following things randomly:',
        '打开后可随机获得以下物品之一：',
    ),
    (
        'Only characters with level 220 or higher can use it.',
        '仅限220级及以上角色使用。',
    ),
    (
        'Equip to gain a spell effect that increases Skill EXP gained by 100%.',
        '装备后可获得法术效果：技能经验获取量提高100%。',
    ),
)


def normalize_description(value):
    text = str(value or '').replace('\\n', '\n').replace('\\r', '\r').strip()
    if not text or text.casefold() in _UNUSABLE_DESCRIPTIONS or _PLACEHOLDER.fullmatch(text):
        return ''
    return _COLOR_TAG.sub('', text.replace('/c*', '')).replace('%s', '……').strip()


_LCMAP = None


def to_simplified(value):
    global _LCMAP
    text = str(value or '')
    if not text or not _HAN.search(text):
        return text
    if os.name == 'nt':
        if _LCMAP is None:
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            _LCMAP = kernel32.LCMapStringEx
            _LCMAP.argtypes = (
                ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_int,
                ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                ctypes.c_void_p,
            )
            _LCMAP.restype = ctypes.c_int
        output = ctypes.create_unicode_buffer(len(text) * 2 + 16)
        written = _LCMAP(
            'zh-CN', 0x02000000, text, len(text), output, len(output),
            None, None, None,
        )
        if not written:
            raise ctypes.WinError(ctypes.get_last_error())
        text = output.value[:written]
    text = text.translate(_TRADITIONAL_FIXES)
    for original, replacement in _PHRASE_FIXES:
        text = text.replace(original, replacement)
    return text


def looks_chinese(value):
    text = str(value or '')
    han = len(_HAN.findall(text))
    latin = len(re.findall(r'[A-Za-z]', text))
    return bool(han) and not _JAPANESE_OR_KOREAN.search(text) and latin <= han * 4 + 20


@functools.lru_cache(maxsize=8192)
def localize_official_description(value):
    text = normalize_description(value)
    if not looks_chinese(text):
        return ''
    return to_simplified(text)


def read_client_descriptions(client):
    client = pathlib.Path(client)
    if not client.is_dir():
        return {}
    paks = sorted(
        (path for path in client.iterdir()
         if path.suffix.lower() == '.pak' and paks_cliente.numero(path.name) >= -1),
        key=lambda path: paks_cliente.numero(path.name),
    )
    latest = {}
    for pak in paks:
        try:
            with pak.open('rb') as stream, mmap.mmap(
                    stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
                for name, _, compressed, _, offset in paks_cliente._directorio(data):
                    normalized = name.lower().replace('\\', '/')
                    if (normalized.startswith('setting/big5/')
                            and pathlib.PurePosixPath(normalized).stem in TABLES):
                        latest[normalized] = (pak, compressed, offset)
        except (OSError, ValueError, zlib.error):
            continue
    descriptions = {}
    for table in TABLES:
        entry = latest.get(f'setting/big5/{table}.xml')
        if entry is None:
            continue
        pak, compressed, offset = entry
        try:
            with pak.open('rb') as stream:
                stream.seek(offset)
                raw = zlib.decompress(stream.read(compressed), -15)
            root = ET.fromstring(raw)
        except (OSError, ValueError, zlib.error, ET.ParseError):
            continue
        for row in root:
            identifier = row.get('編號', '')
            if identifier.isdigit() and identifier not in descriptions:
                descriptions[identifier] = row.get('說明定義', '')
    return descriptions


def load_fallbacks(path):
    path = pathlib.Path(path)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    return {
        normalize_description(source): str(translation)
        for source, translation in data.get('by_source', {}).items()
    }


def fallback_description(value):
    text = normalize_description(value)
    if not text:
        return ''
    match = re.fullmatch(
        r'\(equipment level limited to Lv (\d+)\)', text, re.IGNORECASE)
    if match:
        return f'（装备等级限制：Lv {match.group(1)}）'
    match = re.fullmatch(
        r'Lv (\d+) Zionic (Armor|weapon)\.\s*'
        r'\(equipment level limited to Lv (\d+)\)',
        text, re.IGNORECASE | re.DOTALL,
    )
    if match:
        kind = '护甲' if match.group(2).casefold() == 'armor' else '武器'
        return f'Lv {match.group(1)} Zionic {kind}。\n（装备等级限制：Lv {match.group(3)}）'
    match = re.fullmatch(r'Lv (\d+) special ride\.', text, re.IGNORECASE)
    if match:
        return f'Lv {match.group(1)} 特殊坐骑。'
    match = re.fullmatch(r'Level (\d+) special mount\.', text, re.IGNORECASE)
    if match:
        return f'Lv {match.group(1)} 特殊坐骑。'
    match = re.fullmatch(r'A special ride with Level (\d+) stats\.', text, re.IGNORECASE)
    if match:
        return f'拥有 Lv {match.group(1)} 属性的特殊坐骑。'
    match = re.fullmatch(
        r'A Lv (\d+) special ride\. Requires Lv (\d+) and above\.', text, re.IGNORECASE)
    if match:
        return f'Lv {match.group(1)} 特殊坐骑，需 Lv {match.group(2)} 以上。'
    return ''


def localize_description(identifier, source, official, fallbacks):
    official_text = localize_official_description(official.get(identifier, ''))
    if official_text:
        return official_text
    source_text = normalize_description(source)
    if not source_text:
        return ''
    if source_text in fallbacks:
        return fallbacks[source_text]
    translated = fallback_description(source_text)
    if translated:
        return translated
    if looks_chinese(source_text):
        return to_simplified(source_text)
    return '暂无官方中文说明。'


def read_items(database, catalog, descriptions=None, fallbacks=None):
    translations = json.loads(catalog.read_text(encoding='utf-8'))['item']
    descriptions = descriptions or {}
    fallbacks = fallbacks or {}
    items = {}
    with contextlib.closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        for table in TABLES:
            for record in connection.execute(f'SELECT * FROM "{table}"'):
                row = dict(record)
                identifier = str(row.get('id', ''))
                if not identifier.isdigit() or int(identifier) in items:
                    continue
                name = str(row.get('基本名稱') or '')
                prefix = str(row.get('原型名稱') or '')
                english = f'{prefix} {name}'.strip() if prefix and prefix.casefold() not in name.casefold() else name
                items[int(identifier)] = {
                    'id': int(identifier), 'zh': translations.get(identifier, ''),
                    'en': english, 'kind': str(row.get('物品類別') or '未分类'),
                    'level': str(row.get('等級限制') or row.get('物品等級') or ''),
                    'quality': str(row.get('顏色') or ''),
                    'description': localize_description(
                        identifier, row.get('說明定義') or '',
                        descriptions, fallbacks,
                    ), 'table': table,
                }
    return sorted(items.values(), key=lambda row: row['id'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=pathlib.Path, default=ROOT / 'corpus/content.db')
    parser.add_argument('--catalog', type=pathlib.Path, default=ROOT / 'data/localization/zh_CN.json')
    parser.add_argument('--output', type=pathlib.Path, default=ROOT / 'data/localization/items.zh-CN.html')
    parser.add_argument('--client', type=pathlib.Path, default=ROOT / 'client-local')
    parser.add_argument(
        '--fallbacks', type=pathlib.Path,
        default=ROOT / 'tools/item_description_fallbacks_zh_cn.json',
    )
    parser.add_argument('--no-client', action='store_true')
    args = parser.parse_args()
    descriptions = {} if args.no_client else read_client_descriptions(args.client)
    items = read_items(args.database, args.catalog, descriptions, load_fallbacks(args.fallbacks))
    data = json.dumps(items, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    template = (ROOT / 'tools/item_catalog_zh_cn.html').read_text(encoding='utf-8')
    output = template.replace('__GENERATED_AT__', datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
    output = output.replace('__ITEM_DATA__', data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(output, encoding='utf-8')
    temporary.replace(args.output)
    print(
        f'{len(items)} items; {sum(bool(row["zh"]) for row in items)} CN names; '
        f'{sum(bool(row["description"]) for row in items)} CN descriptions; {args.output}'
    )


if __name__ == '__main__':
    main()
