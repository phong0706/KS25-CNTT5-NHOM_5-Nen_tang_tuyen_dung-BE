"""Migration idempotent bổ sung cột deleted_at vào bảng jobs."""
from sqlalchemy import text
from sqlalchemy.engine import Engine


def run_job_soft_delete_migration(engine: Engine) -> None:
    """Thêm cột deleted_at và index vào bảng jobs nếu chưa tồn tại."""
    with engine.connect() as conn:
        # Kiểm tra cột deleted_at trong bảng jobs
        res = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'jobs' AND column_name = 'deleted_at'"
            )
        ).scalar()
        if not res:
            conn.execute(
                text("ALTER TABLE jobs ADD COLUMN deleted_at DATETIME NULL DEFAULT NULL")
            )
            try:
                conn.execute(
                    text("CREATE INDEX ix_jobs_deleted_at ON jobs (deleted_at)")
                )
            except Exception:
                pass
            conn.commit()


if __name__ == "__main__":
    from app.db.session import engine
    run_job_soft_delete_migration(engine)
    print("Migration deleted_at thành công!")
