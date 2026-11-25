"""Khởi tạo toàn bộ cơ sở dữ liệu TechRecruit bằng Python (47 bảng + seed demo).

Thực thi tuần tự:
1. backend/sql/01_schema.sql (47 bảng)
2. backend/sql/02_seed_demo.sql (Dữ liệu mẫu)
"""
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
import pymysql
from pymysql.constants import CLIENT


def execute_sql_file(conn, file_path: Path):
    print(f"Đang thực thi: {file_path.name}...")
    with open(file_path, encoding="utf-8") as f:
        sql = f.read()

    with conn.cursor() as cur:
        cur.execute(sql)
        result_count = 0
        while True:
            try:
                cur.fetchall()
                result_count += 1
            except Exception:
                pass
            if not cur.nextset():
                break
    conn.commit()
    print(f"-> {file_path.name} hoàn tất ({result_count} resultset).")


def main():
    files_to_run = [
        BASE_DIR / "sql" / "01_schema.sql",
        BASE_DIR / "sql" / "02_seed_demo.sql",
    ]

    conn = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset="utf8mb4",
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    try:
        for f in files_to_run:
            if f.exists():
                execute_sql_file(conn, f)
            else:
                print(f"Bỏ qua: Không tìm thấy {f.name}")
        print("\nKhởi tạo Database thành công với toàn bộ 47 bảng và dữ liệu mẫu!")
    except Exception as e:
        conn.rollback()
        print(f"Lỗi khởi tạo DB: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

