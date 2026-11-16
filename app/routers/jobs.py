"""API quản lý Tin tuyển dụng (Jobs) và Lưu tin tuyển dụng (Saved Jobs).

Hỗ trợ:
- Tìm kiếm & lọc việc làm nâng cao có phân trang (khách chưa đăng nhập vẫn dùng được):
  GET /api/jobs/search (trả về dữ liệu phân trang: items, total, page, page_size, total_pages)
  GET /api/jobs        (trả về danh sách tin khớp bộ lọc, tương thích với script test)
  GET /api/jobs/{id}   (xem chi tiết 1 tin tuyển dụng)
- Đăng tin / sửa tin / đổi trạng thái tin (cho employer và admin):
  POST  /api/v1/jobs & POST  /api/jobs
  PUT   /api/v1/jobs/{job_id} & PUT   /api/jobs/{job_id}
  PATCH /api/v1/jobs/{job_id}/status & PATCH /api/jobs/{job_id}/status
- Lưu tin / xem danh sách tin đã lưu / bỏ lưu tin (cho ứng viên):
  POST   /api/saved-jobs
  GET    /api/me/saved-jobs
  GET    /api/candidates/{candidate_profile_id}/saved-jobs
  DELETE /api/candidates/{candidate_profile_id}/saved-jobs/{job_id}
  DELETE /api/saved-jobs/{job_id}
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, get_optional_user
from app.crud import job as job_crud
from app.crud import saved_job as saved_job_crud
from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobMutationResponse,
    JobOut,
    JobSearchOut,
    JobSearchPageOut,
    JobSortBy,
    JobStatusUpdate,
    JobType,
    JobUpdate,
    SavedJobDetailOut,
)
from app.schemas.saved_job import SavedJobCreate, SavedJobOut

router = APIRouter(tags=["Jobs"])


# ============================================================================
# Helpers
# ============================================================================


def _get_candidate_profile_id_if_any(
    db: Session, current_user: User | None
) -> int | None:
    """Lấy candidate_profile_id của user đang đăng nhập (nếu có), trả None nếu là khách."""
    if current_user is None:
        return None
    profile = db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)
    )
    return profile.id if profile else None


def _resolve_candidate_profile_for_action(
    db: Session,
    current_user: User | None,
    explicit_profile_id: int | None = None,
) -> int:
    """Xác định và kiểm tra quyền sở hữu candidate_profile_id khi thao tác lưu/xóa tin đã lưu."""
    if current_user is not None:
        if current_user.role not in {"candidate", "admin"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chức năng lưu tin tuyển dụng chỉ dành cho ứng viên",
            )
        profile = db.scalar(
            select(CandidateProfile).where(
                CandidateProfile.user_id == current_user.id
            )
        )
        if current_user.role == "admin" and explicit_profile_id is not None:
            return explicit_profile_id
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bạn chưa có hồ sơ ứng viên. Vui lòng tạo hồ sơ trước khi lưu tin.",
            )
        if explicit_profile_id is not None and explicit_profile_id != profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thao tác trên danh sách tin đã lưu của ứng viên khác",
            )
        return profile.id

    if explicit_profile_id is not None:
        return explicit_profile_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Vui lòng đăng nhập hoặc cung cấp candidate_profile_id hợp lệ",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ============================================================================
# Job Search & Public Listing (Khách chưa đăng nhập vẫn dùng được)
# ============================================================================


@router.get(
    "/jobs/search",
    response_model=JobSearchPageOut,
    summary="Tìm kiếm và lọc việc làm nâng cao (có phân trang, khách dùng được)",
)
def search_jobs(
    keyword: str | None = Query(
        default=None,
        description="Từ khóa tìm theo tiêu đề việc làm, tên công ty hoặc kỹ năng",
    ),
    q: str | None = Query(
        default=None,
        description="Bí danh (alias) của keyword",
    ),
    industry_id: int | None = Query(
        default=None, gt=0, description="Lọc theo ID ngành nghề"
    ),
    location_id: int | None = Query(
        default=None, gt=0, description="Lọc theo ID địa điểm"
    ),
    skill_id: int | None = Query(
        default=None, gt=0, description="Lọc theo ID kỹ năng"
    ),
    salary_min: Decimal | None = Query(
        default=None, ge=0, description="Mức lương tối thiểu mong muốn (VNĐ)"
    ),
    salary_max: Decimal | None = Query(
        default=None, ge=0, description="Mức lương tối đa mong muốn (VNĐ)"
    ),
    job_type: JobType | None = Query(
        default=None,
        description="Hình thức làm việc: FULLTIME, PARTTIME, INTERN, REMOTE",
    ),
    experience_level: str | None = Query(
        default=None,
        description="Kinh nghiệm yêu cầu (vd: Chưa có kinh nghiệm, Junior, Middle, Senior)",
    ),
    sort_by: JobSortBy = Query(
        default="newest",
        description="Sắp xếp theo: newest (mới nhất), salary_desc (lương cao), salary_asc (lương thấp)",
    ),
    page: int = Query(default=1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(
        default=10, ge=1, le=100, description="Số lượng tin trên mỗi trang (tối đa 100)"
    ),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Tìm kiếm việc làm công khai (chỉ lấy tin OPEN và còn hạn nộp).

    - **Khách chưa đăng nhập** sử dụng bình thường (`is_saved = False`).
    - **Ứng viên đã đăng nhập** (gửi kèm Bearer token) sẽ thấy thêm cờ `is_saved = True/False` trên từng tin.
    """
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="salary_min không được lớn hơn salary_max",
        )

    effective_keyword = keyword if keyword is not None else q
    candidate_profile_id = _get_candidate_profile_id_if_any(db, current_user)

    return job_crud.search_jobs(
        db=db,
        keyword=effective_keyword,
        industry_id=industry_id,
        location_id=location_id,
        skill_id=skill_id,
        salary_min=salary_min,
        salary_max=salary_max,
        job_type=job_type,
        experience_level=experience_level,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
        candidate_profile_id=candidate_profile_id,
    )


