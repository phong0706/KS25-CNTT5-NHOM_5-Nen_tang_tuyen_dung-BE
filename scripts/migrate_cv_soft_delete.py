"""Migration idempotent: Thêm cột deleted_at và index cho bảng cvs (MIG-CV-01).
Chạy: python scripts/migrate_cv_soft_delete.py
Tuân thủ techrecruit-rules: <= 100 dòng, lặp lại được, không DROP bảng.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.db.session import engine

def migrate_database():
    with engine.connect() as conn:
        db_name = conn.execute(text("SELECT DATABASE()")).scalar()
        print(f"[*] Đang chạy migration trên database: {db_name}")

        # 1. Kiểm tra bảng cvs có tồn tại không
        has_table = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cvs'"
        )).scalar()
        if not has_table:
            print("[-] Bảng cvs chưa tồn tại. Bỏ qua.")
            return

        # 2. Kiểm tra cột deleted_at
        col_check = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cvs' AND COLUMN_NAME = 'deleted_at'"
        )).scalar()

        if not col_check:
            print("[+] Thêm cột deleted_at vào bảng cvs...")
            conn.execute(text("ALTER TABLE cvs ADD COLUMN deleted_at DATETIME NULL DEFAULT NULL"))
            conn.commit()
            print("[✓] Đã thêm cột deleted_at.")
        else:
            print("[i] Cột deleted_at đã tồn tại.")

        # 3. Kiểm tra index idx_cvs_candidate_deleted
        idx_check = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cvs' AND INDEX_NAME = 'idx_cvs_candidate_deleted'"
        )).scalar()

        if not idx_check:
            print("[+] Thêm index idx_cvs_candidate_deleted vào bảng cvs...")
            conn.execute(text("CREATE INDEX idx_cvs_candidate_deleted ON cvs (candidate_id, deleted_at)"))
            conn.commit()
            print("[✓] Đã tạo index idx_cvs_candidate_deleted.")
        else:
            print("[i] Index idx_cvs_candidate_deleted đã tồn tại.")

        print(f"[✓] Hoàn thành migration cho {db_name}.")

if __name__ == "__main__":
    migrate_database()
