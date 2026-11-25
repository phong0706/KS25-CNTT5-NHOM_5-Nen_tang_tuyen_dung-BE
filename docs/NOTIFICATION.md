# Hướng dẫn: Module Thông báo (Notification)

Task: Hàm thông báo dùng chung `create_notification()` + API danh sách / số chưa đọc / đánh dấu đã đọc.
Ngày thực hiện: 15/11/2026 — Nhóm 5 RIKKEILAB HN-KS25-CNTT5

---

## 1. Danh sách API đã làm

Tất cả endpoint đều bắt đầu bằng `/api/notifications` và **yêu cầu đăng nhập** (Bearer token).

| Method | URL | Mô tả | Auth |
|--------|-----|--------|------|
| GET | `/api/notifications` | Danh sách thông báo của tôi (có phân trang) | Bearer token |
| GET | `/api/notifications/unread-count` | Số thông báo chưa đọc (badge chuông) | Bearer token |
| POST | `/api/notifications/read` | Đánh dấu đã đọc nhiều thông báo (theo danh sách id) | Bearer token |
| POST | `/api/notifications/read-all` | Đánh dấu đã đọc toàn bộ | Bearer token |
| POST | `/api/notifications/{id}/read` | Đánh dấu đã đọc 1 thông báo | Bearer token |
| DELETE | `/api/notifications` | Xoá toàn bộ thông báo của tôi | Bearer token |

### Query params của `GET /api/notifications`

| Param | Kiểu | Mặc định | Mô tả |
|-------|------|----------|------|
| `unread_only` | bool | `false` | Chỉ lấy thông báo chưa đọc |
| `type` | string | — | Lọc theo loại thông báo (vd: `application_submitted`) |
| `page` | int | `1` | Trang hiện tại |
| `page_size` | int | `10` | Số bản ghi mỗi trang (tối đa 50) |

---

## 2. Các file đã tạo / sửa

### File mới tạo

```
backend/app/
├── models/
│   └── notification.py      ← SQLAlchemy map bảng notifications
├── schemas/
│   └── notification.py      ← Pydantic: NotificationOut, NotificationListOut, ...
├── services/
│   └── notification.py      ← HÀM DÙNG CHUNG create_notification() + helpers
└── routers/
    └── notifications.py     ← 6 endpoint: list, unread-count, read, read-all, read-1, delete

backend/sql/
└── patch_notifications.sql  ← CREATE TABLE notifications (cho nhóm chạy tay)

backend/tests/
├── test_notifications.py           ← 3 test: 401, list+unread+read, không đọc chéo của user khác
└── test_notification_fe_be_sync.py ← 3 test: link đúng route FE, shape response, endpoint đọc
```

### File mới tạo (Frontend)

```
frontend/js/
├── services/
│   └── notificationApi.js     ← Lớp gọi API thông báo + map icon/màu theo `type`
└── components/
    └── notificationBell.js    ← Nút chuông + panel danh sách (dùng chung mọi trang)

frontend/css/
└── notification.css           ← Style nút chuông, badge, panel, item (dùng design token)
```

### File đã sửa

| File | Thay đổi |
|------|----------|
| `app/models/__init__.py` | Import `Notification` để `create_all` nhìn thấy |
| `app/main.py` | `include_router(notifications.router, prefix="/api")` |
| `app/routers/candidate_apply.py` | Gọi `notify_application_submitted()` khi ứng viên nộp hồ sơ |
| `app/routers/candidate_detail.py` | Gọi `create_notification()` khi ứng viên rút hồ sơ |
| `app/routers/employer_applications.py` | Gọi `notify_application_status_changed()` + `notify_interview()` |
| `app/routers/employer_jobs.py` | Gọi `notify_job_status_changed()` khi tin đổi trạng thái (duyệt/từ chối) |
| `app/services/notification.py` | Link trỏ đúng route FE (`/pages/...?...`); log phân biệt trùng key vs lỗi FK |

### File đã sửa (Frontend)

