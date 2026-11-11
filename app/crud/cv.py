"""CRUD operations cho CV của ứng viên."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import Cv
from app.schemas.candidate_schema import CvCreate


def get_cvs_by_profile(db: Session, profile_id: int) -> list[Cv]:
    """Lấy danh sách CV của một profile."""
    query = select(Cv).where(Cv.profile_id == profile_id).order_by(Cv.uploaded_at.desc())
    return list(db.scalars(query))


def get_cv_by_id(db: Session, cv_id: int) -> Cv | None:
    """Lấy CV theo ID."""
    return db.get(Cv, cv_id)


def count_cvs_by_profile(db: Session, profile_id: int) -> int:
    """Đếm số lượng CV của một profile."""
    query = select(Cv).where(Cv.profile_id == profile_id)
    return len(list(db.scalars(query)))


def create_cv(db: Session, profile_id: int, data: CvCreate, stored_name: str) -> Cv:
    """
    Tạo bản ghi CV mới.

    Args:
        db: Database session
        profile_id: ID của CandidateProfile
        data: Dữ liệu CV (CvCreate schema)
        stored_name: Tên file được lưu trên server (UUID)

    Returns:
        CV object vừa tạo
    """
    cv = Cv(
        profile_id=profile_id,
        original_name=data.original_name,
        stored_name=stored_name,
        file_size=data.file_size,
        mime_type=data.mime_type,
        is_default=data.is_default,
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


def set_default_cv(db: Session, profile_id: int, cv_id: int) -> Cv | None:
    """
    Đặt CV làm mặc định. Bỏ default của các CV khác cùng profile.

    Args:
        db: Database session
        profile_id: ID của profile
        cv_id: ID của CV cần đặt làm default

    Returns:
        CV object đã cập nhật, hoặc None nếu không tìm thấy
    """
    # Bỏ default của tất cả CV trong profile
    cvs = get_cvs_by_profile(db, profile_id)
    for cv in cvs:
        cv.is_default = False

    # Đặt CV được chọn làm default
    target_cv = db.get(Cv, cv_id)
    if target_cv and target_cv.profile_id == profile_id:
        target_cv.is_default = True
        db.commit()
        db.refresh(target_cv)
        return target_cv

    db.rollback()
    return None


def delete_cv(db: Session, cv: Cv) -> None:
    """Xóa CV khỏi database."""
    db.delete(cv)
    db.commit()


def check_cv_used_in_applications(db: Session, cv_id: int) -> bool:
    """
    Kiểm tra CV đã được dùng để nộp đơn chưa.

    Note: Tạm thời return False vì chưa có bảng applications.
    Khi có bảng applications, cần implement logic kiểm tra thực tế.

    Args:
        db: Database session
        cv_id: ID của CV

    Returns:
        True nếu CV đã được dùng, False nếu chưa
    """
    # TODO: Implement khi có bảng applications
    # query = select(Application).where(Application.cv_id == cv_id).limit(1)
    # return db.scalar(query) is not None
    return False
