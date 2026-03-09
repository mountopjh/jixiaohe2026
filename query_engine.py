import requests
import sqlite3
import logging
from data_manager import get_db_connection

logger = logging.getLogger(__name__)

ALIPAY_API_URL = "https://ccdcapi.alipay.com/validateAndCacheCardInfo.json"

def query_local_db(card_number):
    """
    Search for a matching BIN in the local SQLite database.
    We try matching the longest prefix possible from 10 chars down to 3.
    """
    conn = get_db_connection()
    c = conn.cursor()
    # Check prefixes starting with largest possible length (e.g. 10 chars -> 3 chars)
    for length in range(10, 2, -1):
        if len(card_number) >= length:
            prefix = card_number[:length]
            c.execute("SELECT * FROM bin_data WHERE bin_code = ?", (prefix,))
            row = c.fetchone()
            if row:
                conn.close()
                return dict(row)
    conn.close()
    return None

def query_alipay_api(card_number):
    """
    Query the Alipay API to find card info.
    Particularly effective for full 15-19 digit card numbers.
    """
    try:
        params = {
            '_input_charset': 'utf-8',
            'cardNo': card_number,
            'cardBinCheck': 'true'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        res = requests.get(ALIPAY_API_URL, params=params, headers=headers, timeout=5)
        data = res.json()
        
        if data.get('validated') == True:
            bank_abbr = data.get('bank')
            card_type = data.get('cardType')  # e.g., DC (debit), CC (credit)
            
            # Map type abbreviations to string
            type_map = {
                "DC": "借记卡",
                "CC": "信用卡",
                "SCC": "准贷记卡",
                "PC": "预付卡"
            }
            card_type_cn = type_map.get(card_type, card_type)
            
            # Try to get bank name from our DB mapped abbreviations
            from data_manager import get_chinese_bank_name
            bank_name = get_chinese_bank_name(bank_abbr)
            
            # Assuming bin mapping directly as 'alipay-dynamic' or full card prefix isn't standard BIN.
            # But we can store it.
            return {
                "bank_abbr": bank_abbr,
                "bank_name": bank_name,
                "card_type": card_type_cn,
                "bin_code": card_number[:6], # generic assumption
                "card_length": len(card_number),
                "source": "Alipay API"
            }
    except Exception as e:
        logger.error(f"Alipay API Error: {e}")
    return None

def query_cardbin_cn(card_number):
    """
    Playwright scraper for cardbin.cn as a final fallback.
    """
    try:
        url = f"https://cardbin.cn/query/{card_number}.html"
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # use headless mode
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Setup route to block images/css for speed
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "stylesheet", "font"] else route.continue_())
            
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # check if there is a result table or "没有查询到"
            # In typical cardbin.cn, the data is in an html table
            # let's extract all tds
            # Often structured like:
            # <table class="table">...
            # <th>发卡行</th><td>...</td>
            try:
                # Wait for the table to appear
                page.wait_for_selector(".table", timeout=3000)
            except:
                browser.close()
                return None
            
            # Using evaluate to run JS to extract standard info
            data = page.evaluate('''() => {
                let rows = document.querySelectorAll('.table tr');
                let result = {};
                for (let row of rows) {
                    let th = row.querySelector('th');
                    let td = row.querySelector('td');
                    if (th && td) {
                        let key = th.innerText.trim();
                        let val = td.innerText.trim();
                        if (key.includes('发卡行')) result.bank_name = val;
                        if (key.includes('卡种名')) result.card_name = val;
                        if (key.includes('卡类型')) result.card_type = val;
                        if (key.includes('卡号长')) result.card_length = parseInt(val);
                        if (key.includes('BIN号')) result.bin_code = val;
                    }
                }
                return result;
            }''')
            browser.close()
            
            if data and data.get('bank_name'):
                from data_manager import get_chinese_bank_name
                raw_bankName = data.get('bank_name')
                final_bankName = get_chinese_bank_name(raw_bankName)
                return {
                    "bank_abbr": "UNKNOWN", 
                    "bank_name": final_bankName,
                    "card_type": data.get('card_type', '未知'),
                    "bin_code": data.get('bin_code', card_number[:6]),
                    "card_length": data.get('card_length', len(card_number)),
                    "source": "cardbin.cn"
                }
                
    except Exception as e:
        logger.error(f"Cardbin.cn Scraper Error: {e}")
    return None

