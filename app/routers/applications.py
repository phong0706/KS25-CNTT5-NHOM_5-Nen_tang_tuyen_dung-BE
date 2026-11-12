"""API quản lý đơn ứng tuyển (Applications).

    POST /api/applications          Nộp đơn ứng tuyển (candidate only)
    GET  /api/applications          Lấy danh sách đơn của ứng viên hiện tại
    GET  /api/applications/{id}     Xem chi tiết đơn ứng tuyển
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_user, role_required
from app.crud import application as application_crud
from app.crud import notification as notification_crud
from app.db.session import get_db
from app.models.application import Application
from app.models.candidate import CandidateProfile, Cv
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.schemas.application_schema import ApplicationCreate, ApplicationOut

router = APIRouter(prefix="/applications", tags=["Applications"])


# ============================================================================
# Helper Functions
# ============================================================================


def get_candidate_profile(db: Session, user_id: int) -> CandidateProfile:
    """Lấy CandidateProfile từ user_id hoặc raise 404."""
    profile = db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hồ sơ ứng viên không tồn tại. Vui lòng tạo hồ sơ trước khi nộp đơn.",
        )
    return profile


def validate_cv_ownership(db: Session, cv_id: int, profile_id: int) -> Cv:
    """Kiểm tra CV có thuộc về ứng viên hay không."""
    cv = db.get(Cv, cv_id)
    if not cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy CV với id={cv_id}",
        )
    
    if cv.profile_id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CV này không thuộc về bạn. Bạn chỉ có thể sử dụng CV của chính mình để nộp đơn.",
        )
    
    return cv


def validate_job_availability(db: Session, job_id: int) -> Job:
    """Kiểm tra tin tuyển dụng có tồn tại, OPEN và còn hạn nộp không."""
    job = db.get(Job, job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tin tuyển dụng với id={job_id}",
        )
    
    if job.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tin tuyển dụng này đã đóng (trạng thái: {job.status}). Bạn không thể nộp đơn.",
        )
    
    # Kiểm tra deadline
    if job.deadline < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tin tuyển dụng này đã hết hạn nộp (deadline: {job.deadline.strftime('%d/%m/%Y %H:%M')})",
        )
    
    return job


def get_employer_user_id(db: Session, job: Job) -> int:
    """Lấy user_id của nhà tuyển dụng từ job (qua company.employer_id)."""
    company = db.get(Company, job.company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không tìm thấy thông tin công ty của tin tuyển dụng này.",
        )
    return company.employer_id


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def submit_application(
    data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Nộp đơn ứng tuyển vào tin tuyển dụng.
    
    Yêu cầu:
    - Chỉ ứng viên (role=candidate) mới được nộp đơn
    - CV phải thuộc về ứng viên hiện tại
    - Tin tuyển dụng phải OPEN và còn hạn nộp
    - Không được nộp trùng (UNIQUE constraint: candidate_profile_id + job_id)
    
    Sau khi nộp thành công:
    - Tạo đơn ứng tuyển với trạng thái SUBMITTED
    - Ghi lịch sử trạng thái
    - Gửi thông báo cho nhà tuyển dụng
    
    Returns:
        ApplicationOut: Thông tin đơn ứng tuyển vừa tạo
        
    Raises:
        400: Tin đã đóng hoặc hết hạn
        403: CV không thuộc về ứng viên
        404: Không tìm thấy hồ sơ, CV hoặc tin tuyển dụng
        409: Đã nộp đơn trước đó (duplicate)
    """
    # 1. Lấy CandidateProfile của ứng viên hiện tại
    profile = get_candidate_profile(db, current_user.id)
    
    # 2. Kiểm tra CV (nếu có) thuộc về ứng viên
    if data.cv_id is not None:
        validate_cv_ownership(db, data.cv_id, profile.id)
    
    # 3. Kiểm tra tin tuyển dụng (tồn tại, OPEN, còn hạn)
    job = validate_job_availability(db, data.job_id)
    
    # 4. Kiểm tra đã nộp đơn chưa (trước khi tạo để tránh race condition)
    existing_app = application_crud.check_duplicate_application(
        db, profile.id, data.job_id
    )
    if existing_app:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bạn đã nộp đơn ứng tuyển vào tin này trước đó (lúc {existing_app.created_at.strftime('%d/%m/%Y %H:%M')}). "
                   "Mỗi ứng viên chỉ được nộp một đơn cho mỗi tin tuyển dụng.",
        )
    
    # 5. Tạo đơn ứng tuyển (có IntegrityError protection cho race condition)
    try:
        application = application_crud.create_application(
            db=db,
            candidate_profile_id=profile.id,
            data=data,
        )
    except IntegrityError:
        # Race condition: 2 requests cùng lúc đều pass check ở bước 4
        # nhưng một trong hai sẽ vi phạm UNIQUE constraint khi INSERT
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã nộp đơn ứng tuyển vào tin này. Mỗi ứng viên chỉ được nộp một đơn cho mỗi tin tuyển dụng.",
        )
    
    # 6. Gửi thông báo cho nhà tuyển dụng
    try:
        employer_user_id = get_employer_user_id(db, job)
        notification_crud.notify_new_application(
            db=db,
            employer_user_id=employer_user_id,
            job_title=job.title,
            candidate_name=current_user.full_name,
            application_id=application.id,
        )
    except Exception as e:
        # Thông báo thất bại không nên làm thất bại toàn bộ request
        # Log lỗi nhưng vẫn trả về đơn ứng tuyển đã tạo thành công
        print(f"[WARNING] Không thể gửi thông báo: {str(e)}")
    
    return application


@router.get("", response_model=list[ApplicationOut])
def list_my_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Lấy danh sách đơn ứng tuyển của ứng viên hiện tại.
    
    Chỉ ứng viên (role=candidate) mới được xem danh sách đơn của mình.
    Sắp xếp theo thời gian nộp (mới nhất trước).
    """
    profile = get_candidate_profile(db, current_user.id)
    applications = application_crud.get_applications_by_candidate(db, profile.id)
    return applications


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application_detail(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem chi tiết đơn ứng tuyển.
    
    Quyền truy cập:
    - Ứng viên: chỉ xem đơn của mình
    - Nhà tuyển dụng: xem đơn ứng tuyển vào tin của mình
    - Admin: xem tất cả
    """
    application = application_crud.get_application_by_id(db, application_id)
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đơn ứng tuyển với id={application_id}",
        )
    
    # Kiểm tra quyền truy cập
    if current_user.role == "admin":
        # Admin xem tất cả
        pass
    elif current_user.role == "candidate":
        # Ứng viên chỉ xem đơn của mình
        profile = get_candidate_profile(db, current_user.id)
        if application.candidate_profile_id != profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem đơn ứng tuyển của người khác.",
            )
    elif current_user.role == "employer":
        # Nhà tuyển dụng xem đơn vào tin của mình
        job = db.get(Job, application.job_id)
        if job:
            company = db.get(Company, job.company_id)
            if not company or company.employer_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn chỉ có thể xem đơn ứng tuyển vào tin tuyển dụng của công ty mình.",
                )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập.",
        )
    
    return application


