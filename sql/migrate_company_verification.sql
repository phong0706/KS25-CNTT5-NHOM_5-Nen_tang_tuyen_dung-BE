-- Migration: Luồng xác minh công ty (Company Verification)
-- Chạy an toàn trên MySQL 8 (app_db)

CREATE TABLE IF NOT EXISTS company_verifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    mst VARCHAR(20) NOT NULL COMMENT 'MST đã chuẩn hóa: 10 số hoặc 10 số-3 số',
    mst_raw VARCHAR(50) NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'cho_duyet'
        COMMENT 'cho_duyet | da_xac_minh | tu_choi | thu_hoi',
    license_storage_key VARCHAR(255) NOT NULL,
    license_original_name VARCHAR(255) NULL,
    license_mime_type VARCHAR(80) NOT NULL,
    license_size_bytes INT NOT NULL,
    submitted_by INT NOT NULL,
    reviewed_by INT NULL,
    rejection_reason TEXT NULL,
    idempotency_key VARCHAR(120) NULL,
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at DATETIME NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    version INT NOT NULL DEFAULT 1,
    pending_company_lock INT GENERATED ALWAYS AS (IF(status = 'cho_duyet', company_id, NULL)) VIRTUAL,
    CONSTRAINT fk_cv_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    CONSTRAINT fk_cv_submitter FOREIGN KEY (submitted_by) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_cv_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE KEY uq_company_single_pending (pending_company_lock),
    INDEX idx_cv_company_created (company_id, submitted_at DESC),
    INDEX idx_cv_status_submitted (status, submitted_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
