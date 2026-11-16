# Import mọi model ở đây để Base.metadata.create_all() "nhìn thấy" và tạo bảng.
# Thêm model mới -> nhớ thêm 1 dòng import vào file này.
# Thứ tự quan trọng: model nào có FK trỏ tới model khác phải import SAU.
from app.models.user import User        # noqa: F401  ← phải trước Company (Company FK → users)
from app.models.company import Company  # noqa: F401  ← sau User vì có FK employer_id → users.id
from app.models.item import Item        # noqa: F401
from app.models.candidate_profile import (  # noqa: F401
    CandidateEducation,
    CandidateExperience,
    CandidateProfile,
)
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
from app.models.application import (  # noqa: F401
    Application,
    ApplicationDraft,
    ApplicationStatusHistory,
    CoverLetterTemplate,
    CV,
    MetaApplicationStatus,
    MetaWithdrawReason,
    SavedSearch,
)
from app.models.cv_document import CVDocument  # noqa: F401
from app.models.notification import Notification  # noqa: F401  ← sau User vì có FK user_id → users.id
