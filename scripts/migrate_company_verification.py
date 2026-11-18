"""Migration idempotent khởi tạo bảng company_verifications và các cột liên quan."""
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from app.db.session import SessionLocal


def run_migration() -> None:
    db = SessionLocal()
    try:
        sql_file = BASE_DIR / "sql" / "migrate_company_verification.sql"
        ddl = sql_file.read_text(encoding="utf-8")
        for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
            db.execute(text(stmt))

        verif_cols = {r[0] for r in db.execute(text("DESCRIBE company_verifications")).fetchall()}
        if "pending_company_lock" not in verif_cols:
            db.execute(text(
                "ALTER TABLE company_verifications "
                "ADD COLUMN pending_company_lock INT GENERATED ALWAYS AS (IF(status = 'cho_duyet', company_id, NULL)) VIRTUAL, "
                "ADD UNIQUE KEY uq_company_single_pending (pending_company_lock)"
            ))

        comp_cols = {r[0] for r in db.execute(text("DESCRIBE companies")).fetchall()}
        if "verification_status" not in comp_cols:
            db.execute(text(
                "ALTER TABLE companies ADD COLUMN verification_status VARCHAR(24) NOT NULL DEFAULT 'chua_xac_minh', "
                "ADD INDEX idx_companies_verif_status (verification_status)"
            ))
        if "logo_status" not in comp_cols:
            db.execute(text("ALTER TABLE companies ADD COLUMN logo_status VARCHAR(20) NOT NULL DEFAULT 'missing'"))
        if "logo_uploaded_by" not in comp_cols:
            db.execute(text("ALTER TABLE companies ADD COLUMN logo_uploaded_by INT NULL"))
        if "logo_uploaded_at" not in comp_cols:
            db.execute(text("ALTER TABLE companies ADD COLUMN logo_uploaded_at DATETIME NULL"))

        db.execute(text("ALTER TABLE jobs MODIFY COLUMN status VARCHAR(32) NOT NULL DEFAULT 'draft'"))
        db.execute(text("ALTER TABLE jobs MODIFY COLUMN location_id INT NULL"))
        db.execute(text("ALTER TABLE jobs MODIFY COLUMN company_id INT NULL"))
        db.execute(text("ALTER TABLE jobs MODIFY COLUMN deadline DATE NULL"))

        user_cols = {r[0] for r in db.execute(text("DESCRIBE users")).fetchall()}
        if "locked_reason" not in user_cols:
            db.execute(text("ALTER TABLE users ADD COLUMN locked_reason VARCHAR(500) NULL"))
        if "token_version" not in user_cols:
            db.execute(text("ALTER TABLE users ADD COLUMN token_version INT NOT NULL DEFAULT 1"))
        if "is_verified" not in user_cols:
            db.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT FALSE"))
        db.execute(text(
            "ALTER TABLE users MODIFY COLUMN role "
            "ENUM('candidate','employer','recruiter','admin','operator') "
            "NOT NULL DEFAULT 'candidate'"
        ))

        audit_cols = {r[0] for r in db.execute(text("DESCRIBE audit_logs")).fetchall()}
        if "reason" not in audit_cols:
            db.execute(text("ALTER TABLE audit_logs ADD COLUMN reason TEXT NULL"))

        db.commit()
        print("[MIGRATION] Hoan tat migrate_company_verification thanh cong.")
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
