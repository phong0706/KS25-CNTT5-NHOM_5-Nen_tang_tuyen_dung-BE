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