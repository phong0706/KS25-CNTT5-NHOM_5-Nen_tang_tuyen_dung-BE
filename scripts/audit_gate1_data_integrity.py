"""Script kiểm toán Giai đoạn 1: 1.2 - 1.6 Toàn vẹn dữ liệu, ràng buộc, dữ liệu rác, trùng lặp và quét Seed."""
import os
import re
import json
from sqlalchemy import text
from app.db.session import engine

def audit_data_integrity():
    with engine.connect() as conn:
        report = {}
        
        # -------------------------------------------------------------
        # 1.2 Dữ liệu mồ côi
        # -------------------------------------------------------------
        # a) Jobs with company_id IS NULL
        jobs_null_company = conn.execute(text("SELECT id, title, status, employer_id FROM jobs WHERE company_id IS NULL")).mappings().all()
        
        # b) Jobs with company_id not pointing to existing company
        jobs_invalid_company = conn.execute(text("""
            SELECT j.id, j.title, j.company_id 
            FROM jobs j 
            LEFT JOIN companies c ON j.company_id = c.id 
            WHERE j.company_id IS NOT NULL AND c.id IS NULL
        """)).mappings().all()
        
        # c) Companies with owner not existing in users
        comp_invalid_owner = conn.execute(text("""
            SELECT c.id, c.name, c.employer_id, c.owner_id 
            FROM companies c 
            LEFT JOIN users u1 ON c.employer_id = u1.id 
            LEFT JOIN users u2 ON c.owner_id = u2.id 
            WHERE (c.employer_id IS NOT NULL AND u1.id IS NULL)
               OR (c.owner_id IS NOT NULL AND u2.id IS NULL)
               OR (c.employer_id IS NULL AND c.owner_id IS NULL)
        """)).mappings().all()
        
        # d) Applications pointing to CV not belonging to candidate
        apps_cv_mismatch = conn.execute(text("""
            SELECT a.id AS app_id, a.candidate_id, a.cv_id, c.candidate_id AS cv_owner_id
            FROM applications a
            JOIN cvs c ON a.cv_id = c.id
            WHERE a.candidate_id != c.candidate_id
        """)).mappings().all()
        
        # e) Single CV shared across multiple users in applications
        cv_multi_users = conn.execute(text("""
            SELECT cv_id, COUNT(DISTINCT candidate_id) as user_count, GROUP_CONCAT(DISTINCT candidate_id) as user_ids
            FROM applications
            WHERE cv_id IS NOT NULL
            GROUP BY cv_id
            HAVING COUNT(DISTINCT candidate_id) > 1
        """)).mappings().all()

        report["1.2_orphan_data"] = {
            "jobs_null_company_count": len(jobs_null_company),
            "jobs_null_company_sample": [dict(r) for r in jobs_null_company[:10]],
            "jobs_invalid_company_count": len(jobs_invalid_company),
            "jobs_invalid_company_sample": [dict(r) for r in jobs_invalid_company],
            "companies_invalid_owner_count": len(comp_invalid_owner),
            "apps_cv_mismatch_count": len(apps_cv_mismatch),
            "apps_cv_mismatch_sample": [dict(r) for r in apps_cv_mismatch],
            "cv_multi_users_count": len(cv_multi_users),
            "cv_multi_users_sample": [dict(r) for r in cv_multi_users]
        }

        # -------------------------------------------------------------
        # 1.3 Ràng buộc nghiệp vụ trong dữ liệu
        # -------------------------------------------------------------
        # a) Multi active logos per company
        multi_active_logos = conn.execute(text("""
            SELECT company_id, COUNT(*) as active_count, GROUP_CONCAT(id) as logo_ids
            FROM company_logos
            WHERE is_current = 1
            GROUP BY company_id
            HAVING COUNT(*) > 1
        """)).mappings().all() if "company_logos" in [t[0] for t in conn.execute(text("SHOW TABLES")).all()] else []

        # b) Reviewed at before created at
        jobs_date_inversion = conn.execute(text("""
            SELECT id, title, created_at, reviewed_at, published_at
            FROM jobs
            WHERE reviewed_at IS NOT NULL AND reviewed_at < created_at
        """)).mappings().all()
        
        verif_date_inversion = conn.execute(text("""
            SELECT id, company_id, submitted_at, reviewed_at
            FROM company_verifications
            WHERE reviewed_at IS NOT NULL AND submitted_at IS NOT NULL AND reviewed_at < submitted_at
        """)).mappings().all() if "company_verifications" in [t[0] for t in conn.execute(text("SHOW TABLES")).all()] else []

        # c) Invalid statuses
        jobs_invalid_status = conn.execute(text("""
            SELECT id, title, status FROM jobs
            WHERE status NOT IN ('draft', 'pending', 'published', 'rejected', 'closed')
        """)).mappings().all()

        # d) Negative numbers
        neg_values = conn.execute(text("""
            SELECT id, title, salary_min, salary_max, quantity, views_count
            FROM jobs
            WHERE salary_min < 0 OR salary_max < 0 OR quantity < 0 OR views_count < 0
        """)).mappings().all()

        report["1.3_business_rules"] = {
            "multi_active_logos_count": len(multi_active_logos),
            "multi_active_logos_sample": [dict(r) for r in multi_active_logos],
            "jobs_date_inversion_count": len(jobs_date_inversion),
            "verif_date_inversion_count": len(verif_date_inversion),
            "verif_date_inversion_sample": [dict(r) for r in verif_date_inversion],
            "jobs_invalid_status_count": len(jobs_invalid_status),
            "negative_numeric_fields_count": len(neg_values)
        }

        # -------------------------------------------------------------
        # 1.4 Dữ liệu test và rác (C1)
        # -------------------------------------------------------------
        # Hex jobs or test patterns
        test_jobs = conn.execute(text("""
            SELECT id, title, status, created_at, employer_id 
            FROM jobs 
            WHERE title REGEXP '[0-9a-f]{6,}'
               OR title LIKE '%Valid Engineer%'
               OR title LIKE '%Job Test%'
               OR title LIKE '%Pending Engineer%'
               OR title LIKE '%Test%'
               OR title LIKE '%[Seed]%'
        """)).mappings().all()
        
        # Hex companies or HTML tags
        test_companies = conn.execute(text("""
            SELECT id, name, created_at, employer_id
            FROM companies
            WHERE name REGEXP '[0-9a-f]{6,}'
               OR name LIKE '%Company %'
               OR name LIKE '%<%>%'
               OR name LIKE '%Test%'
        """)).mappings().all()
        
        # @test.com accounts with admin/employer role
        test_accounts = conn.execute(text("""
            SELECT id, role, created_at, is_active
            FROM users
            WHERE email LIKE '%@test.com' OR email LIKE '%@example.com'
        """)).mappings().all()

        report["1.4_test_and_junk_data"] = {
            "test_jobs_count": len(test_jobs),
            "test_jobs_sample": [dict(r) for r in test_jobs[:15]],
            "test_companies_count": len(test_companies),
            "test_companies_sample": [dict(r) for r in test_companies[:15]],
            "test_accounts_count": len(test_accounts),
            "test_accounts_by_role": {
                role: len([a for a in test_accounts if a["role"] == role])
                for role in set(a["role"] for a in test_accounts)
            }
        }

        # -------------------------------------------------------------
        # 1.5 Trùng lặp
        # -------------------------------------------------------------
        dup_emails = conn.execute(text("""
            SELECT LOWER(TRIM(email)) as norm_email, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
            FROM users
            GROUP BY LOWER(TRIM(email))
            HAVING COUNT(*) > 1
        """)).mappings().all()
        
        dup_tax_codes = conn.execute(text("""
            SELECT tax_code, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
            FROM companies
            WHERE tax_code IS NOT NULL AND TRIM(tax_code) != ''
            GROUP BY tax_code
            HAVING COUNT(*) > 1
        """)).mappings().all()

        report["1.5_duplicates"] = {
            "duplicate_emails_count": len(dup_emails),
            "duplicate_tax_codes_count": len(dup_tax_codes),
            "duplicate_tax_codes_sample": [dict(r) for r in dup_tax_codes]
        }

    # -------------------------------------------------------------
    # 1.6 Quét Seed (sql/01_schema.sql và 02_seed_demo.sql)
    # -------------------------------------------------------------
    seed_findings = []
    for sfile in ["sql/01_schema.sql", "sql/02_seed_demo.sql"]:
        if os.path.exists(sfile):
            with open(sfile, "r", encoding="utf-8") as sf:
                scontent = sf.read()
                
            # Check for hashes ($2b$, $2a$)
            hashes = re.findall(r'\$2[abxy]\$\d+\$[A-Za-z0-9./]{53}', scontent)
            # Check for real email domains or test emails
            test_emails = re.findall(r'[\w.-]+@(?:test\.com|example\.com|gmail\.com)', scontent)
            # Check for potential tokens or hex
            hex_tokens = re.findall(r'[\'"][0-9a-f]{32,64}[\'"]', scontent)
            # Check for CV file paths
            cv_paths = re.findall(r'[\'"][^\'"]*?\.(?:pdf|docx|doc)[\'"]', scontent)
            # Check for test strings
            test_names = re.findall(r'[\'"][^\'"]*?(?:Valid Engineer|Test Company|Pending Engineer)[^\'"]*?[\'"]', scontent)

            seed_findings.append({
                "file": sfile,
                "bcrypt_hashes_count": len(hashes),
                "bcrypt_hash_sample_masked": [h[:10] + "..." for h in hashes[:3]],
                "emails_count": len(test_emails),
                "email_domains": list(set([e.split("@")[1] for e in test_emails])),
                "hex_tokens_count": len(hex_tokens),
                "cv_paths_count": len(cv_paths),
                "cv_paths_sample": cv_paths[:5],
                "test_names_count": len(test_names)
            })
            
    report["1.6_seed_scan"] = seed_findings

    with open("audit_gate1_data.json", "w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, default=str)
        
    print("Data integrity audit completed. Saved audit_gate1_data.json")

if __name__ == "__main__":
    audit_data_integrity()
