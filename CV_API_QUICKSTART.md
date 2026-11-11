# Hướng dẫn sử dụng API Upload CV

## Tóm tắt
API upload CV an toàn với các tính năng:
- ✅ Kiểm tra MIME type thực tế (magic bytes)
- ✅ Giới hạn 5MB/file, tối đa 3 CV/ứng viên
- ✅ Đổi tên file bằng UUID
- ✅ Lưu ngoài thư mục public
- ✅ Quản lý CV mặc định
- ✅ Bảo vệ CV đã sử dụng

## Cài đặt nhanh

```bash
# Cài đặt dependencies
pip install -r requirements.txt

# Chạy server
uvicorn app.main:app --reload
```

## API Endpoints

### 1. Upload CV
```bash
POST /api/cvs/upload
Content-Type: multipart/form-data

# Tham số:
- file: File CV (PDF/DOC/DOCX, max 5MB)

# Response 201:
{
  "id": 1,
  "original_name": "CV_NguyenVanA.pdf",
  "stored_name": "uuid-here",
  "file_size": 524288,
  "mime_type": "application/pdf",
  "is_default": true,
  "uploaded_at": "2026-11-11T10:30:00"
}
```

### 2. Danh sách CV
```bash
GET /api/cvs

# Response 200: Array of CV objects
```

### 3. Đặt CV mặc định
```bash
PUT /api/cvs/{cv_id}/default

# Response 200: CV object với is_default=true
```

### 4. Xóa CV
```bash
DELETE /api/cvs/{cv_id}

# Response 204: No Content
# Lỗi 400: Nếu CV đã được dùng để nộp đơn
```

## Test bằng Swagger UI
Mở trình duyệt: http://127.0.0.1:8000/docs

## Cấu trúc Files

```
app/
├── routers/
│   └── cv.py                    # API endpoints
├── crud/
│   └── cv.py                    # Database operations
├── utils/
│   ├── __init__.py
│   └── file_validator.py        # MIME type validator
├── models/
│   └── candidate.py             # Cv model (đã có)
├── schemas/
│   └── candidate_schema.py      # CvCreate, CvOut (đã có)
└── core/
    └── config.py                # Settings (đã cập nhật)

storage/
└── cvs/                         # Thư mục lưu CV (tự động tạo)

CV_UPLOAD_API.md                 # Documentation đầy đủ
```

## Bảo mật

### Kiểm tra MIME type thực tế
```python
# Sử dụng python-magic để đọc magic bytes
import magic
mime = magic.from_buffer(file_content, mime=True)

# Chỉ chấp nhận:
- application/pdf
- application/msword (.doc)
- application/vnd.openxmlformats-officedocument.wordprocessingml.document (.docx)
```

### Đổi tên bằng UUID
```python
stored_name = str(uuid.uuid4())
# Ví dụ: a1b2c3d4-e5f6-7890-abcd-ef1234567890.pdf
```

### Giới hạn
- Tối đa 3 CV/ứng viên
- Tối đa 5MB/file
- Không xóa được CV đã nộp đơn

## TODO: Authentication

Hiện tại đang hardcode `profile_id = 1` để test.

Khi có authentication:
1. Thay đổi `get_current_profile_id()` trong `app/routers/cv.py`
2. Decode JWT token từ header Authorization
3. Lấy user_id từ token
4. Query CandidateProfile theo user_id

```python
# Ví dụ với JWT:
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

def get_current_profile_id(token = Depends(security)) -> int:
    # Decode JWT token
    payload = decode_jwt(token.credentials)
    user_id = payload["user_id"]
    
    # Query profile
    db = next(get_db())
    profile = db.query(CandidateProfile).filter_by(user_id=user_id).first()
    return profile.id
```

## Kiểm tra

Chạy test đơn giản:
```python
from app.main import app

# Kiểm tra routes
for route in app.routes:
    if 'cvs' in str(getattr(route, 'path', '')):
        print(route.path)

# Output:
# /api/cvs/upload
# /api/cvs
# /api/cvs/{cv_id}/default
# /api/cvs/{cv_id}
```

## Xem thêm
- [CV_UPLOAD_API.md](./CV_UPLOAD_API.md) - Documentation đầy đủ
- http://127.0.0.1:8000/docs - Swagger UI
