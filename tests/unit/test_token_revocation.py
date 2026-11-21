"""
backend/tests/unit/test_token_revocation.py
Kiểm thử cơ chế thu hồi token JWT khi đổi/đặt lại mật khẩu.
Token cũ phải bị get_current_user từ chối (401).
"""
import pytest
from app.core.security import create_access_token, get_current_user
from app.models.user import User
from app.db.session import SessionLocal
from fastapi import HTTPException

from fastapi.security import HTTPAuthorizationCredentials

def test_token_version_revocation():
    db = SessionLocal()
    user = None
    orig_ver = 1
    try:
        user = db.query(User).filter(User.role == "candidate").first()
        assert user is not None, "Candidate user must exist"
        
        orig_ver = getattr(user, "token_version", 1) or 1
        old_token = create_access_token(user_id=user.id, role=user.role, token_version=orig_ver)
        
        # Verify old token works
        cred_old = HTTPAuthorizationCredentials(scheme="Bearer", credentials=old_token)
        curr = get_current_user(credentials=cred_old, db=db)
        assert curr.id == user.id
        
        # Simulate password change: increment token_version
        user.token_version = orig_ver + 1
        db.commit()
        db.refresh(user)
        
        # Verify old token is now REJECTED with 401
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials=cred_old, db=db)
        assert exc.value.status_code == 401
        
        # New token with new version works
        new_token = create_access_token(user_id=user.id, role=user.role, token_version=user.token_version)
        cred_new = HTTPAuthorizationCredentials(scheme="Bearer", credentials=new_token)
        curr2 = get_current_user(credentials=cred_new, db=db)
        assert curr2.id == user.id
    finally:
        if user:
            user.token_version = orig_ver
            db.commit()
        db.close()
