"""Migration: Điền slug cho mọi công ty và đặt UNIQUE NOT NULL trên cột slug.
Chạy lặp lại an toàn (idempotent).
"""
import os
import sys
from pathlib import Path

# Đảm bảo import được app dù chạy từ đâu
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, text
from app.db.session import SessionLocal, engine
from app.models.company import Company
from app.services.public_company_rules import generate_unique_company_slug


def run_migration():
    updated_count = 0
    total_companies = 0
    db = SessionLocal()
    try:
        companies = db.scalars(select(Company).order_by(Company.id.asc())).all()
        total_companies = len(companies)
        for c in companies:
            if not c.slug or not str(c.slug).strip() or str(c.slug).isdigit() or not any(ch.isalpha() for ch in str(c.slug)):
                old_slug = c.slug
                c.slug = generate_unique_company_slug(db, c.name, current_company_id=c.id)
                db.commit()
                print(f"[Slug Migration] Công ty ID {c.id} ('{c.name}'): '{old_slug}' -> '{c.slug}'", flush=True)
                updated_count += 1
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Slug Migration] Lỗi: {e}", flush=True)
        raise
    finally:
        db.close()

    print(f"[Slug Migration] Đã kiểm tra {total_companies} công ty, cập nhật slug cho {updated_count} công ty.", flush=True)

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE companies MODIFY COLUMN slug VARCHAR(120) NOT NULL;"))
        conn.commit()
        print("[Slug Migration] Đã cập nhật thành công: slug VARCHAR(120) NOT NULL.", flush=True)


if __name__ == "__main__":
    run_migration()