@router.get(
    "/jobs",
    response_model=list[JobSearchOut],
    summary="Danh sách việc làm đang mở (tương thích với FE & script test)",
)
def list_open_jobs(
    keyword: str | None = Query(default=None),
    q: str | None = Query(default=None),
    industry_id: int | None = Query(default=None, gt=0),
    location_id: int | None = Query(default=None, gt=0),
    skill_id: int | None = Query(default=None, gt=0),
    salary_min: Decimal | None = Query(default=None, ge=0),
    salary_max: Decimal | None = Query(default=None, ge=0),
    job_type: JobType | None = Query(default=None),
    experience_level: str | None = Query(default=None),
    sort_by: JobSortBy = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Trả về mảng các tin tuyển dụng OPEN còn hạn theo bộ lọc."""
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="salary_min không được lớn hơn salary_max",
        )

    effective_keyword = keyword if keyword is not None else q
    candidate_profile_id = _get_candidate_profile_id_if_any(db, current_user)

    result = job_crud.search_jobs(
        db=db,
        keyword=effective_keyword,
        industry_id=industry_id,
        location_id=location_id,
        skill_id=skill_id,
        salary_min=salary_min,
        salary_max=salary_max,
        job_type=job_type,
        experience_level=experience_level,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
        candidate_profile_id=candidate_profile_id,
    )
    return result["items"]


@router.get(
    "/jobs/{job_id}",
    response_model=JobOut,
    summary="Xem chi tiết 1 tin tuyển dụng",
)
def get_job_detail(
    job_id: int,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Xem chi tiết 1 tin tuyển dụng.

    - Khách / ứng viên: chỉ xem được tin đang ở trạng thái OPEN (và tăng lượt xem views_count).
    - Chủ tin (employer) hoặc admin: xem được cả tin ở trạng thái DRAFT / PENDING / HIDDEN / CLOSED.
    """
    job_obj = db.get(Job, job_id)
    if job_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tin tuyển dụng id={job_id}",
        )

    is_privileged = current_user is not None and (
        current_user.role == "admin" or current_user.id == job_obj.posted_by
    )
    if not is_privileged and job_obj.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tin tuyển dụng không tồn tại hoặc đã ngừng nhận hồ sơ",
        )

    if not is_privileged:
        job_obj.views_count = (job_obj.views_count or 0) + 1
        db.commit()
        db.refresh(job_obj)

    return job_crud.get_job_by_id(db, job_id)


# ============================================================================
# Job Create / Update / Status Mutation (Hỗ trợ cả /v1/jobs và /jobs)
# ============================================================================


@router.post(
    "/v1/jobs",
    response_model=JobMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng tin tuyển dụng mới (v1)",
)
@router.post(
    "/jobs",
    response_model=JobMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng tin tuyển dụng mới",
)
def create_job(
    data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"employer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chức năng này chỉ dành cho nhà tuyển dụng",
        )
    job = job_crud.create_job(
        db, current_user.id, data, is_admin=current_user.role == "admin"
    )
    return {
        "statusCode": 201,
        "message": "Tạo tin tuyển dụng thành công",
        "data": job,
    }


