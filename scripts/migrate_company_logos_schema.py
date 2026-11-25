"""Script di chuyển và tạo schema cho company_logos (Idempotent).
Tuân thủ techrecruit-rules: <= 200 dòng, không DROP, không TRUNCATE.
"""
from sqlalchemy import text
from app.db.session import engine


def migrate_company_logos_schema():
    with engine.connect() as conn:
        print("[MIGRATION] Bắt đầu migration schema company_logos...")

        # 1. Thêm cột logo_version vào companies nếu chưa có
        try:
            conn.execute(text("ALTER TABLE companies ADD COLUMN logo_version INT NOT NULL DEFAULT 1"))
            conn.commit()
            print("  + Đã thêm cột logo_version vào bảng companies")
        except Exception as e:
            if "Duplicate column name" in str(e) or "1060" in str(e):
                print("  = Cột logo_version đã tồn tại trong companies")
            else:
                print(f"  ! Lỗi kiểm tra logo_version: {e}")

        # 2. Tạo bảng company_logos nếu chưa có
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS company_logos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            company_id INT NOT NULL,
            file_key VARCHAR(255) NOT NULL,
            version INT NOT NULL DEFAULT 1,
            status VARCHAR(24) NOT NULL DEFAULT 'cho_duyet',
            is_current BOOLEAN NOT NULL DEFAULT FALSE,
            uploaded_by INT NULL,
            reviewed_by INT NULL,
            reviewed_at DATETIME NULL,
            reject_reason TEXT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_comp_logos_company (company_id),
            INDEX idx_comp_logos_status (status),
            INDEX idx_comp_logos_current (is_current),
            CONSTRAINT fk_comp_logos_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        conn.execute(text(create_table_sql))
        conn.commit()
        print("  + Bảng company_logos đã sẵn sàng")

        # 3. Tạo unique index có điều kiện hoặc ràng buộc cho is_current
        # Trong MySQL 8.0, tạo partial unique index bằng expression functional index hoặc trigger/transaction
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX uk_company_current_logo 
                ON company_logos (company_id, (IF(is_current, 1, NULL)))
            """))
            conn.commit()
            print("  + Đã tạo unique index uk_company_current_logo cho 1 logo is_current duy nhất")
        except Exception as e:
            if "Duplicate key name" in str(e) or "already exists" in str(e):
                print("  = Index uk_company_current_logo đã tồn tại")
            else:
                print(f"  ! Ghi chú index uk_company_current_logo: {e}")

        # 4. Di chuyển dữ liệu logo đang có từ companies sang company_logos (Seed idempotent)
        seed_sql = """
        INSERT INTO company_logos (company_id, file_key, version, status, is_current, uploaded_by, reviewed_by, reviewed_at, created_at)
        SELECT 
            c.id,
            SUBSTRING_INDEX(c.logo_url, '/', -1),
            1,
            'dang_dung',
            TRUE,
            c.logo_uploaded_by,
            23,
            NOW(),
            NOW()
        FROM companies c
        WHERE c.logo_url IS NOT NULL 
          AND TRIM(c.logo_url) != ''
          AND c.logo_status = 'approved'
          AND NOT EXISTS (
              SELECT 1 FROM company_logos cl WHERE cl.company_id = c.id AND cl.is_current = TRUE
          );
        """
        result = conn.execute(text(seed_sql))
        conn.commit()
        print(f"  + Đã seed {result.rowcount} logo đang dùng sang company_logos")

        print("[MIGRATION] Hoàn thành migration schema company_logos.")


if __name__ == "__main__":
    migrate_company_logos_schema()
