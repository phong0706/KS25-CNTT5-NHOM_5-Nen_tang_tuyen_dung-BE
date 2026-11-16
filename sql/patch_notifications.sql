-- ==================================================================
-- Bảng thông báo dùng chung (notifications)
-- ------------------------------------------------------------------
-- Module: Thông báo (Notification) — Nhóm 5 RIKKEILAB HN-KS25-CNTT5
--
-- LƯU Ý: bảng này cũng được SQLAlchemy tự tạo khi khởi động server
--        (Base.metadata.create_all trong app/main.py). Script này để
--        các bạn chạy thủ công bằng MySQL Workbench / cho Docker.
--
-- Chạy:  mở file này trong MySQL Workbench rồi bấm ⚡ (Execute)
-- ==================================================================

CREATE TABLE IF NOT EXISTS notifications (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT          NOT NULL,              -- người NHẬN thông báo
    actor_id     INT          NULL,                  -- người gây ra sự kiện
    type         VARCHAR(50)  NOT NULL,              -- loại thông báo
    title        VARCHAR(255) NOT NULL,              -- tiêu đề
    message      TEXT         NULL,                  -- nội dung chi tiết
    link         VARCHAR(500) NULL,                  -- đường dẫn FE mở khi bấm
    ref_type     VARCHAR(50)  NULL,                  -- loại đối tượng liên quan
    ref_id       INT          NULL,                  -- id đối tượng liên quan
    is_read      TINYINT(1)   NOT NULL DEFAULT 0,    -- 0 = chưa đọc, 1 = đã đọc
    read_at      DATETIME     NULL,                  -- thời điểm đánh dấu đã đọc
    dedupe_key   VARCHAR(120) NULL,                  -- khoá chống tạo trùng
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_notifications_user
        FOREIGN KEY (user_id)  REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_notifications_actor
        FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL,

    -- Chống tạo trùng thông báo cho cùng 1 người nhận
    UNIQUE KEY uq_notifications_user_dedupe (user_id, dedupe_key),

    -- Index cho các truy vấn chính
    KEY idx_notifications_user_created (user_id, created_at),
    KEY idx_notifications_user_unread  (user_id, is_read),
    KEY idx_notifications_ref          (ref_type, ref_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------------
-- (Tùy chọn) Dữ liệu mẫu để demo — bỏ comment nếu muốn chạy
-- ------------------------------------------------------------------
-- SET @candidate_id = (SELECT id FROM users WHERE email = 'ungvien1@gmail.com' LIMIT 1);
-- SET @employer_id  = (SELECT id FROM users WHERE email = 'hr1@tuyendung.com' LIMIT 1);
--
-- INSERT INTO notifications
--     (user_id, actor_id, type, title, message, link, ref_type, ref_id, is_read, dedupe_key)
-- VALUES
--     (@employer_id, @candidate_id, 'application_submitted',
--      'Có hồ sơ ứng tuyển mới',
--      'Nguyễn Văn A vừa ứng tuyển vị trí Frontend Developer.',
--      '/employer/applications/1', 'application', 1, 0, 'demo:app:1:submitted');
--
-- INSERT INTO notifications
--     (user_id, actor_id, type, title, message, link, ref_type, ref_id, is_read, dedupe_key)
-- VALUES
--     (@candidate_id, @employer_id, 'application_status_changed',
--      'Hồ sơ của bạn đã được cập nhật',
--      'Hồ sơ ứng tuyển vị trí Frontend Developer đã chuyển sang trạng thái ''Đang xem xét''.',
--      '/candidate/applications/1', 'application', 1, 0, 'demo:app:1:status:screening');
