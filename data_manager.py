import logging
import os
import re
import shutil
import sqlite3
import stat
from typing import Iterable

from app_paths import APP_DATA_DIR, BUNDLE_DIR, DB_PATH, LEGACY_DB_PATH, OLD_DB_PATHS, RUN_DIR, ensure_app_data_dir

logger = logging.getLogger(__name__)

DATA_DIR = APP_DATA_DIR
BANK_DIR = os.path.join(RUN_DIR, "bank2025.2")
_LEGACY_DB_PATHS = (*OLD_DB_PATHS, LEGACY_DB_PATH)


def _ensure_data_dir() -> None:
    ensure_app_data_dir()


def _ensure_db_writable() -> None:
    """Best-effort clear of read-only bit after copying seed DB."""
    if not os.path.exists(DB_PATH):
        return
    try:
        os.chmod(DB_PATH, stat.S_IREAD | stat.S_IWRITE)
    except Exception:
        pass


def _seed_db_candidates() -> Iterable[str]:
    # Preferred: bundled in one-file EXE resources.
    yield os.path.join(BUNDLE_DIR, "bin_database.db")
    # Dev fallback.
    yield os.path.join(RUN_DIR, "bin_database.db")


def ensure_local_db_ready() -> None:
    """Ensure writable local DB exists. First run copies bundled seed DB."""
    if os.path.exists(DB_PATH):
        _ensure_db_writable()
        return

    _ensure_data_dir()

    # Migration path: if legacy DB exists, keep user data without writing back.
    for legacy_path in _LEGACY_DB_PATHS:
        if os.path.exists(legacy_path) and os.path.abspath(legacy_path) != os.path.abspath(DB_PATH):
            shutil.copy2(legacy_path, DB_PATH)
            _ensure_db_writable()
            logger.info("Migrated legacy DB from %s to %s", legacy_path, DB_PATH)
            return

    for candidate in _seed_db_candidates():
        if os.path.exists(candidate):
            shutil.copy2(candidate, DB_PATH)
            _ensure_db_writable()
            logger.info("Initialized local DB from seed: %s", candidate)
            return

    # Last resort: create empty DB.
    conn = sqlite3.connect(DB_PATH)
    conn.close()
    _ensure_db_writable()
    logger.warning("No seed DB found. Created empty local DB at %s", DB_PATH)


def get_db_connection() -> sqlite3.Connection:
    ensure_local_db_ready()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_query_history_schema(conn: sqlite3.Connection) -> None:
    """Add new columns for forward compatibility."""
    c = conn.cursor()
    c.execute("PRAGMA table_info(query_history)")
    columns = {row[1] for row in c.fetchall()}

    if "card_length" not in columns:
        try:
            c.execute("ALTER TABLE query_history ADD COLUMN card_length INTEGER DEFAULT 0")
        except sqlite3.OperationalError as exc:
            logger.warning("Skip schema upgrade for query_history: %s", exc)


