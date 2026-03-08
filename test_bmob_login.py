import requests
import json

BMOB_APP_ID = "e3b7e91520e0147500562cccdcd04262"
BMOB_REST_API_KEY = "710c52dbe686363f6eb21c660bde099d"
BMOB_BASE_URL = "https://api2.bmob.cn/1/login"

HEADERS = {
    "X-Bmob-Application-Id": BMOB_APP_ID,
    "X-Bmob-REST-API-Key": BMOB_REST_API_KEY,
    "Content-Type": "application/json"
}

URLS = [
    "https://api.bmobcloud.com/1/login",
    "http://api.bmobcloud.com/1/login",
    "https://api.bmob.cn/1/login",
]

def test_login(username, password):
    params = {"username": username, "password": password}
    
    for url in URLS:
        print(f"\nTrying {url} (verify=False)...")
        try:
            res = requests.get(url, params=params, headers=HEADERS, timeout=8, verify=False)
            print("Status Code:", res.status_code)
            try:
                print("Response JSON:", res.json())
                if res.status_code == 200:
                    return # found working one
            except Exception as e:
                print("Response Text:", res.text)
        except Exception as e:
            print(f"Error on {url}: {e}")

if __name__ == "__main__":
    test_login("shipengsong", "sps123456")
