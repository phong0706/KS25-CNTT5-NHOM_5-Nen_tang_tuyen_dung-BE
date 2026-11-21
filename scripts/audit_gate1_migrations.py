"""Script kiểm toán Giai đoạn 1: 1.7 Kiểm tra tính Idempotent, Rollback, DROP/TRUNCATE của các migration."""
import os
import re
import json
import subprocess
from sqlalchemy import create_engine, text
from app.core.config import settings

def audit_migrations():
    migration_files = []
    
    # Collect SQL migrations
    for root, _, files in os.walk("sql"):
        for f in files:
            if "migrat" in f.lower() or "patch" in f.lower():
                migration_files.append(os.path.join(root, f).replace("\\", "/"))
                
    # Collect Python migrations
    for root, _, files in os.walk("app/db/migrations"):
        for f in files:
            if f.endswith(".py"):
                migration_files.append(os.path.join(root, f).replace("\\", "/"))
                
    for f in os.listdir("scripts"):
        if f.startswith("migrate_") and f.endswith(".py"):
            migration_files.append(os.path.join("scripts", f).replace("\\", "/"))

    report = {
        "scanned_files": len(migration_files),
        "files_with_drop_or_truncate": [],
        "files_without_rollback": [],
        "idempotence_results": []
    }

    drop_pattern = re.compile(r'\b(?:DROP\s+TABLE|DROP\s+COLUMN|DROP\s+DATABASE|TRUNCATE\s+TABLE|TRUNCATE)\b', re.IGNORECASE)

    for mf in sorted(migration_files):
        with open(mf, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Check DROP/TRUNCATE
        drops = drop_pattern.findall(content)
        if drops:
            report["files_with_drop_or_truncate"].append({
                "file": mf,
                "matches": list(set(drops))
            })

        # Check rollback
        has_rollback = bool(re.search(r'\b(?:downgrade|down|rollback)\b', content, re.IGNORECASE))
        if not has_rollback:
            report["files_without_rollback"].append(mf)

    # Test idempotence on test database
    from app.db.session import engine
    base_engine = create_engine(engine.url.set(database=None))
    
    test_db = "app_db_mig_audit"
    with base_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db};"))
        conn.execute(text(f"CREATE DATABASE {test_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))
        conn.commit()

    test_url = engine.url.set(database=test_db)
    mig_engine = create_engine(test_url)

    # Test python migrations on app/db/migrations
    from app.db.migrations.job_moderation_migration import run_job_moderation_migration
    from app.db.migrations.job_soft_delete_migration import run_job_soft_delete_migration
    from scripts.migrate_home_config_tables import migrate_home_config
    
    # Run twice to test idempotence
    idemp_results = []
    
    # 1. job_soft_delete_migration
    try:
        # First needs jobs table
        with mig_engine.connect() as conn:
            conn.execute(text("CREATE TABLE jobs (id INT PRIMARY KEY AUTO_INCREMENT, title VARCHAR(255), status VARCHAR(50));"))
            conn.commit()
            
        run_job_soft_delete_migration(mig_engine)
        run_job_soft_delete_migration(mig_engine)
        idemp_results.append({"migration": "job_soft_delete_migration", "idempotent": True, "error": None})
    except Exception as e:
        idemp_results.append({"migration": "job_soft_delete_migration", "idempotent": False, "error": str(e)})

    # 2. job_moderation_migration
    try:
        run_job_moderation_migration(mig_engine)
        run_job_moderation_migration(mig_engine)
        idemp_results.append({"migration": "job_moderation_migration", "idempotent": True, "error": None})
    except Exception as e:
        idemp_results.append({"migration": "job_moderation_migration", "idempotent": False, "error": str(e)})

    # 3. migrate_home_config_tables
    try:
        migrate_home_config(mig_engine)
        migrate_home_config(mig_engine)
        idemp_results.append({"migration": "migrate_home_config_tables", "idempotent": True, "error": None})
    except Exception as e:
        idemp_results.append({"migration": "migrate_home_config_tables", "idempotent": False, "error": str(e)})

    # Clean up
    with base_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db};"))
        conn.commit()

    report["idempotence_results"] = idemp_results

    with open("audit_gate1_migrations.json", "w", encoding="utf-8") as out:
        json.dump(report, out, indent=2)

    print("Migration audit completed. Saved audit_gate1_migrations.json")

if __name__ == "__main__":
    audit_migrations()
