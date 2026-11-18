# API Upload CV An Toàn

## Mô tả
API upload CV với các tính năng bảo mật:
- Upload file CV định dạng PDF/DOC/DOCX, tối đa 5MB
- Kiểm tra MIME type thực tế (không chỉ dựa vào đuôi file)
- Đổi tên file bằng UUID để bảo mật
- Lưu file ngoài thư mục public (trong `storage/cvs/`)
- Mỗi ứng viên tối đa 3 CV
- Chọn CV mặc định
- Xóa CV chưa dùng để nộp đơn

## API Endpoints

### 1. Upload CV
**POST** `/api/cvs/upload`

Upload CV mới cho ứng viên.

**Request:**
- Content-Type: `multipart/form-data`
- Body: 
  - `file`: File CV (PDF/DOC/DOCX, tối đa 5MB)

**Response:** `201 Created`
```json
{
  "id": 1,
  "original_name": "CV_NguyenVanA.pdf",
  "stored_name": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "file_size": 524288,
  "mime_type": "application/pdf",
  "is_default": true,
  "uploaded_at": "2026-11-11T10:30:00"
}
```

**Errors:**
- `400 Bad Request`: Định dạng file không hợp lệ, đã đủ 3 CV
- `413 Payload Too Large`: File quá 5MB
- `404 Not Found`: Hồ sơ ứng viên không tồn tại

---

### 2. Danh sách CV
**GET** `/api/cvs`

Lấy danh sách CV của ứng viên hiện tại.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "original_name": "CV_NguyenVanA.pdf",
    "stored_name": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "file_size": 524288,
    "mime_type": "application/pdf",
    "is_default": true,
    "uploaded_at": "2026-11-11T10:30:00"
  }
]
```

---

### 3. Đặt CV mặc định
**PUT** `/api/cvs/{cv_id}/default`

Đặt CV làm mặc định (sẽ được dùng khi nộp đơn nếu không chọn CV khác).

**Response:** `200 OK`
```json
{
  "id": 1,
  "original_name": "CV_NguyenVanA.pdf",
  "stored_name": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "file_size": 524288,
  "mime_type": "application/pdf",
  "is_default": true,
  "uploaded_at": "2026-11-11T10:30:00"
}
```

**Errors:**
- `404 Not Found`: CV không tồn tại
- `403 Forbidden`: CV không thuộc về ứng viên hiện tại

---

### 4. Xóa CV
**DELETE** `/api/cvs/{cv_id}`

Xóa CV (chỉ được xóa CV chưa dùng để nộp đơn).

**Response:** `204 No Content`

**Errors:**
- `400 Bad Request`: CV đã được sử dụng để nộp đơn
- `404 Not Found`: CV không tồn tại
- `403 Forbidden`: CV không thuộc về ứng viên hiện tại

---

## Tính năng bảo mật

### 1. Kiểm tra MIME type thực tế
- Sử dụng `python-magic` để đọc magic bytes của file
- Không chỉ dựa vào đuôi file (có thể giả mạo)
- Chỉ chấp nhận:
  - `application/pdf` (.pdf)
  - `application/msword` (.doc)
  - `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (.docx)

### 2. Đổi tên file bằng UUID
- File được lưu với tên UUID thay vì tên gốc
- Tránh lộ thông tin cá nhân từ tên file
- Tránh conflict tên file

### 3. Lưu file ngoài public
- File được lưu trong `storage/cvs/` (không public)
- Chỉ truy cập được thông qua API có xác thực

### 4. Giới hạn số lượng và kích thước
- Mỗi ứng viên tối đa 3 CV
- Mỗi file tối đa 5MB

### 5. Kiểm tra quyền sở hữu
- Chỉ có chủ sở hữu mới có thể xem/sửa/xóa CV của mình

### 6. Bảo vệ CV đã sử dụng
- Không cho phép xóa CV đã được dùng để nộp đơn

---

## Cấu trúc Database

### Bảng `cvs`
Bảng đã tồn tại trong model `app/models/candidate.py`:

```python
class Cv(Base):
    __tablename__ = "cvs"
    
    id: int                    # Primary key
    profile_id: int            # Foreign key -> candidate_profiles.id
    original_name: str         # Tên file gốc
    stored_name: str           # UUID (unique)
    file_size: int             # Kích thước (bytes)
    mime_type: str             # MIME type
    is_default: bool           # CV mặc định
    uploaded_at: datetime      # Thời gian upload
```

---

## Cài đặt

### 1. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

Dependencies mới:
- `python-multipart`: Xử lý multipart/form-data (file upload)
- `python-magic-bin`: Kiểm tra MIME type (Windows compatible)

### 2. Cấu hình (app/core/config.py)
```python
CV_UPLOAD_DIR: str = "storage/cvs"           # Thư mục lưu CV
CV_MAX_SIZE_MB: int = 5                       # Kích thước tối đa
CV_MAX_FILES_PER_CANDIDATE: int = 3           # Số CV tối đa
```

### 3. Tạo thư mục storage
Thư mục sẽ được tự động tạo khi upload CV lần đầu.

---

## Testing

### Test bằng cURL

**Upload CV:**
```bash
curl -X POST "http://127.0.0.1:8000/api/cvs/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/your/cv.pdf"
```

**Lấy danh sách CV:**
```bash
curl -X GET "http://127.0.0.1:8000/api/cvs"
```

**Đặt CV mặc định:**
```bash
curl -X PUT "http://127.0.0.1:8000/api/cvs/1/default"
```

**Xóa CV:**
```bash
curl -X DELETE "http://127.0.0.1:8000/api/cvs/1"
```

### Test bằng Swagger UI
Truy cập: http://127.0.0.1:8000/docs

---

## TODO - Authentication

Hiện tại API đang hardcode `profile_id = 1` để test. 

Khi tích hợp authentication:
1. Decode JWT token từ header `Authorization: Bearer <token>`
2. Lấy `user_id` từ token
3. Query `CandidateProfile` theo `user_id`
4. Thay đổi hàm `get_current_profile_id()` trong `app/routers/cv.py`

---

## Files Created/Modified

### Created:
1. `app/routers/cv.py` - API endpoints
2. `app/crud/cv.py` - CRUD operations
3. `app/utils/file_validator.py` - File validation utility
4. `app/utils/__init__.py` - Utils module init

### Modified:
1. `requirements.txt` - Added python-multipart, python-magic-bin
2. `app/main.py` - Registered CV router
3. `app/core/config.py` - Added CV upload settings

### Existing (Used):
1. `app/models/candidate.py` - Cv model (already exists)
2. `app/schemas/candidate_schema.py` - CvCreate, CvOut schemas (already exists)
