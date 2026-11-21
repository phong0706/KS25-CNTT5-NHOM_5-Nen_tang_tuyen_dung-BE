"""Unit tests cho hàm thuần resolve_profile_access và safe_url (<= 150 dòng)."""
import pytest
from app.services.profile_access import resolve_profile_access, safe_url


def test_safe_url_validation():
    assert safe_url("https://github.com/techrecruit") == "https://github.com/techrecruit"
    assert safe_url("http://linkedin.com/in/test") == "http://linkedin.com/in/test"
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("data:text/html;base64,PHNjcmlwdD4=") is None
    assert safe_url("") is None
    assert safe_url(None) is None
    assert safe_url("https://example.com/<script>") is None


def test_resolve_access_admin():
    admin = {"id": 1, "role": "admin"}
    cand = {"user_id": 10, "is_public": False, "is_active": True}
    assert resolve_profile_access(admin, cand, []) == "full"


def test_resolve_access_candidate_self_and_others():
    cand_self = {"id": 10, "role": "candidate"}
    cand_other = {"id": 11, "role": "candidate"}
    cand_data = {"user_id": 10, "is_public": True, "is_active": True}

    # Xem chính mình
    assert resolve_profile_access(cand_self, cand_data, []) == "full"
    # Xem người khác -> PermissionError
    with pytest.raises(PermissionError):
        resolve_profile_access(cand_other, cand_data, [])


def test_resolve_access_employer_with_active_application():
    emp = {"id": 2, "role": "employer"}
    cand_pub = {"user_id": 10, "is_public": True, "is_active": True}
    cand_priv = {"user_id": 10, "is_public": False, "is_active": True}

    active_app = [{"id": 1, "status": "SUBMITTED", "withdrawn_at": None}]
    assert resolve_profile_access(emp, cand_pub, active_app) == "full"
    assert resolve_profile_access(emp, cand_priv, active_app) == "full"


def test_resolve_access_employer_with_withdrawn_application():
    emp = {"id": 2, "role": "employer"}
    cand_pub = {"user_id": 10, "is_public": True, "is_active": True}
    cand_priv = {"user_id": 10, "is_public": False, "is_active": True}

    withdrawn_app_status = [{"id": 1, "status": "WITHDRAWN", "withdrawn_at": None}]
    withdrawn_app_date = [{"id": 1, "status": "SUBMITTED", "withdrawn_at": "2026-11-20"}]

    # Rút đơn: nếu công khai -> public; nếu riêng tư -> none
    assert resolve_profile_access(emp, cand_pub, withdrawn_app_status) == "public"
    assert resolve_profile_access(emp, cand_priv, withdrawn_app_status) == "none"
    assert resolve_profile_access(emp, cand_pub, withdrawn_app_date) == "public"
    assert resolve_profile_access(emp, cand_priv, withdrawn_app_date) == "none"


def test_resolve_access_inactive_candidate():
    emp = {"id": 2, "role": "employer"}
    cand_inactive = {"user_id": 10, "is_public": True, "is_active": False}
    active_app = [{"id": 1, "status": "SUBMITTED", "withdrawn_at": None}]
    assert resolve_profile_access(emp, cand_inactive, active_app) == "none"
    assert resolve_profile_access(emp, cand_inactive, []) == "none"
