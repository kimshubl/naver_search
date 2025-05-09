import sqlite3

def create_rank_chart_db():
    conn = sqlite3.connect('rank_chart.db')
    cursor = conn.cursor()

    # 기존 테이블 삭제 후 재생성 (개발 중) 또는 ALTER TABLE 사용
    # cursor.execute("DROP TABLE IF EXISTS requests")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            store_name TEXT,
            keyword TEXT,
            date DATETIME,
            rank INTEGER,
            visitor_reviews INTEGER,
            blog_reviews INTEGER,
            saved_count INTEGER  -- << 저장하기 수 컬럼 추가
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT NOT NULL,
            keyword TEXT NOT NULL,
            UNIQUE(store_name, keyword)
        )
    ''')

    conn.commit()
    conn.close()
    print("rank_chart.db에 requests (saved_count 추가됨) 및 tracked_items 테이블이 성공적으로 생성/확인되었습니다.")

if __name__ == "__main__":
    create_rank_chart_db()