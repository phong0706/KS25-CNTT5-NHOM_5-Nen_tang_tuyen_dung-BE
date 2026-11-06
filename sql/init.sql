-- Tạo database app_db + bảng users + dữ liệu mẫu.
-- Cách chạy bằng MySQL Workbench:
--   File > Open SQL Script... > chọn file này > bấm nút tia sét (Execute) > Refresh ô SCHEMAS.
-- Chạy lại nhiều lần không lỗi (đã có thì bỏ qua), chỉ là dữ liệu mẫu sẽ bị thêm lặp.

SET NAMES utf8mb4; -- để tiếng Việt không bị lỗi font

CREATE DATABASE IF NOT EXISTS app_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE app_db;

-- Xóa bảng cũ nếu muốn reset (bỏ comment dòng dưới)
 -- DROP TABLE IF EXISTS users;

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_email (email),
    INDEX idx_role (role),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO users (email, password, full_name, phone, role, is_active, is_verified) VALUES
-- Admin
('admin@tuyendung.com', 'admin123"', 'System Admin', '0901234567', 'admin', TRUE, TRUE),

-- Nhà tuyển dụng
('admin@tuyendung.com', 'admin123@', 'Nguyễn Tấn Phong', '0912345678', 'employer', TRUE, TRUE),
('hr1@tuyendung.com', 'ahr1@', 'Trần Thị Bình', '0923456789', 'employer', TRUE, TRUE),
('hr2@tuyendung.com', 'hr2@', 'Lê Văn Cường', '0934567890', 'employer', TRUE, FALSE),
('hr3@tuyendung.com', 'hr3@', 'Lê Văn Liêm', '0932562890', 'employer', TRUE, FALSE),
('hr4tuyendung.com', 'hr4@', 'Lê Quang Hùng', '0961738289', 'employer', TRUE, FALSE),
('hr5@tuyendung.com', 'hr5@', 'Nguyễn Thị Tươi', '0934567890', 'employer', TRUE, FALSE),


-- Ứng viên
('ungvien1@gmail.com', 'ungvien1@', 'Phạm Minh Đức', '0945678901', 'candidate', TRUE, TRUE),
('ungvien2@gmail.com', 'ungdung2@', 'Hoàng Thu Hà', '0956789012', 'candidate', TRUE, TRUE),
('ungvien3@gmail.com', 'ungvien3@', 'Vũ Tuấn Kiệt', '0967890123', 'candidate', TRUE, FALSE),
('ungvien4@gmail.com', 'ungvien4@', 'Đỗ Lan Anh', '0978901234', 'candidate', FALSE, TRUE),
('ungvien5@gmail.com', 'ungvien5@', 'Nguyễn Văn An', '0989012345', 'candidate', TRUE, TRUE),
('ungvien6@gmail.com', 'ungvien6@', 'Trần Thị Mai', '0901234567', 'candidate', TRUE, FALSE),
('ungvien7@gmail.com', 'ungvien7@', 'Lê Hoàng Nam', '0912345678', 'candidate', FALSE, TRUE),
('ungvien8@gmail.com', 'ungvien8@', 'Phan Thanh Tùng', '0923456789', 'candidate', TRUE, TRUE),
('ungvien9@gmail.com', 'ungvien9@', 'Bùi Thị Hương', '0934567890', 'candidate', FALSE, FALSE),
('ungvien10@gmail.com', 'ungvien10@', 'Đặng Quốc Anh', '0941234567', 'candidate', TRUE, TRUE),
('ungvien11@gmail.com', 'ungvien11@', 'Trịnh Bảo Ngọc', '0952345678', 'candidate', TRUE, FALSE),
('ungvien12@gmail.com', 'ungvien12@', 'Ngô Gia Huy', '0963456789', 'candidate', TRUE, TRUE),
('ungvien13@gmail.com', 'ungvien13@', 'Dương Thảo Linh', '0974567890', 'candidate', FALSE, TRUE),
('ungvien14@gmail.com', 'ungvien14@', 'Lý Minh Trí', '0985678901', 'candidate', TRUE, TRUE),
('ungvien15@gmail.com', 'ungvien15@', 'Nguyễn Khánh Vân', '0996789012', 'candidate', TRUE, FALSE)

ON DUPLICATE KEY UPDATE email=email; -- Không thêm trùng nếu chạy lại

SELECT * FROM users;