| File | Thay đổi |
|------|----------|
| `frontend/js/components/siteHeader.js` | Thêm `<div id="site-notif-host">` vào khối `.site-header-actions` |
| `frontend/js/siteHeaderBoot.js` | `mountNotificationBell()` khi đã đăng nhập (import thêm `resolveSiteRoot`) |
| `frontend/css/style.css` | `@import url("./notification.css")` — áp dụng cho mọi trang, không sửa 30+ file HTML |
| `frontend/js/pages/candidateApplications.js` | Đọc `?app_id=` để mở thẳng hồ sơ từ thông báo |
| `frontend/js/pages/employerApplications.js` | Đọc `?app_id=` để mở thẳng modal chi tiết hồ sơ |
| `frontend/js/pages/employerJobs.js` | Đọc `?job_id=` để tô đậm tin tuyển dụng được trỏ tới |

### File kiểm thử (Frontend)

```
test_notification_bell_e2e.mjs  ← Puppeteer E2E: badge, panel, đánh dấu đã đọc, KHÔNG trùng chuông
```

---

## 3. Model `Notification`

**Bảng:** `notifications` (tự tạo bởi `Base.metadata.create_all()` khi khởi động server).

| Cột | Kiểu | Ràng buộc | Ý nghĩa |
|-----|------|-----------|----------|
| `id` | INT | PK, auto_increment | id thông báo |
| `user_id` | INT | FK → `users.id` ON DELETE CASCADE | **Người nhận** thông báo |
| `actor_id` | INT | FK → `users.id` ON DELETE SET NULL, NULL | Người gây ra sự kiện (người gửi) |
| `type` | VARCHAR(50) | NOT NULL | Loại thông báo (xem bảng dưới) |
| `title` | VARCHAR(255) | NOT NULL | Tiêu đề hiển thị |
| `message` | TEXT | NULL | Nội dung chi tiết |
| `link` | VARCHAR(500) | NULL | Đường dẫn FE mở khi bấm vào thông báo |
| `ref_type` | VARCHAR(50) | NULL | Loại đối tượng liên quan (`application`, `job`…) |
| `ref_id` | INT | NULL | id đối tượng liên quan |
| `is_read` | TINYINT(1) | NOT NULL, default 0 | 0 = chưa đọc, 1 = đã đọc |
| `read_at` | DATETIME | NULL | Thời điểm đánh dấu đã đọc |
| `dedupe_key` | VARCHAR(120) | NULL, UNIQUE(user_id, dedupe_key) | Khoá chống tạo trùng |
| `created_at` | DATETIME | NOT NULL, default CURRENT_TIMESTAMP | Thời điểm tạo |

**Index:** `idx_notifications_user_created`, `idx_notifications_user_unread`, `idx_notifications_ref`.

## 4. Hàm dùng chung `create_notification()`

**File:** `app/services/notification.py`

```python
from app.services.notification import create_notification, NotificationType

create_notification(
    db,                      # Session SQLAlchemy (dùng chung transaction với nghiệp vụ)
    user_id=employer.id,     # BẮT BUỘC — người nhận
    type=NotificationType.APPLICATION_SUBMITTED,
    title="Có hồ sơ mới",   # Bỏ trống -> lấy tiêu đề mặc định theo `type`
    message="Nguyễn Văn A vừa ứng tuyển vị trí Frontend Developer.",
    actor_id=candidate.id,   # Người gửi (có thể None)
    link="/employer/applications/12",
    ref_type="application",
    ref_id=12,
    dedupe_key="application:12:submitted",
    commit=False,            # Mặc định: để transaction của caller quyết định
)
```

### Tham số

| Tham số | Bắt buộc | Mô tả |
|---------|-----------|-------|
| `db` | ✔ | SQLAlchemy Session |
| `user_id` | ✔ | id người **nhận** thông báo |
| `type` | ✔ | Loại thông báo (xem `NotificationType`) |
| `title` | ✗ | Tiêu đề; bỏ trống → dùng tiêu đề mặc định theo `type` |
| `message` | ✗ | Nội dung chi tiết |
| `actor_id` | ✗ | id người gây ra sự kiện |
| `link` | ✗ | Đường dẫn FE mở khi bấm |
| `ref_type` / `ref_id` | ✗ | Con trỏ tới đối tượng liên quan |
| `dedupe_key` | ✗ | Khoá chống trùng, duy nhất theo `user_id` |
| `commit` | ✗ | `True` = tự commit; `False` (mặc định) = dùng chung transaction của caller |

