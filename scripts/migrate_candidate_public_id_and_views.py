"""Migration idempotent:
1. Thêm cột public_id (VARCHAR(32), UNIQUE, INDEX) cho candidate_profiles và tự sinh mã ngẫu nhiên url-safe >= 16 ký tự cho hồ sơ hiện có.
2. Tạo bảng profile_views kèm index (candidate_user_id, viewed_at).
Hoàn toàn idempotent (chạy lặp lại được nhiều lần không lỗi).
"""
import os
import secrets
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import inspect, text
from app.db.session import engine


def generate_public_id() -> str:
    # secrets.token_urlsafe(16) sinh chuỗi 22 ký tự an toàn url-safe
    return secrets.token_urlsafe(16)


def run_migration():
    print("[Profile Migration] Bắt đầu migration idempotent candidate_profiles.public_id và profile_views...")
    with engine.begin() as conn:
        # 1. Kiểm tra cột public_id trong candidate_profiles
        inspector = inspect(conn)
        columns = [c["name"] for c in inspector.get_columns("candidate_profiles")]
        
        if "public_id" not in columns:
            print("  - Thêm cột public_id vào candidate_profiles...")
            conn.execute(text("ALTER TABLE candidate_profiles ADD COLUMN public_id VARCHAR(32) NULL;"))
        else:
            print("  - Cột public_id đã tồn tại trong candidate_profiles.")

        # Sinh public_id cho các hồ sơ chưa có
        rows = conn.execute(text("SELECT id FROM candidate_profiles WHERE public_id IS NULL OR public_id = ''")).fetchall()
        if rows:
            print(f"  - Đang sinh public_id ngẫu nhiên cho {len(rows)} hồ sơ hiện có...")
            for r in rows:
                p_id = generate_public_id()
                conn.execute(
                    text("UPDATE candidate_profiles SET public_id = :pub WHERE id = :id"),
                    {"pub": p_id, "id": r[0]},
                )

        # Đảm bảo có unique index uk_candidate_profiles_public_id
        indexes = [idx["name"] for idx in inspector.get_indexes("candidate_profiles")]
        if "uk_candidate_profiles_public_id" not in indexes and "public_id" not in indexes:
            try:
                print("  - Thêm UNIQUE INDEX cho public_id...")
                conn.execute(text("CREATE UNIQUE INDEX uk_candidate_profiles_public_id ON candidate_profiles(public_id);"))
            except Exception as e:
                print(f"  - Ghi chú khi tạo index: {e}")

        # 2. Tạo bảng profile_views
        tables = inspector.get_table_names()
        if "profile_views" not in tables:
            print("  - Tạo bảng profile_views...")
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS profile_views (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employer_user_id INT NOT NULL,
                candidate_user_id INT NOT NULL,
                application_id INT NULL,
                viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                context VARCHAR(50) NULL,
                INDEX idx_pv_candidate_viewed (candidate_user_id, viewed_at),
                INDEX idx_pv_employer (employer_user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """))
        else:
            print("  - Bảng profile_views đã tồn tại.")

    print("[Profile Migration] Hoàn thành migration thành công!")


if __name__ == "__main__":
    run_migration()
