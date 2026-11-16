"""Router tra cứu lương & việc làm phù hợp."""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
import json
import statistics

from app.db.session import get_db
from app.core.security import get_current_user

router = APIRouter(tags=["Salary & Matching"])

class SalaryLookupResponse(BaseModel):
    min_salary: Optional[int] = None
    median_salary: Optional[int] = None
    max_salary: Optional[int] = None
    sample_count: int
    message: Optional[str] = None

@router.get("/api/salary-lookup", response_model=SalaryLookupResponse, summary="Tra cứu lương theo danh mục, cấp bậc, địa điểm")
def lookup_salary(
    category_id: Optional[int] = Query(None),
    level_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    query_str = """
        SELECT salary_min, salary_max 
        FROM jobs 
        WHERE status = 'published' AND (salary_min IS NOT NULL OR salary_max IS NOT NULL)
    """
    params = {}
    if category_id:
        query_str += " AND category_id = :cat_id"
        params["cat_id"] = category_id
    if level_id:
        query_str += " AND level_id = :lvl_id"
        params["lvl_id"] = level_id
    if location_id:
        query_str += " AND location_id = :loc_id"
        params["loc_id"] = location_id

    rows = db.execute(text(query_str), params).fetchall()
    sample_count = len(rows)

    if sample_count < 5:
        return SalaryLookupResponse(
            sample_count=sample_count,
            message="Chưa đủ dữ liệu (yêu cầu tối thiểu 5 tin tuyển dụng phù hợp)."
        )

    # Tính toán min, max, median dựa trên trung bình lương từng tin
    avg_salaries = []
    for r in rows:
        s_min = r.salary_min or r.salary_max
        s_max = r.salary_max or r.salary_min
        avg = (s_min + s_max) // 2
        avg_salaries.append(avg)

    avg_salaries.sort()
    return SalaryLookupResponse(
        min_salary=min(avg_salaries),
        median_salary=int(statistics.median(avg_salaries)),
        max_salary=max(avg_salaries),
        sample_count=sample_count
    )

class MatchedJobItem(BaseModel):
    id: int
    title: str
    company_name: str
    location: str
    salary: str
    match_score: int
    matched_skills: List[str]
    missing_skills: List[str]

@router.get("/api/candidate/matched-jobs", summary="Việc làm phù hợp với kỹ năng của ứng viên")
def get_matched_jobs(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")

    # Lấy kỹ năng của ứng viên.
    # LƯU Ý: cột trong DB là `skills_json` (xem app/models/candidate_profile.py).
    # Truy vấn `skills` sẽ gây lỗi SQL 1054 (Unknown column).
    profile_row = db.execute(
        text("SELECT skills_json FROM candidate_profiles WHERE user_id = :uid"),
        {"uid": current_user.id}
    ).fetchone()

    user_skills = set()
    if profile_row and profile_row.skills_json:
        raw = profile_row.skills_json
        if isinstance(raw, list):
            user_skills = {str(s).lower().strip() for s in raw if str(s).strip()}
        elif isinstance(raw, str):
            # skills_json lưu dạng TEXT chứa JSON array; fallback sang CSV nếu dữ liệu cũ.
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    user_skills = {str(s).lower().strip() for s in parsed if str(s).strip()}
                else:
                    user_skills = {s.lower().strip() for s in str(parsed).split(",") if s.strip()}
            except (ValueError, TypeError):
                user_skills = {s.lower().strip() for s in raw.split(",") if s.strip()}

    if not user_skills:
        return {
            "has_profile_skills": False,
            "message": "Bạn chưa cập nhật kỹ năng trong hồ sơ. Hãy cập nhật để xem việc làm phù hợp!",
            "items": []
        }

    # Lấy danh sách tin tuyển dụng published
    jobs = db.execute(text("""
        SELECT j.id, j.title, c.name as company_name, l.name as location_name, j.salary_min, j.salary_max, j.is_salary_negotiable, j.requirements
        FROM jobs j
        LEFT JOIN companies c ON j.company_id = c.id
        LEFT JOIN meta_locations l ON j.location_id = l.id
        WHERE j.status = 'published'
        LIMIT 50
    """)).fetchall()

    results = []
    for job in jobs:
        # Giả lập hoặc bóc tách kỹ năng từ requirements/title
        req_text = (job.requirements or "").lower() + " " + (job.title or "").lower()
        # Tìm các kỹ năng khớp
        matched = [sk for sk in user_skills if sk in req_text]
        score = int((len(matched) / max(1, len(user_skills))) * 100)
        missing = [sk for sk in user_skills if sk not in matched]

        if score > 0:
            sal_str = "Thỏa thuận"
            if not job.is_salary_negotiable and (job.salary_min or job.salary_max):
                sal_str = f"{(job.salary_min or 0) // 1000000} - {(job.salary_max or 0) // 1000000} triệu"

            results.append({
                "id": job.id,
                "title": job.title,
                "company_name": job.company_name or "Doanh nghiệp",
                "location": job.location_name or "Toàn quốc",
                "salary": sal_str,
                "match_score": min(100, score),
                "matched_skills": matched,
                "missing_skills": missing
            })

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return {
        "has_profile_skills": True,
        "items": results[:20]
    }