def save_new_bin_to_db(record):
    """
    Save new discovered BIN info to local DB
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR IGNORE INTO bin_data 
            (bin_code, bank_abbr, bank_name, card_type, card_length, source) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            record.get("bin_code"), 
            record.get("bank_abbr", ""), 
            record.get("bank_name", "未知"), 
            record.get("card_type", ""), 
            record.get("card_length", 0), 
            record.get("source", "Network")
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"Save to DB Error: {e}")
    finally:
        conn.close()

def log_query_history(card_number, record):
    """
    Log query into history table
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO query_history 
            (card_no, bin_code, bank_name, card_type, source) 
            VALUES (?, ?, ?, ?, ?)
        ''', (
            card_number,
            record.get("bin_code", ""),
            record.get("bank_name", ""),
            record.get("card_type", ""),
            record.get("source", "")
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"History DB Error: {e}")
    finally:
        conn.close()

def clear_failed_history():
    """Remove all history entries where the result was not found."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM query_history WHERE bank_name = '未匹配到结果' OR bank_name IS NULL OR bank_name = ''")
        conn.commit()
    except Exception as e:
        logger.error(f"Clear History Error: {e}")
    finally:
        conn.close()

def get_query_history(success_only=False):
    conn = get_db_connection()
    c = conn.cursor()
    if success_only:
        c.execute("SELECT * FROM query_history WHERE bank_name != '未匹配到结果' AND bank_name IS NOT NULL AND bank_name != '' ORDER BY id DESC")
    else:
        c.execute("SELECT * FROM query_history ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def perform_full_query(card_number, signal_sender=None):
    """
    Main entrypoint: 
    1. Check Local DB
    2. If not found, show 'searching' UI if signal_sender provided
    3. Fallback to Alipay API
    4. Fallback to cardbin.cn
    5. Save to DB & History
    """
    # Sanitize: extract all digits
    card_number = "".join([c for c in card_number if c.isdigit()])
    if not card_number:
        return None
        
    record = query_local_db(card_number)
    
    if record:
        # Found locally immediately
        if signal_sender:
            pass # The caller handles showing the immediate popup
    else:
        # Not found locally, dispatch searching notification
        if signal_sender:
            from PyQt6.QtCore import QPoint
            temp_record = {"_status": "searching", "source": "Alipay/Cardbin.cn API"}
            # We don't have cursor pos here easily, but the popup logic handles None
            signal_sender.show_popup_signal.emit(card_number, temp_record, None)
            
        # Step 2: Alipay API
        logger.info("Local DB miss. Trying Alipay API...")
        record = query_alipay_api(card_number)
            
        # Step 3: Cardbin.cn
        if not record:
            logger.info("Alipay API miss or invalid. Trying cardbin.cn...")
            record = query_cardbin_cn(card_number)
            
        if record:
            # Auto save new found record to local DB ONLY IF completely valid
            if record.get("bank_name") and record.get("bank_name") != "未知":
                save_new_bin_to_db(record)
                # Also silently upload to Bmob for cloud collection
                try:
                    from bmob_client import upload_new_bin
                    upload_new_bin(record)
                except Exception:
                    pass
            
            # Send final result if we did a delayed search
            if signal_sender:
                # We do NOT pop it up again here as requirement says: 
                # "如果BIN库没有，弹窗提示正在那个具体网站查询，结果在程序面板查看"
                # So we just let the history update.
                pass
                
    # Always log into history, even if no result was found
    if not record:
        record = {
            "bin_code": "-",
            "bank_name": "未匹配到结果",
            "card_type": "-",
            "source": "None"
        }
        
    log_query_history(card_number, record)
        
    return record


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # Test
    res = perform_full_query('6222021234567890')
    print("Result:", res)
