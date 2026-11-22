"""Router quản lý tin tuyển dụng của nhà tuyển dụng."""
from datetime import date, datetime, timezone
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.company import Company, CompanyStatus
from app.models.application import Application
from app.models.job import Job
from app.models.user import User
from app.schemas.job import (
    AllowedActionOut,
    BulkJobActionIn,
    BulkJobActionOut,
    EmployerJobsListOut,
    JobActionResultOut,
    JobDeleteOut,
    JobDetailOut,
    JobDuplicateOut,
    JobListItemOut,
    JobPaginationOut,
    JobPayloadIn,
    JobStatusPatchIn,
    JobTabOut,
)
from app.services.company_verification_actions import enforce_company_job_rule
from app.services.notification import (
    notify_company_followers_about_job,
    notify_job_status_changed,
)

router = APIRouter(prefix="/employer/jobs", tags=["Employer Jobs"])

PAGE_SIZE = 10

STATUS_META: dict[str, tuple[str, str]] = {
    "draft": ("Bản nháp", "neutral"),
    "pending": ("Chờ duyệt", "warning"),
    "reverify_pending": ("Chờ xác minh lại", "warning"),
    "published": ("Đang tuyển", "success"),
    "open": ("Đang tuyển", "success"),
    "hidden": ("Đang ẩn", "muted"),
    "closed": ("Đã đóng", "danger"),
    "rejected": ("Bị xóa", "danger"),
    "deleted": ("Bị xóa", "danger"),
}

ACTION_DEFS: dict[str, tuple[str, str]] = {
    "edit": ("Sửa", "default"),
    "submit": ("Đăng tin", "primary"),
    "hide": ("Ẩn", "default"),
    "close": ("Đóng", "danger"),
    "reopen": ("Mở lại", "primary"),
    "withdraw": ("Thu hồi", "default"),
    "duplicate": ("Nhân bản", "default"),
    "delete": ("Xóa", "danger"),
}

ALLOWED_ACTIONS_BY_STATUS: dict[str, list[str]] = {
    "draft": ["edit", "submit", "duplicate", "delete"],
    "pending": ["edit", "withdraw", "duplicate", "delete"],
    "reverify_pending": ["edit", "close", "delete"],
    "published": ["edit", "hide", "close", "duplicate", "delete"],
    "open": ["edit", "hide", "close", "duplicate", "delete"],
    "hidden": ["edit", "reopen", "close", "duplicate", "delete"],
    "closed": ["edit", "reopen", "duplicate", "delete"],
    "rejected": ["delete"],
    "deleted": [],
}

TAB_DEFS: list[tuple[str, str]] = [
    ("all", "Tất cả"),
    ("draft", "Nháp"),
    ("pending", "Chờ duyệt"),
    ("reverify_pending", "Chờ xác minh lại"),
    ("published", "Đang tuyển"),
    ("closed", "Đã đóng"),
]


def _build_allowed_actions(job_status: str) -> list[AllowedActionOut]:
    keys = ALLOWED_ACTIONS_BY_STATUS.get(job_status, ["edit", "duplicate"])
    return [
        AllowedActionOut(
            key=k,
            label=ACTION_DEFS[k][0],
            tone=ACTION_DEFS[k][1],
        )
        for k in keys
    ]


