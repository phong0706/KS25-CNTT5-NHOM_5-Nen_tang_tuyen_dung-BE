"""Router Lộ trình sự nghiệp cho ứng viên (/api/career-path).
Đọc trọng số kỹ năng đã tính sẵn từ bảng career_role_stats & career_role_skill_weights,
gợi ý bước hiện tại, bước tiếp theo (+1 bậc / chuyển họ qua bảng transitions) và bước sau nữa (+2 bậc).
Giới hạn: < 200 dòng.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_optional_user, role_required
from app.db.session import get_db
from app.models.user import User
from app.services.career_path_service import refresh_career_weights_in_db
from app.services.career_roadmap_resolver import resolve_roadmap

router = APIRouter(prefix="/career-path", tags=["Career Path"])


class CareerPathRequest(BaseModel):
    user_id: Optional[int] = None
    skills: Optional[list[str]] = None
    current_family_slug: Optional[str] = None
    current_level_slug: Optional[str] = None


@router.get("", summary="Gợi ý lộ trình sự nghiệp cho ứng viên (GET)")
def get_career_path(
    user_id: Optional[int] = Query(None),
    skills: Optional[str] = Query(None, description="Danh sách kỹ năng phân tách bằng dấu phẩy"),
    family: Optional[str] = Query(None, description="Slug họ nghề hiện tại (vd: backend, frontend)"),
    level: Optional[str] = Query(None, description="Slug cấp bậc hiện tại (vd: junior, middle, senior)"),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    eff_uid = user_id or (current_user.id if current_user and current_user.role == "candidate" else None)
    parsed_skills = [s.strip() for s in skills.split(",") if s.strip()] if skills else None
    return resolve_roadmap(db, eff_uid, parsed_skills, family, level)


@router.post("", summary="Gợi ý lộ trình sự nghiệp nhận danh sách kỹ năng từ body (POST)")
def post_career_path(
    payload: CareerPathRequest,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    eff_uid = payload.user_id or (current_user.id if current_user and current_user.role == "candidate" else None)
    return resolve_roadmap(db, eff_uid, payload.skills, payload.current_family_slug, payload.current_level_slug)


@router.post("/refresh", summary="Job cập nhật lại bảng trọng số kỹ năng theo vai trò")
def trigger_refresh_career_weights(
    current_user: User = Depends(role_required("admin", "operator")),
    db: Session = Depends(get_db),
):
    return refresh_career_weights_in_db(db)
