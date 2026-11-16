# Hướng dẫn: Phân quyền & Kiểm tra quyền sở hữu (Authorization)

Task: Phân quyền theo role + kiểm tra quyền sở hữu tài nguyên + 401/403 rõ ràng + chặn tài khoản khoá.
Ngày thực hiện: 11/11/2026 — Nhóm 5 RIKKEILAB HN-KS25-CNTT5

---

## 1. Tổng quan các dependency & helper

Tất cả đều nằm trong `app/core/security.py` và `app/core/permissions.py`.

| Tên | Loại | Dùng khi | Trả về / Lỗi |
|-----|------|----------|--------------|
| `get_current_user` | Dependency | Bắt buộc đăng nhập | `User` hoặc 401/403 |
| `get_optional_user` | Dependency | Khách vẫn xem được (vd: danh sách việc làm) | `User \| None` |
| `role_required(*roles)` | Factory → Dependency | Giới hạn theo role | `User` hoặc 401/403 |
| `require_owner(owner_id, current_user)` | Helper | Chỉ chủ tin / chủ hồ sơ được sửa | `None` hoặc 403 |
| `is_owner_or_admin(owner_id, current_user)` | Helper | Rẽ nhánh logic (không raise) | `bool` |

---

## 2. Quy tắc mã lỗi (401 / 403)

| Mã | Ý nghĩa | Khi nào trả về |
|----|---------|----------------|
| **401 Unauthorized** | Chưa xác thực được danh tính | Thiếu token / token sai / token hết hạn / user_id không có trong DB |
| **403 Forbidden** | Đã xác thực nhưng không có quyền | Tài khoản bị khoá (`is_active=False`) / sai role / không phải chủ sở hữu |

> **Quy ước:** 401 = "Tôi không biết bạn là ai", 403 = "Tôi biết bạn là ai nhưng bạn không được phép".

---

## 3. Cấu trúc file

```
backend/app/core/
├── security.py      ← get_current_user, get_optional_user, role_required, hash/verify password, JWT
└── permissions.py   ← require_owner, is_owner_or_admin (kiểm tra quyền sở hữu)
```

---

## 4. Import chuẩn — copy dòng này vào đầu router

```python
from app.core.security import get_current_user, get_optional_user, role_required
from app.core.permissions import require_owner, is_owner_or_admin
```

---

## 5. Các kịch bản dùng — copy & paste vào router

### 5.1. Khách vẫn xem được, user đăng nhập thấy thêm tính năng

```python
from app.core.security import get_optional_user

@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),   # ← có thể là None (khách)
):
    jobs = job_crud.get_jobs(db)
    # Nếu đã đăng nhập → hiện thêm "đã lưu tin này chưa"
    if current_user:
        for job in jobs:
            job.is_saved = saved_crud.is_saved(db, user_id=current_user.id, job_id=job.id)
    return jobs
```

### 5.2. Bắt buộc đăng nhập (mọi role)

```python
from app.core.security import get_current_user

@router.get("/me/saved-jobs", response_model=list[SavedJobOut])
def my_saved_jobs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),     # ← bắt buộc, khách → 401
):
    return saved_crud.get_by_user(db, user_id=current_user.id)
```

### 5.3. Giới hạn theo role

```python
from app.core.security import role_required

# Chỉ employer được đăng tin
@router.post("/jobs", response_model=JobOut, status_code=201)
def create_job(
    data: JobCreate,
    db: Session = Depends(get_db),
    current_user=Depends(role_required("employer")),   # ← chỉ employer
):
    return job_crud.create_job(db, data, employer_id=current_user.id)

# Employer HOẶC admin đều được
@router.put("/jobs/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(role_required("employer", "admin")),
):
    ...
```

### 5.4. Chỉ chủ tin / chủ hồ sơ mới được sửa (kiểm tra quyền sở hữu)

```python
from app.core.security import get_current_user
from app.core.permissions import require_owner

@router.put("/jobs/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 1. Lấy tài nguyên từ DB
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy việc làm id={job_id}")

    # 2. Kiểm tra quyền sở hữu — 1 dòng duy nhất, raise 403 nếu không phải chủ
    require_owner(job.employer_id, current_user)

    # 3. Thực hiện sửa
    return job_crud.update_job(db, job, data)
```

> `require_owner` cho phép **admin** sửa/xoá tài nguyên của người khác.
> Nếu chỉ muốn chính chủ (không có ngoại lệ admin), kiểm tra thủ công:
> ```python
> if current_user.id != job.employer_id:
>     raise HTTPException(status_code=403, detail="Không phải chủ tin")
> ```

### 5.5. Rẽ nhánh logic theo quyền (không raise exception)

```python
from app.core.permissions import is_owner_or_admin

@router.get("/jobs/{job_id}", response_model=JobOutDetail)
def get_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy id={job_id}")

    # Chủ tin / admin → thấy cả tin ở trạng thái nháp
    if current_user and is_owner_or_admin(job.employer_id, current_user):
        return job

    # Khách chỉ thấy tin đã duyệt
    if not job.is_approved:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy id={job_id}")
    return job
```

