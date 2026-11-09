# Import mọi model ở đây để Base.metadata.create_all() "nhìn thấy" và tạo bảng.
# Thêm model mới -> nhớ thêm 1 dòng import vào file này.
from app.models.user import User  # noqa: F401
from app.models.item import Item  # noqa: F401
from app.models.catalog import Industry, Location, Skill
from app.models.report import Report, ReportStatus
from app.models.candidate import CandidateProfile, CandidateSkill, Experience, Education, Cv
from app.models.company import Company, CompanyStatus  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.job_skill import JobSkill  # noqa: F401
from app.models.saved_job import SavedJob  # noqa: F401