# Import mọi model ở đây để Base.metadata.create_all() "nhìn thấy" và tạo bảng.
# Thêm model mới -> nhớ thêm 1 dòng import vào file này.
# Thứ tự quan trọng: model nào có FK trỏ tới model khác phải import SAU.
from app.models.user import User        # noqa: F401  ← phải trước Company (Company FK → users)
from app.models.company import Company  # noqa: F401  ← sau User vì có FK employer_id → users.id
from app.models.item import Item        # noqa: F401
