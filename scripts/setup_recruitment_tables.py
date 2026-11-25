"""Setup script for Employer Recruitment tables:
- Add viewed_at to applications (if not exists)
- Create application_notes
- Create interviews
- Create meta_rejection_reasons & seed data
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db.session import engine

def setup_tables():
    with engine.begin() as conn:
        # 1. Add viewed_at to applications if not exists
        res = conn.execute(text("SHOW COLUMNS FROM applications LIKE 'viewed_at'")).fetchone()
        if not res:
            print("Adding viewed_at column to applications...")
            conn.execute(text("ALTER TABLE applications ADD COLUMN viewed_at DATETIME NULL;"))
            print("Added viewed_at.")
        else:
            print("viewed_at already exists in applications.")

        # 2. application_notes
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS application_notes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                application_id INT NOT NULL,
                author_id INT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_app_notes_app_id (application_id),
                CONSTRAINT fk_app_notes_app FOREIGN KEY (application_id) REFERENCES applications (id) ON DELETE CASCADE,
                CONSTRAINT fk_app_notes_author FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))
        print("Checked/created application_notes table.")

        # 3. interviews
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS interviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                application_id INT NOT NULL,
                scheduled_at DATETIME NOT NULL,
                duration_min INT NOT NULL DEFAULT 45,
                mode VARCHAR(80) NOT NULL DEFAULT 'Trực tuyến qua Google Meet',
                location_or_link VARCHAR(500) NULL,
                interviewer VARCHAR(255) NULL,
                note VARCHAR(500) NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'scheduled',
                cancel_reason VARCHAR(500) NULL,
                created_by INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_interviews_app_id (application_id),
                INDEX idx_interviews_scheduled_at (scheduled_at),
                INDEX idx_interviews_created_by (created_by),
                CONSTRAINT fk_interviews_app FOREIGN KEY (application_id) REFERENCES applications (id) ON DELETE CASCADE,
                CONSTRAINT fk_interviews_creator FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))
        print("Checked/created interviews table.")

        # 4. meta_rejection_reasons
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS meta_rejection_reasons (
                id INT AUTO_INCREMENT PRIMARY KEY,
                slug VARCHAR(60) NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                sort_order INT NOT NULL DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))
        print("Checked/created meta_rejection_reasons table.")

        # Seed meta_rejection_reasons
        seeds = [
            ("skills_mismatch", "Kỹ năng chưa phù hợp với yêu cầu vị trí", 1),
            ("experience_mismatch", "Kinh nghiệm làm việc chưa đạt kỳ vọng", 2),
            ("salary_expectation", "Mức lương kỳ vọng chưa phù hợp ngân sách", 3),
            ("culture_fit", "Chưa phù hợp với văn hóa tổ chức/đội ngũ", 4),
            ("found_another_candidate", "Đã tuyển đủ nhân sự cho vị trí này", 5),
            ("candidate_unresponsive", "Không thể liên hệ được với ứng viên", 6),
            ("other", "Lý do khác", 7),
        ]
        for slug, name, sort_order in seeds:
            conn.execute(text("""
                INSERT INTO meta_rejection_reasons (slug, name, sort_order)
                VALUES (:slug, :name, :sort_order)
                ON DUPLICATE KEY UPDATE name = :name, sort_order = :sort_order
            """), {"slug": slug, "name": name, "sort_order": sort_order})
        print("Seeded meta_rejection_reasons.")

if __name__ == "__main__":
    setup_tables()
    print("Database setup complete.")
