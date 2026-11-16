# ✅ CV Upload API - Implementation Complete

## Tổng quan
API upload CV an toàn đã được triển khai đầy đủ theo yêu cầu với các tính năng bảo mật cao.

---

## ✅ Tính năng đã hoàn thành

### Upload CV an toàn
- ✅ Kiểm tra MIME type thực tế bằng `python-magic` (đọc magic bytes)
- ✅ Chỉ chấp nhận PDF, DOC, DOCX
- ✅ Giới hạn 5MB/file
- ✅ Mỗi ứng viên tối đa 3 CV
- ✅ Đổi tên file bằng UUID để bảo mật
- ✅ Lưu file ngoài thư mục public (`storage/cvs/`)

### Quản lý CV
- ✅ Xem danh sách CV của ứng viên
- ✅ Chọn CV mặc định
- ✅ Xóa CV (chỉ CV chưa dùng để nộp đơn)
- ✅ Kiểm tra quyền sở hữu CV

---

## 📁 Files đã tạo/sửa

### Files mới tạo (6 files):
1. **app/routers/cv.py** (7,341 bytes) - API endpoints
2. **app/crud/cv.py** (3,116 bytes) - Database operations
3. **app/utils/file_validator.py** (4,103 bytes) - MIME validation
4. **app/utils/__init__.py** (18 bytes) - Package init
5. **CV_UPLOAD_API.md** - Full documentation
6. **CV_API_QUICKSTART.md** - Quick start guide

### Files đã chỉnh sửa (3 files):
1. **requirements.txt** - Added python-multipart, python-magic-bin
2. **app/main.py** - Registered CV router
3. **app/core/config.py** - Added CV upload settings

---

## 🔌 API Endpoints

```
POST   /api/cvs/upload           - Upload CV mới
GET    /api/cvs                  - Danh sách CV
PUT    /api/cvs/{cv_id}/default  - Đặt CV mặc định
DELETE /api/cvs/{cv_id}          - Xóa CV
```

---

## 🛡️ Security Features

1. **MIME Type Validation** - Đọc magic bytes, không chỉ extension
2. **UUID Naming** - File được đổi tên UUID để bảo mật
3. **Outside Public** - Lưu trong `storage/cvs/` (không public)
4. **Rate Limiting** - Max 3 CVs/candidate, 5MB/file
5. **Authorization** - Kiểm tra ownership
6. **Data Protection** - Không xóa được CV đã nộp đơn

---

## 🚀 Cách sử dụng

### 1. Cài đặt
```bash
pip install -r requirements.txt
```

### 2. Chạy server
```bash
uvicorn app.main:app --reload
```

### 3. Test API
- Swagger UI: http://127.0.0.1:8000/docs
- Upload CV: `POST /api/cvs/upload` với multipart/form-data

---

## ✅ Verification Results

```
✓ Total routes: 15
✓ CV endpoints: 4 (upload, list, set default, delete)
✓ Allowed MIME types: 3 (PDF, DOC, DOCX)
✓ CRUD functions: 7 (get, list, count, create, set_default, delete, check_used)
✓ All modules imported successfully
```

---

## 📋 TODO: Authentication

Hiện tại đang hardcode `profile_id = 1` để test.

Khi có JWT authentication, thay đổi hàm `get_current_profile_id()` trong `app/routers/cv.py`:

```python
def get_current_profile_id(token = Depends(security)) -> int:
    payload = jwt.decode(token.credentials, SECRET_KEY)
    user_id = payload["user_id"]
    # Query profile by user_id
    return profile.id
```

---

## 📚 Documentation

- **CV_UPLOAD_API.md** - Full API documentation (English/Vietnamese)
- **CV_API_QUICKSTART.md** - Quick start guide (Vietnamese)
- **Swagger UI** - http://127.0.0.1:8000/docs

---

## ✅ Status: COMPLETED

All requirements implemented:
- ✅ Upload CV PDF/DOC/DOCX max 5MB
- ✅ Python validates real MIME type
- ✅ Rename with UUID
- ✅ Save outside public directory
- ✅ Max 3 CVs per candidate
- ✅ Select default CV
- ✅ Delete unused CV only

**Date:** 2026-11-11  
**Lines of code:** ~500+
