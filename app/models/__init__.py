# Import mọi model ở đây để Base.metadata.create_all() "nhìn thấy" và tạo bảng.
# Thêm model mới -> nhớ thêm 1 dòng import vào file này.
# Thứ tự quan trọng: model nào có FK trỏ tới model khác phải import SAU.

# 1. Các bảng gốc / danh mục độc lập (không có hoặc ít FK)
from app.models.user import User  # noqa: F401  ← phải trước Company (Company FK → users)
from app.models.item import Item  # noqa: F401
from app.models.catalog import Industry, Location, Skill  # noqa: F401

# 2. Công ty (FK → users)
from app.models.company import Company, CompanyStatus  # noqa: F401
from app.models.company_verification import CompanyVerification  # noqa: F401

# 3. Hồ sơ ứng viên
from app.models.candidate import (  # noqa: F401
    CandidateProfile,
    CandidateSkill,
    Education,
    Experience,
)
from app.models.candidate_profile import (  # noqa: F401
    CandidateEducation,
    CandidateExperience,
)

# 4. Việc làm & kỹ năng công việc
from app.models.job import (  # noqa: F401
    Job,
    JobApplication,
    MetaCategory,
    MetaLevel,
    MetaLocation,
    MetaSkill,
    MetaWorkType,
    SavedJob,
)
from app.models.job_status_history import JobStatusHistory  # noqa: F401
from app.models.job_skill import JobSkill  # noqa: F401

# 5. Hồ sơ ứng tuyển, CV & lịch sử trạng thái
from app.models.application import (  # noqa: F401
    Application,
    ApplicationDraft,
    ApplicationStatus,
    ApplicationStatusHistory,
    CoverLetterTemplate,
    CV,
    MetaApplicationStatus,
    MetaWithdrawReason,
    SavedSearch,
)
from app.models.cv_document import CVDocument  # noqa: F401

# 6. Phỏng vấn, báo cáo & thông báo
from app.models.interview import Interview  # noqa: F401
from app.models.report import Report, ReportStatus  # noqa: F401
from app.models.notification import Notification  # noqa: F401  ← sau User vì có FK user_id → users.id
from app.models.password_reset import PasswordResetToken  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.career_path import (  # noqa: F401
    CareerRoleSkillWeight,
    CareerRoleStat,
    CareerRoleTransition,
)



