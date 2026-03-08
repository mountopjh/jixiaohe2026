import os
import re
import sqlite3
import logging

logger = logging.getLogger(__name__)

DB_PATH = 'bin_database.db'
BANK_DIR = 'bank2025.2'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Create bin_data table
    c.execute('''
        CREATE TABLE IF NOT EXISTS bin_data (
            bin_code TEXT PRIMARY KEY,
            bank_abbr TEXT,
            bank_name TEXT,
            card_type TEXT,
            card_length INTEGER,
            source TEXT
        )
    ''')
    
    # Create query_history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            card_no TEXT,
            bin_code TEXT,
            bank_name TEXT,
            card_type TEXT,
            source TEXT
        )
    ''')
    conn.commit()
    conn.close()

def parse_go_files_to_db():
    bin_go_path = os.path.join(BANK_DIR, 'bin.go')
    name_go_path = os.path.join(BANK_DIR, 'name.go')
    
    if not os.path.exists(bin_go_path) or not os.path.exists(name_go_path):
        logger.error(f"Cannot find bin.go or name.go in {BANK_DIR}")
        return False
        
    bank_name_map = {}
    
    # Parse name.go
    # Example: "ABC":  "中国农业银行",
    name_pattern = re.compile(r'"([^"]+)":\s*"([^"]+)",')
    with open(name_go_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = name_pattern.search(line)
            if match:
                bank_name_map[match.group(1)] = match.group(2)
                
    # Parse bin.go
    # Example: {Bin: "103", Bank: "ABC", Type: "DC", Length: 19},
    bin_pattern = re.compile(r'\{Bin:\s*"(\d+)",\s*Bank:\s*"([^"]+)",\s*Type:\s*"([^"]+)",\s*Length:\s*(\d+)\}')
    
    records = []
    with open(bin_go_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = bin_pattern.search(line)
            if match:
                bin_code = match.group(1)
                bank_abbr = match.group(2)
                card_type = match.group(3)
                card_length = int(match.group(4))
                
                bank_name = bank_name_map.get(bank_abbr, bank_abbr)
                # Map Type DC/CC etc to more readable strings if needed, but let's keep original or standard mapping
                # DC = 借记卡 (Debit Card), CC = 信用卡 (Credit Card), SCC = 准贷记卡, PC = 预付卡
                type_map = {
                    "DC": "借记卡",
                    "CC": "信用卡",
                    "SCC": "准贷记卡",
                    "PC": "预付卡"
                }
                card_type_cn = type_map.get(card_type, card_type)
                
                records.append((bin_code, bank_abbr, bank_name, card_type_cn, card_length, "LocalDB"))

    # Insert into SQLite
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("BEGIN TRANSACTION")
    c.executemany('''
        INSERT OR REPLACE INTO bin_data 
        (bin_code, bank_abbr, bank_name, card_type, card_length, source) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', records)
    conn.commit()
    conn.close()
    
    logger.info(f"Successfully loaded {len(records)} BIN records into the database.")
    return True

def import_excel_to_db(file_path):
    import pandas as pd
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        raise Exception(f"Failed to read Excel file: {e}")
        
    # We expect columns like: BIN码, 银行缩写, 银行名称, 卡类型, 卡号长度, 数据来源
    # Or fallback to indexing if someone uploads a raw list
    required_cols = {"BIN码", "银行名称", "卡类型"}
    present_cols = set(df.columns)
    
    if not required_cols.issubset(present_cols):
        # Maybe it has no headers, try to infer or just fail
        raise Exception(f"Excel file missing required columns. Needs at least: {required_cols}")
        
    records = []
    for _, row in df.iterrows():
        bin_code = str(row.get('BIN码', '')).strip()
        if not bin_code or bin_code == 'nan': continue
        
        bank_abbr = str(row.get('银行缩写', '')).strip()
        if bank_abbr == 'nan': bank_abbr = ''
            
        bank_name = str(row.get('银行名称', '')).strip()
        card_type = str(row.get('卡类型', '')).strip()
        
        card_length = row.get('卡号长度', 0)
        try:
            card_length = int(card_length)
        except:
            card_length = 0
            
        source = str(row.get('数据来源', 'UserImport')).strip()
        if not source or source == 'nan':
            source = 'UserImport'
            
        records.append((bin_code, bank_abbr, bank_name, card_type, card_length, source))
        
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("BEGIN TRANSACTION")
    c.executemany('''
        INSERT OR REPLACE INTO bin_data 
        (bin_code, bank_abbr, bank_name, card_type, card_length, source) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', records)
    conn.commit()
    conn.close()
    
    return len(records)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    init_db()
    parse_go_files_to_db()
