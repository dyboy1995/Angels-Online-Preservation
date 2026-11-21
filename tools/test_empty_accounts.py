"""An intentionally cleared database must not resurrect legacy accounts."""
import json
import pathlib
import sqlite3
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import cuentas


@pytest.fixture
def isolated_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(cuentas, 'BASE', tmp_path)
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path / 'cuentas.db')
    monkeypatch.setattr(cuentas, 'ARCHIVO', tmp_path / 'cuentas.json')
    monkeypatch.setattr(cuentas, 'BACKUPS_DIR', tmp_path / 'backups')
    monkeypatch.setattr(cuentas, '_notificar_cambio', lambda **kwargs: None)
    return tmp_path


def test_existing_empty_database_never_imports_old_mirrors_or_creates_default(isolated_accounts, monkeypatch):
    old = {'cuentas': {'legacy-test': {'password': 'unused-test-value', 'personajes': []}}}
    cuentas.ARCHIVO.write_text(json.dumps(old), encoding='utf-8')
    cuentas.ARCHIVO.with_suffix('.json.bak').write_text(json.dumps(old), encoding='utf-8')
    with sqlite3.connect(cuentas.DB_PATH) as connection:
        connection.execute("CREATE TABLE cuentas(usuario TEXT PRIMARY KEY COLLATE NOCASE, password TEXT NOT NULL DEFAULT '')")
    def unexpected_migration(connection):
        pytest.fail('Existing empty database must not be migrated')
    monkeypatch.setattr(cuentas, '_migrar_desde_json', unexpected_migration)
    cuentas._init_db()
    cuentas._init_db()
    with sqlite3.connect(cuentas.DB_PATH) as connection:
        assert connection.execute('SELECT COUNT(*) FROM cuentas').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM personajes').fetchone()[0] == 0


def test_first_database_creation_still_imports_legacy_accounts(isolated_accounts, monkeypatch):
    old = {'cuentas': {'legacy-test': {'password': 'unused-test-value', 'personajes': []}}}
    cuentas.ARCHIVO.write_text(json.dumps(old), encoding='utf-8')
    monkeypatch.setattr(cuentas, 'hacer_backup', lambda **kwargs: None)
    cuentas._init_db()
    with sqlite3.connect(cuentas.DB_PATH) as connection:
        assert connection.execute('SELECT usuario FROM cuentas').fetchall() == [('legacy-test',)]


def test_new_login_registers_password_after_reset(isolated_accounts):
    with sqlite3.connect(cuentas.DB_PATH) as connection:
        connection.execute("CREATE TABLE cuentas(usuario TEXT PRIMARY KEY COLLATE NOCASE, password TEXT NOT NULL DEFAULT '')")
    cuentas._init_db()
    auth = b'new-user'.ljust(21, b'\0') + b'1' * 32 + bytes(20)
    result, reason = cuentas.validar('new-user', auth)
    assert result == {'personajes': []}
    assert cuentas.validar('new-user', auth)[0] == result
    wrong = auth[:21] + b'2' * 32 + auth[53:]
    assert cuentas.validar('new-user', wrong)[0] is None
    cuentas._init_db()
    with sqlite3.connect(cuentas.DB_PATH) as connection:
        assert connection.execute('SELECT COUNT(*) FROM cuentas').fetchone()[0] == 1
