-- Tạo các bảng catalog (industries, locations, skills) và reports + seed dữ liệu mẫu
-- Cách chạy: File > Open SQL Script > chọn file này > Execute > Refresh SCHEMAS

SET NAMES utf8mb4;
USE app_db;

-- ============================================
-- 1. TẠO BẢNG INDUSTRIES (Ngành nghề)
-- ============================================
CREATE TABLE IF NOT EXISTS industries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    INDEX idx_name (name),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 2. TẠO BẢNG LOCATIONS (Địa điểm)
-- ============================================
CREATE TABLE IF NOT EXISTS locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    INDEX idx_name (name),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 3. TẠO BẢNG SKILLS (Kỹ năng)
-- ============================================
CREATE TABLE IF NOT EXISTS skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    INDEX idx_name (name),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 4. TẠO BẢNG REPORTS (Báo cáo vi phạm)
-- ============================================
CREATE TABLE IF NOT EXISTS reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    post_id INT NOT NULL,
    reason TEXT NOT NULL,
    status ENUM('PENDING', 'RESOLVED', 'REJECTED') NOT NULL DEFAULT 'PENDING',
    resolution_result TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_post_id (post_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 5. SEED DỮ LIỆU: 15 NGÀNH NGHỀ
-- ============================================
INSERT INTO industries (name, status) VALUES
('Công nghệ thông tin', 'active'),
('Kinh doanh / Bán hàng', 'active'),
('Marketing / Truyền thông', 'active'),
('Tài chính / Kế toán', 'active'),
('Nhân sự / Hành chính', 'active'),
('Giáo dục / Đào tạo', 'active'),
('Y tế / Chăm sóc sức khỏe', 'active'),
('Xây dựng / Kiến trúc', 'active'),
('Sản xuất / Vận hành', 'active'),
('Du lịch / Khách sạn', 'active'),
('Logistics / Vận tải', 'active'),
('Luật / Pháp lý', 'active'),
('Thiết kế / Nghệ thuật', 'active'),
('Bất động sản', 'active'),
('Nông nghiệp / Lâm nghiệp', 'active')
ON DUPLICATE KEY UPDATE name=name;

-- ============================================
-- 6. SEED DỮ LIỆU: 10 ĐỊA ĐIỂM
-- ============================================
INSERT INTO locations (name, status) VALUES
('Hà Nội', 'active'),
('Hồ Chí Minh', 'active'),
('Đà Nẵng', 'active'),
('Hải Phòng', 'active'),
('Cần Thơ', 'active'),
('Bình Dương', 'active'),
('Đồng Nai', 'active'),
('Khánh Hòa', 'active'),
('Lâm Đồng', 'active'),
('Quảng Ninh', 'active')
ON DUPLICATE KEY UPDATE name=name;

-- ============================================
-- 7. SEED DỮ LIỆU: 40 KỸ NĂNG
-- ============================================
INSERT INTO skills (name, status) VALUES
-- Kỹ năng lập trình & IT
('Python', 'active'),
('Java', 'active'),
('JavaScript', 'active'),
('React', 'active'),
('Node.js', 'active'),
('Angular', 'active'),
('Vue.js', 'active'),
('PHP', 'active'),
('C#', 'active'),
('.NET', 'active'),
('SQL', 'active'),
('MySQL', 'active'),
('PostgreSQL', 'active'),
('MongoDB', 'active'),
('Docker', 'active'),
('Kubernetes', 'active'),
('AWS', 'active'),
('Azure', 'active'),
('DevOps', 'active'),
('Git', 'active'),

-- Kỹ năng kinh doanh & marketing
('Sales', 'active'),
('Marketing Digital', 'active'),
('SEO/SEM', 'active'),
('Content Marketing', 'active'),
('Social Media', 'active'),
('Google Ads', 'active'),
('Facebook Ads', 'active'),

-- Kỹ năng mềm & quản lý
('Giao tiếp', 'active'),
('Làm việc nhóm', 'active'),
('Quản lý dự án', 'active'),
('Lãnh đạo', 'active'),
('Giải quyết vấn đề', 'active'),
('Tư duy phản biện', 'active'),

-- Kỹ năng chuyên môn khác
('Kế toán', 'active'),
('Tài chính', 'active'),
('Photoshop', 'active'),
('Illustrator', 'active'),
('UI/UX Design', 'active'),
('AutoCAD', 'active'),
('Tiếng Anh', 'active')
ON DUPLICATE KEY UPDATE name=name;

-- ============================================
-- 8. KẾT QUẢ KIỂM TRA
-- ============================================
SELECT 'Industries' as Table_Name, COUNT(*) as Total FROM industries
UNION ALL
SELECT 'Locations', COUNT(*) FROM locations
UNION ALL
SELECT 'Skills', COUNT(*) FROM skills
UNION ALL
SELECT 'Reports', COUNT(*) FROM reports;
