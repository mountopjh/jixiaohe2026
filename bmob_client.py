"""
Bmob Backend Cloud Client
Handles silent authentication - no error messages are shown to the user on failure.
App silently locks if account is invalid/deleted/banned.
"""
import requests
import urllib3
import logging
import json

# Suppress insecure request warnings if verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

BMOB_APP_ID = "e3b7e91520e0147500562cccdcd04262"
BMOB_REST_API_KEY = "710c52dbe686363f6eb21c660bde099d"
BMOB_BASE_URL = "https://api.bmobcloud.com/1/login"
BMOB_UPLOAD_URL = "https://api.bmobcloud.com/1/classes/BinCodes"

HEADERS = {
    "X-Bmob-Application-Id": BMOB_APP_ID,
    "X-Bmob-REST-API-Key": BMOB_REST_API_KEY,
    "Content-Type": "application/json"
}

# In-memory session token after successful login
_session_token = None
_is_authorized = False
_object_id = None  # Stored from login response for password updates
_username = "" # Stored for UI display


def login(username, password):
    """
    Silently log in to Bmob. Returns True if success, False otherwise.
    NO error messages shown to user -- silent fail is intentional.
    """
    global _session_token, _is_authorized, _object_id, _username
    
    try:
        params = {"username": username, "password": password}
        res = requests.get(BMOB_BASE_URL, params=params, headers=HEADERS, timeout=8, verify=False)
        
        if res.status_code == 200:
            data = res.json()
            _session_token = data.get("sessionToken", "")
            _object_id = data.get("objectId", "")
            _username = data.get("username", username)
            _is_authorized = bool(_session_token)
            return _is_authorized
        else:
            # Silently fail: return False, no error message shown to user
            _is_authorized = False
            _object_id = None
            _username = ""
            return False
    except Exception as e:
        # Network error, offline, etc. -- silently fail
        logger.debug(f"Bmob login error (silent): {e}")
        _is_authorized = False
        _object_id = None
        _username = ""
        return False


def is_authorized():
    """Check if current session is valid."""
    return _is_authorized

def get_current_username():
    """Return the currently logged in username"""
    return _username


def upload_new_bin(record):
    """..."""
    if not _is_authorized or not _session_token:
        return
        
    try:
        payload = {
            "bin_code": record.get("bin_code", ""),
            "bank_name": record.get("bank_name", ""),
            "bank_abbr": record.get("bank_abbr", ""),
            "card_type": record.get("card_type", ""),
            "card_length": record.get("card_length", 0),
            "source": record.get("source", "Network")
        }
        
        headers_with_session = {**HEADERS, "X-Bmob-Session-Token": _session_token}
        requests.post(BMOB_UPLOAD_URL, json=payload, headers=headers_with_session, timeout=5, verify=False)
    except Exception:
        pass


def change_password(old_password, new_password):
    """
    Change the currently logged-in user's password.
    Verifies old password first by re-logging in.
    Returns True on success, False on any failure (silently).
    No error messages are shown to the user.
    """
    global _session_token, _object_id
    
    if not _is_authorized or not _object_id:
        return False
    
    try:
        # Step 1: Re-verify old password is correct by trying to login again with it
        # We need the username - get it from current session via GET /1/users/me
        me_url = "https://api.bmobcloud.com/1/users/me"
        headers_with_session = {**HEADERS, "X-Bmob-Session-Token": _session_token}
        me_res = requests.get(me_url, headers=headers_with_session, timeout=8, verify=False)
        if me_res.status_code != 200:
            return False
        
        username = me_res.json().get("username", "")
        if not username:
            return False
        
        # Step 2: Verify old password by login
        verify_params = {"username": username, "password": old_password}
        verify_res = requests.get(BMOB_BASE_URL, params=verify_params, headers=HEADERS, timeout=8, verify=False)
        if verify_res.status_code != 200:
            return False  # Silent fail if old password is wrong
        
        # Step 3: Update password using PUT /1/users/<objectId>
        update_url = f"https://api.bmobcloud.com/1/users/{_object_id}"
        payload = {"password": new_password}
        update_res = requests.put(update_url, json=payload, headers=headers_with_session, timeout=8, verify=False)
        
        return update_res.status_code == 200
    except Exception as e:
        logger.debug(f"Change password error (silent): {e}")
        return False