@router.get("", response_model=EmployerJobsListOut, summary="Danh sách tin của nhà tuyển dụng")
def list_employer_jobs(
    status: str = Query("", description="all|draft|pending|published|hidden|closed"),
    q: str = Query("", max_length=120),
    sort: str = Query("newest", description="newest|most_applicants|expiring_soon"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    # 1. Đếm số lượng theo từng trạng thái bằng GROUP BY
    count_rows = db.execute(
        select(Job.status, func.count(Job.id))
        .where(Job.employer_id == current_user.id, Job.deleted_at.is_(None))
        .group_by(Job.status)
    ).all()

    counts: dict[str, int] = {
        "all": 0,
        "draft": 0,
        "pending": 0,
        "reverify_pending": 0,
        "published": 0,
        "hidden": 0,
        "closed": 0,
    }
    for st, cnt in count_rows:
        counts[st] = int(cnt)
        counts["all"] += int(cnt)

    tabs = [
        JobTabOut(key=key, label=label, count=counts.get(key, 0))
        for key, label in TAB_DEFS
    ]

    # 2. Subquery đếm hồ sơ & hồ sơ mới theo job_id bằng GROUP BY / COUNT
    app_stats_subq = (
        select(
            Application.job_id.label("job_id"),
            func.count(Application.id).label("applicants_count"),
            func.coalesce(
                func.sum(case((Application.viewed_at.is_(None), 1), else_=0)),
                0,
            ).label("new_applicants_count"),
        )
        .group_by(Application.job_id)
        .subquery()
    )

    applicants_col = func.coalesce(app_stats_subq.c.applicants_count, 0)
    new_applicants_col = func.coalesce(app_stats_subq.c.new_applicants_count, 0)

    # 3. Bộ lọc truy vấn danh sách
    filters = [Job.employer_id == current_user.id, Job.deleted_at.is_(None)]
    normalized_status = status.strip().lower()
    if normalized_status and normalized_status != "all":
        filters.append(Job.status == normalized_status)

    keyword = q.strip()
    if keyword:
        filters.append(Job.title.ilike(f"%{keyword}%"))

    total_items = int(
        db.scalar(select(func.count(Job.id)).where(*filters)) or 0
    )
    total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
    safe_page = min(page, total_pages)
    offset = (safe_page - 1) * PAGE_SIZE

    # 4. Sắp xếp
    if sort == "most_applicants":
        order_clauses = [applicants_col.desc(), Job.created_at.desc(), Job.id.desc()]
    elif sort == "expiring_soon":
        order_clauses = [
            case((Job.deadline.is_(None), 1), else_=0).asc(),
            Job.deadline.asc(),
            Job.id.desc(),
        ]
    else:
        order_clauses = [Job.created_at.desc(), Job.id.desc()]

    stmt = (
        select(
            Job,
            applicants_col.label("applicants_count"),
            new_applicants_col.label("new_applicants_count"),
        )
        .outerjoin(app_stats_subq, Job.id == app_stats_subq.c.job_id)
        .where(*filters)
        .order_by(*order_clauses)
        .offset(offset)
        .limit(PAGE_SIZE)
    )

    rows = db.execute(stmt).all()
    job_ids = [job.id for job, _, _ in rows]
    application_statuses = {
        job_id: {
            "SUBMITTED": 0,
            "REVIEWING": 0,
            "INTERVIEW": 0,
            "OFFERED": 0,
            "REJECTED": 0,
            "WITHDRAWN": 0,
        }
        for job_id in job_ids
    }
    if job_ids:
        status_rows = db.execute(
            select(Application.job_id, func.upper(Application.status), func.count(Application.id))
            .where(Application.job_id.in_(job_ids))
            .group_by(Application.job_id, func.upper(Application.status))
        ).all()
        for job_id, application_status, count in status_rows:
            if application_status in application_statuses[job_id]:
                application_statuses[job_id][application_status] = int(count)

    items: list[JobListItemOut] = []
    for job, app_cnt, new_cnt in rows:
        st_label, st_tone = STATUS_META.get(job.status, (job.status, "neutral"))
        items.append(
            JobListItemOut(
                id=job.id,
                title=job.title,
                level=job.level,
                work_type=job.work_type,
                location=job.location,
                quantity=job.quantity,
                deadline=job.deadline,
                status=job.status,
                status_label=st_label,
                status_tone=st_tone,
                applicants_count=int(app_cnt or 0),
                new_applicants_count=int(new_cnt or 0),
                application_counts=application_statuses[job.id],
                views_count=job.views_count,
                published_at=job.published_at,
                created_at=job.created_at,
                updated_at=job.updated_at,
                allowed_actions=_build_allowed_actions(job.status),
            )
        )

    return EmployerJobsListOut(
        items=items,
        tabs=tabs,
        counts=counts,
        pagination=JobPaginationOut(
            page=safe_page,
            page_size=PAGE_SIZE,
            total_items=total_items,
            total_pages=total_pages,
        ),
        server_time=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Helpers & State Transitions
# ---------------------------------------------------------------------------

TRANSITIONS: dict[str, tuple[set[str], str, str | None, str]] = {
    # action: (allowed_from_statuses, next_status, undo_action, message)
    "submit": ({"draft"}, "pending", None, "Đã gửi tin chờ duyệt"),
    "withdraw": ({"pending"}, "draft", None, "Đã thu hồi tin về nháp"),
    "hide": ({"published"}, "hidden", "reopen", "Đã ẩn tin tuyển dụng"),
    "close": ({"published", "hidden"}, "closed", "reopen", "Đã đóng tin tuyển dụng"),
    "reopen": ({"hidden", "closed"}, "published", None, "Đã mở lại tin tuyển dụng"),
}


def _get_owned_job(db: Session, job_id: int, employer_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job or job.deleted_at is not None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tin tuyển dụng",
        )
    if job.employer_id != employer_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thao tác trên tin tuyển dụng này",
        )
    return job


@router.patch("/{job_id}/status", response_model=JobActionResultOut, summary="Chuyển trạng thái tin")
def patch_job_status(
    job_id: int,
    body: JobStatusPatchIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    action = body.action.strip().lower()
    if action not in TRANSITIONS:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Hành động chuyển trạng thái không hợp lệ",
        )

    job = _get_owned_job(db, job_id, current_user.id)
    allowed_from, next_status, undo_action, message = TRANSITIONS[action]
    if action in ("submit", "reopen"):
        enforce_company_job_rule(db, current_user.id, next_status, is_creating=False, existing_job=job)
    if job.status not in allowed_from:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Không thể thực hiện thao tác '{action}' khi tin đang ở trạng thái '{job.status}'",
        )
    if next_status in ("pending", "published"):
        company = db.scalar(select(Company).where(Company.employer_id == current_user.id))
        if company is None or company.status != CompanyStatus.VERIFIED:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Công ty chưa được xác minh, chỉ được lưu tin nháp",
            )

    # Chỉ trả undo_action nếu tin trước đó đang hiển thị (published) hoặc đóng từ published
    effective_undo = undo_action if (action in ("hide", "close") and job.status == "published") else None
    first_publication = next_status == "published" and job.published_at is None
    job.status = next_status
    if next_status == "published" and job.published_at is None:
        job.published_at = datetime.now(timezone.utc)

    # ── Thông báo cho nhà tuyển dụng: tin đổi trạng thái ──
    # Gọi trước db.commit() để thông báo nằm cùng transaction với thay đổi trạng thái.
    st_label, st_tone = STATUS_META.get(next_status, (next_status, "neutral"))
    notify_job_status_changed(
        db,
        employer_id=current_user.id,
        job_id=job.id,
        job_title=job.title,
        status=next_status,
        status_label=st_label,
        actor_id=current_user.id,
    )
    if first_publication and job.company_id is not None:
        notify_company_followers_about_job(
            db,
            company_id=job.company_id,
            company_name=company.name if company else "Công ty",
            job_id=job.id,
            job_title=job.title,
            actor_id=current_user.id,
        )

    db.commit()
    db.refresh(job)
    st_label, st_tone = STATUS_META.get(job.status, (job.status, "neutral"))
    return JobActionResultOut(
        id=job.id,
        status=job.status,
        status_label=st_label,
        status_tone=st_tone,
        undo_action=effective_undo,
        message=message,
    )


