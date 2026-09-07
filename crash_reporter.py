import traceback
from datetime import datetime

from app_paths import CRASH_LOG_PATH, ensure_app_data_dir


def write_crash_log(exc_type, exc_value, exc_traceback):
    """
    Format exception and write it to the application data crash log file.
    """
    try:
        ensure_app_data_dir()
        with open(CRASH_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("============== CRASH REPORT ==============\n")
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
            f.write("\n")
    except Exception:
        pass