### Kiểu thông báo (`NotificationType`)

| Hằng số | Giá trị | Chiều |
|----------|----------|-------|
| `APPLICATION_SUBMITTED` | `application_submitted` | Ứng viên → NTD |
| `APPLICATION_STATUS_CHANGED` | `application_status_changed` | NTD → ứng viên |
| `APPLICATION_INTERVIEW` | `application_interview` | NTD → ứng viên |
| `JOB_SUBMITTED` | `job_submitted` | NTD (hệ thống) |
| `JOB_APPROVED` | `job_approved` | Hệ thống → NTD |
| `JOB_REJECTED` | `job_rejected` | Hệ thống → NTD |
| `CV_UPLOADED` / `CV_DELETED` | `cv_uploaded` / `cv_deleted` | CV |
| `SYSTEM` | `system` | Hệ thống |

> Dùng hằng số (không dùng `ENUM` trong MySQL) để thêm loại mới **không phải ALTER bảng**.

### Hàm helper theo sự kiện

| Hàm | Dùng khi |
|-----|----------|
| `notify_application_submitted(db, employer_id, candidate_name, job_title, application_id, candidate_id)` | Ứng viên nộp hồ sơ |
| `notify_application_status_changed(db, candidate_id, status, status_label, job_title, application_id, actor_id, note)` | NTD đổi trạng thái hồ sơ |
| `notify_job_status_changed(db, employer_id, job_id, job_title, status, status_label, actor_id, note)` | Tin tuyển dụng đổi trạng thái |
| `notify_interview(db, candidate_id, application_id, job_title, interview_at, interview_mode, interview_location, actor_id)` | Lên lịch phỏng vấn |

### 3 nguyên tắc quan trọng

1. **Không bao giờ làm hỏng nghiệp vụ chính.**
   Hàm bọc mọi lỗi DB trong `try/except` và trả `None`. Lỗi tạo thông báo **KHÔNG** làm fail
   request nộp hồ sơ / đổi trạng thái.

2. **Dùng SAVEPOINT (nested transaction), không `rollback()` thật.**
   `with db.begin_nested():` → nếu insert lỗi (FK violation, trùng `dedupe_key`), chỉ rollback

## 5. Luồng xử lý chi tiết

### 5.1. Ứng viên nộp hồ sơ → NTD nhận thông báo "Có hồ sơ mới"

**Endpoint:** `POST /api/jobs/{job_id}/apply` → `app/routers/candidate_apply.py`

```
Ứng viên gửi POST /api/jobs/{job_id}/apply
        │
        ├─ 1. Kiểm tra idempotency_key → nếu đã nộp, trả kết quả cũ, KHÔNG tạo thông báo lần 2
        ├─ 2. Kiểm tra đã ứng tuyển chưa (active_flag = 1) → 409
        ├─ 3. Kiểm tra tin đang tuyển (status = published) + hạn nộp → 422
        ├─ 4. Kiểm tra CV thuộc về ứng viên → 422
        ├─ 5. INSERT Application (status = submitted, active_flag = 1)
        ├─ 6. db.flush()  → lấy app.id
        ├─ 7. INSERT ApplicationStatusHistory (submitted)  → timeline
        │
        ├─ 8. ★ GỌI notify_application_submitted(...)   ← TRƯỚC db.commit()
        │        │
        │        ├─ dedupe_key = "application:{app.id}:submitted"
        │        ├─ Kiểm tra trùng → nếu trùng thì bỏ qua (return None)
        │        ├─ SAVEPOINT: INSERT notifications
        │        │     user_id = job.employer_id   ← NGƯỜI NHẬN
        │        │     actor_id = candidate.id     ← NGƯỜI GỬI
        │        │     type     = application_submitted
        │        │     title    = "Có hồ sơ ứng tuyển mới"
        │        │     message  = "{tên ứng viên} vừa ứng tuyển vị trí {tên tin}."
        │        │     link     = "/employer/applications/{app.id}"
        │        │     ref_type = "application", ref_id = app.id
        │        └─ Lỗi → log + bỏ qua, KHÔNG ảnh hưởng nộp hồ sơ
        │
        ├─ 9. db.commit()   ← hồ sơ + timeline + thông báo commit CÙNG LẦN
        └─ 10. Trả ApplyOut { application_id, status: "submitted", message }
```

