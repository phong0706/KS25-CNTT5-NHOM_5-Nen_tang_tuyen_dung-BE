"""Router báo cáo vi phạm: Ứng viên tạo báo cáo; Admin kiểm duyệt.

Endpoint:
    POST   /api/reports          (đăng nhập) - Tạo báo cáo vi phạm mới
    GET    /api/reports/me       (đăng nhập) - Danh sách báo cáo của tôi
    GET    /api/admin/reports    (admin)    - Danh sách báo cáo awaiting moderation
    GET    /api/admin/reports/{id} (admin)  - Chi tiết báo cáo
    PATCH  /api/admin/reports/{id} (admin)  - Gỡ tin / Bỏ qua
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import ALL_AUTHENTICATED_ROLES, role_required
from app.db.session import get_db
from app.models.job import Job
from app.models.report import Report, ReportStatus
from app.models.user import User
from app.schemas.report_schema import (
    AdminReportActionOut,
    AdminReportListOut,
    AdminReportPageOut,
    ReportActionIn,
    ReportCreate,
    ReportResponse,
)
from app.services.notification import NotificationType, create_notification

router = APIRouter(tags=["Reports"])


# --- Ứng viên tạo báo cáo -----------------------------------------------


@router.post(
    "/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Báo cáo tin vi phạm (lừa đảo, sai thông tin)",
)
def create_report(
    data: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(*ALL_AUTHENTICATED_ROLES)),
):
    """Người dùng đã đăng nhập báo cáo 1 tin tuyển dụng vi phạm (body: post_id, reason)."""
    from app.crud.report import create_report as _create_report

    if current_user.role != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ ứng viên mới có thể báo cáo tin tuyển dụng.",
        )
    return _create_report(db, current_user.id, data)


@router.get(
    "/reports/me",
    response_model=list[ReportResponse],
    summary="Danh sách báo cáo của tôi",
)
def list_my_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(*ALL_AUTHENTICATED_ROLES)),
):
    """Lịch sử các báo cáo mà tôi đã gửi."""
    from app.crud.report import list_my_reports as _list_my_reports

    return _list_my_reports(db, current_user.id, skip, limit)


# --- Admin moderation ----------------------------------------------------


@router.get(
    "/admin/reports",
    response_model=AdminReportPageOut,
    summary="[ADMIN] Danh sách báo cáo vi phạm",
)
def admin_list_reports(
    status_filter: str | None = Query(None, alias="status", description="PENDING|RESOLVED|REJECTED|all"),
    q: str = Query("", max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    """Admin xem danh sách báo cáo, có thể lọc theo trạng thái."""
    from app.crud.report import list_reports_admin as _list_reports_admin

    rows, total = _list_reports_admin(db, status_filter, q, skip, limit)
    items = []
    for report, job_title, reporter_name, reporter_email in rows:
        employer = db.get(User, report.employer_id)
        items.append(
            AdminReportListOut(
                id=report.id,
                post_id=report.post_id,
                reporter_full_name=reporter_name,
                reporter_email=reporter_email,
                post_title=job_title,
                employer_full_name=employer.full_name if employer else None,
                reason=report.reason,
                status=report.status,
                resolution_result=report.resolution_result,
                created_at=report.created_at.isoformat() if report.created_at else None,
            )
        )
    return AdminReportPageOut(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/admin/reports/{report_id}",
    response_model=AdminReportListOut,
    summary="[ADMIN] Chi tiết 1 báo cáo",
)
def admin_get_report(
    report_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    """Admin xem chi tiết 1 báo cáo trước khi quyết định."""
    from app.crud.report import get_report_admin as _get_report_admin

    report = _get_report_admin(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo.")

    job = db.get(Job, report.post_id)
    reporter = db.get(User, report.reporter_id)
    employer = db.get(User, report.employer_id)

    return AdminReportListOut(
        id=report.id,
        post_id=report.post_id,
        reporter_full_name=reporter.full_name if reporter else None,
        reporter_email=reporter.email if reporter else None,
        post_title=job.title if job else None,
        employer_full_name=employer.full_name if employer else None,
        reason=report.reason,
        status=report.status,
        resolution_result=report.resolution_result,
        created_at=report.created_at.isoformat() if report.created_at else None,
    )


@router.patch(
    "/admin/reports/{report_id}",
    response_model=AdminReportActionOut,
    summary="[ADMIN] Gỡ tin (RESOLVED) hoặc Bỏ qua (REJECTED)",
)
def admin_resolve_report(
    report_id: int,
    data: ReportActionIn,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    """Admin xử lý báo cáo: RESOLVED → ẩn tin (HIDDEN); REJECTED → bỏ qua.
    Body: { "status": "RESOLVED"|"REJECTED", "resolution_result": "..." }
    """
    from app.crud.report import resolve_report as _resolve_report

    new_status = ReportStatus(data.status)

    report, job_hidden = _resolve_report(
        db,
        report_id,
        admin_id=admin.id,
        new_status=new_status,
        resolution_result=data.resolution_result,
    )

    job = db.get(Job, report.post_id)
    job_title = job.title if job else "tin tuyển dụng"
    outcome = (
        "được xác nhận vi phạm; tin đã bị ẩn (HIDDEN)"
        if new_status == ReportStatus.RESOLVED
        else "đã được xem xét và không gỡ tin"
    )
    create_notification(
        db,
        user_id=report.employer_id,
        actor_id=admin.id,
        type=NotificationType.SYSTEM,
        title="Kết quả xử lý báo cáo tin tuyển dụng",
        message=(
            f"Báo cáo #{report.id} về tin '{job_title}' {outcome}. "
            f"Kết quả: {report.resolution_result}"
        ),
        link="/pages/employer/jobs.html",
        ref_type="report",
        ref_id=report.id,
        payload_json={"report_status": report.status.value},
        dedupe_key=f"report:{report.id}:moderated",
        commit=False,
    )
    db.commit()
    db.refresh(report)

    action = "resolved" if new_status == ReportStatus.RESOLVED else "rejected"
    return AdminReportActionOut(
        id=report.id,
        action=action,
        message=f"Đã {action} báo cáo #{report.id} thành công.",
        job_hidden=job_hidden,
    )
