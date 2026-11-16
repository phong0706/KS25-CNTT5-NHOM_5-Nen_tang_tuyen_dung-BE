import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== NOTIFICATIONS SCHEMA ===")
    rows = db.execute(text("DESCRIBE notifications")).fetchall()
    for r in rows:
        print(r)
    print("\n=== INDEXES ===")
    indexes = db.execute(text("SHOW INDEX FROM notifications")).fetchall()
    for idx in indexes:
        print(idx[2], idx[4])
finally:
    db.close()