**Kết quả:** NTD mở app thấy badge chuông = 1, bấm vào thông báo → điều hướng tới
`/employer/applications/{app.id}`.

**Vì sao gọi TRƯỚC `db.commit()`?**
Nếu commit lỗi → hồ sơ, timeline, thông báo cùng rollback. Không có "thông báo ma" cho
hồ sơ không tồn tại. Nếu gọi SAU commit → thông báo có thể tồn tại dù hồ sơ đã fail.

---

### 5.2. NTD đổi trạng thái hồ sơ → ứng viên nhận thông báo

Nhà tuyển dụng dùng `GET /api/employer/applications?job_id={job_id}&status=REVIEWING` để lọc hồ sơ theo tin và trạng thái. Cả hai API kiểm tra quyền qua công ty của tin tuyển dụng. Tin hoặc hồ sơ ngoài phạm vi công ty trả về `404`.

Gửi `PATCH /api/employer/applications/{app_id}/status` với trạng thái mới và ghi chú tối đa 500 ký tự.

```json
{ "status": "REVIEWING", "note": "CV phù hợp, mời xem xét" }
```

Các bước hợp lệ là `SUBMITTED → REVIEWING → INTERVIEW`, rồi từ `INTERVIEW` sang `OFFERED` hoặc `REJECTED`. Trạng thái không hợp lệ trả về `422`. Chuyển đổi ngoài luồng trả về `409`. Hồ sơ dùng trạng thái chữ thường tiếp tục dùng định dạng đó, với `screening` tương ứng `REVIEWING`.

Khi cập nhật thành công, API lưu trạng thái, ghi chú, lịch sử và thông báo `application_status_changed` trong cùng giao dịch. Hàm `notify_application_status_changed` gửi thông báo đến tài khoản ứng viên gắn với hồ sơ, kèm liên kết mở hồ sơ và dữ liệu trạng thái. Nếu không tạo được thông báo, giao dịch được hoàn tác.

### 5.3. Lên lịch phỏng vấn → ứng viên nhận lời mời

**Endpoint:** `POST /api/employer/applications/{app_id}/interview`

```
NTD gửi POST /api/employer/applications/{app_id}/interview
body: { "interview_at": "...", "interview_mode": "Google Meet", "interview_location": "..." }
        │
        ├─ 1. Kiểm tra hồ sơ thuộc NTD → 404
        ├─ 2. UPDATE interview_at / interview_mode / interview_location, status = "interview"
        ├─ 3. INSERT ApplicationStatusHistory ("interview")
        ├─ 4. ★ GỌI notify_interview(...)   ← TRƯỚC db.commit()
        ├─ 5. db.commit()
        └─ 6. Trả { message: "Đã lên lịch hẹn phỏng vấn thành công!", interview_at }
```

---

### 5.4. Ứng viên rút hồ sơ → NTD nhận thông báo

**Endpoint:** `POST /api/candidate/applications/{app_id}/withdraw` → `app/routers/candidate_detail.py`

```
Ứng viên gửi POST /api/candidate/applications/{app_id}/withdraw
        │
        ├─ 1. Kiểm tra hồ sơ thuộc ứng viên → 404
        ├─ 2. Kiểm tra trạng thái hiện tại có phải terminal không → 409
        ├─ 3. UPDATE status = "withdrawn", active_flag = NULL, withdraw_reason, withdrawn_at
        ├─ 4. INSERT ApplicationStatusHistory ("withdrawn")
        ├─ 5. ★ GỌI create_notification() cho NTD
        │        user_id   = job.employer_id   ← NGƯỜI NHẬN (NTD)
        │        actor_id  = current_user.id   ← NGƯỜI GỬI (ứng viên)
        │        title     = "Ứng viên đã rút hồ sơ"
        │        message   = "{tên ứng viên} đã rút hồ sơ ứng tuyển vị trí {tên tin}."
        │                   + (" Lý do: {lý do}" nếu có)
        ├─ 6. db.commit()
        └─ 7. Trả { message: "Rút hồ sơ thành công.", status: "withdrawn" }
```