def init_db() -> None:
    ensure_local_db_ready()
    conn = get_db_connection()
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS bin_data (
            bin_code TEXT PRIMARY KEY,
            bank_abbr TEXT,
            bank_name TEXT,
            card_type TEXT,
            card_length INTEGER,
            source TEXT
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            card_no TEXT,
            bin_code TEXT,
            bank_name TEXT,
            card_type TEXT,
            card_length INTEGER DEFAULT 0,
            source TEXT
        )
        """
    )

    _ensure_query_history_schema(conn)

    conn.commit()
    conn.close()


def parse_go_files_to_db() -> bool:
    """Load seed BIN data from bank2025.2/bin.go + name.go."""
    bin_go_path = os.path.join(BANK_DIR, "bin.go")
    name_go_path = os.path.join(BANK_DIR, "name.go")
    if not os.path.exists(bin_go_path) or not os.path.exists(name_go_path):
        logger.error("Cannot find bin.go or name.go in %s", BANK_DIR)
        return False

    bank_name_map: dict[str, str] = {}
    name_pattern = re.compile(r'"([^"]+)":\s*"([^"]+)",')
    with open(name_go_path, "r", encoding="utf-8") as f:
        for line in f:
            m = name_pattern.search(line)
            if m:
                bank_name_map[m.group(1)] = m.group(2)

    bin_pattern = re.compile(
        r'\{Bin:\s*"(\d+)",\s*Bank:\s*"([^"]+)",\s*Type:\s*"([^"]+)",\s*Length:\s*(\d+)\}'
    )
    type_map = {
        "DC": "借记卡",
        "CC": "信用卡",
        "SCC": "准贷记卡",
        "PC": "预付费卡",
    }

    records: list[tuple[str, str, str, str, int, str]] = []
    with open(bin_go_path, "r", encoding="utf-8") as f:
        for line in f:
            m = bin_pattern.search(line)
            if not m:
                continue
            bin_code = m.group(1)
            bank_abbr = m.group(2)
            card_type_raw = m.group(3)
            card_length = int(m.group(4))
            bank_name = bank_name_map.get(bank_abbr, bank_abbr)
            records.append(
                (
                    bin_code,
                    bank_abbr,
                    bank_name,
                    type_map.get(card_type_raw, card_type_raw),
                    card_length,
                    "LocalDB",
                )
            )

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("BEGIN TRANSACTION")
    c.executemany(
        """
        INSERT OR REPLACE INTO bin_data
        (bin_code, bank_abbr, bank_name, card_type, card_length, source)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    conn.close()

    logger.info("Loaded %d BIN records into local DB.", len(records))
    return True


def _pick_column(columns: set[str], candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return ""


def import_excel_to_db(file_path: str) -> int:
    import pandas as pd

    try:
        df = pd.read_excel(file_path)
    except Exception as exc:
        raise Exception(f"Failed to read Excel file: {exc}")

    columns = set(str(col).strip() for col in df.columns)

    col_bin = _pick_column(columns, ["BIN码", "BIN", "bin_code"])
    col_abbr = _pick_column(columns, ["银行简称", "bank_abbr"])
    col_bank = _pick_column(columns, ["银行名称", "bank_name"])
    col_type = _pick_column(columns, ["卡类型", "card_type"])
    col_len = _pick_column(columns, ["卡号长度", "卡号位数", "card_length"])
    col_source = _pick_column(columns, ["来源", "source"])

    if not col_bin or not col_bank:
        raise Exception("Excel 缺少必要列：BIN码、银行名称")

    records: list[tuple[str, str, str, str, int, str]] = []
    for _, row in df.iterrows():
        bin_code = str(row.get(col_bin, "")).strip()
        if not bin_code or bin_code.lower() == "nan":
            continue

        bank_abbr = str(row.get(col_abbr, "")).strip() if col_abbr else ""
        bank_name = str(row.get(col_bank, "")).strip()
        card_type = str(row.get(col_type, "")).strip() if col_type else ""

        card_length = 0
        if col_len:
            try:
                card_length = int(row.get(col_len, 0) or 0)
            except Exception:
                card_length = 0

        source = "UserImport"
        if col_source:
            raw_source = str(row.get(col_source, "")).strip()
            if raw_source and raw_source.lower() != "nan":
                source = raw_source

        records.append((bin_code, bank_abbr, bank_name, card_type, card_length, source))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("BEGIN TRANSACTION")
    c.executemany(
        """
        INSERT OR REPLACE INTO bin_data
        (bin_code, bank_abbr, bank_name, card_type, card_length, source)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    conn.close()

    return len(records)


def get_chinese_bank_name(abbr_or_name: str) -> str:
    if not abbr_or_name:
        return ""

    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT bank_name FROM bin_data WHERE bank_abbr = ? LIMIT 1", (abbr_or_name,))
    row = c.fetchone()
    if row and row["bank_name"]:
        conn.close()
        return row["bank_name"]

    c.execute("SELECT bank_name FROM bin_data WHERE bank_name LIKE ? LIMIT 1", (f"%{abbr_or_name}%",))
    row = c.fetchone()
    if row and row["bank_name"]:
        conn.close()
        return row["bank_name"]

    conn.close()
    return abbr_or_name


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    parse_go_files_to_db()
