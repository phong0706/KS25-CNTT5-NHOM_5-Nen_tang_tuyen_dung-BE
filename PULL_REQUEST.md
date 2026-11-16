# [Feature] API Hồ Sơ Ứng Viên

## Mô tả

API quản lý hồ sơ ứng viên bao gồm:
- ✅ Xem/sửa thông tin hồ sơ cá nhân
- ✅ Thêm/sửa/xóa kỹ năng (chọn từ danh mục kỹ năng)
- ✅ Thêm/sửa/xóa kinh nghiệm làm việc
- ✅ Thêm/sửa/xóa học vấn
- ✅ Chỉ chủ hồ sơ được phép chỉnh sửa (ownership validation)

## Endpoints (13 endpoints)

### Hồ sơ
- `GET /api/profiles/me` - Xem hồ sơ của mình
- `GET /api/profiles/{id}` - Xem hồ sơ công khai
- `POST /api/profiles` - Tạo hồ sơ mới
- `PUT /api/profiles/{id}` - Cập nhật hồ sơ

### Kỹ năng
- `POST /api/profiles/{id}/skills` - Thêm kỹ năng
- `PUT /api/profiles/{id}/skills/{skill_id}` - Sửa kỹ năng
- `DELETE /api/profiles/{id}/skills/{skill_id}` - Xóa kỹ năng

### Kinh nghiệm
- `POST /api/profiles/{id}/experiences` - Thêm kinh nghiệm
- `PUT /api/profiles/{id}/experiences/{exp_id}` - Sửa kinh nghiệm
- `DELETE /api/profiles/{id}/experiences/{exp_id}` - Xóa kinh nghiệm

### Học vấn
- `POST /api/profiles/{id}/educations` - Thêm học vấn
- `PUT /api/profiles/{id}/educations/{edu_id}` - Sửa học vấn
- `DELETE /api/profiles/{id}/educations/{edu_id}` - Xóa học vấn

## Files thay đổi

### Mới tạo
- `app/crud/candidate_profile.py` - CRUD operations (213 lines)
- `app/routers/candidate_profile.py` - API endpoints (386 lines)
- `sql/candidate_profiles.sql` - Database migration với seed data
- `CANDIDATE_PROFILE_SUMMARY.md` - Documentation đầy đủ

### Cập nhật
- `app/main.py` - Thêm router mới
- `app/core/config.py` - Fix indentation issue

## Database Schema

5 bảng:
- `candidate_profiles` (hồ sơ)
- `candidate_skills` (kỹ năng)
- `experiences` (kinh nghiệm)
- `educations` (học vấn)
- `cvs` (CV files - đã có)

Foreign keys với CASCADE DELETE, indexes cho performance.

## Cách test

### 1. Chạy SQL migration
```bash
# MySQL Workbench: File > Open SQL Script > sql/candidate_profiles.sql > Execute
```

### 2. Khởi động server
```bash
cd KS25-CNTT5-NHOM_5-Nen_tang_tuyen_dung-BE
.venv/Scripts/activate
uvicorn app.main:app --reload
```

### 3. Test API tại http://127.0.0.1:8000/docs

**Workflow:**
1. Đăng nhập: `POST /api/auth/login` → lấy token
2. Tạo hồ sơ: `POST /api/profiles` (với Bearer token)
3. Thêm kỹ năng/kinh nghiệm/học vấn
4. Xem hồ sơ đầy đủ: `GET /api/profiles/me`

## Security

- ✅ JWT authentication required
- ✅ Ownership validation (chỉ chủ hồ sơ mới sửa được)
- ✅ Public/Private profiles (`is_public` flag)
- ✅ Cascade delete khi xóa hồ sơ

## Technical Details

- **Models & Schemas**: Reuse existing code (đã có sẵn)
- **CRUD**: SQLAlchemy với eager loading (joinedload)
- **Authorization**: Helper function `_check_profile_ownership()`
- **HTTP Status codes**: 200, 201, 204, 401, 403, 404, 409

## Checklist

- ✅ Code compile thành công
- ✅ Import không lỗi
- ✅ CRUD operations đầy đủ
- ✅ API endpoints hoàn chỉnh
- ✅ Authorization checks
- ✅ SQL migration ready
- ✅ Documentation hoàn chỉnh

## Tài liệu chi tiết

Xem: `CANDIDATE_PROFILE_SUMMARY.md`