> Ứng viên **không** nhận thông báo cho hành động của chính mình.

---

### 5.5. Tin tuyển dụng đổi trạng thái (được duyệt / từ chối)

**Endpoint:** `PATCH /api/employer/jobs/{job_id}/status` → `app/routers/employer_jobs.py`

```
NTD gửi PATCH /api/employer/jobs/{job_id}/status
body: { "action": "submit" }   # draft → pending (gửi duyệt)
        │
        ├─ 1. Kiểm tra action hợp lệ trong TRANSITIONS → 400
        ├─ 2. Kiểm tra tin thuộc NTD → 403
        ├─ 3. Kiểm tra trạng thái hiện tại cho phép chuyển → 409
        ├─ 4. UPDATE Job.status (+ published_at nếu chuyển sang published)
        │
        ├─ 5. ★ GỌI notify_job_status_changed(...)   ← TRƯỚC db.commit()
        │        type tự chọn theo status:
        │          "published" -> job_approved   ("Tin tuyển dụng đã được duyệt")
        │          "rejected"  -> job_rejected   ("Tin tuyển dụng chưa được duyệt")
        │          còn lại     -> job_submitted
        │        dedupe_key = "job:{job.id}:status:{status}"
        │
        ├─ 6. db.commit()
        └─ 7. Trả JobActionResultOut { id, status, status_label, undo_action, message }
```

**Bảng chuyển trạng thái tin (`TRANSITIONS` trong `employer_jobs.py`):**

| Action | Từ | Sang | Ý nghĩa |
|--------|----|------|---------|

## 6. Luồng đọc thông báo (API)

### 6.1. `GET /api/notifications`

```
FE gửi GET /api/notifications?unread_only=true&page=1&page_size=10
Header: Authorization: Bearer <token>
        │
        ├─ 1. get_current_user → không có token → 401
        ├─ 2. base = SELECT * FROM notifications WHERE user_id = current_user.id
        │      + điều kiện unread_only / type nếu có
        ├─ 3. total = COUNT(*) trên base
        ├─ 4. Lấy trang: ORDER BY created_at DESC, id DESC LIMIT/OFFSET
        ├─ 5. _actor_names(): 1 query lấy tên người gửi cho cả trang (tránh N+1)
        └─ 6. Trả NotificationListOut
```

**Response:**

```json
{
  "items": [
    {
      "id": 7,
      "type": "application_submitted",
      "title": "Có hồ sơ ứng tuyển mới",
      "message": "Nguyễn Văn A vừa ứng tuyển vị trí Frontend Developer.",
      "link": "/employer/applications/12",
      "ref_type": "application",
      "ref_id": 12,
      "is_read": false,
      "read_at": null,
      "actor_id": 29,
      "actor_name": "Nguyễn Văn A",
      "created_at": "2026-11-15T10:30:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "total_pages": 1,
  "unread_count": 1
}
```

> `unread_count` trả kèm luôn để FE tiện hiển thị badge mà không cần gọi thêm endpoint.

### 6.2. `GET /api/notifications/unread-count`

```
FE gửi GET /api/notifications/unread-count
        │
        ├─ 1. get_current_user → 401 nếu chưa đăng nhập
        ├─ 2. SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0
        └─ 3. Trả { "unread_count": 3 }
```

### 6.3. `POST /api/notifications/read` (nhiều thông báo)

