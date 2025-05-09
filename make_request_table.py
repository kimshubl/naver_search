import sqlite3

def create_request_db():
    # SQLite 데이터베이스에 연결 (파일이 없으면 새로 생성됨)
    conn = sqlite3.connect('requests.db')
    cursor = conn.cursor()

    # requests 테이블 생성 (VARCHAR 및 INTEGER CHECK 제약 조건 적용)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255),                      
            merchandise INTEGER CHECK (merchandise IN (0, 1)), 
            service INTEGER CHECK (service IN (1, 2)),         
            sub_time VARCHAR(30),                  
            traffic_amount VARCHAR(50),             
            state VARCHAR(20) DEFAULT '대기중',      
            user_id VARCHAR(15),                   
            link TEXT,
            keyword TEXT                              
        )
    ''')
    # 컬럼 설명 및 VARCHAR/TEXT 길이 선정 이유:
    # - name VARCHAR(255): 요청자 이름, 충분한 길이를 위해 255자로 설정
    # - merchandise INTEGER CHECK (merchandise IN (0, 1)): 상품 목록 선택 (0 또는 1만 허용)
    # - service INTEGER CHECK (service IN (1, 2)): 서비스 목록 선택 (1 또는 2만 허용)
    # - sub_time VARCHAR(30): 요청 제출 시간 (YYYY-MM-DD HH:MM:SS 형식, 19자), 여유 공간 포함 30자
    # - traffic_amount VARCHAR(50): 트래픽 양 (문자열로 저장, 예: '10GB', '무제한'), 50자로 여유있게 설정
    # - state VARCHAR(20): 요청 상태 문자열 (예: '대기중', '완료됨', '취소됨'), 20자로 여유있게 설정
    # - user_id VARCHAR(15): users 테이블의 username과 동일하게 15자 제한
    # - link TEXT: 은 길이가 매우 다양할 수 있으므로 TEXT 타입 사용 (길이 제한 없음)
    # - 참고: SQLite의 VARCHAR(n)은 다른 DB와 달리 엄격한 길이 제한을 강제하지 않을 수 있음.

    # 커밋하여 변경 사항 저장
    conn.commit()
    # 연결 종료
    conn.close()
    print("requests.db와 requests 테이블이 성공적으로 생성되었습니다.")

if __name__ == "__main__":
    create_request_db()
