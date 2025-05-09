import sqlite3
import sys
import ast

def modify_table(db_name, table_name, action, *args):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    if action == "add_column":
        column_name = args[0]
        default_value = args[1] if len(args) > 1 else "NULL"
        
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]
        
        if column_name not in columns:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT DEFAULT {default_value if default_value != 'NULL' else 'NULL'}"
            )
            print(f"{column_name} 컬럼을 추가했습니다. 기본값: {default_value}")
        else:
            print(f"{column_name} 컬럼이 이미 존재합니다.")
    
    elif action == "remove_column":
        column_name = args[0]
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]

        if column_name in columns:
            new_columns = [col for col in columns if col != column_name]
            column_list = ', '.join(new_columns)

            cursor.execute(f"CREATE TABLE new_{table_name} AS SELECT {column_list} FROM {table_name}")
            cursor.execute(f"DROP TABLE {table_name}")
            cursor.execute(f"ALTER TABLE new_{table_name} RENAME TO {table_name}")
            print(f"{column_name} 컬럼을 삭제했습니다.")
        else:
            print(f"{column_name} 컬럼이 존재하지 않습니다.")
    
    elif action == "remove":
        request_id = args[0]
        cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (request_id,))
        print(f"id {request_id}의 데이터를 삭제했습니다.")
    
    elif action == "insert":
        columns = ', '.join(args[0::2])
        placeholders = ', '.join(['?'] * (len(args) // 2))
        values = tuple(args[1::2])
        cursor.execute(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values)
        print("데이터를 추가했습니다.")
    
    elif action == "update":
        request_id = args[0]
        column_name = args[1]
        new_value = args[2]

        if new_value in ("0", "1"):
            new_value = bool(int(new_value))
        if new_value in ("True", "False"):
            new_value = int(ast.literal_eval(new_value))
        if new_value.lower() == "null":
            new_value = 0

        cursor.execute(f"UPDATE {table_name} SET {column_name} = ? WHERE id = ?", (new_value, request_id))
        print(f"id {request_id}의 {column_name} 값을 {new_value}(으)로 변경했습니다.")

    elif action == "reset":
        cursor.execute(f"DELETE FROM {table_name}")
        print(f"{table_name} 테이블의 모든 데이터를 초기화했습니다.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("사용법: python modify_db.py <database> <table> <action> [args]")
    else:
        modify_table(sys.argv[1], sys.argv[2], sys.argv[3], *sys.argv[4:])
