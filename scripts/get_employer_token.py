import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))

import json
from app.db.session import SessionLocal
from app.models.user import User
from app.models.company import Company
from app.core.security import create_access_token

db = SessionLocal()
u = db.query(User).filter(User.role == "employer").first()
c = db.query(Company).filter(Company.employer_id == u.id).first() if u else None

token = create_access_token(u.id, u.role)
user_data = {
    "id": u.id,
    "email": u.email,
    "full_name": u.full_name,
    "role": u.role,
    "is_active": u.is_active,
    "is_verified": u.is_verified,
}

print("TOKEN:", token)
print("USER_JSON:", json.dumps(user_data))
print("USER_ID:", u.id)
print("COMPANY_ID:", c.id if c else None)
print("COMPANY_NAME:", c.name if c else None)
