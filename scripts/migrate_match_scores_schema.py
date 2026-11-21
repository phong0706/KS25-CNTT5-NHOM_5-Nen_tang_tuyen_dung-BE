"""Migration idempotent: Tạo bảng match_scores, candidate_matching_settings, và skill_job_index.
Không DROP, không TRUNCATE.
"""
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.session import engine


def run_migration():
    print("[Matching Migration] Bắt đầu migration idempotent...")
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS match_scores (
            id INT AUTO_INCREMENT PRIMARY KEY,
            candidate_id INT NOT NULL,
            job_id INT NOT NULL,
            total_score FLOAT NOT NULL,
            skill_score FLOAT NOT NULL,
            level_score FLOAT NOT NULL,
            place_score FLOAT NOT NULL,
            salary_score FLOAT NOT NULL,
            matched_skills_json TEXT,
            missing_required_json TEXT,
            labels_json TEXT,
            formula_version VARCHAR(20) NOT NULL,
            computed_at DATETIME NOT NULL,
            is_dirty BOOLEAN NOT NULL DEFAULT FALSE,
            UNIQUE KEY uk_match_cand_job (candidate_id, job_id),
            INDEX idx_match_cand (candidate_id),
            INDEX idx_match_job (job_id),
            INDEX idx_match_score (total_score),
            INDEX idx_match_dirty (is_dirty)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS candidate_matching_settings (
            user_id INT PRIMARY KEY,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            open_to_relocate BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_cand_match_enabled (is_enabled)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS skill_job_index (
            id INT AUTO_INCREMENT PRIMARY KEY,
            skill_canonical VARCHAR(100) NOT NULL,
            job_id INT NOT NULL,
            is_required BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE KEY uk_skill_job (skill_canonical, job_id),
            INDEX idx_sji_skill (skill_canonical),
            INDEX idx_sji_job (job_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))
        conn.commit()
        print("[Matching Migration] Hoàn thành migration các bảng khớp việc làm thành công!")


if __name__ == "__main__":
    run_migration()