### 5.6. Kết hợp role + ownership

```python
@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(role_required("employer", "admin")),  # lọc role trước
):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy id={job_id}")
    require_owner(job.employer_id, current_user)               # lọc ownership sau
    job_crud.delete_job(db, job)
```

---

## 6. Bảng tra nhanh: chọn dependency nào?

| Yêu cầu endpoint | Dependency dùng |
|------------------|-----------------|
| Ai cũng xem được, đăng nhập thì thấy thêm | `get_optional_user` |
| Phải đăng nhập (bất kỳ role) | `get_current_user` |
| Chỉ employer | `role_required("employer")` |
| Chỉ candidate | `role_required("candidate")` |
| Chỉ admin | `role_required("admin")` |
| Employer + admin | `role_required("employer", "admin")` |
| Phải là chủ tin / chủ hồ sơ mới sửa/xoá | `get_current_user` + `require_owner(...)` |
| Role cụ thể + phải là chủ | `role_required(...)` + `require_owner(...)` |

---

## 7. Tài khoản bị khoá — hành vi

Khi `is_active = False` (admin khoá tài khoản trong DB):

| Endpoint dùng | Kết quả |
|---------------|---------|
| `get_current_user` | **403** "Tài khoản đã bị khoá..." |
| `get_optional_user` | Trả **None** (khách xem bình thường) |
| `role_required(...)` | **403** (vì gọi `get_current_user` bên trong) |
| `POST /api/auth/login` | **403** "Tài khoản đã bị khoá..." (đã có sẵn) |

> Token cũ của tài khoản bị khoá **vẫn hợp lệ về mặt JWT**, nhưng bị chặn ở bước kiểm tra `is_active`.
> Không cần đợi token hết hạn — khoá tài khoản có hiệu lực ngay lập tức.

---

## 8. Checklist gắn phân quyền vào API mới

Khi thêm endpoint mới, kiểm tra đủ các bước:

- [ ] Xác định: khách xem được không? → dùng `get_optional_user`
- [ ] Xác định: cần đăng nhập? → dùng `get_current_user`
- [ ] Xác định: giới hạn role? → dùng `role_required(...)`
- [ ] Có sửa/xoá tài nguyên? → gọi `require_owner(owner_id, current_user)`
- [ ] Test 3 trường hợp bắt buộc:
  1. Không token → kỳ vọng **401** (nếu bắt buộc đăng nhập)
  2. Token đúng role, không phải chủ → kỳ vọng **403**
  3. Token đúng role, là chủ → kỳ vọng **200/201**

---

## 9. Test nhanh bằng curl

```bash
# Lấy token candidate
TOKEN_CAND=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ungvien1@gmail.com","password":"ungvien1@"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Lấy token employer
TOKEN_EMP=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"hr1@tuyendung.com","password":"hr1@"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Không token → 401
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/auth/me

# Candidate cố đăng tin (chỉ employer được) → 403
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/api/jobs \
  -H "Authorization: Bearer $TOKEN_CAND" \
  -H "Content-Type: application/json" -d '{"title":"Test"}'

# Employer A sửa tin của employer B → 403
curl -s -o /dev/null -w "%{http_code}\n" -X PUT http://127.0.0.1:8000/api/jobs/999 \
  -H "Authorization: Bearer $TOKEN_EMP" \
  -H "Content-Type: application/json" -d '{"title":"Sửa tin người khác"}'
```

---

## 10. Các file đã tạo / sửa

| File | Thay đổi |
|------|----------|
| `app/core/security.py` | Thêm `get_optional_user`, `role_required`, kiểm tra `is_active` trong `get_current_user`, tách `_extract_user_id` |
| `app/core/permissions.py` | File mới — `require_owner`, `is_owner_or_admin` |
| `docs/PERMISSIONS.md` | File mới — tài liệu này |

---

## 11. Lỗi hay gặp

| Lỗi | Nguyên nhân | Cách sửa |
|-----|-------------|----------|
| `401` dù đã gắn token | Token hết hạn hoặc tài khoản bị khoá | Đăng nhập lại; nếu vẫn 401 → kiểm tra `is_active` trong DB |
| `403` dù đúng role | Chạm `require_owner` — không phải chủ tài nguyên | Kiểm tra `owner_id` truyền vào đúng chưa (vd: `job.employer_id` chứ không phải `job.id`) |
| `role_required` không nhận nhiều role | Gọi sai cú pháp | Dùng `role_required("employer", "admin")` — nhiều tham số riêng lẻ, **không** truyền list |
| `get_optional_user` trả `None` dù có token | Token sai hoặc tài khoản bị khoá | Kiểm tra token hợp lệ và `is_active=True` trong DB |