@router.post("/{job_id}/duplicate", response_model=JobDuplicateOut, status_code=http_status.HTTP_201_CREATED, summary="Nhân bản tin tuyển dụng")
def duplicate_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    src = _get_owned_job(db, job_id, current_user.id)
    company = db.scalar(select(Company).where(Company.employer_id == current_user.id).order_by(Company.id.asc()))
    copy_title = f"{src.title} (Bản sao)"[:255]
    new_job = Job(
        employer_id=current_user.id,
        company_id=company.id if company else src.company_id,
        title=copy_title,
        level=src.level,
        work_type=src.work_type,
        location=src.location,
        quantity=src.quantity,
        deadline=src.deadline,
        description=src.description,
        requirements=src.requirements,
        skills=list(src.skills) if src.skills else None,
        salary_min=src.salary_min,
        salary_max=src.salary_max,
        is_salary_negotiable=src.is_salary_negotiable,
        benefits=list(src.benefits) if src.benefits else None,
        status="draft",
        views_count=0,
        published_at=None,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return JobDuplicateOut(
        id=new_job.id,
        title=new_job.title,
        status=new_job.status,
        message="Đã nhân bản tin tuyển dụng thành bản nháp",
    )


@router.delete("/{job_id}", response_model=JobDeleteOut, summary="Xóa tin tuyển dụng của nhà tuyển dụng (xóa mềm)")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    job = _get_owned_job(db, job_id, current_user.id)
    job.deleted_at = datetime.now(timezone.utc)
    job.version += 1
    db.commit()
    return JobDeleteOut(id=job_id, message="Đã xóa tin tuyển dụng")


def _validate_job_payload(body: JobPayloadIn) -> None:
    if body.deadline and body.deadline < date.today():
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hạn nộp hồ sơ không được ở trong quá khứ",
        )
    if not body.is_salary_negotiable and body.salary_min is not None and body.salary_max is not None:
        if body.salary_max < body.salary_min:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Mức lương tối đa phải lớn hơn hoặc bằng mức lương tối thiểu",
            )


