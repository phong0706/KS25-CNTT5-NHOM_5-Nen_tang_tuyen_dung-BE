-- Tạo bảng companies (thông tin công ty / nhà tuyển dụng) + seed 5 công ty đã xác minh (VERIFIED)
-- Yêu cầu: đã chạy sql/init.sql (bảng users) và sql/catalog_and_reports.sql (bảng industries) trước.
-- Cách chạy: File > Open SQL Script... > chọn file này > Execute > Refresh SCHEMAS

SET NAMES utf8mb4;
USE app_db;

-- ============================================
-- 1. TẠO BẢNG COMPANIES (Công ty / Nhà tuyển dụng)
-- ============================================
CREATE TABLE IF NOT EXISTS companies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL COMMENT 'chủ tài khoản (user role=employer)',
    name VARCHAR(255) NOT NULL,
    logo VARCHAR(500) NULL COMMENT 'URL ảnh logo',
    cover_image VARCHAR(500) NULL COMMENT 'URL ảnh bìa',
    tax_code VARCHAR(50) NULL COMMENT 'mã số thuế',
    company_size VARCHAR(50) NULL COMMENT 'quy mô, vd: 1-50, 51-200, 201-500, 501-1000, 1000+',
    industry_id INT NULL COMMENT 'ngành (link industries.id)',
    address VARCHAR(500) NULL,
    website VARCHAR(255) NULL,
    description TEXT NULL,
    status ENUM('PENDING', 'VERIFIED', 'REJECTED') NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_owner_id (owner_id),
    INDEX idx_industry_id (industry_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 2. SEED 5 CÔNG TY ĐÃ XÁC MINH (VERIFIED)
-- owner_id tra theo email trong users; industry_id tra theo tên trong industries
-- Guard NOT EXISTS theo tên công ty -> chạy lại nhiều lần không trùng
-- ============================================

-- 1) FPT Software
INSERT INTO companies (owner_id, name, logo, cover_image, tax_code, company_size, industry_id, address, website, description, status)
SELECT
    (SELECT id FROM users WHERE email = 'hr1@tuyendung.com' LIMIT 1),
    'FPT Software', 'https://example.com/logos/fpt.png', 'https://example.com/covers/fpt.png',
    '0301363748', '1000+',
    (SELECT id FROM industries WHERE name = 'Công nghệ thông tin' LIMIT 1),
    'Tòa nhà FPT, 17 Tố Hữu, Nam Từ Liêm, Hà Nội', 'https://fpt.com',
    'FPT Software là đơn vị hàng đầu Việt Nam về xuất khẩu phần mềm và dịch vụ CNTT.', 'VERIFIED'
WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'FPT Software');

-- 2) VNG Corporation
INSERT INTO companies (owner_id, name, logo, cover_image, tax_code, company_size, industry_id, address, website, description, status)
SELECT
    (SELECT id FROM users WHERE email = 'hr2@tuyendung.com' LIMIT 1),
    'VNG Corporation', 'https://example.com/logos/vng.png', 'https://example.com/covers/vng.png',
    '0305126689', '1000+',
    (SELECT id FROM industries WHERE name = 'Công nghệ thông tin' LIMIT 1),
    'Z06, Khu Công Nghệ Cao, Đường D1, TP. Thủ Đức, Hồ Chí Minh', 'https://vng.com.vn',
    'VNG là công ty công nghệ Internet đầu tiên của Việt Nam, phát triển game và Zalo.', 'VERIFIED'
WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'VNG Corporation');

-- 3) Viettel Group
INSERT INTO companies (owner_id, name, logo, cover_image, tax_code, company_size, industry_id, address, website, description, status)
SELECT
    (SELECT id FROM users WHERE email = 'hr3@tuyendung.com' LIMIT 1),
    'Viettel Group', 'https://example.com/logos/viettel.png', 'https://example.com/covers/viettel.png',
    '0100626389', '1000+',
    (SELECT id FROM industries WHERE name = 'Công nghệ thông tin' LIMIT 1),
    'Tòa nhà Viettel, 285 Cầu Giấy, Dịch Vọng, Cầu Giấy, Hà Nội', 'https://viettel.vn',
    'Tập đoàn Công nghiệp - Viễn thông Quân đội, nhà mạng lớn nhất Việt Nam.', 'VERIFIED'
WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'Viettel Group');

-- 4) Vingroup
INSERT INTO companies (owner_id, name, logo, cover_image, tax_code, company_size, industry_id, address, website, description, status)
SELECT
    (SELECT id FROM users WHERE email = 'hr4tuyendung.com' LIMIT 1),
    'Vingroup', 'https://example.com/logos/vingroup.png', 'https://example.com/covers/vingroup.png',
    '0101341018', '1000+',
    (SELECT id FROM industries WHERE name = 'Bất động sản' LIMIT 1),
    'Tòa nhà Vincom Center, 191 Bà Triệu, Hai Bà Trưng, Hà Nội', 'https://vingroup.net',
    'Tập đoàn kinh tế tư nhân lớn nhất Việt Nam, hoạt động trong bất động sản, bán lẻ và y tế.', 'VERIFIED'
WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'Vingroup');

-- 5) Masan Group
INSERT INTO companies (owner_id, name, logo, cover_image, tax_code, company_size, industry_id, address, website, description, status)
SELECT
    (SELECT id FROM users WHERE email = 'hr5@tuyendung.com' LIMIT 1),
    'Masan Group', 'https://example.com/logos/masan.png', 'https://example.com/covers/masan.png',
    '0106202113', '1000+',
    (SELECT id FROM industries WHERE name = 'Sản xuất / Vận hành' LIMIT 1),
    'Tòa nhà Masan, 26-28 Đường số 5, Khu đô thị Him Lam, Bình Hưng, Hồ Chí Minh', 'https://masangroup.com',
    'Tập đoàn Masan hoạt động trong lĩnh vực hàng tiêu dùng nhanh (FMCG) và bán lẻ.', 'VERIFIED'
WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'Masan Group');

-- ============================================
-- 3. KIỂM TRA KẾT QUẢ
-- ============================================
SELECT name, status, tax_code, company_size FROM companies ORDER BY id;
