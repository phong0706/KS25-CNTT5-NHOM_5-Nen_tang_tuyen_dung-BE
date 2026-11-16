"""API upload và quản lý CV của ứng viên.

    POST   /api/cvs/upload         Upload CV mới (PDF/DOC/DOCX, tối đa 5MB)
    GET    /api/cvs                Danh sách CV của ứng viên hiện tại
    PUT    /api/cvs/{cv_id}/default   Đặt CV làm mặc định
    DELETE /api/cvs/{cv_id}        Xóa CV (chỉ được xóa CV chưa dùng để nộp đơn)
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.crud import cv as cv_crud
from app.db.session import get_db
from app.models.candidate import CandidateProfile, Cv
from app.schemas.candidate_schema import CvCreate, CvOut
from app.utils.file_validator import FileValidator

router = APIRouter(prefix="/cvs", tags=["CV Management"])


# ============================================================================
# Dependencies
# ============================================================================


def get_current_profile_id(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int:
    """Lấy candidate_profile_id của user hiện tại từ JWT token.
    
    Chỉ cho phép user có role 'candidate' truy cập.
    """
    from app.core.security import role_required  # noqa: PLC0415
    
    # Kiểm tra role
    if current_user.role != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chức năng này chỉ dành cho ứng viên",
        )
    
    # Lấy CandidateProfile từ user_id
    profile = db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)
    )
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hồ sơ ứng viên không tồn tại. Vui lòng tạo hồ sơ trước.",
        )
    
    return profile.id


def get_profile_or_404(
    profile_id: int = Depends(get_current_profile_id),
    db: Session = Depends(get_db),
) -> CandidateProfile:
    """Lấy CandidateProfile hoặc trả 404."""
    profile = db.get(CandidateProfile, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hồ sơ ứng viên không tồn tại",
        )
    return profile


def get_cv_or_404(cv_id: int, db: Session = Depends(get_db)) -> Cv:
    """Lấy CV hoặc trả 404."""
    cv = cv_crud.get_cv_by_id(db, cv_id)
    if not cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy CV id={cv_id}",
        )
    return cv


def verify_cv_ownership(
    cv: Cv = Depends(get_cv_or_404),
    profile: CandidateProfile = Depends(get_profile_or_404),
) -> Cv:
    """Kiểm tra CV có thuộc về profile hiện tại không."""
    if cv.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập CV này",
        )
    return cv


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/upload", response_model=CvOut, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: UploadFile = File(..., description="File CV (PDF/DOC/DOCX, tối đa 5MB)"),
    profile: CandidateProfile = Depends(get_profile_or_404),
    db: Session = Depends(get_db),
):
    """
    Upload CV mới cho ứng viên.

    - Chỉ chấp nhận PDF, DOC, DOCX
    - Tối đa 5MB
    - Mỗi ứng viên tối đa 3 CV
    - Kiểm tra MIME type thực tế (không chỉ đuôi file)
    - File được đổi tên bằng UUID để bảo mật
    """
    # 1. Kiểm tra số lượng CV hiện có
    current_cv_count = cv_crud.count_cvs_by_profile(db, profile.id)
    if current_cv_count >= settings.CV_MAX_FILES_PER_CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bạn đã tải lên tối đa {settings.CV_MAX_FILES_PER_CANDIDATE} CV. Vui lòng xóa CV cũ trước khi tải lên CV mới.",
        )

    # 2. Validate file (MIME type, kích thước)
    max_size_bytes = settings.CV_MAX_SIZE_MB * 1024 * 1024
    file_info = FileValidator.validate_cv_file(file, max_size_bytes)

    # 3. Tạo tên file UUID
    stored_name = str(uuid.uuid4())

    # 4. Lưu file vào thư mục storage
    upload_dir = FileValidator.ensure_upload_dir(settings.CV_UPLOAD_DIR)
    file_path = upload_dir / f"{stored_name}{file_info['extension']}"

    try:
        # Ghi file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 5. Nếu đây là CV đầu tiên, tự động đặt làm default
        is_default = current_cv_count == 0

        # 6. Lưu thông tin vào database
        cv_data = CvCreate(
            original_name=file_info["original_name"],
            file_size=file_info["file_size"],
            mime_type=file_info["mime_type"],
            is_default=is_default,
        )

        cv = cv_crud.create_cv(
            db=db,
            profile_id=profile.id,
            data=cv_data,
            stored_name=stored_name,
        )

        return cv

    except Exception as e:
        # Nếu có lỗi, xóa file đã lưu
        FileValidator.safe_delete_file(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lưu file: {str(e)}",
        )


@router.get("", response_model=list[CvOut])
def list_cvs(
    profile: CandidateProfile = Depends(get_profile_or_404),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách CV của ứng viên hiện tại.

    Sắp xếp theo thời gian upload (mới nhất trước).
    """
    return cv_crud.get_cvs_by_profile(db, profile.id)


@router.put("/{cv_id}/default", response_model=CvOut)
def set_default_cv(
    cv: Cv = Depends(verify_cv_ownership),
    profile: CandidateProfile = Depends(get_profile_or_404),
    db: Session = Depends(get_db),
):
    """
    Đặt CV làm mặc định.

    CV mặc định sẽ được dùng khi ứng viên nộp đơn (nếu không chọn CV khác).
    """
    updated_cv = cv_crud.set_default_cv(db, profile.id, cv.id)
    if not updated_cv:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể cập nhật CV mặc định",
        )
    return updated_cv


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cv(
    cv: Cv = Depends(verify_cv_ownership),
    db: Session = Depends(get_db),
):
    """
    Xóa CV.

    - Chỉ được xóa CV chưa dùng để nộp đơn
    - File trên server cũng sẽ bị xóa
    """
    # Kiểm tra CV đã được dùng để nộp đơn chưa
    if cv_crud.check_cv_used_in_applications(db, cv.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa CV đã được sử dụng để nộp đơn ứng tuyển",
        )

    # Xóa file trên server
    upload_dir = Path(settings.CV_UPLOAD_DIR)
    # Tìm file với stored_name (có thể có các extension khác nhau)
    for file_path in upload_dir.glob(f"{cv.stored_name}.*"):
        FileValidator.safe_delete_file(file_path)

    # Xóa record trong database
    cv_crud.delete_cv(db, cv)

