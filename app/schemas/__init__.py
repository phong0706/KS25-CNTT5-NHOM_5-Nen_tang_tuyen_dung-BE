# Import các schema danh mục (Industry, Location, Skill)
from app.schemas.catalog_schema import (
    CatalogBase,
    CatalogCreate,
    CatalogUpdate,
    CatalogResponse,
)

# Import các schema báo cáo vi phạm (Report)
from app.schemas.report_schema import (
    ReportCreate,
    ReportUpdate,
    ReportResponse,
)

# Import các schema ứng viên
from app.schemas.candidate_schema import (
    CandidateSkillCreate,
    CandidateSkillUpdate,
    CandidateSkillOut,
    ExperienceCreate,
    ExperienceUpdate,
    ExperienceOut,
    EducationCreate,
    EducationUpdate,
    EducationOut,
    CvCreate,
    CvOut,
    CandidateProfileCreate,
    CandidateProfileUpdate,
    CandidateProfileOut,
)

# Import các schema đơn ứng tuyển
from app.schemas.application_schema import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationOut,
)

# Import các schema lịch sử trạng thái đơn ứng tuyển
from app.schemas.application_status_history_schema import (
    ApplicationStatusHistoryCreate,
    ApplicationStatusHistoryOut,
)

# Import các schema lịch phỏng vấn
from app.schemas.interview_schema import (
    InterviewCreate,
    InterviewUpdate,
    InterviewOut,
)