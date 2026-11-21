"""Build ignored display-name mappings from a locally installed CN client."""
import argparse
import collections
import json
import mmap
import pathlib
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
import paks_cliente


def client_tables(client):
    wanted = {'npc.xml', 'monster.xml', 'skill.xml', 'magic.xml',
              'achievement.xml', 'crown.xml', 'quest.xml', 'stage.xml', 'string.xml'}
    wanted.update('item.xml' if number == 1 else f'item{number}.xml' for number in range(1, 10))
    latest = {}
    paks = sorted((path for path in client.iterdir()
                   if path.suffix.lower() == '.pak' and paks_cliente.numero(path.name) >= -1),
                  key=lambda path: paks_cliente.numero(path.name))
    for pak in paks:
        with pak.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            for name, crc, compressed, size, offset in paks_cliente._directorio(data):
                name = name.lower().replace('\\', '/')
                if name.startswith('setting/gb/') and pathlib.PurePosixPath(name).name in wanted:
                    latest[name] = (pak, compressed, offset)
    for name, (pak, compressed, offset) in latest.items():
        loose = client / pathlib.PurePosixPath(name)
        if loose.is_file():
            raw = loose.read_bytes()
            source = str(loose.relative_to(client))
        else:
            with pak.open('rb') as stream:
                stream.seek(offset)
                raw = zlib.decompress(stream.read(compressed), -15)
            source = pak.name
        yield pathlib.PurePosixPath(name).stem, ET.fromstring(raw), source


def build(client, database):
    result = {'locale': 'zh_CN', 'npc': {}, 'monster': {}, 'item': {},
              'skill': {}, 'magic': {}, 'achievement': {}, 'crown': {},
              'quest': {}, 'stage': {}, 'string': {}, 'aliases': {}, 'sources': {}}
    candidates = collections.defaultdict(set)
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        for table, rows, source in client_tables(client):
            category = 'item' if table.startswith('item') else table
            result['sources'][table] = source
            for row in rows:
                identifier = row.get('編號', '')
                name_column = {'item': '基本名稱', 'crown': '封號', 'quest': '任務名稱',
                               'string': '文字'}.get(category, '名稱')
                name = row.get(name_column)
                if identifier.isdigit() and name:
                    result[category][identifier] = name
            if category in ('skill', 'achievement', 'crown', 'string'):
                continue
            column = {'item': '基本名稱', 'quest': '任務名稱'}.get(category, 'name')
            for identifier, english in connection.execute(f'SELECT id, "{column}" FROM "{table}"'):
                chinese = result[category].get(str(identifier))
                if english and chinese:
                    candidates[str(english)].add(chinese)
    for filename, category in (('logros.json', 'achievement'), ('misiones.json', 'quest')):
        data = json.loads((ROOT / 'server' / 'plantillas' / filename).read_text(encoding='utf-8'))
        for entry in data.get('filas', []):
            chinese = result[category].get(str(entry.get('id')))
            english = entry.get('nombre')
            if english and chinese:
                candidates[english].add(chinese)
    import daily_events
    for english, brackets in daily_events.GAMES:
        chinese = result['string'].get(str(brackets[0][1]))
        if chinese:
            candidates[english] = {chinese.rstrip('ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ ')}
    import clases
    for identifier, english in clases.NOMBRE_RAMA.items():
        chinese = result['skill'].get(str(identifier))
        if chinese:
            candidates[english].add(chinese)
    for path in (ROOT / 'server' / 'plantillas').glob('*.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            continue
        for entry in data.get('spawns', []):
            if not isinstance(entry, dict):
                continue
            category = 'monster' if entry.get('monstruo') or entry.get('klass') == 1 else 'npc'
            chinese = result[category].get(str(entry.get('npc_type', '')))
            english = entry.get('nombre')
            if english and chinese:
                candidates[english].add(chinese)
    result['aliases'] = {english: next(iter(names)) for english, names in sorted(candidates.items())
                         if len(names) == 1 and not re.search('[\u3400-\u9fff]', english)}
    if not result['npc'] or not result['monster']:
        raise ValueError('The selected client has no setting/gb NPC or monster tables')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, default=ROOT / 'data' / 'localization' / 'zh_CN.json')
    args = parser.parse_args()
    data = build(args.client, ROOT / 'corpus' / 'content.db')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(args.output)
    print(json.dumps({key: len(value) for key, value in data.items() if isinstance(value, dict)}))
    print(args.output)


if __name__ == '__main__':
    main()
