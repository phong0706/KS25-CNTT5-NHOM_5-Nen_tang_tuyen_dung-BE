"""Idempotent migration adding time-limited featured job fields."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def run_job_featured_migration(engine: Engine) -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("jobs")}
        if "is_featured" not in columns:
            connection.execute(
                text("ALTER TABLE jobs ADD COLUMN is_featured BOOLEAN NOT NULL DEFAULT FALSE")
            )
        if "featured_until" not in columns:
            connection.execute(
                text("ALTER TABLE jobs ADD COLUMN featured_until DATETIME NULL")
            )

        indexes = {index["name"] for index in inspect(connection).get_indexes("jobs")}
        if "idx_jobs_featured_until" not in indexes:
            connection.execute(
                text(
                    "CREATE INDEX idx_jobs_featured_until "
                    "ON jobs (is_featured, featured_until)"
                )
            )


if __name__ == "__main__":
    from app.db.session import engine

    run_job_featured_migration(engine)
    print("Migration tin nổi bật hoàn tất.")
