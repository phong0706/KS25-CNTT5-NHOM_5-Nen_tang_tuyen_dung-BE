"""CRUD cho bảng reports (báo cáo vi phạm tin tuyển dụng).

Luồng nghiệp vụ:
    1. Ứng viên (hoặc người dùng đã đăng nhập) gọi create_report để tố cáo 1 tin.
    2. Admin gọi list_reports + get_report + resolve_report để kiểm duyệt.
    3. Khi RESOLVED → job.status = "hidden" (ẩn tin) + gửi notification cho NTD.
"""
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.job import Job
from app.models.report import Report, ReportStatus
from app.models.user import User
from app.schemas.report_schema import ReportCreate


def _validate_report_data(db: Session, data: ReportCreate) -> tuple[Job, User]:
    """Kiểm tra tin tuyển dụng tồn tại, chưa bị ẩn/đóng, và trả về employer."""
    job = db.get(Job, data.post_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin tuyển dụng.")
    if job.status.lower() != "published":
        raise HTTPException(
            status_code=400,
            detail="Chỉ có thể báo cáo tin tuyển dụng đang được công khai.",
        )
    employer = db.get(User, job.employer_id)
    if employer is None:
        raise HTTPException(status_code=400, detail="Nhà tuyển dụng không hợp lệ.")
    return job, employer


def _duplicate_pending_report(db: Session, reporter_id: int, post_id: int) -> bool:
    return db.scalar(
        select(func.count(Report.id)).where(
            Report.reporter_id == reporter_id,
            Report.post_id == post_id,
            Report.status == ReportStatus.PENDING,
        )
    ) > 0


def create_report(db: Session, reporter_id: int, data: ReportCreate) -> Report:
    """Tạo báo cáo mới. Người dùng không được tự báo cáo tin của chính mình."""
    job, employer = _validate_report_data(db, data)
    if job.employer_id == reporter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể báo cáo tin tuyển dụng của chính mình.",
        )
    if _duplicate_pending_report(db, reporter_id, data.post_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã báo cáo tin này trước đó và đang chờ xử lý.",
        )
    report = Report(
        reporter_id=reporter_id,
        post_id=data.post_id,
        employer_id=job.employer_id,
        reason=data.reason.strip(),
        status=ReportStatus.PENDING,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_my_reports(db: Session, user_id: int, skip: int = 0, limit: int = 20) -> list[Report]:
    return (
        db.query(Report)
        .filter(Report.reporter_id == user_id)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# --- ADMIN ----------------------------------------------------------------


def _filter_reports_query(db: Session, status_filter: str | None, q: str | None):
    Reporter = aliased(User)
    Employer = aliased(User)
    stmt = (
        select(
            Report,
            Job.title.label("job_title"),
            Reporter.full_name.label("reporter_name"),
            Reporter.email.label("reporter_email"),
        )
        .join(Job, Report.post_id == Job.id)
        .join(Reporter, Report.reporter_id == Reporter.id)
        .outerjoin(Employer, Report.employer_id == Employer.id)
    )
    if status_filter and status_filter != "all":
        stmt = stmt.where(Report.status == status_filter)
    kw = (q or "").strip()
    if kw:
        stmt = stmt.where(
            (Job.title.ilike(f"%{kw}%"))
            | (Report.reason.ilike(f"%{kw}%"))
            | (Reporter.full_name.ilike(f"%{kw}%"))
        )
    return stmt.order_by(Report.created_at.desc(), Report.id.desc())


def list_reports_admin(db: Session, status_filter: str | None, q: str | None, skip: int, limit: int):
    stmt = _filter_reports_query(db, status_filter, q)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.offset(skip).limit(limit)).all()
    return rows, total


def get_report_admin(db: Session, report_id: int) -> Report | None:
    return db.get(Report, report_id)


def resolve_report(
    db: Session,
    report_id: int,
    *,
    admin_id: int,
    new_status: ReportStatus,
    resolution_result: str | None,
) -> tuple[Report, bool]:
    """Xử lý báo cáo. Trả về (report, job_hidden)."""
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo.")
    if report.status != ReportStatus.PENDING:
        raise HTTPException(status_code=400, detail="Báo cáo đã được xử lý trước đó.")

    job_hidden = False
    if new_status == ReportStatus.RESOLVED:
        # Vi phạm属实 → ẩn tin (HIDDEN) + ghi kết quả + báo NTD
        job = db.get(Job, report.post_id)
        if job and job.status.lower() != "hidden":
            job.status = "hidden"
            job_hidden = True

    report.status = new_status
    report.resolution_result = (resolution_result or "").strip()
    report.updated_at = datetime.utcnow()
    return report, job_hidden