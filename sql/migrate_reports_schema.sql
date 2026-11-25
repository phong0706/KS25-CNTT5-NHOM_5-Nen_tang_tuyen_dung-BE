-- Upgrade legacy reports table to match app/models/report.py.
-- Run from MySQL Workbench after selecting the application database.

SET NAMES utf8mb4;
USE app_db;

-- Rename the legacy reporter column only when needed.
SET @has_legacy_reporter = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND COLUMN_NAME = 'user_id'
);
SET @has_reporter = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND COLUMN_NAME = 'reporter_id'
);
SET @migration_sql = IF(
    @has_legacy_reporter > 0 AND @has_reporter = 0,
    'ALTER TABLE reports CHANGE COLUMN user_id reporter_id INT NOT NULL COMMENT ''Người báo cáo''',
    'SELECT ''reporter_id already migrated'' AS migration_status'
);
PREPARE migration_stmt FROM @migration_sql;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

-- Add employer_id as nullable first so historical rows can be backfilled.
SET @has_employer = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND COLUMN_NAME = 'employer_id'
);
SET @migration_sql = IF(
    @has_employer = 0,
    'ALTER TABLE reports ADD COLUMN employer_id INT NULL COMMENT ''Người đăng tin (nhà tuyển dụng)'' AFTER post_id',
    'SELECT ''employer_id already exists'' AS migration_status'
);
PREPARE migration_stmt FROM @migration_sql;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

-- Add timestamps required by the current ORM model.
SET @has_created_at = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND COLUMN_NAME = 'created_at'
);
SET @migration_sql = IF(
    @has_created_at = 0,
    'ALTER TABLE reports ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
    'SELECT ''created_at already exists'' AS migration_status'
);
PREPARE migration_stmt FROM @migration_sql;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @has_updated_at = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND COLUMN_NAME = 'updated_at'
);
SET @migration_sql = IF(
    @has_updated_at = 0,
    'ALTER TABLE reports ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    'SELECT ''updated_at already exists'' AS migration_status'
);
PREPARE migration_stmt FROM @migration_sql;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

-- Existing reports belong to the employer who owns their reported job.
UPDATE reports AS r
JOIN jobs AS j ON j.id = r.post_id
SET r.employer_id = j.employer_id
WHERE r.employer_id IS NULL;

SELECT COUNT(*) AS reports_without_employer
FROM reports
WHERE employer_id IS NULL;

-- This fails explicitly rather than assigning an invalid employer if a
-- historical report no longer has a matching job.
ALTER TABLE reports MODIFY COLUMN employer_id INT NOT NULL COMMENT 'Người đăng tin (nhà tuyển dụng)';

-- Add query indexes only when they are not already present.
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND INDEX_NAME = 'idx_reporter_id'
);
SET @migration_sql = IF(@idx_exists = 0, 'ALTER TABLE reports ADD INDEX idx_reporter_id (reporter_id)', 'SELECT ''idx_reporter_id already exists'' AS migration_status');
PREPARE migration_stmt FROM @migration_sql;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND INDEX_NAME = 'idx_post_id'
);
SET @migration_sql = IF(@idx_exists = 0, 'ALTER TABLE reports ADD INDEX idx_post_id (post_id)', 'SELECT ''idx_post_id already exists'' AS migration_status');
PREPARE migration_stmt FROM @migration_sql;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND INDEX_NAME = 'idx_employer_id'
);
SET @migration_sql = IF(@idx_exists = 0, 'ALTER TABLE reports ADD INDEX idx_employer_id (employer_id)', 'SELECT ''idx_employer_id already exists'' AS migration_status');
PREPARE migration_stmt FROM @migration_sql;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND INDEX_NAME = 'idx_status'
);
SET @migration_sql = IF(@idx_exists = 0, 'ALTER TABLE reports ADD INDEX idx_status (status)', 'SELECT ''idx_status already exists'' AS migration_status');
PREPARE migration_stmt FROM @migration_sql;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;
