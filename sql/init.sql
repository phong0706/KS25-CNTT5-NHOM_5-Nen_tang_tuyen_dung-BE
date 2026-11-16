-- Khởi tạo database app_db + bảng users + companies + dữ liệu mẫu.
-- Cách chạy bằng MySQL Workbench:
--   File > Open SQL Script... > chọn file này > bấm nút tia sét (Execute) > Refresh SCHEMAS.
-- Chạy lại nhiều lần không lỗi (đã có thì bỏ qua).

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS app_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE app_db;

CREATE TABLE IF NOT EXISTS users(
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    role ENUM('candidate', 'employer', 'admin') NOT NULL DEFAULT 'candidate',
    avatar_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    locked_reason VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_email (email),
    INDEX idx_role (role),
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
-- Password đã bcrypt (rounds=12). Plain text tương ứng.
-- ------------------------------------------------------------------ --
INSERT INTO users (email, password, full_name, phone, role, is_active, is_verified) VALUES

-- Admin
('admin@tuyendung.com',
 '$2b$12$fTGjATGtOEQd1xdBxUcHf.gG33r/SUx7n8OqJz4pyqlltwvBtO8.a',
 'System Admin', '0901234567', 'admin', TRUE, TRUE),

-- Nhà tuyển dụng
('employer0@tuyendung.com',
 '$2b$12$rvnEOqdsVorbZw.ju0PzpurPsVG0O5dsjzdl/beMhITgvqVYztz9W',
 'Nguyễn Tấn Phong', '0912345678', 'employer', TRUE, TRUE),

('hr1@tuyendung.com',
 '$2b$12$rvnEOqdsVorbZw.ju0PzpurPsVG0O5dsjzdl/beMhITgvqVYztz9W',
 'Trần Thị Bình', '0923456789', 'employer', TRUE, TRUE),

('hr2@tuyendung.com',
 '$2b$12$SihYzvVfoZpRwbfk0OOfROLNeGNM.f8ZaMP/cE4Xie8FkVTkMp07i',
 'Lê Văn Cường', '0934567890', 'employer', TRUE, FALSE),

('hr3@tuyendung.com',
 '$2b$12$CMbnNMubGhH5ZsQeM2F6TOp3kAAd2R6xaO90z3VKck0isX9T8x89C',
 'Lê Văn Liêm', '0932562890', 'employer', TRUE, FALSE),

('hr4@tuyendung.com',
 '$2b$12$CMbnNMubGhH5ZsQeM2F6TOp3kAAd2R6xaO90z3VKck0isX9T8x89C',
 'Lê Quang Hùng', '0961738289', 'employer', TRUE, FALSE),

('hr5@tuyendung.com',
 '$2b$12$K3JTG.xfwnw07lO/paT2Q.XPWgoIpH5K7nNYur3qZVSi2KD83U3Ge',
 'Nguyễn Thị Tươi', '0934567890', 'employer', TRUE, FALSE),

-- Ứng viên
('ungvien1@gmail.com',
 '$2b$12$I8B6cNsYsGn3245rCkKcXeQmQrlFxJ1KbfEskpdxiLml1Flr4pS/m',
 'Phạm Minh Đức', '0945678901', 'candidate', TRUE, TRUE),

('ungvien2@gmail.com',
 '$2b$12$EyAuxlInwlmQ268.KRtsoO4mT0xRmLsKpH5VuCf92lsGezrWjK9fi',
 'Hoàng Thu Hà', '0956789012', 'candidate', TRUE, TRUE),

('ungvien3@gmail.com',
 '$2b$12$y/biG5MG7CX6sJOBDVXL2uIAu5J1DlBfiaL5iGdI0yRPK9EumH6ym',
 'Vũ Tuấn Kiệt', '0967890123', 'candidate', TRUE, FALSE),

('ungvien4@gmail.com',
 '$2b$12$rM6Fy1JJDTOQlNNEm6bXS.PVUlhOkQ2Ov18J.Pu7zSFocMI.YP2Tq',
 'Đỗ Lan Anh', '0978901234', 'candidate', FALSE, TRUE),

('ungvien5@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Nguyễn Văn An', '0989012345', 'candidate', TRUE, TRUE),

('ungvien6@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Trần Thị Mai', '0901234567', 'candidate', TRUE, FALSE),

('ungvien7@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Lê Hoàng Nam', '0912345678', 'candidate', FALSE, TRUE),

('ungvien8@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Phan Thanh Tùng', '0923456789', 'candidate', TRUE, TRUE),

('ungvien9@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Bùi Thị Hương', '0934567890', 'candidate', FALSE, FALSE),

('ungvien10@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Đặng Quốc Anh', '0941234567', 'candidate', TRUE, TRUE),

('ungvien11@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Trịnh Bảo Ngọc', '0952345678', 'candidate', TRUE, FALSE),

('ungvien12@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Ngô Gia Huy', '0963456789', 'candidate', TRUE, TRUE),

('ungvien13@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Dương Thảo Linh', '0974567890', 'candidate', FALSE, TRUE),

('ungvien14@gmail.com',
 '$2b$12$DM0efAfFmp5Zr9Cn6Yl6Huc7UsaE6qyVVPri8N7.Qpv5vmfh/XB6K',
 'Lý Minh Trí', '0985678901', 'candidate', TRUE, TRUE),

('ungvien15@gmail.com',
 '$2b$12$J84tu091we6y0sn82rq7XuFfQbWyw4QCv6qd9zTER3UbzvUqMylxe',
 'Nguyễn Khánh Vân', '0996789012', 'candidate', TRUE, FALSE)

ON DUPLICATE KEY UPDATE email = email;

-- ------------------------------------------------------------------ --
-- Dữ liệu mẫu: companies (công ty của từng employer)
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