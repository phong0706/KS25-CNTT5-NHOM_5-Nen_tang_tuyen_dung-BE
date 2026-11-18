"""Migration idempotent tạo các bảng cấu hình trang chủ & audit log.
Tuân thủ Bước 1: Không DROP, không TRUNCATE, chạy lại an toàn nhiều lần.
Giới hạn file: < 195 dòng.
"""
import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import engine


def migrate_home_config():
    with engine.begin() as conn:
        # 1. Bảng home_salary_settings
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS home_salary_settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                min_sample INT NOT NULL DEFAULT 5,
                max_items INT NOT NULL DEFAULT 6,
                version INT NOT NULL DEFAULT 1,
                updated_by INT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_home_sal_updated_by FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))

        # Seed dòng cấu hình đầu tiên nếu chưa có
        res = conn.execute(text("SELECT COUNT(*) FROM home_salary_settings")).scalar()
        if res == 0:
            conn.execute(text("""
                INSERT INTO home_salary_settings (id, min_sample, max_items, version, updated_at)
                VALUES (1, 5, 6, 1, NOW())
            """))

        # 2. Bảng home_salary_skill_overrides
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS home_salary_skill_overrides (
                id INT AUTO_INCREMENT PRIMARY KEY,
                skill_id INT NOT NULL,
                skill_name VARCHAR(100) NOT NULL,
                mode VARCHAR(20) NOT NULL DEFAULT 'auto',
                position INT NULL,
                version INT NOT NULL DEFAULT 1,
                updated_by INT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY idx_home_skill_override_skill (skill_id),
                CONSTRAINT fk_home_skill_ov_user FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))

        # 3. Bảng home_featured_companies
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS home_featured_companies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                company_id INT NOT NULL,
                position INT NULL,
                version INT NOT NULL DEFAULT 1,
                updated_by INT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY idx_home_featured_comp_company (company_id),
                CONSTRAINT fk_home_feat_comp_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                CONSTRAINT fk_home_feat_comp_user FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))

        # 4. Bảng home_config_audit
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS home_config_audit (
                id INT AUTO_INCREMENT PRIMARY KEY,
                section VARCHAR(50) NOT NULL,
                action VARCHAR(50) NOT NULL,
                actor_id INT NOT NULL,
                before_json LONGTEXT NULL,
                after_json LONGTEXT NULL,
                reason TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                KEY idx_home_audit_section_created (section, created_at),
                CONSTRAINT fk_home_audit_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))

    print("Migration home_config tables completed successfully.")


if __name__ == "__main__":
    migrate_home_config()
