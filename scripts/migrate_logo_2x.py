"""Migration chạy lặp lại được: thêm cột logo_url_2x vào companies và file_key_2x vào company_logos."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from app.db.session import engine


def migrate():
    insp = inspect(engine)
    with engine.connect() as conn:
        # 1. companies.logo_url_2x
        comp_cols = [c["name"] for c in insp.get_columns("companies")]
        if "logo_url_2x" not in comp_cols:
            print("Adding column logo_url_2x to companies...")
            conn.execute(text("ALTER TABLE companies ADD COLUMN logo_url_2x VARCHAR(500) NULL AFTER logo_url"))
            conn.commit()
            print("Added logo_url_2x to companies.")
        else:
            print("Column logo_url_2x already exists in companies.")

        # 2. company_logos.file_key_2x
        if "company_logos" in insp.get_table_names():
            logo_cols = [c["name"] for c in insp.get_columns("company_logos")]
            if "file_key_2x" not in logo_cols:
                print("Adding column file_key_2x to company_logos...")
                conn.execute(text("ALTER TABLE company_logos ADD COLUMN file_key_2x VARCHAR(255) NULL AFTER file_key"))
                conn.commit()
                print("Added file_key_2x to company_logos.")
            else:
                print("Column file_key_2x already exists in company_logos.")


if __name__ == "__main__":
    migrate()