def _to_job_detail(db: Session, job: Job) -> JobDetailOut:
    company = db.get(Company, job.company_id) if job.company_id else None
    st_label, st_tone = STATUS_META.get(job.status, (job.status, "neutral"))
    return JobDetailOut(
        id=job.id,
        title=job.title,
        level=job.level,
        work_type=job.work_type,
        location=job.location,
        quantity=job.quantity,
        deadline=job.deadline,
        description=job.description,
        requirements=job.requirements,
        skills=list(job.skills or []),
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        is_salary_negotiable=job.is_salary_negotiable,
        benefits=list(job.benefits or []),
        status=job.status,
        status_label=st_label,
        status_tone=st_tone,
        views_count=job.views_count,
        company_name=company.name if company else None,
        published_at=job.published_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        server_time=datetime.now(timezone.utc),
    )


@router.get("/{job_id}", response_model=JobDetailOut, summary="Chi tiết tin tuyển dụng")
def get_employer_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    job = _get_owned_job(db, job_id, current_user.id)
    return _to_job_detail(db, job)


@router.post("", response_model=JobDetailOut, status_code=http_status.HTTP_201_CREATED, summary="Tạo tin tuyển dụng mới")
def create_employer_job(
    body: JobPayloadIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    _validate_job_payload(body)
    company = enforce_company_job_rule(db, current_user.id, body.status, is_creating=True)
    if company is None:
        company = db.scalar(select(Company).where(Company.employer_id == current_user.id))
    company_verified = (
        company is not None
        and company.status == CompanyStatus.VERIFIED
        and company.verification_status == "da_xac_minh"
    )
    if not company_verified and body.status != "draft":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "COMPANY_NOT_VERIFIED", "message": "Công ty chưa được xác minh nên chỉ có thể lưu nháp tin tuyển dụng."},
        )
    clean_skills = list(dict.fromkeys([s.strip() for s in body.skills if s.strip()]))[:15]
    clean_benefits = [b.strip() for b in body.benefits if b.strip()]

    job = Job(
        employer_id=current_user.id,
        company_id=company.id if company else None,
        title=body.title.strip(),
        level=body.level,
        work_type=body.work_type,
        location=body.location,
        quantity=body.quantity,
        deadline=body.deadline,
        description=body.description,
        requirements=body.requirements,
        skills=clean_skills,
        salary_min=None if body.is_salary_negotiable else body.salary_min,
        salary_max=None if body.is_salary_negotiable else body.salary_max,
        is_salary_negotiable=body.is_salary_negotiable,
        benefits=clean_benefits,
        status=body.status if company_verified else "draft",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _to_job_detail(db, job)


@router.put("/{job_id}", response_model=JobDetailOut, summary="Cập nhật tin tuyển dụng")
def update_employer_job(
    job_id: int,
    body: JobPayloadIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    _validate_job_payload(body)
    job = _get_owned_job(db, job_id, current_user.id)
    company = enforce_company_job_rule(
        db, current_user.id, body.status, is_creating=False, existing_job=job, new_deadline=body.deadline
    )
    if company is None:
        company = db.scalar(select(Company).where(Company.employer_id == current_user.id))
    if (company is None or company.status != CompanyStatus.VERIFIED) and body.status != "draft":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "COMPANY_NOT_VERIFIED", "message": "Công ty chưa được xác minh nên chỉ có thể lưu nháp tin tuyển dụng."},
        )
    clean_skills = list(dict.fromkeys([s.strip() for s in body.skills if s.strip()]))[:15]
    clean_benefits = [b.strip() for b in body.benefits if b.strip()]

    if job.company_id is None and company is not None:
        job.company_id = company.id

    job.title = body.title.strip()
    job.level = body.level
    job.work_type = body.work_type
    job.location = body.location
    job.quantity = body.quantity
    job.deadline = body.deadline
    job.description = body.description
    job.requirements = body.requirements
    job.skills = clean_skills
    job.salary_min = None if body.is_salary_negotiable else body.salary_min
    job.salary_max = None if body.is_salary_negotiable else body.salary_max
    job.is_salary_negotiable = body.is_salary_negotiable
    job.benefits = clean_benefits
    # Cho phép nâng từ draft lên pending; nếu tin đang published/hidden/closed giữ trạng thái hiện tại trừ khi sửa draft
    if (company is None or company.status != CompanyStatus.VERIFIED or company.verification_status != "da_xac_minh") and job.status != "reverify_pending":
        job.status = "draft"
        job.published_at = None
    elif job.status == "draft" and body.status in ("draft", "pending"):
        job.status = body.status

    db.commit()
    db.refresh(job)
    return _to_job_detail(db, job)


@router.post("/bulk", response_model=BulkJobActionOut, summary="Thao tác hàng loạt (Ẩn/Đóng/Xóa)")
def bulk_employer_jobs_action(
    body: BulkJobActionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    jobs = db.scalars(
        select(Job).where(Job.employer_id == current_user.id, Job.id.in_(body.job_ids))
    ).all()

    processed = 0
    skipped = 0
    for job in jobs:
        if body.action == "hide":
            if job.status == "published":
                job.status = "hidden"
                processed += 1
            else:
                skipped += 1
        elif body.action == "close":
            if job.status in ("published", "hidden"):
                job.status = "closed"
                processed += 1
            else:
                skipped += 1
        elif body.action == "delete":
            if job.status in ("draft", "closed"):
                db.delete(job)
                processed += 1
            else:
                skipped += 1

    db.commit()
    action_labels = {"hide": "ẩn", "close": "đóng", "delete": "xóa"}
    label = action_labels.get(body.action, body.action)
    msg = f"Đã {label} {processed} tin tuyển dụng"
    if skipped > 0:
        msg += f" ({skipped} tin bỏ qua do không đúng trạng thái)"
    return BulkJobActionOut(processed=processed, skipped=skipped, message=msg)

