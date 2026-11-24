"""Seed 2 công ty độc lập (Sao Khuê & Xanh Lam) có tin đủ trạng thái đi qua service và hồ sơ khác nhau."""
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.application import Application, ApplicationStatus, Interview
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.user import User
from app.services.job_moderation_service import approve_job_service, submit_job_for_review_service


def _ensure_user(db: Session, email: str, full_name: str, role: str) -> User:
    u = db.scalar(select(User).where(User.email == email))
    if not u:
        u = User(
            email=email,
            password=hash_password(os.getenv("SEED_USER_PASSWORD", "TechRecruit2026!")),
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=True,
        )
        db.add(u)
        db.flush()
    return u


def _ensure_verified_company(db: Session, slug: str, name: str, owner: User, industry_id: int = 1) -> Company:
    comp = db.scalar(select(Company).where(Company.slug == slug))
    if not comp:
        comp = Company(
            slug=slug,
            name=name,
            employer_id=owner.id,
            owner_id=owner.id,
            industry_id=industry_id,
            status=CompanyStatus.VERIFIED,
            verification_status="da_xac_minh",
            is_verified=True,
            is_visible=True,
            is_draft=False,
        )
        db.add(comp)
        db.flush()
    else:
        comp.employer_id = owner.id
        comp.owner_id = owner.id
        comp.status = CompanyStatus.VERIFIED
        comp.verification_status = "da_xac_minh"
        comp.is_verified = True
        comp.is_visible = True
        comp.is_draft = False
        db.flush()
    return comp


def _create_draft_job(db: Session, comp: Company, title: str, deadline: date) -> Job:
    existing = db.scalar(select(Job).where(Job.company_id == comp.id, Job.title == title, Job.deleted_at.is_(None)))
    if existing:
        return existing
    job = Job(
        employer_id=comp.employer_id,
        company_id=comp.id,
        title=title,
        level="Middle",
        work_type="Full-time",
        location="Hà Nội",
        quantity=2,
        deadline=deadline,
        description="Mô tả vị trí tuyển dụng chuẩn hệ thống TechRecruit.",
        requirements="Yêu cầu kinh nghiệm chuyên môn liên quan và tư duy hệ thống.",
        skills=["Python", "MySQL"],
        is_salary_negotiable=True,
        status="draft",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def seed_two_companies_via_service(db: Session) -> None:
    admin = db.scalar(select(User).where(User.role == "admin", User.is_active == True).order_by(User.id.asc()))  # noqa: E712
    if not admin:
        admin = _ensure_user(db, "admin_seed@tuyendung.com", "System Admin", "admin")

    emp_a = _ensure_user(db, "hr1@tuyendung.com", "Trần Thị Bình", "employer")
    emp_b = _ensure_user(db, "hr_xanhlam@tuyendung.com", "Lê Hoàng Minh", "employer")
    cand = _ensure_user(db, "ungvien1@gmail.com", "Phạm Minh Đức", "candidate")
    db.commit()

    comp_a = _ensure_verified_company(db, "sao-khue-cloud-labs", "Sao Khuê Cloud Labs", emp_a)
    comp_b = _ensure_verified_company(db, "edge-unverified-standard", "Khởi nghiệp Công nghệ Xanh Lam", emp_b)
    db.commit()

    future = date.today() + timedelta(days=30)
    # Công ty A (Sao Khuê): 2 đang tuyển, 1 chờ duyệt, 1 nháp, 1 đã đóng (qua service)
    for idx, title in enumerate(["Backend Cloud Engineer (Sao Khuê)", "DevOps Kubernetes Lead (Sao Khuê)"], 1):
        j = _create_draft_job(db, comp_a, title, future)
        if j.status == "draft":
            j = submit_job_for_review_service(db, j.id, emp_a.id, j.version, company_id=comp_a.id)
        if j.status == "pending":
            approve_job_service(db, j.id, admin.id, j.version)

    j_pend = _create_draft_job(db, comp_a, "SRE Platform Engineer (Sao Khuê)", future)
    if j_pend.status == "draft":
        submit_job_for_review_service(db, j_pend.id, emp_a.id, j_pend.version, company_id=comp_a.id)

    _create_draft_job(db, comp_a, "QA Automation Draft (Sao Khuê)", future)

    j_closed = _create_draft_job(db, comp_a, "Frontend React Closed (Sao Khuê)", future)
    if j_closed.status == "draft":
        j_closed = submit_job_for_review_service(db, j_closed.id, emp_a.id, j_closed.version, company_id=comp_a.id)
    if j_closed.status == "pending":
        j_closed = approve_job_service(db, j_closed.id, admin.id, j_closed.version)
    if j_closed.status == "published":
        j_closed.status = "closed"
        db.commit()

    # Công ty B (Xanh Lam): 1 đang tuyển, 1 nháp (qua service)
    jb1 = _create_draft_job(db, comp_b, "Fullstack Engineer (Xanh Lam)", future)
    if jb1.status == "draft":
        jb1 = submit_job_for_review_service(db, jb1.id, emp_b.id, jb1.version, company_id=comp_b.id)
    if jb1.status == "pending":
        jb1 = approve_job_service(db, jb1.id, admin.id, jb1.version)
    _create_draft_job(db, comp_b, "Data Analyst Draft (Xanh Lam)", future)

    # Đảm bảo công ty B có 1 hồ sơ ứng tuyển của Phạm Minh Đức và công ty A không bị lẫn
    has_app_b = db.scalar(select(Application).where(Application.job_id == jb1.id, Application.candidate_id == cand.id))
    if not has_app_b:
        app_b = Application(
            candidate_id=cand.id,
            job_id=jb1.id,
            cv_name_snapshot="CV_PhamMinhDuc.pdf",
            status=ApplicationStatus.SUBMITTED.value,
        )
        db.add(app_b)
        db.flush()
        db.add(Interview(
            application_id=app_b.id,
            scheduled_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2),
            duration_min=45,
            mode="Online",
            location_or_link="https://meet.google.com/xanh-lam",
            status="scheduled",
            created_by=emp_b.id,
        ))
        db.commit()
