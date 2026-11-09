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

-- Mật khẩu đã được hash bằng bcrypt (rounds=12).
-- Plain-text tương ứng: admin → admin123@, hr1→hr5 → hr1@→hr5@, hr6 → hr6@, ungvienN → ungvienN@
INSERT INTO users (email, password, full_name, phone, role, is_active, is_verified) VALUES
-- Admin
('admin@tuyendung.com', '$2b$12$uLvxKn7Bw.9K1vsHdTbc6ux1nKrMsIprXDL5W84ea2s.cjYMsS282', 'System Admin', '0901234567', 'admin', TRUE, TRUE),

-- Nhà tuyển dụng
('hr6@tuyendung.com', '$2b$12$TAtNiSbMNag.p5rYSD7j0O9naHjSBOj8ePp5x9VdS0CODrk30d7nW', 'Nguyễn Tấn Phong', '0912345678', 'employer', TRUE, TRUE),
('hr1@tuyendung.com', '$2b$12$dDPD6jsctO2Iq9oHmpyDaeMpVVwaltjBc/tf/N0KbYmsiN/WT.q0e', 'Trần Thị Bình', '0923456789', 'employer', TRUE, TRUE),
('hr2@tuyendung.com', '$2b$12$p9h/1eBlauhKavg/d1/a/eZi7vzIfOkSNHIuBlnAd3IeAtBpEsfmK', 'Lê Văn Cường', '0934567890', 'employer', TRUE, FALSE),
('hr3@tuyendung.com', '$2b$12$qWoLPvt76wivoEDlPdeTwuFpEoT4pDq/mRL.DSDIk9X6Y4Uzvvdne', 'Lê Văn Liêm', '0932562890', 'employer', TRUE, FALSE),
('hr4@tuyendung.com', '$2b$12$X/jqCA8G0ikbLdPP3NPH/enoW558VZNxBsnlGbS50nQTGwRVhagqu', 'Lê Quang Hùng', '0961738289', 'employer', TRUE, FALSE),
('hr5@tuyendung.com', '$2b$12$R50PP/eH1lOw5VqArQG0wexbEGn.w6vzmRXzBQbtPZXAU806PKgVa', 'Nguyễn Thị Tươi', '0935567890', 'employer', TRUE, FALSE),


-- Ứng viên
('ungvien1@gmail.com', '$2b$12$RMaI9hDi9ylbRo60bpCPC.7kIoD7K8.x1bR4Zg5iDWy.gyQfiJRbO', 'Phạm Minh Đức', '0945678901', 'candidate', TRUE, TRUE),
('ungvien2@gmail.com', '$2b$12$O4jCFgz5ZKgahDSgCI.eW.pmI5qmMKw7PO0WGmebYjZR/MdFhF1mm', 'Hoàng Thu Hà', '0956789012', 'candidate', TRUE, TRUE),
('ungvien3@gmail.com', '$2b$12$prwDHnxddNpuFzCifLN86e0Bx4sNyQf8RD472frhKs58bJ/o8wilO', 'Vũ Tuấn Kiệt', '0967890123', 'candidate', TRUE, FALSE),
('ungvien4@gmail.com', '$2b$12$zs9Wq7OrGvi74YGI1PcGue3I87D9pZDOO4rLY4Tg7meHZ6eSATG5i', 'Đỗ Lan Anh', '0978901234', 'candidate', FALSE, TRUE),
('ungvien5@gmail.com', '$2b$12$GvtZNksCuqELZeeWmSNk7OSOiJvdB/aeBZvS3zyd4JiAh8X0x7Xz.', 'Nguyễn Văn An', '0989012345', 'candidate', TRUE, TRUE),
('ungvien6@gmail.com', '$2b$12$khAV3pTrZjlA.OMQOakBC.LpXtUA/fvy6PPKOqaRyvsdZ3U9vKhAK', 'Trần Thị Mai', '0910234567', 'candidate', TRUE, FALSE),
('ungvien7@gmail.com', '$2b$12$qkTubMll4TDw2JMqhNDk/u5y9o0Ik0YuSn4IAjMVJ650BjergCRG6', 'Lê Hoàng Nam', '0913456789', 'candidate', FALSE, TRUE),
('ungvien8@gmail.com', '$2b$12$TYoXHx8X/ZVytdRnEMD5XeWbQrD//Da1b8itjPazXQCfGsWEhfULe', 'Phan Thanh Tùng', '0924567890', 'candidate', TRUE, TRUE),
('ungvien9@gmail.com', '$2b$12$SCTl0GDMFbwGr164D7UylO6kiDP55MWFkrmtl.5d8CLFU19sSPS/G', 'Bùi Thị Hương', '0936567890', 'candidate', FALSE, FALSE),
('ungvien10@gmail.com', '$2b$12$p5vbq/0nvw1awes4StMzkOV69KP/.N0NNkx.8TSPzPI9fnlSclCRC', 'Đặng Quốc Anh', '0941234567', 'candidate', TRUE, TRUE),
('ungvien11@gmail.com', '$2b$12$aU/QYzAQOmd6tk72Lx45IeWdtAuvWzEl6GwHTEJVjZi5/FaaBw1tK', 'Trịnh Bảo Ngọc', '0952345678', 'candidate', TRUE, FALSE),
('ungvien12@gmail.com', '$2b$12$pyz2VfSz1oiyIgmTZvNg.u8RrWcKtnXsBPLv0pp51zs59IRhGp7US', 'Ngô Gia Huy', '0963456789', 'candidate', TRUE, TRUE),
('ungvien13@gmail.com', '$2b$12$5BgZtizxqfPoI.8B1Tlvt.Vv4riCZSG7O3EsC8ZLljVg4Ey8/mLfG', 'Dương Thảo Linh', '0974567890', 'candidate', FALSE, TRUE),
('ungvien14@gmail.com', '$2b$12$NvWf3PifrRnhRbhdX4uDJOifANFKnGgC2xdhe8u9QBwMwh7VyhZ/O', 'Lý Minh Trí', '0985678901', 'candidate', TRUE, TRUE),
('ungvien15@gmail.com', '$2b$12$v4aS5w9BI6jjraUrSY0f7u4Ef43cd9QradlWPc5cFIDT3gt8aTjb2', 'Nguyễn Khánh Vân', '0996789012', 'candidate', TRUE, FALSE)

ON DUPLICATE KEY UPDATE email=email; -- Không thêm trùng nếu chạy lại

SELECT * FROM users;
