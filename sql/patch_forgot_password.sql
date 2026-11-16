-- Migration: Thêm bảng password_reset_tokens và cột token_version cho users
-- Phục vụ tính năng Quên mật khẩu & Hủy phiên đăng nhập cũ

-- 1. Thêm cột token_version vào bảng users
ALTER TABLE users ADD COLUMN token_version INT NOT NULL DEFAULT 1;

-- 2. Tạo bảng lưu mã đặt lại mật khẩu
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    used_at DATETIME NULL,
    attempts INT NOT NULL DEFAULT 0,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(255) NULL,
    CONSTRAINT fk_prt_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_prt_user_id (user_id),
    INDEX idx_prt_token_hash (token_hash),
    INDEX idx_prt_expires_at (expires_at),
    INDEX idx_prt_is_used (is_used)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
