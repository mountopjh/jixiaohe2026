import logging
import re
from typing import Any, Dict, Optional

import requests

from data_manager import get_chinese_bank_name, get_db_connection

logger = logging.getLogger(__name__)

ALIPAY_API_URL = "https://ccdcapi.alipay.com/validateAndCacheCardInfo.json"
CARD_BIN_URL = "https://cardbin.cn/query/{card_number}.html"
NOT_FOUND_TEXT = "未查询到"

SEARCH_WEBSITES = [
    {
        "name": "支付宝 BIN 接口",
        "url": "https://ccdcapi.alipay.com/validateAndCacheCardInfo.json",
    },
    {
        "name": "cardbin",
        "url": "https://cardbin.cn",
    },
]

CARD_TYPE_MAP = {
    "DC": "借记卡",
    "CC": "信用卡",
    "SCC": "准贷记卡",
    "PC": "预付费卡",
}


DEFAULT_MIN_CARD_LENGTH = 16


def get_min_bank_card_length() -> int:
    """Best-effort read of minimum card length from local BIN DB."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT MIN(card_length) AS min_len FROM bin_data WHERE card_length > 0")
        row = c.fetchone()
        min_len = int(row["min_len"]) if row and row["min_len"] else 0
        return min_len if min_len > 0 else DEFAULT_MIN_CARD_LENGTH
    except Exception as exc:
        logger.warning("Read min card length failed, fallback=%s, err=%s", DEFAULT_MIN_CARD_LENGTH, exc)
        return DEFAULT_MIN_CARD_LENGTH
    finally:
        conn.close()


def _normalize_card_type(card_type: str) -> str:
    if not card_type:
        return ""
    return CARD_TYPE_MAP.get(card_type.strip().upper(), card_type.strip())


def query_local_db(card_number: str) -> Optional[Dict[str, Any]]:
    """Find BIN data by longest prefix match from 10 to 3 digits."""
    conn = get_db_connection()
    c = conn.cursor()
    for length in range(10, 2, -1):
        if len(card_number) < length:
            continue
        prefix = card_number[:length]
        c.execute("SELECT * FROM bin_data WHERE bin_code = ?", (prefix,))
        row = c.fetchone()
        if row:
            conn.close()
            return dict(row)
    conn.close()
    return None


def query_alipay_api(card_number: str) -> Optional[Dict[str, Any]]:
    """Network fallback #1: Alipay public BIN endpoint."""
    try:
        params = {
            "_input_charset": "utf-8",
            "cardNo": card_number,
            "cardBinCheck": "true",
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        res = requests.get(ALIPAY_API_URL, params=params, headers=headers, timeout=6)
        data = res.json()
        if data.get("validated") is not True:
            return None

        bank_abbr = (data.get("bank") or "").strip()
        bank_name = get_chinese_bank_name(bank_abbr) if bank_abbr else ""
        return {
            "bank_abbr": bank_abbr,
            "bank_name": bank_name or NOT_FOUND_TEXT,
            "card_type": _normalize_card_type(data.get("cardType", "")),
            "bin_code": card_number[:6],
            "card_length": len(card_number),
            "source": "Alipay API",
        }
    except Exception as exc:
        logger.error("Alipay API error: %s", exc)
        return None


def _extract_cardbin_value(html: str, keys: list[str]) -> str:
    for key in keys:
        pattern = rf"{key}</th>\s*<td[^>]*>(.*?)</td>"
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            value = re.sub(r"<[^>]+>", "", match.group(1))
            return value.strip()
    return ""


def query_cardbin_cn(card_number: str) -> Optional[Dict[str, Any]]:
    """Network fallback #2: cardbin.cn HTML parse."""
    try:
        url = CARD_BIN_URL.format(card_number=card_number)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code != 200:
            return None

        html = res.text
        bank_name_raw = _extract_cardbin_value(html, ["发卡银行", "银行名称", "银行"])
        card_type = _extract_cardbin_value(html, ["卡类型", "卡种"])
        card_length_text = _extract_cardbin_value(html, ["卡号长度", "长度"])
        bin_code = _extract_cardbin_value(html, ["BIN", "BIN码", "发卡行识别码"]) or card_number[:6]

        if not bank_name_raw:
            return None

        card_length = len(card_number)
        if card_length_text:
            digits = re.findall(r"\d+", card_length_text)
            if digits:
                card_length = int(digits[0])

        return {
            "bank_abbr": "",
            "bank_name": get_chinese_bank_name(bank_name_raw) or bank_name_raw,
            "card_type": _normalize_card_type(card_type),
            "bin_code": bin_code,
            "card_length": card_length,
            "source": "cardbin.cn",
        }
    except Exception as exc:
        logger.error("cardbin.cn parse error: %s", exc)
        return None


def save_new_bin_to_db(record: Dict[str, Any]) -> None:
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT OR IGNORE INTO bin_data
            (bin_code, bank_abbr, bank_name, card_type, card_length, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("bin_code", ""),
                record.get("bank_abbr", ""),
                record.get("bank_name", ""),
                record.get("card_type", ""),
                int(record.get("card_length", 0) or 0),
                record.get("source", "Network"),
            ),
        )
        conn.commit()
    except Exception as exc:
        logger.error("Save BIN to DB failed: %s", exc)
    finally:
        conn.close()


