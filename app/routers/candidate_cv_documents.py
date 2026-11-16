"""Router quản lý tài liệu CV người dùng (/api/candidate/cv-documents)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.cv_document import CVDocument
from app.models.user import User
from app.schemas.cv_document import (
    CVDocumentCreate,
    CVDocumentListItem,
    CVDocumentOut,
    CVDocumentRename,
    CVDocumentUpdate,
)

router = APIRouter(prefix="/candidate/cv-documents", tags=["Candidate CV Documents"])


def _get_user_cv_or_fail(cv_id: int, user: User, db: Session) -> CVDocument:
    cv = db.scalar(select(CVDocument).where(CVDocument.id == cv_id))
    if not cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài liệu CV",
        )
    if cv.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thao tác trên tài liệu này",
        )
    return cv


@router.get("", response_model=list[CVDocumentListItem], summary="Danh sách CV đã tạo của ứng viên")
def list_cv_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")
    stmt = (
        select(CVDocument)
        .where(CVDocument.user_id == current_user.id)
        .order_by(CVDocument.updated_at.desc())
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=CVDocumentOut, status_code=status.HTTP_201_CREATED, summary="Tạo mới tài liệu CV")
def create_cv_document(
    data: CVDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")
    cv = CVDocument(
        user_id=current_user.id,
        title=data.title.strip(),
        template_slug=data.template_slug.strip() or "simple",
        content_json=data.content_json,
        version=1,
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


@router.get("/{cv_id}", response_model=CVDocumentOut, summary="Xem chi tiết tài liệu CV")
def get_cv_document(
    cv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")
    return _get_user_cv_or_fail(cv_id, current_user, db)


@router.put("/{cv_id}", response_model=CVDocumentOut, summary="Cập nhật tài liệu CV (OCC version)")
def update_cv_document(
    cv_id: int,
    data: CVDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")
    cv = _get_user_cv_or_fail(cv_id, current_user, db)

    # Kiểm tra xung đột phiên bản (Optimistic Concurrency Control)
    if cv.version != data.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phiên bản tài liệu đã thay đổi trên hệ thống. Vui lòng làm mới để tránh mất dữ liệu.",
        )

    cv.title = data.title.strip()
    cv.template_slug = data.template_slug.strip() or "simple"
    cv.content_json = data.content_json
    cv.version = cv.version + 1

    db.commit()
    db.refresh(cv)
    return cv


@router.patch("/{cv_id}/rename", response_model=CVDocumentOut, summary="Đổi tên tài liệu CV")
def rename_cv_document(
    cv_id: int,
    data: CVDocumentRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")
    cv = _get_user_cv_or_fail(cv_id, current_user, db)
    cv.title = data.title.strip()
    db.commit()
    db.refresh(cv)
    return cv


@router.post("/{cv_id}/duplicate", response_model=CVDocumentOut, status_code=status.HTTP_201_CREATED, summary="Nhân bản tài liệu CV")
def duplicate_cv_document(
    cv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")
    orig = _get_user_cv_or_fail(cv_id, current_user, db)
    copy_cv = CVDocument(
        user_id=current_user.id,
        title=f"{orig.title} (Bản sao)",
        template_slug=orig.template_slug,
        content_json=orig.content_json,
        version=1,
    )
    db.add(copy_cv)
    db.commit()
    db.refresh(copy_cv)
    return copy_cv


@router.delete("/{cv_id}", summary="Xoá tài liệu CV")
def delete_cv_document(
    cv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")
    cv = _get_user_cv_or_fail(cv_id, current_user, db)
    db.delete(cv)
    db.commit()
    return {"status": "ok", "message": "Đã xoá tài liệu CV thành công"}
