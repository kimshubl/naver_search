import sqlite3
import sys

# 데이터베이스 연결을 위한 함수
def get_db_connection(db_name):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row  # 결과를 딕셔너리 형식으로 반환
    return conn

# 데이터베이스의 모든 테이블과 그 데이터를 출력하는 함수
def print_db(db_name):
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    # 데이터베이스의 모든 테이블 이름 가져오기
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        print(f"'{db_name}' 데이터베이스에 테이블이 없습니다.")
        conn.close()
        return

    # 각 테이블의 데이터 출력
    for table in tables:
        table_name = table['name']
        print(f"테이블: {table_name}")
        
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if rows:
            for row in rows:
                print(dict(row))  # 딕셔너리 형태로 각 레코드를 출력
        else:
            print("  테이블에 데이터가 없습니다.")
        print("-" * 40)

    conn.close()

# 메인 실행
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("사용법: python print_db.py <데이터베이스 이름>")
    else:
        db_name = sys.argv[1]
        print_db(db_name)
