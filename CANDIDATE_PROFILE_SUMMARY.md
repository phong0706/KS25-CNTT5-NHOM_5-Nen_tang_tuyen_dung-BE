# API Hồ Sơ Ứng Viên - Implementation Summary

## ✅ Đã hoàn thành

### 1. CRUD Operations (`app/crud/candidate_profile.py`)
✅ Hồ sơ:
- `get_profile_by_user_id()` - Lấy hồ sơ theo user_id
- `get_profile_by_id()` - Lấy hồ sơ theo profile_id
- `create_profile()` - Tạo hồ sơ mới
- `update_profile()` - Cập nhật hồ sơ

✅ Kỹ năng:
- `get_skill_by_id()` - Lấy kỹ năng
- `add_skill()` - Thêm kỹ năng
- `update_skill()` - Sửa kỹ năng
- `delete_skill()` - Xóa kỹ năng

✅ Kinh nghiệm:
- `get_experience_by_id()` - Lấy kinh nghiệm
- `add_experience()` - Thêm kinh nghiệm
- `update_experience()` - Sửa kinh nghiệm
- `delete_experience()` - Xóa kinh nghiệm

✅ Học vấn:
- `get_education_by_id()` - Lấy học vấn
- `add_education()` - Thêm học vấn
- `update_education()` - Sửa học vấn
- `delete_education()` - Xóa học vấn

### 2. API Endpoints (`app/routers/candidate_profile.py`)
✅ Hồ sơ:
- `GET /api/profiles/me` - Xem hồ sơ của mình
- `GET /api/profiles/{profile_id}` - Xem hồ sơ công khai
- `POST /api/profiles` - Tạo hồ sơ
- `PUT /api/profiles/{profile_id}` - Cập nhật hồ sơ

✅ Kỹ năng (9 endpoints):
- `POST /api/profiles/{profile_id}/skills`
- `PUT /api/profiles/{profile_id}/skills/{skill_id}`
- `DELETE /api/profiles/{profile_id}/skills/{skill_id}`

✅ Kinh nghiệm (9 endpoints):
- `POST /api/profiles/{profile_id}/experiences`
- `PUT /api/profiles/{profile_id}/experiences/{exp_id}`
- `DELETE /api/profiles/{profile_id}/experiences/{exp_id}`

✅ Học vấn (9 endpoints):
- `POST /api/profiles/{profile_id}/educations`
- `PUT /api/profiles/{profile_id}/educations/{edu_id}`
- `DELETE /api/profiles/{profile_id}/educations/{edu_id}`

**Tổng cộng: 13 endpoints**

### 3. Database Migration (`sql/candidate_profiles.sql`)
✅ Tạo 5 bảng:
- `candidate_profiles` - Hồ sơ ứng viên
- `candidate_skills` - Kỹ năng
- `experiences` - Kinh nghiệm làm việc
- `educations` - Học vấn
- `cvs` - CV files (đã có sẵn)

✅ Foreign keys với CASCADE DELETE
✅ Indexes cho performance
✅ Seed data mẫu cho testing

### 4. Integration (`app/main.py`)
✅ Import router: `from app.routers import candidate_profile`
✅ Include router: `app.include_router(candidate_profile.router, prefix="/api")`

## 🔒 Bảo mật

✅ **Ownership validation**: Helper function `_check_profile_ownership()`
✅ **JWT Authentication**: Sử dụng `get_current_user` dependency
✅ **Permission checks**: Chỉ chủ hồ sơ mới sửa được
✅ **Public/Private profiles**: Kiểm tra `is_public` flag

## 📊 Database Schema

```
users (đã có sẵn)
  └─ candidate_profiles (1-1)
      ├─ candidate_skills (1-N, CASCADE DELETE)
      ├─ experiences (1-N, CASCADE DELETE)
      ├─ educations (1-N, CASCADE DELETE)
      └─ cvs (1-N, CASCADE DELETE)
```

## 🚀 Cách sử dụng

### 1. Chạy Database Migration
```bash
# Mở MySQL Workbench
# File > Open SQL Script > sql/candidate_profiles.sql
# Execute (⚡)
```

### 2. Khởi động Server
```bash
cd KS25-CNTT5-NHOM_5-Nen_tang_tuyen_dung-BE
.venv/Scripts/activate
uvicorn app.main:app --reload
```

### 3. Test API
Mở: http://127.0.0.1:8000/docs

**Workflow:**
1. Đăng nhập: `POST /api/auth/login` → lấy `access_token`
2. Tạo hồ sơ: `POST /api/profiles` (với Bearer token)
3. Thêm kỹ năng: `POST /api/profiles/{id}/skills`
4. Thêm kinh nghiệm: `POST /api/profiles/{id}/experiences`
5. Thêm học vấn: `POST /api/profiles/{id}/educations`
6. Xem hồ sơ: `GET /api/profiles/me`

## 📁 Files đã tạo

```
KS25-CNTT5-NHOM_5-Nen_tang_tuyen_dung-BE/
├── app/
│   ├── crud/
│   │   └── candidate_profile.py        ⭐ MỚI (213 lines)
│   ├── routers/
│   │   └── candidate_profile.py        ⭐ MỚI (386 lines)
│   └── main.py                         ✅ CẬP NHẬT (+1 import, +1 router)
├── sql/
│   └── candidate_profiles.sql          ⭐ MỚI (154 lines)
└── CANDIDATE_PROFILE_SUMMARY.md        ⭐ MỚI (tài liệu này)
```

## ✅ Kiểm tra

- ✅ Code compile thành công
- ✅ Import không lỗi
- ✅ Models & Schemas đã có sẵn (reuse existing)
- ✅ CRUD operations đầy đủ
- ✅ API endpoints hoàn chỉnh
- ✅ Authorization checks đúng
- ✅ SQL migration ready

## 🎯 Tính năng chính

1. **Quản lý hồ sơ**: Xem, tạo, sửa thông tin cá nhân
2. **Quản lý kỹ năng**: Thêm/sửa/xóa kỹ năng (chọn từ catalog hoặc tự nhập)
3. **Quản lý kinh nghiệm**: Thêm/sửa/xóa kinh nghiệm làm việc
4. **Quản lý học vấn**: Thêm/sửa/xóa học vấn
5. **Privacy control**: Công khai hoặc riêng tư (`is_public`)
6. **Ownership**: Chỉ chủ hồ sơ mới sửa được

## 📝 Ghi chú

- Mỗi user chỉ có **1 hồ sơ duy nhất**
- Kỹ năng reference đến bảng `skills` (nullable) → có thể chọn từ catalog hoặc tự nhập
- Kinh nghiệm/Học vấn hỗ trợ `is_current=true` cho công việc/trường đang học
- Cascade delete: Xóa hồ sơ → tự động xóa skills, experiences, educations
- Eager loading: Dùng `joinedload` để tối ưu query

## 🔗 API Documentation

Chi tiết đầy đủ xem tại: http://127.0.0.1:8000/docs (sau khi chạy server)

Hoặc trong file router comments: `app/routers/candidate_profile.py`
