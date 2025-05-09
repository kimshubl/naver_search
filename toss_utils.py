import requests
import base64
import json
import uuid
import hmac
import hashlib
from config import TOSS_SECRET_KEY, TOSS_WEBHOOK_SECRET

TOSS_API_BASE_URL = "https://api.tosspayments.com/v1"

def get_toss_auth_header():
    """Toss Payments API 인증 헤더 생성 (Basic Auth)"""
    # 시크릿 키 뒤에 콜론(:) 추가 후 Base64 인코딩
    encoded_key = base64.b64encode(f"{TOSS_SECRET_KEY}:".encode('utf-8')).decode('utf-8')
    return {
        "Authorization": f"Basic {encoded_key}",
        "Content-Type": "application/json",
    }

def request_toss_payment_approval(payment_key: str, order_id: str, amount: int):
    """
    Toss Payments 결제 승인 요청
    (일반 결제 및 빌링키 첫 결제 시 사용)
    """
    url = f"{TOSS_API_BASE_URL}/payments/{payment_key}"
    headers = get_toss_auth_header()
    payload = {
        "orderId": order_id,
        "amount": amount,
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status() # 오류 발생 시 예외 발생
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Toss 결제 승인 요청 실패: {e}")
        # 응답 내용 로깅 (디버깅용)
        if hasattr(e, 'response') and e.response is not None:
             print(f"Response Body: {e.response.text}")
        return None

def request_toss_billing_key_payment(billing_key: str, customer_key: str, order_id: str, amount: int, order_name: str):
    """
    저장된 빌링키로 자동 결제 요청 (구독 갱신용)
    customerKey는 사용자를 식별하는 고유값 (예: user.id 또는 user.username)
    """
    url = f"{TOSS_API_BASE_URL}/billing/authorizations/{billing_key}"
    headers = get_toss_auth_header()
    # idempotency_key는 재요청 시 중복 처리를 방지하기 위해 사용 (선택 사항)
    # headers["Idempotency-Key"] = str(uuid.uuid4())
    payload = {
        "customerKey": customer_key,
        "amount": amount,
        "orderId": order_id,
        "orderName": order_name,
        # 필요에 따라 추가 파라미터 설정 가능 (예: taxFreeAmount)
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Toss 빌링키 결제 요청 실패: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"Response Body: {e.response.text}")
        return None

def verify_toss_webhook_signature(request_body: bytes, signature: str) -> bool:
    """
    Toss Payments 웹훅 요청 서명 검증
    request_body: Flask request.data (bytes)
    signature: request.headers.get('TossPayments-Signature')
    """
    if not TOSS_WEBHOOK_SECRET or not signature:
        print("웹훅 시크릿 키 또는 서명이 없습니다.")
        return False

    try:
        # HMAC-SHA256으로 서명 생성
        generated_signature = hmac.new(
            key=TOSS_WEBHOOK_SECRET.encode('utf-8'),
            msg=request_body,
            digestmod=hashlib.sha256
        ).hexdigest()

        # 제공된 서명과 생성된 서명 비교
        return hmac.compare_digest(generated_signature, signature)
    except Exception as e:
        print(f"웹훅 서명 검증 중 오류 발생: {e}")
        return False

def generate_unique_order_id(prefix=""):
    """고유한 주문 ID 생성 (예: 'sub_uuid' 또는 'point_uuid')"""
    return f"{prefix}{uuid.uuid4()}"
