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

## 4. Cấu trúc JWT

Token gồm 3 phần ngăn bởi dấu `.` (đều là base64url):

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9          ← Header: {"alg":"HS256","typ":"JWT"}
.
eyJzdWIiOiI0MiIsInJvbGUiOiJjYW5kaWRhdGUiLCJleHAiOjE3...  ← Payload
.
SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c               ← Signature (HS256)
```

Payload sau khi decode:
```json
{
  "sub": "42",
  "role": "candidate",
  "exp": 1763212800
}
```

**JWT không lưu vào DB.** Server chỉ verify chữ ký bằng `JWT_SECRET`.
Muốn invalidate token cần thêm blacklist table hoặc refresh token (ngoài phạm vi task này).

---

## 5. Bảng HTTP Status

| Tình huống | Status | Body (detail) |
|------------|--------|---------------|
| Đăng ký thành công | 201 Created | UserOut (không có password) |
| Employer thiếu `company_name` | 422 Unprocessable | Pydantic validation error |
| Password < 6 ký tự | 422 Unprocessable | Pydantic validation error |
| Email đã tồn tại | 409 Conflict | `"Email '...' đã được sử dụng"` |
| Đăng nhập thành công | 200 OK | `{"access_token": "eyJ...", "token_type": "bearer"}` |
| Sai email hoặc password | 401 Unauthorized | `"Email hoặc mật khẩu không đúng"` |
| Tài khoản bị khóa | 403 Forbidden | `"Tài khoản đã bị khoá..."` |
| `/me` token hợp lệ | 200 OK | UserOut |
| `/me` không có / sai token | 401 Unauthorized | `"Token không hợp lệ hoặc đã hết hạn"` |

---

## 6. Test trên Swagger UI (step by step)

1. Chạy server:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. Mở `http://127.0.0.1:8000/docs` → thấy nhóm **Auth**

3. **Đăng ký candidate** — `POST /api/auth/register` → Try it out:
   ```json
   {
     "email": "test@example.com",
     "password": "pass123",
     "full_name": "Nguyễn Văn Test",
     "role": "candidate"
   }
   ```
   → Execute → nhận **201**, body có `id`, `role`, không có `password`

4. **Đăng ký employer** — thêm `company_name`:
   ```json
   {
     "email": "emp@example.com",
     "password": "pass456",
     "full_name": "Trần Văn Employer",
     "role": "employer",
     "company_name": "Cty TNHH ABC"
   }
   ```
   → **201**. Thử bỏ `company_name` → **422**.

5. **Đăng ký email trùng** — gửi lại body bước 3 → **409**
   ```json
   {"detail": "Email 'test@example.com' đã được sử dụng"}
   ```

6. **Đăng nhập** — `POST /api/auth/login`:
   ```json
   {"email": "test@example.com", "password": "pass123"}
   ```
   → **200**, copy toàn bộ giá trị `access_token`

7. **Gắn token vào Swagger:**
   - Bấm nút **Authorize 🔒** (góc trên phải)
   - Dán `access_token` vào ô **Value**
   - Bấm **Authorize** → **Close**

8. **GET /me** → Try it out → Execute → **200**:
   ```json
   {
     "id": 49,
     "email": "test@example.com",
     "role": "candidate",
     "is_active": true,
     ...
   }
   ```

9. **Test token sai** — xóa token khỏi Authorize → GET /me → **401**

---

## 7. Kết quả test tự động (23/23 PASS)

```
=== POST /api/auth/register ===
[OK]  candidate → 201
[OK]    có id, role=candidate, không có password
[OK]  employer + company_name → 201
[OK]    role=employer
[OK]  employer thiếu company_name → 422
[OK]  email trùng → 409  "Email '...' đã được sử dụng"
[OK]  password < 6 ký tự → 422

=== POST /api/auth/login ===
[OK]  login đúng → 200, JWT bắt đầu eyJhbGci...
[OK]  sai password → 401
[OK]  email không tồn tại → 401
[OK]  login admin (seed data) → 200

=== GET /api/auth/me ===
[OK]  token hợp lệ → 200, email khớp, không có password
[OK]  không có token → 401
[OK]  token giả → 401
[OK]  admin token → 200, role=admin

KẾT QUẢ: 23 OK  |  0 FAIL  |  tổng 23
```

---

## 8. Dùng token trong API khác

```python
# app/routers/ten_router.py
from app.core.security import get_current_user

@router.get("/data-rieng-tu")
def get_private_data(current_user=Depends(get_current_user)):
    # current_user là object User từ DB
    # current_user.id, current_user.role, current_user.email...
    return {"message": f"Xin chào {current_user.full_name}"}
```

Phân quyền theo role:
```python
from fastapi import HTTPException, status

@router.post("/chi-admin")
def admin_only(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ admin mới được dùng chức năng này"
        )
    # xử lý logic admin...
```

---

## 9. Tài khoản seed data để test

| Email | Password (plain) | Role |
|-------|-----------------|------|
| admin@tuyendung.com | admin123@ | admin |
| hr1@tuyendung.com | hr1@ | employer |
| hr2@tuyendung.com | hr2@ | employer |
| hr3@tuyendung.com | hr3@ | employer |
| hr5@tuyendung.com | hr5@ | employer |
| ungvien1@gmail.com | ungvien1@ | candidate |
| ungvien2@gmail.com | ungvien2@ | candidate |
| ungvien3@gmail.com | ungvien3@ | candidate |
| ungvien4@gmail.com | ungvien4@ | candidate |
| ungvien5@gmail.com | ungvien5@ | candidate |
| ungvien15@gmail.com | ungvien15@ | candidate |

> Password trong DB đã là bcrypt hash. Nếu reset DB, chạy lại `sql/init.sql`.

---

## 10. Lỗi hay gặp

| Lỗi | Nguyên nhân | Cách sửa |
|-----|------------|----------|
| `ValueError: Invalid salt` khi login | Password DB vẫn plain-text, chưa bcrypt | Bỏ comment `DROP TABLE` trong `init.sql`, chạy lại |
| `Table 'app_db.companies' doesn't exist` | Chưa có bảng companies | Chạy lại `sql/init.sql` |
| `401` dù đã gắn token trên Swagger | Token hết hạn (1440 phút) | Đăng nhập lại, copy token mới vào Authorize |
| `422` khi register employer | Thiếu `company_name` | Thêm `"company_name": "Tên công ty"` vào body |
| `ModuleNotFoundError: No module named 'jose'` | Chưa cài thư viện | `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'bcrypt'` | Chưa cài thư viện | `pip install -r requirements.txt` |
| `JWT_SECRET` vẫn là giá trị mặc định | Chưa sửa `.env` | Thay bằng chuỗi random: `python -c "import secrets; print(secrets.token_hex(32))"` |

