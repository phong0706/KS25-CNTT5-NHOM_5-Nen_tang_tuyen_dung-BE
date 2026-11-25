-- Migration mở rộng bảng companies cho trang Công ty công khai (idempotent - chạy lặp lại an toàn).
-- Chạy thủ công: mysql -u root -p app_db < backend/sql/migrations/20261118_companies_public.sql

SET @db = DATABASE();

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND COLUMN_NAME='tagline'),
  'SELECT 1', 'ALTER TABLE companies ADD COLUMN `tagline` VARCHAR(120) NULL AFTER `name`'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND COLUMN_NAME='location_id'),
  'SELECT 1', 'ALTER TABLE companies ADD COLUMN `location_id` INT NULL AFTER `industry_id`'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND COLUMN_NAME='size_range'),
  'SELECT 1', 'ALTER TABLE companies ADD COLUMN `size_range` ENUM(''1-50'',''51-200'',''201-500'',''501-1000'',''1000+'') NULL AFTER `address`'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND COLUMN_NAME='founded_year'),
  'SELECT 1', 'ALTER TABLE companies ADD COLUMN `founded_year` SMALLINT NULL AFTER `size_range`'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND COLUMN_NAME='is_visible'),
  'SELECT 1', 'ALTER TABLE companies ADD COLUMN `is_visible` BOOLEAN NOT NULL DEFAULT TRUE AFTER `description`'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND COLUMN_NAME='is_verified'),
  'SELECT 1', 'ALTER TABLE companies ADD COLUMN `is_verified` BOOLEAN NOT NULL DEFAULT FALSE AFTER `is_visible`'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND COLUMN_NAME='verified_at'),
  'SELECT 1', 'ALTER TABLE companies ADD COLUMN `verified_at` DATETIME NULL AFTER `is_verified`'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND COLUMN_NAME='search_text'),
  'SELECT 1', 'ALTER TABLE companies ADD COLUMN `search_text` VARCHAR(500) NULL AFTER `verified_at`'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND INDEX_NAME='idx_companies_visible_name'),
  'SELECT 1', 'ALTER TABLE companies ADD INDEX `idx_companies_visible_name` (`is_visible`, `name`)'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND INDEX_NAME='idx_companies_industry_id'),
  'SELECT 1', 'ALTER TABLE companies ADD INDEX `idx_companies_industry_id` (`industry_id`)'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND INDEX_NAME='idx_companies_location_id'),
  'SELECT 1', 'ALTER TABLE companies ADD INDEX `idx_companies_location_id` (`location_id`)'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='companies' AND INDEX_NAME='idx_companies_search_text'),
  'SELECT 1', 'ALTER TABLE companies ADD INDEX `idx_companies_search_text` (`search_text`)'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;

SET @q = (SELECT IF(
  EXISTS(SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='jobs' AND INDEX_NAME='idx_jobs_company_status_pub'),
  'SELECT 1', 'ALTER TABLE jobs ADD INDEX `idx_jobs_company_status_pub` (`company_id`, `status`, `published_at`)'
));
PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s;