```
FE gửi POST /api/notifications/read
body: { "notification_ids": [7, 8, 9] }
        │
        ├─ 1. get_current_user → 401
        ├─ 2. ★ mark_as_read(db, current_user.id, [7,8,9])
        │      UPDATE notifications
        │         SET is_read = 1, read_at = NOW()
        │       WHERE user_id = current_user.id     ← BẮT BUỘC
        │         AND id IN (7,8,9)
        │         AND is_read = 0                  ← chỉ đếm bản ghi thực sự đổi
        ├─ 3. db.commit()
        └─ 4. Trả { updated, unread_count, message }

## 7. Bảo mật

| Quy tắc | Thực hiện ở đâu |
|---------|-----------------|
| Chưa đăng nhập → **401** | `get_current_user` trong mọi endpoint |
| Chỉ thấy thông báo **của chính mình** | Mọi query đều lọc `user_id = current_user.id` |
| Không đánh dấu đã đọc được thông báo của người khác | `UPDATE ... WHERE user_id = current_user.id AND id IN (...)` → `updated = 0` |
| Thông báo của user bị xoá tài khoản → tự xoá | FK `ON DELETE CASCADE` |
| Người gửi bị xoá tài khoản → giữ thông báo, set `actor_id = NULL` | FK `ON DELETE SET NULL` |

**Test đã viết** (`tests/test_notifications.py`):
- `test_notifications_require_auth` — 401 cho cả 5 endpoint
- `test_notification_list_and_unread_count` — tạo → list → unread-count → đánh dấu đã đọc → read-all → xoá
- `test_cannot_mark_other_users_notification_read` — user B đánh dấu thông báo của user A → `updated = 0`, thông báo A vẫn chưa đọc

Chạy test:
```bash
cd backend
.venv\Scripts\python.exe -m pytest tests\test_notifications.py -q
```

---

## 8. Frontend — đồng bộ với Backend

> **Frontend đã được cài đặt đầy đủ.** Nếu nhóm muốn tự viết lại hoặc mở rộng, đọc phần này
> để biết đúng cách gọi API và cách render.

### 8.1. Kiến trúc FE

```
frontend/js/services/notificationApi.js     ← Lớp gọi API (dùng window.api → tự gắn Bearer)
        │
        ▼
