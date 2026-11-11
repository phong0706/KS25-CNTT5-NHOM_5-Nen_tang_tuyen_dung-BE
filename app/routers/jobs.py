from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import job as job_crud
from app.crud import saved_job as saved_job_crud
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobMutationResponse,
    JobSearchOut,
    JobStatusUpdate,
    JobUpdate,
    SavedJobDetailOut,
)
from app.schemas.saved_job import SavedJobCreate, SavedJobOut

router = APIRouter(tags=["Jobs"])


@router.post("/v1/jobs", response_model=JobMutationResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"employer", "admin"}:
        raise HTTPException(status_code=403, detail="Chức năng này chỉ dành cho nhà tuyển dụng")
    job = job_crud.create_job(db, current_user.id, data, is_admin=current_user.role == "admin")
    return {"statusCode": 201, "message": "Tạo tin tuyển dụng thành công", "data": job}


@router.put("/v1/jobs/{job_id}", response_model=JobMutationResponse)
def update_job(
    job_id: int,
    data: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "employer":
        raise HTTPException(status_code=403, detail="Chỉ nhà tuyển dụng sở hữu tin mới được chỉnh sửa")
    job = job_crud.update_job(db, job_id, current_user.id, data)
    return {"statusCode": 200, "message": "Cập nhật tin tuyển dụng thành công", "data": job}


@router.patch("/v1/jobs/{job_id}/status", response_model=JobMutationResponse)
def update_job_status(
    job_id: int,
    data: JobStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"employer", "admin"}:
        raise HTTPException(status_code=403, detail="Chức năng này chỉ dành cho nhà tuyển dụng hoặc quản trị viên")
    if current_user.role == "employer" and data.status not in {"PENDING", "OPEN", "HIDDEN", "CLOSED"}:
        raise HTTPException(status_code=403, detail="Trạng thái này chỉ quản trị viên được thiết lập")
    job = job_crud.change_job_status(
        db, job_id, current_user.id, data.status, is_admin=current_user.role == "admin"
    )
    return {"statusCode": 200, "message": "Cập nhật trạng thái tin tuyển dụng thành công", "data": job}


@router.get("/jobs/search", response_model=list[JobSearchOut])
def search_jobs(
    keyword: str | None = Query(default=None),
    industry_id: int | None = Query(default=None, gt=0),
    location_id: int | None = Query(default=None, gt=0),
    skill_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    return job_crud.search_jobs(db, keyword, industry_id, location_id, skill_id)


@router.post("/saved-jobs", response_model=SavedJobOut, status_code=status.HTTP_201_CREATED)
def create_saved_job(data: SavedJobCreate, db: Session = Depends(get_db)):
    try:
        return saved_job_crud.save_job(db, data.candidate_profile_id, data.job_id)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tin tuyển dụng đã được lưu hoặc dữ liệu không hợp lệ",
        )


@router.get(
    "/candidates/{candidate_profile_id}/saved-jobs",
    response_model=list[SavedJobDetailOut],
)
def list_saved_jobs(candidate_profile_id: int, db: Session = Depends(get_db)):
    return saved_job_crud.get_saved_jobs(db, candidate_profile_id)


@router.delete("/candidates/{candidate_profile_id}/saved-jobs/{job_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def remove_saved_job(candidate_profile_id: int, job_id: int, db: Session = Depends(get_db)):
    deleted = saved_job_crud.delete_saved_job(db, candidate_profile_id, job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin đã lưu")
