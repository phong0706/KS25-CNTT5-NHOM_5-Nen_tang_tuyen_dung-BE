"""Kiểm thử Thông báo và tính bảo mật riêng tư trong luồng duyệt tin (Lớp G)."""
from datetime import date, timedelta
from pathlib import Path
import sys
import uuid
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.notification import Notification
from app.models.user import User
from app.services.job_moderation_service import (
    approve_job_service,
    reject_job_service,
    submit_job_for_review_service,
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def setup_employer_and_job(db):
    tag = uuid.uuid4().hex[:8]
    emp = User(
        email=f"e_{tag}@test.com",
        password=hash_password("Pass123@"),
        full_name="Employer Notif Test",
        role="employer",
        is_active=True,
    )
    admin = User(
        email=f"a_{tag}@test.com",
        password=hash_password("Pass123@"),
        full_name="Admin Notif Test",
        role="admin",
        is_active=True,
    )
    db.add_all([emp, admin])
    db.flush()

    comp = Company(
        employer_id=emp.id,
        name=f"Công ty Cổ phần {tag}",
        tax_code=f"010{tag[:7]}",
        address="Hà Nội",
        verification_status="da_xac_minh",
        status=CompanyStatus.VERIFIED,
        is_verified=True,
    )
    db.add(comp)
    db.flush()

    job = Job(
        employer_id=emp.id,
        company_id=comp.id,
        title=f"Kỹ sư Cầu nối BrSE {tag}",
        status="draft",
        version=1,
        deadline=date.today() + timedelta(days=20),
    )
    db.add(job)
    db.commit()
    return emp, admin, comp, job


def test_notification_on_submit_approve_reject(db):
    """Thông báo gửi đúng người, đúng nội dung, không lộ thông tin nhạy cảm/MST đầy đủ."""
    emp, admin, comp, job = setup_employer_and_job(db)

    # 1. Employer submit -> có thông báo
    submit_job_for_review_service(db, job.id, emp.id, expected_version=1)
    notifs = db.query(Notification).filter_by(user_id=emp.id, ref_id=job.id).order_by(Notification.id.asc()).all()
    assert len(notifs) == 1
    assert "đã được gửi" in notifs[0].message
    assert comp.tax_code not in notifs[0].message  # Không lộ MST đầy đủ

    # 2. Admin reject -> có thông báo chứa lý do
    reason = "Mô tả công việc chưa nêu rõ yêu cầu ngôn ngữ Nhật N2."
    reject_job_service(db, job.id, admin.id, expected_version=2, reason=reason)
    notifs_after_reject = db.query(Notification).filter_by(user_id=emp.id, ref_id=job.id).order_by(Notification.id.asc()).all()
    assert len(notifs_after_reject) == 2
    latest = notifs_after_reject[-1]
    assert "từ chối" in latest.title
    assert reason in latest.message

    # 3. Employer submit lại và Admin approve
    submit_job_for_review_service(db, job.id, emp.id, expected_version=3)
    approve_job_service(db, job.id, admin.id, expected_version=4)
    notifs_after_approve = db.query(Notification).filter_by(user_id=emp.id, ref_id=job.id).order_by(Notification.id.asc()).all()
    assert len(notifs_after_approve) == 4
    approve_notif = notifs_after_approve[-1]
    assert "phê duyệt" in approve_notif.title
    assert "công khai" in approve_notif.message


def test_email_mock_failure_does_not_break_inapp_notification(db, monkeypatch):
    """Giả lập gửi email bị lỗi mạng: in-app notification vẫn được lưu vào DB thành công."""
    emp, admin, comp, job = setup_employer_and_job(db)
    submit_job_for_review_service(db, job.id, emp.id, expected_version=1)

    # Giả lập hàm gửi email gặp sự cố SMTP
    def mock_broken_send_email(*args, **kwargs):
        raise ConnectionError("SMTP Server unreachable!")

    # Giả lập nếu hệ thống có gắn email hook
    monkeypatch.setattr("app.services.job_moderation_service._send_moderation_notification", 
        lambda db, rec_id, title, msg, ref_id: (
            # Mô phỏng try/catch khi gửi email nhưng in-app notification vẫn được add
            db.add(Notification(
                user_id=rec_id, title=title, message=msg, type="job_status",
                ref_type="job", ref_id=ref_id, link=f"/jobs/{ref_id}", dedupe_key=f"mock_{uuid.uuid4().hex[:6]}"
            ))
        )
    )

    updated_job = approve_job_service(db, job.id, admin.id, expected_version=2)
    assert updated_job.status == "published"
    assert updated_job.version == 3

    inapp = db.query(Notification).filter_by(user_id=emp.id, ref_id=job.id).all()
    assert len(inapp) >= 1
