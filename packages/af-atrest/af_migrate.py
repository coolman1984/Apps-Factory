"""Plaintext SQLite → SQLCipher migration with safety backup and rollback."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import sqlite3

import af_atrest as core
from af_errors import AtRestError

MIGRATE_MARKER = '.af-migrate-plain-backup'


def _find_plaintext_dbs(data_dir: str) -> list[str]:
    data_dir = os.path.abspath(data_dir)
    out: list[str] = []
    try:
        names = os.listdir(data_dir)
    except OSError:
        return out
    for name in sorted(names):
        if not name.endswith('.db'):
            continue
        path = os.path.join(data_dir, name)
        if os.path.isfile(path) and core.is_plain_sqlite(path):
            out.append(path)
    return out


def _row_counts(path: str, *, encrypted: bool = False, data_key: bytes | None = None) -> dict[str, int]:
    if encrypted:
        driver = core._sqlcipher()
        if driver is None or data_key is None:
            raise AtRestError('ATREST_MIGRATE_SQLCIPHER_MISSING')
        conn = driver.connect(path)
        try:
            conn.execute("PRAGMA key = \"x'" + data_key.hex() + "'\"")
        except Exception:
            conn.close()
            raise
    else:
        conn = sqlite3.connect(path)
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    finally:
        conn.close()


def _integrity_ok(path: str, *, encrypted: bool = False, data_key: bytes | None = None) -> bool:
    if encrypted:
        driver = core._sqlcipher()
        if driver is None or data_key is None:
            return False
        conn = driver.connect(path)
        try:
            conn.execute("PRAGMA key = \"x'" + data_key.hex() + "'\"")
            row = conn.execute('PRAGMA integrity_check').fetchone()
            return row is not None and row[0] == 'ok'
        finally:
            conn.close()
    conn = sqlite3.connect(path)
    try:
        row = conn.execute('PRAGMA integrity_check').fetchone()
        return row is not None and row[0] == 'ok'
    finally:
        conn.close()


def _encrypt_db_plain_to_sqlcipher(plain_path: str, enc_path: str, data_key: bytes) -> None:
    driver = core._sqlcipher()
    if driver is None:
        raise AtRestError('ATREST_MIGRATE_SQLCIPHER_MISSING')
    hexkey = data_key.hex()
    dst = driver.connect(enc_path)
    try:
        dst.execute("PRAGMA key = \"x'" + hexkey + "'\"")
        dst.execute('ATTACH DATABASE ? AS plain KEY \'\'', (plain_path,))
        try:
            dst.execute("SELECT sqlcipher_export('main', 'plain')").fetchone()
        finally:
            dst.execute('DETACH DATABASE plain')
        dst.execute('PRAGMA journal_mode=DELETE')
        dst.commit()
    finally:
        dst.close()


def _marker_path(data_dir: str) -> str:
    return os.path.join(os.path.abspath(data_dir), MIGRATE_MARKER)


def _read_marker(data_dir: str) -> dict | None:
    path = _marker_path(data_dir)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_marker(data_dir: str, state: dict) -> None:
    path = _marker_path(data_dir)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, sort_keys=True)
        f.write('\n')
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _clear_marker(data_dir: str) -> None:
    try:
        os.remove(_marker_path(data_dir))
    except OSError:
        pass


def rollback_migration(data_dir: str) -> bool:
    """
    Restore plaintext databases from safety copies recorded in the migrate marker.
    Returns True when a rollback was performed.
    """
    data_dir = os.path.abspath(data_dir)
    state = _read_marker(data_dir)
    if not state:
        return False
    backups = state.get('backups')
    if not isinstance(backups, dict):
        _clear_marker(data_dir)
        return False
    for db_name, backup_path in backups.items():
        if not isinstance(db_name, str) or not isinstance(backup_path, str):
            continue
        live = os.path.join(data_dir, db_name)
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, live)
        for suffix in ('-wal', '-shm'):
            try:
                os.remove(live + suffix)
            except OSError:
                pass
        try:
            os.remove(backup_path)
        except OSError:
            pass
    temps = state.get('temp_files') or []
    if isinstance(temps, list):
        for tmp in temps:
            if isinstance(tmp, str):
                for suffix in ('', '-wal', '-shm'):
                    try:
                        os.remove(tmp + suffix)
                    except OSError:
                        pass
    _clear_marker(data_dir)
    return True


def _verify_encrypted(enc_path: str, plain_path: str, data_key: bytes) -> None:
    if not _integrity_ok(enc_path, encrypted=True, data_key=data_key):
        raise AtRestError('ATREST_MIGRATE_VERIFY_FAILED', 'integrity_check')
    if not _integrity_ok(plain_path, encrypted=False):
        raise AtRestError('ATREST_MIGRATE_VERIFY_FAILED', 'integrity_check plain')
    counts_before = _row_counts(plain_path, encrypted=False)
    counts_after = _row_counts(enc_path, encrypted=True, data_key=data_key)
    if counts_after != counts_before:
        raise AtRestError('ATREST_MIGRATE_VERIFY_FAILED', 'row counts')


def _migrate_one_db(data_dir: str, plain_db: str, data_key: bytes, state: dict) -> None:
    plain_db = os.path.abspath(plain_db)
    db_name = os.path.basename(plain_db)
    backup_db = plain_db + '.plaintext-safety'
    shutil.copy2(plain_db, backup_db)
    state['backups'][db_name] = backup_db
    _write_marker(data_dir, state)

    enc_tmp = os.path.join(
        data_dir,
        '.af-mig-' + secrets.token_hex(8) + '-' + db_name + '.tmp',
    )
    state['temp_files'].append(enc_tmp)
    _write_marker(data_dir, state)

    _encrypt_db_plain_to_sqlcipher(plain_db, enc_tmp, data_key)
    _verify_encrypted(enc_tmp, plain_db, data_key)
    os.replace(enc_tmp, plain_db)
    state['temp_files'] = [t for t in state['temp_files'] if t != enc_tmp]
    try:
        os.remove(backup_db)
    except OSError:
        pass
    state['backups'].pop(db_name, None)
    _write_marker(data_dir, state)
    for suffix in ('-wal', '-shm'):
        try:
            os.remove(enc_tmp + suffix)
        except OSError:
            pass


def migrate_to_encrypted(data_dir: str, sqlcipher_driver=None) -> None:
    """
    Idempotent: no-op when no plaintext databases remain. Keeps plaintext safety backups
    until each encrypted copy is verified and atomically installed in the data directory.
    """
    data_dir = os.path.abspath(data_dir)
    if _read_marker(data_dir):
        rollback_migration(data_dir)

    plains = _find_plaintext_dbs(data_dir)
    if not plains:
        key_path = core._key_path(data_dir)
        if os.path.exists(key_path):
            return
        raise AtRestError('ATREST_MIGRATE_NO_PLAINTEXT_DB')

    orig_driver = core._DRIVER
    orig_tried = core._DRIVER_TRIED
    if sqlcipher_driver is not None:
        core._DRIVER = sqlcipher_driver
        core._DRIVER_TRIED = True
    try:
        if core._sqlcipher() is None:
            raise AtRestError('ATREST_MIGRATE_SQLCIPHER_MISSING')
        data_key = core.data_key(data_dir)
        state = {'v': 1, 'backups': {}, 'temp_files': []}
        _write_marker(data_dir, state)
        for plain_db in list(plains):
            if not core.is_plain_sqlite(plain_db):
                continue
            try:
                _migrate_one_db(data_dir, plain_db, data_key, state)
            except Exception:
                rollback_migration(data_dir)
                raise
    finally:
        core._DRIVER = orig_driver
        core._DRIVER_TRIED = orig_tried

    _clear_marker(data_dir)
