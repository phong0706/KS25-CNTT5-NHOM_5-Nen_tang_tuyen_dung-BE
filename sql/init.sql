-- Khởi tạo database app_db + bảng users + companies + dữ liệu mẫu.
-- Cách chạy bằng MySQL Workbench:
--   File > Open SQL Script... > chọn file này > bấm nút tia sét (Execute) > Refresh SCHEMAS.
--
-- ĐỂ RESET SẠCH: bỏ comment 2 dòng DROP TABLE bên dưới rồi chạy lại.

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS app_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE app_db;

-- Bỏ comment để reset sạch dữ liệu:
-- DROP TABLE IF EXISTS companies;
-- DROP TABLE IF EXISTS users;

-- ------------------------------------------------------------------ --
-- Bảng users
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    email       VARCHAR(255) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    full_name   VARCHAR(255) NOT NULL,
    phone       VARCHAR(20),
    role        ENUM('candidate', 'employer', 'admin') NOT NULL DEFAULT 'candidate',
    avatar_url  VARCHAR(500),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_email     (email),
    INDEX idx_role      (role),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------ --
-- Bảng companies
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS companies (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    employer_id INT NOT NULL,
    is_draft    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_company_employer
        FOREIGN KEY (employer_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_employer_id (employer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------ --
-- Dữ liệu mẫu: users
-- Password đã bcrypt (rounds=12). Plain text xem bảng bên dưới.
--
--  Email                  | Password (plain) | Role
--  -----------------------|------------------|----------
--  admin@tuyendung.com    | admin123@        | admin
--  hr1@tuyendung.com      | hr1@             | employer
--  hr2@tuyendung.com      | hr2@             | employer
--  hr3@tuyendung.com      | hr3@             | employer
--  hr5@tuyendung.com      | hr5@             | employer
--  ungvien1@gmail.com     | ungvien1@        | candidate
--  ungvien2@gmail.com     | ungvien2@        | candidate
--  ungvien3@gmail.com     | ungvien3@        | candidate
--  ungvien4@gmail.com     | ungvien4@        | candidate
--  ungvien5@gmail.com     | ungvien5@        | candidate
--  ungvien15@gmail.com    | ungvien15@       | candidate
-- ------------------------------------------------------------------ --
INSERT INTO users (email, password, full_name, phone, role, is_active, is_verified) VALUES

-- Admin
('admin@tuyendung.com',
 '$2b$12$fTGjATGtOEQd1xdBxUcHf.gG33r/SUx7n8OqJz4pyqlltwvBtO8.a',
 'System Admin', '0901234567', 'admin', TRUE, TRUE),

-- Nhà tuyển dụng
('hr1@tuyendung.com',
 '$2b$12$rvnEOqdsVorbZw.ju0PzpurPsVG0O5dsjzdl/beMhITgvqVYztz9W',
 'Trần Thị Bình', '0912345678', 'employer', TRUE, TRUE),

('hr2@tuyendung.com',
 '$2b$12$SihYzvVfoZpRwbfk0OOfROLNeGNM.f8ZaMP/cE4Xie8FkVTkMp07i',
 'Lê Văn Cường', '0923456789', 'employer', TRUE, FALSE),

('hr3@tuyendung.com',
 '$2b$12$CMbnNMubGhH5ZsQeM2F6TOp3kAAd2R6xaO90z3VKck0isX9T8x89C',
 'Nguyễn Thị Dung', '0934567890', 'employer', TRUE, TRUE),

('hr5@tuyendung.com',
 '$2b$12$K3JTG.xfwnw07lO/paT2Q.XPWgoIpH5K7nNYur3qZVSi2KD83U3Ge',
 'Phạm Quốc Hùng', '0945678901', 'employer', TRUE, FALSE),

-- Ứng viên
('ungvien1@gmail.com',
 '$2b$12$I8B6cNsYsGn3245rCkKcXeQmQrlFxJ1KbfEskpdxiLml1Flr4pS/m',
 'Phạm Minh Đức', '0956789012', 'candidate', TRUE, TRUE),

('ungvien2@gmail.com',
 '$2b$12$EyAuxlInwlmQ268.KRtsoO4mT0xRmLsKpH5VuCf92lsGezrWjK9fi',
 'Hoàng Thu Hà', '0967890123', 'candidate', TRUE, TRUE),

('ungvien3@gmail.com',
 '$2b$12$y/biG5MG7CX6sJOBDVXL2uIAu5J1DlBfiaL5iGdI0yRPK9EumH6ym',
 'Vũ Tuấn Kiệt', '0978901234', 'candidate', TRUE, FALSE),

('ungvien4@gmail.com',
 '$2b$12$rM6Fy1JJDTOQlNNEm6bXS.PVUlhOkQ2Ov18J.Pu7zSFocMI.YP2Tq',
 'Đỗ Lan Anh', '0989012345', 'candidate', FALSE, TRUE),

('ungvien5@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Bùi Văn Em', '0990123456', 'candidate', TRUE, FALSE),

('ungvien15@gmail.com',
 '$2b$12$J84tu091we6y0sn82rq7XuFfQbWyw4QCv6qd9zTER3UbzvUqMylxe',
 'Trịnh Thị Phương', '0901234568', 'candidate', TRUE, TRUE)

ON DUPLICATE KEY UPDATE email = email; -- Không thêm trùng nếu chạy lại

-- ------------------------------------------------------------------ --
-- Dữ liệu mẫu: companies (công ty của từng employer)
-- Dùng subquery để không cần biết trước id của user.
-- ------------------------------------------------------------------ --
INSERT INTO companies (name, employer_id, is_draft)
SELECT 'Công ty TNHH Giải Pháp Số ABC', id, FALSE FROM users WHERE email = 'hr1@tuyendung.com'
UNION ALL
SELECT 'Tập đoàn Công Nghệ XYZ', id, FALSE FROM users WHERE email = 'hr2@tuyendung.com'
UNION ALL
SELECT 'Công ty Cổ Phần DEF Tech', id, TRUE  FROM users WHERE email = 'hr3@tuyendung.com'
UNION ALL
SELECT 'Startup GHI Innovation', id, TRUE  FROM users WHERE email = 'hr5@tuyendung.com';

-- ------------------------------------------------------------------ --
-- Kiểm tra kết quả
-- ------------------------------------------------------------------ --
SELECT id, email, full_name, role, is_active, is_verified FROM users;
SELECT id, name, employer_id, is_draft FROM companies;

