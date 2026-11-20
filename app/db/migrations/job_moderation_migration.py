"""Migration bổ sung các cột version, review_note, reviewed_at và bảng job_status_history.

Đảm bảo tính idempotent: chạy nhiều lần không gây lỗi và không mất dữ liệu cũ.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine, Connection


def run_job_moderation_migration(bind: Engine | Connection) -> None:
    """Chạy migration bổ sung trường và bảng cho luồng duyệt tin tuyển dụng."""
    insp = inspect(bind)
    job_columns = {col["name"] for col in insp.get_columns("jobs")}

    def _execute(sql: str) -> None:
        if isinstance(bind, Engine):
            with bind.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
        else:
            bind.execute(text(sql))
            if hasattr(bind, "commit"):
                bind.commit()

    # 1. Thêm cột version nếu chưa có
    if "version" not in job_columns:
        _execute("ALTER TABLE jobs ADD COLUMN version INT NOT NULL DEFAULT 1;")
        _execute("UPDATE jobs SET version = 1 WHERE version IS NULL OR version = 0;")

    # 2. Thêm cột review_note nếu chưa có
    if "review_note" not in job_columns:
        _execute("ALTER TABLE jobs ADD COLUMN review_note TEXT NULL;")

    # 3. Thêm cột reviewed_at nếu chưa có
    if "reviewed_at" not in job_columns:
        _execute("ALTER TABLE jobs ADD COLUMN reviewed_at DATETIME NULL;")

    # 4. Tạo bảng job_status_history nếu chưa có
    table_names = insp.get_table_names()
    if "job_status_history" not in table_names:
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS job_status_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            job_id INT NOT NULL,
            from_status VARCHAR(32) NOT NULL,
            to_status VARCHAR(32) NOT NULL,
            changed_by INT NOT NULL,
            reason TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_job_status_history_job_created (job_id, created_at),
            CONSTRAINT fk_jsh_job FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            CONSTRAINT fk_jsh_user FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        _execute(create_table_sql)
