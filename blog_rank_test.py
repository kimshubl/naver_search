import requests
import json
import hashlib
import hmac
import base64
import time

# ▶️ 네이버 검색광고 API 자격 정보
BASE_URL = "https://api.searchad.naver.com"
CUSTOMER_ID = "3446272"
API_KEY = "0100000000bd8891ee4c5db49440aaf83c51fabb44a4e656a3b74635c64ac59f881b2c1913"             # X-API-KEY
SECRET_KEY = "AQAAAAC9iJHuTF20lECq+DxR+rtEfZl1fJIJV6H/Gc+szk0v8A=="
TARGET_KEYWORD = " "

def make_signature(secret_key, method, uri, timestamp):
    message = f"{timestamp}.{method}.{uri}"
    signature = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(signature).decode()

# ▶️ 검색량 가져오기 함수
def get_monthly_search_volume(keyword):
    uri = "/keywordstool"
    method = "GET"
    timestamp = str(int(time.time() * 1000))
    signature = make_signature(SECRET_KEY, method, uri, timestamp)

    headers = {
        "X-Timestamp": timestamp,
        "X-API-KEY": API_KEY,
        "X-CUSTOMER": CUSTOMER_ID,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }

    params = {
        "hintKeywords": keyword,
        "showDetail": 1
    }

    url = f"{BASE_URL}{uri}"
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        result = response.json()
        for item in result['keywordList']:
            if item['relKeyword'] == keyword:
                return {
                    "keyword": item['relKeyword'],
                    "monthlyPcQcCnt": item['monthlyPcQcCnt'],
                    "monthlyMobileQcCnt": item['monthlyMobileQcCnt'],
                    "monthlyTotalQcCnt": int(item['monthlyPcQcCnt']) + int(item['monthlyMobileQcCnt'])

                }
    else:
        print("Error:", response.status_code, response.text)
        return None

# ▶️ 실행
#TARGET_KEYWORD = input()
#result = get_monthly_search_volume(TARGET_KEYWORD)
#print(result)