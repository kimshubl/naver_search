import sqlite3

def create_user_db():
    conn = sqlite3.connect('users.db')  # user.db 생성 또는 연결
    cursor = conn.cursor()

    # users 테이블 생성 (VARCHAR 타입 적용)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(15) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE,
            password_hash TEXT NOT NULL,
            subscription_status TEXT DEFAULT 'inactive', -- 구독 상태 ('active', 'inactive', 'cancelled')
            subscription_expiry DATETIME,               -- 구독 만료일
            toss_billing_key TEXT,                      -- Toss Payments 자동결제 키
            points INTEGER DEFAULT 0                    -- 사용자 보유 포인트
        )
    ''')
    # 컬럼 설명 및 VARCHAR 길이 선정 이유:
    # - username VARCHAR(15): 사용자 이름, 15자 제한 (app.py에서 검증)
    # - email VARCHAR(255): 이메일 주소, 표준 이메일 최대 길이에 맞춰 255자로 설정
    # - password_hash TEXT: bcrypt 해시는 길이가 가변적이므로 TEXT 사용

    conn.commit()
    conn.close()
    print("user.db와 users 테이블이 성공적으로 생성되었습니다.")

if __name__ == "__main__":
    create_user_db()
