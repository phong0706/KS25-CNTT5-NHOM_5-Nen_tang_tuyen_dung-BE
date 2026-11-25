-- Migration: bổ sung các cột còn thiếu cho bảng companies (hồ sơ công ty)
-- Yêu cầu: đã chạy sql/companies.sql trước (tạo bảng companies).
-- Cách chạy: MySQL Workbench > File > Open SQL Script... > chọn file này > Execute
-- An toàn: dùng ADD COLUMN IF NOT EXISTS (MySQL 8.0.29+), nếu phiên bản cũ hơn thì bỏ chữ IF NOT EXISTS.

SET NAMES utf8mb4;
USE app_db;

-- ============================================
-- 1. BỔ SUNG CÁC CỘT CÒN THIẾU CHO BẢNG COMPANIES
-- ============================================
ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS logo VARCHAR(500) NULL COMMENT 'URL ảnh logo' AFTER name,
    ADD COLUMN IF NOT EXISTS cover_image VARCHAR(500) NULL COMMENT 'URL ảnh bìa' AFTER logo,
    ADD COLUMN IF NOT EXISTS tax_code VARCHAR(50) NULL COMMENT 'mã số thuế' AFTER cover_image,
    ADD COLUMN IF NOT EXISTS company_size VARCHAR(50) NULL COMMENT 'quy mô, vd: 1-50, 51-200, 1000+' AFTER tax_code,
    ADD COLUMN IF NOT EXISTS industry_id INT NULL COMMENT 'ngành (link industries.id)' AFTER company_size,
    ADD COLUMN IF NOT EXISTS address VARCHAR(500) NULL AFTER industry_id,
    ADD COLUMN IF NOT EXISTS website VARCHAR(255) NULL AFTER address,
    ADD COLUMN IF NOT EXISTS description TEXT NULL AFTER website,
    ADD COLUMN IF NOT EXISTS is_draft TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'cờ công ty nháp lúc đăng ký' AFTER status,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- ============================================
-- 2. THÊM INDEX CHO CÁC CỘT MỚI
-- ============================================
-- Chỉ thêm nếu chưa có (MySQL không hỗ trợ IF NOT EXISTS cho INDEX trực tiếp,
-- nên dùng kiểm tra information_schema).
SET @idx_exists = (SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE table_schema = 'app_db' AND table_name = 'companies' AND index_name = 'idx_industry_id');
SET @sql = IF(@idx_exists = 0,
    'ALTER TABLE companies ADD INDEX idx_industry_id (industry_id)',
    'SELECT ''idx_industry_id already exists'' AS msg');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================
-- 3. KIỂM TRA KẾT QUẢ
-- ============================================
DESCRIBE companies;
