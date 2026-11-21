"""Report untranslated literal notices at known player-message sinks (not full UI coverage)."""
import argparse
import ast
import json
import os
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
import localizacion


SINKS = {'aviso', '_aviso', '_avisar', 'avisar', 'clases_aviso', 'notice', '_notice',
         'reject', 'Rechazo', 'cartel_deslizante', 'anuncio_banner', '_announce'}


def literals(root=ROOT / 'server'):
    records = {}
    for path in sorted(root.glob('*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            if name not in SINKS:
                continue
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    text = argument.value
                    if re.search('[A-Za-z]', text):
                        records.setdefault(text, []).append(f'{path.name}:{node.lineno}')
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    os.environ['AO_LOCALE'] = 'zh_CN'
    records = literals()
    missing = {text: locations for text, locations in records.items()
               if localizacion.traducir(text) == text}
    print(json.dumps({'checked_literal_notices': len(records), 'untranslated': missing}, ensure_ascii=False, indent=2))
    return int(args.check and bool(missing))


if __name__ == '__main__':
    raise SystemExit(main())
