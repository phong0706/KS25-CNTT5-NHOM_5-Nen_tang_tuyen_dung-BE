"""Script kiểm toán Giai đoạn 1: 1.1 Lệch Schema (ORM Models vs information_schema & Raw SQL scan)"""
import os
import re
import json
from sqlalchemy import inspect, text
from app.db.session import engine, Base
import app.models  # load all models

def audit_schema_divergence():
    inspector = inspect(engine)
    db_tables = inspector.get_table_names()
    
    report = {
        "missing_tables_in_db": [],
        "missing_tables_in_orm": [],
        "column_mismatches": [],
        "fk_mismatches": [],
        "raw_sql_column_errors": []
    }
    
    orm_tables = Base.metadata.tables
    
    # 1. Compare tables
    for tname in orm_tables:
        if tname not in db_tables:
            report["missing_tables_in_db"].append(tname)
            
    for tname in db_tables:
        if tname not in orm_tables:
            report["missing_tables_in_orm"].append(tname)
            
    # 2. Compare columns for matching tables
    for tname in orm_tables:
        if tname not in db_tables:
            continue
        db_cols = {c["name"]: c for c in inspector.get_columns(tname)}
        orm_cols = {c.name: c for c in orm_tables[tname].columns}
        
        # ORM columns missing in DB
        for cname, c in orm_cols.items():
            if cname not in db_cols:
                report["column_mismatches"].append({
                    "table": tname,
                    "column": cname,
                    "issue": "Defined in ORM model but missing in MySQL table"
                })
                
        # DB columns missing in ORM
        for cname, c in db_cols.items():
            if cname not in orm_cols:
                report["column_mismatches"].append({
                    "table": tname,
                    "column": cname,
                    "issue": f"Present in MySQL table (type: {c['type']}) but NOT mapped in ORM model"
                })

    # 3. Scan code for Raw SQL statements referencing non-existent columns (specifically checking candidate_skills.user_id etc.)
    code_dir = os.path.abspath("app")
    sql_patterns = [
        re.compile(r'text\(\s*["\']([^"\']+)["\']\s*\)', re.DOTALL),
        re.compile(r'execute\(\s*["\']([^"\']+)["\']\s*\)', re.DOTALL),
        re.compile(r'SELECT\s+.*?\s+FROM\s+.*?', re.IGNORECASE)
    ]
    
    all_table_cols = {}
    for tname in db_tables:
        all_table_cols[tname.lower()] = [c["name"].lower() for c in inspector.get_columns(tname)]
        
    raw_sql_findings = []
    for root, _, files in os.walk(code_dir):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8") as pyf:
                    content = pyf.read()
                    
                # Look specifically for candidate_skills.user_id as described in C3
                if "candidate_skills" in content and "user_id" in content:
                    lines = content.splitlines()
                    for idx, line in enumerate(lines, 1):
                        if re.search(r'candidate_skills[^\w]+.*user_id|user_id.*candidate_skills', line, re.IGNORECASE):
                            raw_sql_findings.append({
                                "file": os.path.relpath(fpath, os.path.abspath(".")).replace("\\", "/"),
                                "line": idx,
                                "snippet": line.strip(),
                                "issue": "References user_id on candidate_skills (which only has candidate_id or profile_id)"
                            })
                            
                # Check for explicit queries
                matches = re.findall(r'(?:SELECT|INSERT|UPDATE|DELETE)\s+[^;\"\']+', content, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    clean_sql = " ".join(m.split())
                    if "candidate_skills.user_id" in clean_sql.lower() or "candidate_skills cs where cs.user_id" in clean_sql.lower():
                        raw_sql_findings.append({
                            "file": os.path.relpath(fpath, os.path.abspath(".")).replace("\\", "/"),
                            "snippet": clean_sql[:120],
                            "issue": "SQL query references candidate_skills.user_id"
                        })
                        
    report["raw_sql_column_errors"] = raw_sql_findings

    with open("audit_gate1_schema.json", "w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, default=str)
        
    print("Schema divergence scan completed.")
    print(f"- Missing tables in DB: {len(report['missing_tables_in_db'])}")
    print(f"- Tables in DB not in ORM: {len(report['missing_tables_in_orm'])}")
    print(f"- Column mismatches: {len(report['column_mismatches'])}")
    print(f"- Raw SQL column errors found: {len(report['raw_sql_column_errors'])}")

if __name__ == "__main__":
    audit_schema_divergence()
