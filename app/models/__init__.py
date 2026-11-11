# Import mọi model ở đây để Base.metadata.create_all() "nhìn thấy" và tạo bảng.
# Thêm model mới -> nhớ thêm 1 dòng import vào file này.
from app.models.user import User  # noqa: F401
from app.models.item import Item  # noqa: F401
from app.models.catalog import Industry, Location, Skill  # noqa: F401
from app.models.report import Report, ReportStatus  # noqa: F401
from app.models.candidate import CandidateProfile, CandidateSkill, Experience, Education, Cv  # noqa: F401
from app.models.company import Company, CompanyStatus  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.job_skill import JobSkill  # noqa: F401
from app.models.saved_job import SavedJob  # noqa: F401
from app.models.application import Application, ApplicationStatus  # noqa: F401
from app.models.application_status_history import ApplicationStatusHistory  # noqa: F401
from app.models.interview import Interview  # noqa: F401