@router.put(
    "/v1/jobs/{job_id}",
    response_model=JobMutationResponse,
    summary="Cập nhật tin tuyển dụng (v1)",
)
@router.put(
    "/jobs/{job_id}",
    response_model=JobMutationResponse,
    summary="Cập nhật tin tuyển dụng",
)
def update_job(
    job_id: int,
    data: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "employer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ nhà tuyển dụng sở hữu tin mới được chỉnh sửa",
        )
    job = job_crud.update_job(db, job_id, current_user.id, data)
    return {
        "statusCode": 200,
        "message": "Cập nhật tin tuyển dụng thành công",
        "data": job,
    }


@router.patch(
    "/v1/jobs/{job_id}/status",
    response_model=JobMutationResponse,
    summary="Đổi trạng thái tin tuyển dụng (v1)",
)
@router.patch(
    "/jobs/{job_id}/status",
    response_model=JobMutationResponse,
    summary="Đổi trạng thái tin tuyển dụng",
)
def update_job_status(
    job_id: int,
    data: JobStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"employer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chức năng này chỉ dành cho nhà tuyển dụng hoặc quản trị viên",
        )
    if current_user.role == "employer" and data.status not in {
        "PENDING",
        "OPEN",
        "HIDDEN",
        "CLOSED",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trạng thái này chỉ quản trị viên được thiết lập",
        )
    job = job_crud.change_job_status(
        db,
        job_id,
        current_user.id,
        data.status,
        is_admin=current_user.role == "admin",
    )
    return {
        "statusCode": 200,
        "message": "Cập nhật trạng thái tin tuyển dụng thành công",
        "data": job,
    }


# ============================================================================
# Saved Jobs Endpoints (Lưu / Danh sách / Bỏ lưu tin tuyển dụng)
# ============================================================================


@router.post(
    "/saved-jobs",
    response_model=SavedJobOut,
    status_code=status.HTTP_201_CREATED,
    summary="Lưu tin tuyển dụng yêu thích",
)
def create_saved_job(
    data: SavedJobCreate,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Lưu tin tuyển dụng cho ứng viên.

    - Nếu đã đăng nhập (có Bearer token): tự động lấy `candidate_profile_id` từ tài khoản ứng viên.
    - Nếu truyền `candidate_profile_id` trong body: kiểm tra quyền sở hữu khi có token.
    - Chỉ cho phép lưu tin `OPEN` còn hạn và chặn lưu trùng (`409 Conflict`).
    """
    profile_id = _resolve_candidate_profile_for_action(
        db, current_user, data.candidate_profile_id
    )
    return saved_job_crud.save_job(db, profile_id, data.job_id)


@router.get(
    "/me/saved-jobs",
    response_model=list[SavedJobDetailOut],
    summary="Xem danh sách tin đã lưu của ứng viên đang đăng nhập",
)
def list_my_saved_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lấy danh sách tin đã lưu của ứng viên hiện tại (dựa trên JWT token)."""
    profile_id = _resolve_candidate_profile_for_action(db, current_user)
    return saved_job_crud.get_saved_jobs(db, profile_id)


@router.get(
    "/candidates/{candidate_profile_id}/saved-jobs",
    response_model=list[SavedJobDetailOut],
    summary="Xem danh sách tin đã lưu theo candidate_profile_id",
)
def list_saved_jobs(
    candidate_profile_id: int,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    profile_id = _resolve_candidate_profile_for_action(
        db, current_user, candidate_profile_id
    )
    return saved_job_crud.get_saved_jobs(db, profile_id)


@router.delete(
    "/me/saved-jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bỏ lưu tin tuyển dụng của ứng viên đang đăng nhập",
)
def remove_my_saved_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_id = _resolve_candidate_profile_for_action(db, current_user)
    deleted = saved_job_crud.delete_saved_job(db, profile_id, job_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin đã lưu"
        )


@router.delete(
    "/candidates/{candidate_profile_id}/saved-jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bỏ lưu tin tuyển dụng theo candidate_profile_id",
)
def remove_saved_job(
    candidate_profile_id: int,
    job_id: int,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    profile_id = _resolve_candidate_profile_for_action(
        db, current_user, candidate_profile_id
    )
    deleted = saved_job_crud.delete_saved_job(db, profile_id, job_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin đã lưu"
        )
