# Hướng dẫn: Module Xác thực (Authentication)

Task: Đăng ký theo vai trò + Đăng nhập JWT + Lấy thông tin user.
Ngày thực hiện: 09/11/2026 — Nhóm 5 RIKKEILAB HN-KS25-CNTT5

---

## 1. Danh sách API đã làm

| Method | URL | Mô tả | Auth |
|--------|-----|--------|------|
| POST | `/api/auth/register` | Đăng ký tài khoản mới | Không cần |
| POST | `/api/auth/login` | Đăng nhập, nhận JWT | Không cần |
| GET | `/api/auth/me` | Thông tin user đang đăng nhập | Bearer token |

---

## 2. Các file đã tạo / sửa

### File mới tạo

```
backend/app/
├── models/
│   ├── user.py          ← SQLAlchemy map bảng users
│   └── company.py       ← SQLAlchemy map bảng companies
├── schemas/
│   └── auth.py          ← Pydantic: RegisterRequest, LoginRequest, TokenOut, UserOut
├── crud/
│   ├── user.py          ← get_by_email, get_by_id, create_user
│   └── company.py       ← create_draft_company
├── core/
│   └── security.py      ← hash_password, verify_password, create_access_token, get_current_user
└── routers/
    └── auth.py          ← 3 endpoint: register, login, me
```

### File đã sửa

| File | Thay đổi |
|------|----------|
| `app/main.py` | Thêm `include_router(auth.router)` |
| `app/models/__init__.py` | Import User, Company để `create_all` nhìn thấy |
| `app/core/config.py` | Thêm `JWT_SECRET`, `JWT_EXPIRE_MINUTES` |
| `requirements.txt` | Thêm `bcrypt==4.2.0`, `python-jose[cryptography]==3.3.0` |
| `.env.example` | Thêm section JWT |
| `.env` | Thêm giá trị JWT thực tế |
| `sql/init.sql` | Thêm `CREATE TABLE companies`, sửa lỗi data mẫu, bcrypt password |

---

## 3. Luồng xử lý chi tiết

### POST /api/auth/register

```
FE gửi JSON
{
  "email": "user@example.com",
  "password": "secret123",       ← min 6 ký tự
  "full_name": "Nguyễn Văn A",
  "role": "candidate",           ← "candidate" hoặc "employer"
  "company_name": "Cty ABC"      ← BẮT BUỘC nếu role=employer
}
        │
        ▼
[1] Pydantic validate (schemas/auth.py: RegisterRequest)
        ├── password < 6 ký tự               → 422
        ├── role không hợp lệ                → 422
        └── role=employer + không company_name → 422
                "Nhà tuyển dụng phải nhập tên công ty"
        │ OK
        ▼
[2] router: kiểm tra email trùng
        crud/user.py: get_user_by_email(db, email)
        └── CÓ trong DB → 409 Conflict
                {"detail": "Email '...' đã được sử dụng"}
        │ KHÔNG trùng
        ▼
[3] core/security.py: hash_password(plain)
        bcrypt.hashpw(plain, gensalt(12)) → "$2b$12$..."
        │
        ▼
[4] crud/user.py: create_user(...)
        INSERT INTO users (...) VALUES (...)
        └── nếu role=employer:
                crud/company.py: create_draft_company(...)
                INSERT INTO companies (name, employer_id, is_draft=TRUE)
        │
        ▼
[5] Serialize UserOut (KHÔNG có password) → 201 Created
```

---

### POST /api/auth/login

```
FE gửi: {"email": "...", "password": "..."}
        │
        ▼
[1] crud/user.py: get_user_by_email(db, email)
        └── không tìm thấy → user = None
        │
        ▼
[2] if not user OR not verify_password(plain, user.password)
        verify: bcrypt.checkpw("secret123", "$2b$12$...")
        └── FAIL → 401 "Email hoặc mật khẩu không đúng"
               (cùng 1 message → tránh lộ user tồn tại không)
        │ OK
        ▼
[3] if not user.is_active
        └── → 403 "Tài khoản đã bị khoá"
        │
        ▼
[4] core/security.py: create_access_token(user.id, user.role)
        payload = {"sub": "42", "role": "candidate", "exp": now+1440min}
        jwt.encode(payload, JWT_SECRET, "HS256") → "eyJhbGci..."
        │
        ▼
[5] → 200 OK
        {"access_token": "eyJhbGci...", "token_type": "bearer"}
```

---

### GET /api/auth/me

```
FE gửi header: Authorization: Bearer eyJhbGci...
        │
        ▼
[1] Dependency get_current_user() (core/security.py)
        │
        ├── HTTPBearer đọc header
        │       └── không có → 401
        │
        ├── jwt.decode(token, JWT_SECRET, ["HS256"])
        │       ├── hết hạn / sai chữ ký / bị sửa → JWTError → 401
        │       └── OK → payload = {"sub":"42", "role":"candidate", ...}
        │
        ├── user_id = int(payload["sub"]) → 42
        │
        └── crud/user.py: get_user_by_id(db, 42)
                └── không tìm thấy → 401
        │
        ▼
[2] def me(current_user): return current_user
        │
        ▼
[3] Serialize UserOut → 200 OK (KHÔNG có password)
```

---
