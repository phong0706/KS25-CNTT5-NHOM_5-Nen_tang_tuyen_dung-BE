-- Company verification fields.
-- Run after the existing companies table has been created.
-- ADD COLUMN IF NOT EXISTS requires MySQL 8.0.29 or newer.

SET NAMES utf8mb4;
USE app_db;

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS employer_id INT NULL AFTER id,
    ADD COLUMN IF NOT EXISTS verification_document VARCHAR(500) NULL AFTER tax_code,
    ADD COLUMN IF NOT EXISTS verification_rejection_reason TEXT NULL AFTER verification_document,
    ADD COLUMN IF NOT EXISTS verification_submitted_at DATETIME NULL AFTER verification_rejection_reason;

-- Older company schema used owner_id for the employer relationship.
UPDATE companies
SET employer_id = owner_id
WHERE employer_id IS NULL AND owner_id IS NOT NULL;

SET @idx_exists = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE table_schema = 'app_db'
      AND table_name = 'companies'
      AND index_name = 'idx_companies_employer_id'
);
SET @sql = IF(
    @idx_exists = 0,
    'ALTER TABLE companies ADD INDEX idx_companies_employer_id (employer_id)',
    'SELECT ''idx_companies_employer_id already exists'' AS msg'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
