import os
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from app.db.session import SessionLocal
from sqlalchemy import text

def run_migration():
    db = SessionLocal()
    try:
        # Check current columns
        cols = [r[0] for r in db.execute(text("DESCRIBE notifications")).fetchall()]
        print("Existing columns:", cols)

        if "entity_type" not in cols:
            print("Adding entity_type column...")
            db.execute(text("ALTER TABLE notifications ADD COLUMN entity_type VARCHAR(50) NULL AFTER ref_type"))
            db.execute(text("UPDATE notifications SET entity_type = ref_type WHERE entity_type IS NULL"))

        if "entity_id" not in cols:
            print("Adding entity_id column...")
            db.execute(text("ALTER TABLE notifications ADD COLUMN entity_id INT NULL AFTER entity_type"))
            db.execute(text("UPDATE notifications SET entity_id = ref_id WHERE entity_id IS NULL"))

        if "payload_json" not in cols:
            print("Adding payload_json column...")
            db.execute(text("ALTER TABLE notifications ADD COLUMN payload_json TEXT NULL AFTER entity_id"))

        # Check indexes
        idx_rows = db.execute(text("SHOW INDEX FROM notifications")).fetchall()
        idx_names = {r[2] for r in idx_rows}
        print("Existing indexes:", idx_names)

        if "idx_notif_user_read_created" not in idx_names and "idx_notifications_user_read_created" not in idx_names:
            print("Adding compound index (user_id, read_at, created_at)...")
            db.execute(text("CREATE INDEX idx_notif_user_read_created ON notifications (user_id, read_at, created_at)"))

        db.commit()
        print("Migration completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