frontend/js/components/notificationBell.js  ← Nút chuông + panel (mount vào #site-notif-host)
        │
        ├── GET  /api/notifications/unread-count   → badge
        ├── GET  /api/notifications                 → danh sách khi mở panel
        ├── POST /api/notifications/{id}/read       → bấm 1 thông báo
        └── POST /api/notifications/read-all        → "Đánh dấu đã đọc tất cả"

frontend/css/notification.css                ← Style (đã @import trong style.css)
```

**Điểm gắn chuông:** `siteHeaderBoot.js` gọi `mountNotificationBell()` khi đã đăng nhập.
Site header dùng chung cho **mọi** trang — kể cả trang nhà tuyển dụng/admin (vì
`layout.js` render site header bên trong `.admin-shell`). Vì vậy **chỉ có đúng 1 chuông**
trên mọi trang, không gắn thêm vào topbar.

### 8.2. Dùng lại từ module khác (không cần viết lại)

```javascript
import { fetchUnreadCount, markOneRead, markAllRead, onNotificationsChanged }
  from "../services/notificationApi.js";

// Đọc số chưa đọc
const n = await fetchUnreadCount();

// Đánh dấu đã đọc rồi điều hướng
await markOneRead(item.id);
window.location.href = item.link;

// Lắng nghe khi badge đổi (để cập nhật UI khác)
const off = onNotificationsChanged((count) => console.log("badge:", count));
```

### 8.3. Badge chuông (nếu muốn tự viết)

```javascript
// Gọi 1 lần khi load trang + lặp lại mỗi 30-60 giây
async function refreshUnreadCount() {
  const res = await window.api.get("/notifications/unread-count");
  const badge = document.querySelector(".notif-bell-badge");
  badge.textContent = res.unread_count > 99 ? "99+" : String(res.unread_count);
  badge.hidden = res.unread_count <= 0;
}
```

> Luôn dùng `window.api.get(...)` (axios + interceptor Bearer + xử lý 401) thay vì `fetch()` thô,
> để không phải tự gắn token và không phải tự xử lý 401.

### 8.4. Danh sách thông báo

```javascript
const { items, total, page, page_size, total_pages, unread_count } =
  await window.api.get("/notifications", { params: { page: 1, page_size: 20 } });
```

### 8.5. Bấm vào 1 thông báo → đánh dấu đã đọc + điều hướng

```javascript
async function onNotificationClick(item) {
  if (!item.is_read) await markOneRead(item.id);
  if (item.link) window.location.href = item.link;
}
```

### 8.6. Đánh dấu đã đọc tất cả

```javascript
await markAllRead();
```

### 8.7. Icon / màu theo loại (`type`)

Đã định nghĩa trong `notificationApi.js` — khớp 1-1 với `NotificationType` ở backend:

```javascript
export const NOTIFICATION_STYLE = {
  application_submitted:      { icon: "📄", tone: "info",    label: "Hồ sơ mới" },
  application_status_changed: { icon: "🔄", tone: "warning", label: "Cập nhật hồ sơ" },
  application_interview:      { icon: "🎯", tone: "teal",    label: "Phỏng vấn" },
  job_submitted:              { icon: "📤", tone: "info",    label: "Gửi tin" },
  job_approved:               { icon: "✅", tone: "success", label: "Tin được duyệt" },
  job_rejected:               { icon: "❌", tone: "danger",  label: "Tin bị từ chối" },
  cv_uploaded:                { icon: "📎", tone: "info",    label: "CV" },
  cv_deleted:                 { icon: "🗑️", tone: "muted",   label: "CV" },
  system:                     { icon: "🔔", tone: "neutral", label: "Hệ thống" },
};
```

---

## 8b. Đồng bộ FE ↔ BE (bảng đối chiếu)

| BE (`app/services/notification.py`) | Link BE sinh ra | FE xử lý |
|------------------------------------|-----------------|-----------|
| `notify_application_submitted()` | `/pages/employer/applications.html?app_id={id}` | `employerApplications.js` đọc `?app_id=` → mở modal chi tiết |
| `notify_application_status_changed()` | `/pages/candidate/applications.html?app_id={id}` | `candidateApplications.js` đọc `?app_id=` → mở drawer chi tiết |
| `notify_interview()` | `/pages/candidate/applications.html?app_id={id}` | Như trên |
| `notify_job_status_changed()` | `/pages/employer/jobs.html?job_id={id}` | `employerJobs.js` đọc `?job_id=` → tô đậm tin |

**Quy ước:** `link` luôn bắt đầu bằng `/pages/...` (đường dẫn tương đối từ thư mục `frontend/`),
kèm query param định danh đối tượng cần mở. FE ghép `root` (từ `resolveSiteRoot()`) vào
trước khi chuyển trang.

**Kiểm tra tự động:** `backend/tests/test_notification_fe_be_sync.py` assert rằng mọi link
BE sinh ra đều trỏ tới một route trong danh sách route FE thật, và response có đủ key mà
FE đọc.

```

---

## 9. Cách dùng hàm thông báo trong module MỚI (mẫu cho nhóm)

```python
# 1. Import
from app.services.notification import create_notification, NotificationType

# 2. Trong router, SAU khi thực hiện thay đổi nghiệp vụ và TRƯỚC db.commit():
create_notification(
    db,
    user_id=<người nhận>,
    actor_id=current_user.id,
    type=NotificationType.SYSTEM,     # hoặc thêm hằng số mới trong NotificationType
    title="Tiêu đề hiển thị",
    message="Nội dung chi tiết.",
    link="/duong-dan-fe",
    ref_type="xxx",
    ref_id=yyy,
    dedupe_key="xxx:{yyy}:{event}",   # chống trùng
)
```

**Checklist khi thêm thông báo cho module mới:**

- [ ] Thêm hằng số mới vào `NotificationType` (nếu cần loại mới)
- [ ] Gọi **trước** `db.commit()` (để cùng transaction)
- [ ] Truyền `dedupe_key` để không tạo trùng khi request lặp lại
- [ ] Không bọc try/except ở call site — hàm đã tự bắt lỗi, không ném ra ngoài
- [ ] `user_id` = người **nhận**, `actor_id` = người **gửi** (dễ nhầm!)

---

## 10. Tạo bảng thủ công (nếu chưa dùng `create_all`)

Bảng `notifications` **được SQLAlchemy tự tạo** khi khởi động server
(`Base.metadata.create_all()` trong `app/main.py`). Nhưng nếu nhóm muốn tạo bằng tay:

1. Mở MySQL Workbench → kết nối database `app_db`
2. `File → Open SQL Script...` → chọn `backend/sql/patch_notifications.sql`
3. Bấm ⚡ (Execute)

Script có sẵn phần dữ liệu mẫu (comment) để demo.

---

## 11. Xử lý sự cố

| Triệu chứng | Nguyên nhân | Cách sửa |
|-------------|-------------|----------|
| `Table 'app_db.notifications' doesn't exist` | Chưa tạo bảng | Khởi động lại server (auto `create_all`) hoặc chạy `sql/patch_notifications.sql` |
| `IntegrityError` khi tạo thông báo | Trùng `dedupe_key` | Đã được xử lý tự động (bỏ qua, trả `None`). Xem log `[NOTIFICATION]` |
| Badge không tăng sau khi nộp hồ sơ | Chưa restart server sau khi thêm code | Restart `uvicorn app.main:app --reload` |
| 401 khi gọi API thông báo | Thiếu header `Authorization: Bearer <token>` | Đăng nhập lại lấy token |
| Thông báo trùng lặp | Truyền `dedupe_key` rỗng | Luôn truyền `dedupe_key` theo quy ước |
| Thông báo không xuất hiện sau khi đổi trạng thái hồ sơ | Gọi hàm **sau** `db.commit()` | Chuyển lệnh gọi lên **trước** `db.commit()` |

---

## 12. Kiểm thử nhanh (không cần FE)

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests\test_notifications.py -v
.venv\Scripts\python.exe -m pytest tests\test_notification_fe_be_sync.py -v
```

Kiểm thử E2E trên trình duyệt thật (cần backend :8000 + static server :5500):

```bash
node test_notification_bell_e2e.mjs
```

Xem API trên Swagger: <http://127.0.0.1:8000/docs> → nhóm **Notifications**.

```

### 6.4. `POST /api/notifications/read-all`

```
→ UPDATE notifications SET is_read = 1, read_at = NOW()
   WHERE user_id = current_user.id AND is_read = 0
→ Trả { updated: N, unread_count: 0, message: "..." }
```

### 6.5. `POST /api/notifications/{notification_id}/read`

Dùng khi người dùng **bấm vào 1 thông báo** trên danh sách → FE gọi endpoint này rồi điều hướng
theo `link`.

### 6.6. `DELETE /api/notifications`

Xoá toàn bộ thông báo của người đang đăng nhập → `{ "deleted": N, "message": "..." }`.

---

| `submit` | `draft` | `pending` | Gửi tin chờ duyệt |
| `withdraw` | `pending` | `draft` | Thu hồi tin về nháp |
| `hide` | `published` | `hidden` | Ẩn tin |
| `close` | `published`, `hidden` | `closed` | Đóng tin |
| `reopen` | `hidden`, `closed` | `published` | Mở lại tin |

> Hiện tại **chưa có** endpoint Admin duyệt tin (`pending → published`).
> Khi module duyệt tin của Admin được làm, chỉ cần gọi
> `notify_job_status_changed(db, employer_id=job.employer_id, status="published", ...)`
> → NTD nhận thông báo "Tin tuyển dụng đã được duyệt".

---


**Lưu ý về `dedupe_key`:** key theo **trạng thái** chứ không phải theo thời điểm.
Nghĩa là nếu hồ sơ chuyển `screening` → `interview` → `screening` lần nữa thì lần 3
**không** tạo thông báo `screening` mới (vì key đã tồn tại). Nếu nhóm muốn mỗi lần chuyển
đều có thông báo, đổi key thành `application:{id}:status:{status}:{timestamp}`.

---

   phần thông báo. Thay đổi nghiệp vụ đang chờ commit trong cùng transaction **không bị mất**.

3. **Chống tạo trùng bằng `dedupe_key`.**
   Trước khi insert, hàm kiểm tra đã tồn tại thông báo cùng `user_id` + `dedupe_key` chưa.
   Có thêm `UNIQUE(user_id, dedupe_key)` ở DB để chống race condition 2 request song song.
   Quy ước `dedupe_key`:
   - `application:{id}:submitted` — hồ sơ mới
   - `application:{id}:status:{status}` — hồ sơ đổi trạng thái
   - `application:{id}:interview` — lời mời phỏng vấn
   - `job:{id}:status:{status}` — tin tuyển dụng đổi trạng thái

---


---
