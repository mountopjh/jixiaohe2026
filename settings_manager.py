import json
import os
import sys

if getattr(sys, 'frozen', False):
    # 打包为EXE时：配置放在EXE同级目录
    _CONFIG_DIR = os.path.dirname(sys.executable)
else:
    _CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = os.path.join(_CONFIG_DIR, 'settings.json')

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {"hotkey": "f6"}
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"hotkey": "f6"}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")
