from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import job as job_crud
from app.crud import saved_job as saved_job_crud
from app.db.session import get_db
from app.schemas.job import JobSearchOut, SavedJobDetailOut
from app.schemas.saved_job import SavedJobCreate, SavedJobOut

router = APIRouter(tags=["Jobs"])


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