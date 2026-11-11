"""Kiểm tra quyền sở hữu tài nguyên — dùng chung cho mọi router.

Quy tắc:
    • Chủ sở hữu (owner_id == current_user.id) → được phép
    • Admin                                     → luôn được phép
    • Người khác                                → 403 Forbidden

Hàm chính:
    require_owner(owner_id, current_user)   — raise 403 nếu không có quyền
    is_owner_or_admin(owner_id, current_user) → bool (không raise, dùng để rẽ nhánh)

Ví dụ dùng trong router (tin tuyển dụng):
    @router.put("/jobs/{job_id}")
    def update_job(
        job_id: int,
        data: JobUpdate,
        db: Session = Depends(get_db),
        current_user = Depends(get_current_user),
    ):
        job = db.get(Job, job_id) or raise_404(job_id)
        require_owner(job.employer_id, current_user)   # ← 1 dòng
        return job_crud.update_job(db, job, data)

Ví dụ dùng trong router (hồ sơ ứng viên):
    @router.put("/profiles/{profile_id}")
    def update_profile(
        profile_id: int,
        data: ProfileUpdate,
        db: Session = Depends(get_db),
        current_user = Depends(get_current_user),
    ):
        profile = db.get(Profile, profile_id) or raise_404(profile_id)
        require_owner(profile.user_id, current_user)   # ← 1 dòng
        return profile_crud.update_profile(db, profile, data)
"""
from fastapi import HTTPException, status


def is_owner_or_admin(owner_id: int, current_user) -> bool:
    """Trả True nếu current_user là chủ tài nguyên HOẶC là admin.

    Không raise exception — dùng để rẽ nhánh logic (hiện/ẩn nút sửa...).

    Args:
        owner_id:     ID của chủ sở hữu tài nguyên (vd: job.employer_id, profile.user_id)
        current_user: User object từ Depends(get_current_user)

    Returns:
        True nếu có quyền, False nếu không.
    """
    return current_user.id == owner_id or current_user.role == "admin"


def require_owner(owner_id: int, current_user) -> None:
    """Raise 403 nếu current_user KHÔNG phải chủ sở hữu và KHÔNG phải admin.

    Nên gọi ngay sau khi lấy được tài nguyên từ DB và trước khi thực hiện
    bất kỳ thao tác sửa / xoá nào.

    Args:
        owner_id:     ID của chủ sở hữu tài nguyên (vd: job.employer_id, profile.user_id)
        current_user: User object từ Depends(get_current_user)

    Raises:
        HTTPException 403: nếu không có quyền sở hữu.
    """
    if not is_owner_or_admin(owner_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện thao tác này trên tài nguyên của người khác.",
        )
