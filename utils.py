from flask import redirect, url_for, session
from functools import wraps
import sqlite3

import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import time
__all__ = [
    'login_required',
    'get_db_connection',
    'save_to_db',
    'load_from_db',
    'delete_from_db',
    'update_db',
    'hash_password',
    'check_password',
    'send_verification_email',
    'send_password_reset',
    'is_request_too_soon',
    'is_token_expired',
    'send_username_email',
    'send_admin_login_verification' # Add new function to __all__
]

# login_required라는 데코레이터를 정의
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# SQLite 연결을 위한 함수 (데이터베이스 이름을 인자로 받음)
def get_db_connection(db_name):
    conn = sqlite3.connect(db_name, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 결과를 딕셔너리 형식으로 반환
    return conn

# SQLite에 데이터를 저장하는 함수 (테이블 이름과 데이터를 인자로 받음)
def save_to_db(db_name, table_name, data):
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    # 데이터베이스에 맞는 쿼리 작성
    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    query = f'INSERT INTO {table_name} ({columns}) VALUES ({placeholders})'

    cursor.execute(query, tuple(data.values()))
    conn.commit()
    conn.close()

# SQLite에서 데이터를 불러오는 함수 (테이블 이름과 조건을 인자로 받음)
def load_from_db(db_name, table_name, conditions=None):
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    query = f'SELECT * FROM {table_name}'
    if conditions:
        condition_parts = []
        values = []
        for k, v in conditions.items():
            if k == 'email':  # Case-insensitive and whitespace-trimmed search for email
                condition_parts.append('LOWER(TRIM(email)) = LOWER(TRIM(?))')
            else:
                condition_parts.append(f'{k} = ?')
            values.append(v)
        
        condition_str = ' AND '.join(condition_parts)
        query += ' WHERE ' + condition_str
        cursor.execute(query, tuple(values))
    else:
        cursor.execute(query)
    
    rows = cursor.fetchall()
    conn.close()
    return rows

# SQLite에서 데이터를 삭제하는 함수 (테이블 이름과 조건을 인자로 받음)
def delete_from_db(db_name, table_name, conditions):
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    condition_str = ' AND '.join([f'{k} = ?' for k in conditions.keys()])
    query = f'DELETE FROM {table_name} WHERE {condition_str}'

    cursor.execute(query, tuple(conditions.values()))
    conn.commit()
    conn.close()

# SQLite에서 데이터를 수정하는 함수 (테이블 이름과 조건을 인자로 받음)
def update_db(db_name, table_name, conditions, updates):
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    # 조건에 맞는 데이터를 수정
    condition_str = ' AND '.join([f'{k} = ?' for k in conditions.keys()])
    update_str = ', '.join([f'{k} = ?' for k in updates.keys()])

    query = f'UPDATE {table_name} SET {update_str} WHERE {condition_str}'

    # 쿼리 실행
    cursor.execute(query, tuple(updates.values()) + tuple(conditions.values()))
    conn.commit()
    conn.close()


# 비밀번호 해싱 함수
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# 비밀번호 검증 함수
def check_password(stored_hash, password: str) -> bool: # stored_hash 타입 힌트 제거 또는 Union[str, bytes] 사용
    """
    저장된 해시(문자열 또는 바이트)와 입력된 비밀번호(문자열)를 비교합니다.

    Args:
        stored_hash: 데이터베이스에서 가져온 비밀번호 해시 (str 또는 bytes일 수 있음).
        password (str): 사용자가 입력한 비밀번호 문자열.

    Returns:
        bool: 비밀번호가 일치하면 True, 그렇지 않으면 False.
    """
    try:
        password_bytes = password.encode('utf-8')

        # stored_hash의 타입 확인 후 bytes로 변환
        if isinstance(stored_hash, str):
            stored_hash_bytes = stored_hash.encode('utf-8')
        elif isinstance(stored_hash, bytes):
            stored_hash_bytes = stored_hash # 이미 bytes 타입이면 그대로 사용
        else:
            # 예상치 못한 타입일 경우 에러 처리 또는 로깅
            print(f"Warning: Unexpected type for stored_hash: {type(stored_hash)}")
            return False

        # bcrypt.checkpw는 두 인자 모두 bytes 타입을 요구함
        return bcrypt.checkpw(password_bytes, stored_hash_bytes)

    except ValueError as e:
        # bcrypt 해시가 유효하지 않은 형식일 때 발생 가능 (예: DB 데이터 손상)
        print(f"Error comparing password hash: {e}")
        return False
    except Exception as e:
        # 기타 예상치 못한 오류 로깅
        print(f"Unexpected error in check_password: {e}")
        return False


# 공통 HTML 이메일 전송 함수
def send_html_email(to_email, subject, html_content):
    from_email = "sonyeon465@gmail.com"
    password = "hunhqgzkcgsfwkvo"

    msg = MIMEText(html_content, 'html', _charset='utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = from_email
    msg['To'] = to_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(from_email, password)
        server.send_message(msg)

# 이메일 인증용 링크 전송 함수
def send_verification_email(to_email, link):
    subject = '✨ 이메일 인증 요청 | YourAppName'
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
                <h2 style="color: #333;">안녕하세요!</h2>
                <p style="font-size: 16px; color: #555;">
                    이메일 인증을 위해 아래 버튼을 클릭해주세요.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{link}" style="background-color: #4CAF50; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        이메일 인증하기
                    </a>
                </div>
                <p style="font-size: 14px; color: #999;">
                    버튼이 작동하지 않으면 이 링크를 복사해서 붙여넣어 주세요:<br>
                    <a href="{link}" style="color: #4CAF50;">{link}</a>
                </p>
                <hr style="margin: 40px 0;">
                <p style="font-size: 12px; color: #bbb; text-align: center;">
                    본 메일은 YourAppName 회원가입을 위한 인증 메일입니다.
                </p>
            </div>
        </body>
    </html>
    """
    send_html_email(to_email, subject, html_content)

# 비밀번호 재설정용 링크 전송 함수
def send_password_reset(to_email, link):
    from_email = "sonyeon465@gmail.com"
    password = "hunhqgzkcgsfwkvo"

    subject = '🔐 비밀번호 재설정 링크 | YourAppName'
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
                <h2 style="color: #333;">비밀번호 재설정 요청</h2>
                <p style="font-size: 16px; color: #555;">
                    아래 버튼을 눌러 비밀번호를 재설정하세요.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{link}" style="background-color: #f44336; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        비밀번호 재설정
                    </a>
                </div>
                <p style="font-size: 14px; color: #999;">
                    버튼이 작동하지 않으면 다음 링크를 복사하여 브라우저에 붙여넣으세요:<br>
                    <a href="{link}" style="color: #f44336;">{link}</a>
                </p>
                <hr style="margin: 40px 0;">
                <p style="font-size: 12px; color: #bbb; text-align: center;">
                    이 메일은 YourAppName의 비밀번호 재설정을 위해 전송되었습니다.
                </p>
            </div>
        </body>
    </html>
    """

    msg = MIMEText(html_content, 'html', _charset='utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = from_email
    msg['To'] = to_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(from_email, password)
        server.send_message(msg)

# 사용자 아이디 전송용 이메일 함수
def send_username_email(to_email, username):
    subject = '📩 아이디 찾기 결과 | YourAppName'
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
                <h2 style="color: #333;">요청하신 아이디입니다</h2>
                <p style="font-size: 16px; color: #555;">
                    아래는 귀하의 등록된 아이디입니다:
                </p>
                <div style="text-align: center; margin: 30px 20px;">
                    <p style="font-size: 18px; font-weight: bold; color: #4CAF50;">{username}</p>
                </div>
                <p style="font-size: 14px; color: #999;">
                    본 메일은 YourAppName 아이디 찾기 요청에 의해 전송되었습니다.
                </p>
                <hr style="margin: 40px 0;">
                <p style="font-size: 12px; color: #bbb; text-align: center;">
                    본인이 요청하지 않은 경우, 본 메일을 무시해 주세요.
                </p>
            </div>
        </body>
    </html>
    """
    send_html_email(to_email, subject, html_content)


# 관리자 로그인 인증용 링크 전송 함수
def send_admin_login_verification(to_email, link):
    subject = '🔑 관리자 로그인 인증 | YourAppName'
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
                <h2 style="color: #333;">관리자 로그인 인증</h2>
                <p style="font-size: 16px; color: #555;">
                    관리자 계정으로 로그인하려면 아래 버튼을 클릭해주세요.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{link}" style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        관리자 로그인 인증
                    </a>
                </div>
                <p style="font-size: 14px; color: #999;">
                    버튼이 작동하지 않으면 이 링크를 복사해서 붙여넣어 주세요:<br>
                    <a href="{link}" style="color: #007bff;">{link}</a>
                </p>
                <hr style="margin: 40px 0;">
                <p style="font-size: 12px; color: #bbb; text-align: center;">
                    본 메일은 YourAppName 관리자 로그인을 위한 인증 메일입니다. 본인이 요청하지 않았다면 무시해주세요.
                </p>
            </div>
        </body>
    </html>
    """
    send_html_email(to_email, subject, html_content)


def is_request_too_soon(last_time_key, interval):
    """
    세션에 저장된 시간 기반 요청 제한 검사
    """
    last_time = session.get(last_time_key, 0)
    if time.time() - last_time < interval:
        return True
    session[last_time_key] = time.time()
    return False

def is_token_expired(token_data, max_age):
    """
    토큰 데이터가 만료되었는지 확인
    """
    if not token_data:
        return True
    return time.time() - token_data.get('token_time', 0) > max_age