def log_query_history(card_number: str, record: Dict[str, Any]) -> None:
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO query_history
            (card_no, bin_code, bank_name, card_type, card_length, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                card_number,
                record.get("bin_code", ""),
                record.get("bank_name", ""),
                record.get("card_type", ""),
                int(record.get("card_length", 0) or 0),
                record.get("source", ""),
            ),
        )
        conn.commit()
    except Exception as exc:
        # Backward-compat path for older DB schema without card_length.
        if "card_length" in str(exc):
            try:
                c.execute(
                    """
                    INSERT INTO query_history
                    (card_no, bin_code, bank_name, card_type, source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        card_number,
                        record.get("bin_code", ""),
                        record.get("bank_name", ""),
                        record.get("card_type", ""),
                        record.get("source", ""),
                    ),
                )
                conn.commit()
                return
            except Exception as legacy_exc:
                logger.error("Write query_history legacy fallback failed: %s", legacy_exc)
                return
        logger.error("Write query_history failed: %s", exc)
    finally:
        conn.close()


def clear_failed_history() -> None:
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            DELETE FROM query_history
            WHERE bank_name = ? OR bank_name IS NULL OR TRIM(bank_name) = ''
            """,
            (NOT_FOUND_TEXT,),
        )
        conn.commit()
    except Exception as exc:
        logger.error("Clear failed history failed: %s", exc)
    finally:
        conn.close()


def clear_all_history() -> None:
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM query_history")
        conn.commit()
    except Exception as exc:
        logger.error("Clear all history failed: %s", exc)
    finally:
        conn.close()


def get_query_history(success_only: bool = False) -> list[Dict[str, Any]]:
    conn = get_db_connection()
    c = conn.cursor()
    if success_only:
        c.execute(
            """
            SELECT * FROM query_history
            WHERE bank_name != ? AND bank_name IS NOT NULL AND TRIM(bank_name) != ''
            ORDER BY id DESC
            """,
            (NOT_FOUND_TEXT,),
        )
    else:
        c.execute("SELECT * FROM query_history ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def perform_full_query(card_number: str, signal_sender=None) -> Optional[Dict[str, Any]]:
    """
    Query flow:
    1) local SQLite
    2) Network route by card-number length:
       - len < min-card-length: cardbin first
       - len >= min-card-length: Alipay first
    3) Fallback to the other network source
    """
    card_number = "".join(ch for ch in (card_number or "") if ch.isdigit())
    if not card_number:
        return None

    record = query_local_db(card_number)

    if not record:
        min_card_length = get_min_bank_card_length()
        prefer_alipay = len(card_number) >= min_card_length

        ordered_sites = (
            [SEARCH_WEBSITES[0], SEARCH_WEBSITES[1]]
            if prefer_alipay
            else [SEARCH_WEBSITES[1], SEARCH_WEBSITES[0]]
        )

        if signal_sender:
            searching_record = {
                "_status": "searching",
                "website_urls": [site["url"] for site in ordered_sites],
                "website_text": "\n".join(
                    f"{idx + 1}. {site['name']}: {site['url']}"
                    for idx, site in enumerate(ordered_sites)
                ),
            }
            signal_sender.show_popup_signal.emit(card_number, searching_record, None)

        network_chain = (
            [query_alipay_api, query_cardbin_cn] if prefer_alipay else [query_cardbin_cn, query_alipay_api]
        )
        for query_fn in network_chain:
            record = query_fn(card_number)
            if record:
                break

        if record and record.get("bank_name") and record.get("bank_name") != NOT_FOUND_TEXT:
            if not record.get("card_length"):
                record["card_length"] = len(card_number)
            save_new_bin_to_db(record)

    if not record:
        record = {
            "bin_code": card_number[:6] if len(card_number) >= 6 else card_number,
            "bank_name": NOT_FOUND_TEXT,
            "card_type": "-",
            "card_length": len(card_number),
            "source": "Network",
        }

    if not record.get("card_length"):
        record["card_length"] = len(card_number)

    log_query_history(card_number, record)
    return record


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(perform_full_query("6222021234567890"))
