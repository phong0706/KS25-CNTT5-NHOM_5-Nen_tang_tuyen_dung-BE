-- Tạo các bảng cho hệ thống ứng tuyển: applications, application_status_history, interviews
-- Cách chạy: File > Open SQL Script > chọn file này > Execute > Refresh SCHEMAS

SET NAMES utf8mb4;
USE app_db;

-- ============================================
-- 1. TẠO BẢNG APPLICATIONS (Đơn ứng tuyển)
-- ============================================
CREATE TABLE IF NOT EXISTS applications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_profile_id INT NOT NULL,
    job_id INT NOT NULL,
    cv_id INT NULL,
    cover_letter TEXT NULL,
    status ENUM('SUBMITTED', 'REVIEWING', 'INTERVIEW', 'OFFERED', 'REJECTED', 'WITHDRAWN') NOT NULL DEFAULT 'SUBMITTED',
    employer_notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign keys
    CONSTRAINT fk_application_candidate FOREIGN KEY (candidate_profile_id) 
        REFERENCES candidate_profiles(id) ON DELETE CASCADE,
    CONSTRAINT fk_application_job FOREIGN KEY (job_id) 
        REFERENCES jobs(id) ON DELETE CASCADE,
    CONSTRAINT fk_application_cv FOREIGN KEY (cv_id) 
        REFERENCES cvs(id) ON DELETE SET NULL,
    
    -- Unique constraint: một ứng viên chỉ được nộp 1 đơn cho 1 tin tuyển dụng
    CONSTRAINT uq_application_candidate_job UNIQUE (candidate_profile_id, job_id),
    
    -- Indexes
    INDEX idx_application_candidate (candidate_profile_id),
    INDEX idx_application_job (job_id),
    INDEX idx_application_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 2. TẠO BẢNG APPLICATION_STATUS_HISTORY (Lịch sử thay đổi trạng thái)
-- ============================================
CREATE TABLE IF NOT EXISTS application_status_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT NOT NULL,
    old_status VARCHAR(50) NULL,
    new_status VARCHAR(50) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by_user_id INT NULL,
    
    -- Foreign keys
    CONSTRAINT fk_status_history_application FOREIGN KEY (application_id) 
        REFERENCES applications(id) ON DELETE CASCADE,
    CONSTRAINT fk_status_history_user FOREIGN KEY (changed_by_user_id) 
        REFERENCES users(id) ON DELETE SET NULL,
    
    -- Indexes
    INDEX idx_status_history_application (application_id),
    INDEX idx_status_history_user (changed_by_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 3. TẠO BẢNG INTERVIEWS (Lịch phỏng vấn)
-- ============================================
CREATE TABLE IF NOT EXISTS interviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    interview_type VARCHAR(50) NOT NULL,
    location_or_link VARCHAR(500) NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'SCHEDULED',
    notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign keys
    CONSTRAINT fk_interview_application FOREIGN KEY (application_id) 
        REFERENCES applications(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_interview_application (application_id),
    INDEX idx_interview_scheduled (scheduled_at),
    INDEX idx_interview_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 4. KIỂM TRA CẤU TRÚC BẢNG
-- ============================================
SELECT 
    'applications' as table_name, 
    COUNT(*) as row_count 
FROM applications
UNION ALL 
SELECT 
    'application_status_history', 
    COUNT(*) 
FROM application_status_history
UNION ALL 
SELECT 
    'interviews', 
    COUNT(*) 
FROM interviews;

-- Xem cấu trúc bảng
SHOW CREATE TABLE applications;
SHOW CREATE TABLE application_status_history;
SHOW CREATE TABLE interviews;
