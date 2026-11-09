"""Chạy file sql/init.sql bằng Python (khi chưa cài mysql CLI/Workbench).

Dùng pymysql trực tiếp với multi-statement / MULTI_STATEMENTS để tránh lỗi tách câu.
Mỗi kết quả (kể cả SELECT) đều được fetch và bỏ qua, tránh 'Commands out of sync'.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
import pymysql
from pymysql.constants import CLIENT


def main():
    sql_path = os.path.join(os.path.dirname(__file__), "sql", "init.sql")
    with open(sql_path, encoding="utf-8") as f:
        sql = f.read()

    conn = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        charset="utf8mb4",
        # CLIENT.MULTI_STATEMENTS: cho phép chạy nhiều statement cách nhau bằng ';'
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            # Fetch hết mọi resultset để tránh "Commands out of sync"
            result_count = 0
            while True:
                try:
                    rows = cur.fetchall()
                    result_count += 1
                except Exception:
                    pass
                if not cur.nextset():
                    break
        conn.commit()
        print(f"init.sql chạy xong! ({result_count} resultset)")
    except Exception as e:
        conn.rollback()
        print(f"Lỗi: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
