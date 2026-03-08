import sys
import traceback
import requests
from bmob_client import BMOB_APP_ID, BMOB_REST_API_KEY, _username

def upload_crash_log_to_bmob(exc_type, exc_value, exc_traceback):
    """
    Format exception and upload it to Bmob 'ErrorLog' table.
    Also write to a local crash.log file.
    """
    # 1. Write to local file for immediate local inspection
    try:
        with open("crash_report.log", "a", encoding="utf-8") as f:
            f.write("============== CRASH REPORT ==============\n")
            import datetime
            f.write(str(datetime.datetime.now()) + "\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
            f.write("\n")
    except:
        pass

    # 2. Upload to Bmob ErrorLog table
    try:
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        full_trace = "".join(tb_lines)
        
        url = "https://api.bmobcloud.com/1/classes/ErrorLog"
        headers = {
            "X-Bmob-Application-Id": BMOB_APP_ID,
            "X-Bmob-REST-API-Key": BMOB_REST_API_KEY,
            "Content-Type": "application/json"
        }
        
        user_id = _username if _username else "Unknown/NotLoggedIn"
        
        payload = {
            "error_message": str(exc_value),
            "traceback": full_trace,
            "username": user_id,
            "version": "V1.6"
        }
        
        requests.post(url, json=payload, headers=headers, timeout=5, verify=False)
    except Exception:
        pass # If crash reporter crashes, we just silently die
