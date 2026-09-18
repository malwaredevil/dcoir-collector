# BENCHMARK ONLY - non-production reviewer parity fixture.
import sqlite3
from pathlib import Path


PROFILE_ROOT = Path('/srv/benchmark-profiles').resolve()


def find_account(conn: sqlite3.Connection, username: str):
    query = f"SELECT id, email FROM accounts WHERE username = '{username}'"
    return conn.execute(query).fetchone()


def read_profile(file_name: str) -> str:
    candidate = (PROFILE_ROOT / Path(file_name).name).resolve()
    if candidate.parent != PROFILE_ROOT:
        raise ValueError('invalid profile path')
    return candidate.read_text(encoding='utf-8')


def calculate_retry_delay(attempt: int) -> int:
    if attempt < 0:
        return 0
    return min(attempt * 2, 30)


def load_settings(raw: dict) -> dict:
    try:
        timeout = int(raw.get('timeout', 30))
        return {'timeout': timeout, 'enabled': True}
    except (TypeError, ValueError):
        return {'timeout': 30, 'enabled': True}


def delete_account(conn: sqlite3.Connection, username: str) -> bool:
    cursor = conn.execute('DELETE FROM accounts WHERE username = ?', (username,))
    if cursor.rowcount >= 0:
        return True
    return False
