"""Add columns expected by the current public company and job APIs."""
from pathlib import Path
import re
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app.db.session import engine


COLUMN_DEFINITIONS = {
    "companies": {
        "slug": "VARCHAR(120) NULL",
        "logo_url": "VARCHAR(500) NULL",
        "cover_url": "VARCHAR(500) NULL",
        "size": "VARCHAR(50) NULL",
    },
    "jobs": {
        "employer_id": "INT NULL",
        "category_id": "INT NULL",
        "level_id": "INT NULL",
        "work_type_id": "INT NULL",
        "level": "VARCHAR(100) NULL",
        "work_type": "VARCHAR(100) NULL",
        "location": "VARCHAR(120) NULL",
        "skills": "JSON NULL",
        "is_salary_negotiable": "BOOLEAN NOT NULL DEFAULT FALSE",
        "published_at": "DATETIME NULL",
    },
}


def _column_names(connection, table_name):
    return {column["name"] for column in inspect(connection).get_columns(table_name)}


def _add_missing_columns(connection):
    inspector = inspect(connection)
    for table_name, columns in COLUMN_DEFINITIONS.items():
        if not inspector.has_table(table_name):
            raise RuntimeError(f"Required table '{table_name}' does not exist")
        existing = _column_names(connection, table_name)
        for column_name, definition in columns.items():
            if column_name not in existing:
                connection.execute(
                    text(
                        f"ALTER TABLE `{table_name}` "
                        f"ADD COLUMN `{column_name}` {definition}"
                    )
                )
                print(f"Added {table_name}.{column_name}")


def _ensure_company_slug_index(connection):
    inspector = inspect(connection)
    unique_slug = any(
        constraint.get("column_names") == ["slug"]
        for constraint in inspector.get_unique_constraints("companies")
    ) or any(
        index.get("unique") and index.get("column_names") == ["slug"]
        for index in inspector.get_indexes("companies")
    )
    if not unique_slug:
        duplicate = connection.execute(
            text(
                "SELECT slug FROM companies WHERE slug IS NOT NULL "
                "GROUP BY slug HAVING COUNT(*) > 1 LIMIT 1"
            )
        ).first()
        if duplicate:
            raise RuntimeError("Cannot make companies.slug unique: duplicate values exist")
        connection.execute(
            text("CREATE UNIQUE INDEX uq_companies_slug ON companies (slug)")
        )


def _slugify_company(name, company_id, used_slugs):
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "company"
    slug = f"{base}-{company_id}"
    suffix = 2
    while slug in used_slugs:
        slug = f"{base}-{company_id}-{suffix}"
        suffix += 1
    return slug


def _backfill_companies(connection):
    connection.execute(
        text(
            "UPDATE companies SET logo_url = logo "
            "WHERE logo_url IS NULL AND logo IS NOT NULL"
        )
    )
    connection.execute(
        text(
            "UPDATE companies SET cover_url = cover_image "
            "WHERE cover_url IS NULL AND cover_image IS NOT NULL"
        )
    )
    connection.execute(
        text(
            "UPDATE companies SET size = company_size "
            "WHERE size IS NULL AND company_size IS NOT NULL"
        )
    )

    rows = connection.execute(
        text("SELECT id, name, slug FROM companies ORDER BY id")
    ).mappings()
    rows = list(rows)
    used_slugs = {row["slug"] for row in rows if row["slug"]}
    for row in rows:
        if not row["slug"]:
            slug = _slugify_company(row["name"], row["id"], used_slugs)
            connection.execute(
                text("UPDATE companies SET slug = :slug WHERE id = :company_id"),
                {"slug": slug, "company_id": row["id"]},
            )
            used_slugs.add(slug)

    _ensure_company_slug_index(connection)


def _backfill_jobs(connection):
    job_columns = _column_names(connection, "jobs")
    if "posted_by" not in job_columns:
        raise RuntimeError("Cannot populate jobs.employer_id: jobs.posted_by is missing")

    connection.execute(
        text(
            "UPDATE jobs SET employer_id = posted_by "
            "WHERE employer_id IS NULL AND posted_by IS NOT NULL"
        )
    )
    missing_employer = connection.execute(
        text("SELECT COUNT(*) FROM jobs WHERE employer_id IS NULL")
    ).scalar_one()
    if missing_employer:
        raise RuntimeError(
            f"{missing_employer} job(s) have no posted_by value; "
            "populate employer_id before retrying"
        )
    connection.execute(text("ALTER TABLE jobs MODIFY COLUMN employer_id INT NOT NULL"))

    if "experience_level" in job_columns:
        connection.execute(
            text(
                "UPDATE jobs SET level = experience_level "
                "WHERE level IS NULL AND experience_level IS NOT NULL"
            )
        )
    if "job_type" in job_columns:
        connection.execute(
            text(
                "UPDATE jobs SET work_type = CASE UPPER(job_type) "
                "WHEN 'FULLTIME' THEN 'Full-time' "
                "WHEN 'PARTTIME' THEN 'Part-time' "
                "WHEN 'INTERN' THEN 'Internship' "
                "WHEN 'REMOTE' THEN 'Remote' "
                "ELSE job_type END "
                "WHERE work_type IS NULL AND job_type IS NOT NULL"
            )
        )
    if "is_negotiable" in job_columns:
        connection.execute(
            text(
                "UPDATE jobs SET is_salary_negotiable = is_negotiable "
                "WHERE is_negotiable IS NOT NULL"
            )
        )
    if "location_id" in job_columns and inspect(connection).has_table("meta_locations"):
        connection.execute(
            text(
                "UPDATE jobs j JOIN meta_locations l ON l.id = j.location_id "
                "SET j.location = l.name "
                "WHERE j.location IS NULL"
            )
        )
    if "created_at" in job_columns and "status" in job_columns:
        connection.execute(
            text(
                "UPDATE jobs SET published_at = created_at "
                "WHERE published_at IS NULL AND LOWER(status) = 'published' "
                "AND created_at IS NOT NULL"
            )
        )

    indexes = inspect(connection).get_indexes("jobs")
    indexed_columns = {
        tuple(index.get("column_names") or [])
        for index in indexes
    }
    if ("employer_id",) not in indexed_columns:
        connection.execute(
            text("CREATE INDEX idx_jobs_employer_id ON jobs (employer_id)")
        )


def main():
    with engine.begin() as connection:
        _add_missing_columns(connection)
        _backfill_companies(connection)
        _backfill_jobs(connection)
    print("Public API schema migration completed.")


if __name__ == "__main__":
    main()
