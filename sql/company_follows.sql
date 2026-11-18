-- Company follow relationship. Safe to run repeatedly.
CREATE TABLE IF NOT EXISTS company_follows (
    id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id INT NOT NULL,
    company_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_company_follows_candidate
        FOREIGN KEY (candidate_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_company_follows_company
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    CONSTRAINT uq_company_follows_candidate_company
        UNIQUE (candidate_id, company_id),
    INDEX idx_company_follows_company (company_id),
    INDEX idx_company_follows_candidate_created (candidate_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Existing notifications tables created from older patches may lack payload_json.
-- Add it only when needed; the application stores jobId/companyId and display data here.
SET @payload_column_exists = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'notifications'
      AND column_name = 'payload_json'
);
SET @payload_column_migration = IF(
    @payload_column_exists = 0,
    'ALTER TABLE notifications ADD COLUMN payload_json TEXT NULL',
    'SELECT 1'
);
PREPARE payload_column_stmt FROM @payload_column_migration;
EXECUTE payload_column_stmt;
DEALLOCATE PREPARE payload_column_stmt;

-- Notifications has a unique (user_id, dedupe_key) constraint from
-- sql/patch_notifications.sql; notification types are stored as strings.
