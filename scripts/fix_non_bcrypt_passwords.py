"""Script xử lý các tài khoản có users.password không phải bcrypt hash (BUG_DB_001).

Mặc định chạy ở chế độ dry-run (chỉ đọc, không ghi DB).
Truyền --apply để thực thi trong 1 transaction.
TUYỆT ĐỐI không in/log mật khẩu thô hoặc băm.
"""
import argparse
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text  # noqa: E402

from app.core.security import hash_password, is_bcrypt_hash  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


def run_migration(apply: bool = False) -> int:
    db = SessionLocal()
    try:
        users = list(db.scalars(select(User).order_by(User.id.asc())))
        targets = [u for u in users if not is_bcrypt_hash(u.password)]
        print(f"MODE: {'APPLY' if apply else 'DRY-RUN'}")
        print(f"TOTAL_USERS: {len(users)} | NON_BCRYPT_COUNT: {len(targets)}")
        for u in targets:
            kind = "empty_or_null" if not u.password else "non_bcrypt"
            print(f"  id={u.id} | email={u.email} | role={u.role} | kind={kind}")

        if not apply or not targets:
            return len(targets)

        fallback_pw = os.getenv("SEED_USER_PASSWORD")
        for u in targets:
            plain_or_seed = u.password if u.password else (fallback_pw or secrets.token_urlsafe(16))
            u.password = hash_password(plain_or_seed)
            u.token_version = (getattr(u, "token_version", 1) or 1) + 1
        db.commit()

        remaining = db.execute(
            text(r"SELECT COUNT(*) FROM users WHERE password NOT REGEXP '^\\$2[aby]\\$[0-9]{2}\\$'")
        ).scalar()
        print(f"APPLIED: {len(targets)} | REMAINING_NON_BCRYPT: {remaining}")
        return int(remaining or 0)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate non-bcrypt user passwords.")
    parser.add_argument("--apply", action="store_true", help="Thực sự ghi thay đổi vào DB.")
    args = parser.parse_args()
    run_migration(apply=args.apply)


if __name__ == "__main__":
    main()
