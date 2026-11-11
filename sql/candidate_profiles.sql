-- =====================================================================
-- SQL Migration: Candidate Profile Tables
-- =====================================================================
-- Tạo các bảng: candidate_profiles, candidate_skills, experiences, educations, cvs
-- Cách chạy: MySQL Workbench > File > Open SQL Script > Execute (⚡)
-- =====================================================================

SET NAMES utf8mb4;
USE app_db;

-- ---------------------------------------------------------------------
-- Bảng: candidate_profiles (Hồ sơ ứng viên)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    
    -- Thông tin cá nhân
    date_of_birth DATE NULL,
    address VARCHAR(500) NULL,
    
    -- Mong muốn nghề nghiệp
    desired_position VARCHAR(255) NULL,
    desired_salary BIGINT NULL COMMENT 'Mức lương mong muốn (VNĐ)',
    
    -- Giới thiệu bản thân
    summary TEXT NULL,
    
    -- Hiển thị công khai
    is_public BOOLEAN NOT NULL DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_is_public (is_public),
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Bảng: candidate_skills (Kỹ năng của ứng viên)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    profile_id INT NOT NULL,
    skill_id INT NULL COMMENT 'Tham chiếu đến bảng skills (nullable)',
    skill_name VARCHAR(255) NOT NULL,
    level VARCHAR(50) NULL COMMENT 'Beginner / Intermediate / Advanced',
    
    INDEX idx_profile_id (profile_id),
    INDEX idx_skill_id (skill_id),
    
    FOREIGN KEY (profile_id) REFERENCES candidate_profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Bảng: experiences (Kinh nghiệm làm việc)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    profile_id INT NOT NULL,
    
    company_name VARCHAR(255) NOT NULL,
    position VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL COMMENT 'NULL = đang làm việc',
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT NULL,
    
    INDEX idx_profile_id (profile_id),
    
    FOREIGN KEY (profile_id) REFERENCES candidate_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Bảng: educations (Học vấn)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS educations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    profile_id INT NOT NULL,
    
    school_name VARCHAR(255) NOT NULL,
    major VARCHAR(255) NULL COMMENT 'Chuyên ngành',
    degree VARCHAR(100) NULL COMMENT 'Bằng cấp',
    start_date DATE NOT NULL,
    end_date DATE NULL COMMENT 'NULL = đang học',
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT NULL,
    
    INDEX idx_profile_id (profile_id),
    
    FOREIGN KEY (profile_id) REFERENCES candidate_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Bảng: cvs (CV files)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cvs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    profile_id INT NOT NULL,
    
    original_name VARCHAR(255) NOT NULL COMMENT 'Tên file gốc',
    stored_name VARCHAR(36) NOT NULL UNIQUE COMMENT 'UUID để lưu file',
    file_size BIGINT NOT NULL COMMENT 'Kích thước file (bytes)',
    mime_type VARCHAR(127) NOT NULL COMMENT 'application/pdf, application/msword...',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_profile_id (profile_id),
    INDEX idx_stored_name (stored_name),
    
    FOREIGN KEY (profile_id) REFERENCES candidate_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================================
-- Seed dữ liệu mẫu (optional)
-- =====================================================================

-- Tạo hồ sơ cho ứng viên 1 (user_id = 8: ungvien1@gmail.com)
INSERT INTO candidate_profiles (user_id, date_of_birth, address, desired_position, desired_salary, summary, is_public)
VALUES (8, '2001-05-15', 'Quận 1, TP. Hồ Chí Minh', 'Backend Developer', 15000000, 'Sinh viên năm cuối ngành Công nghệ thông tin, đam mê lập trình backend với Python và FastAPI.', TRUE)
ON DUPLICATE KEY UPDATE user_id=user_id;

-- Thêm kỹ năng cho hồ sơ
INSERT INTO candidate_skills (profile_id, skill_id, skill_name, level)
SELECT id, 1, 'Python', 'Advanced' FROM candidate_profiles WHERE user_id = 8
ON DUPLICATE KEY UPDATE skill_name=skill_name;

INSERT INTO candidate_skills (profile_id, skill_id, skill_name, level)
SELECT id, 7, 'FastAPI', 'Intermediate' FROM candidate_profiles WHERE user_id = 8
ON DUPLICATE KEY UPDATE skill_name=skill_name;

-- Thêm kinh nghiệm
INSERT INTO experiences (profile_id, company_name, position, start_date, end_date, is_current, description)
SELECT id, 'FPT Software', 'Backend Intern', '2024-06-01', '2024-12-01', FALSE, 'Phát triển REST API cho hệ thống quản lý nhân sự'
FROM candidate_profiles WHERE user_id = 8
ON DUPLICATE KEY UPDATE company_name=company_name;

-- Thêm học vấn
INSERT INTO educations (profile_id, school_name, major, degree, start_date, end_date, is_current, description)
SELECT id, 'Đại học Công nghệ Thông tin', 'Kỹ thuật phần mềm', 'Cử nhân', '2021-09-01', '2025-06-30', TRUE, 'GPA: 3.6/4.0'
FROM candidate_profiles WHERE user_id = 8
ON DUPLICATE KEY UPDATE school_name=school_name;

-- =====================================================================
-- Kiểm tra kết quả
-- =====================================================================
SELECT 'candidate_profiles' as table_name, COUNT(*) as total FROM candidate_profiles
UNION ALL SELECT 'candidate_skills', COUNT(*) FROM candidate_skills
UNION ALL SELECT 'experiences', COUNT(*) FROM experiences
UNION ALL SELECT 'educations', COUNT(*) FROM educations
UNION ALL SELECT 'cvs', COUNT(*) FROM cvs;
