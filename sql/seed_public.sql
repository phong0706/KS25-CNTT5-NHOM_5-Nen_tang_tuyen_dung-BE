-- Nâng cấp schema & seed >= 40 tin tuyển dụng công khai, công ty nổi bật, ngành nghề cho Trang chủ & Trang tìm việc
SET NAMES utf8mb4;
USE app_db;

-- 1. Bảng meta_categories
CREATE TABLE IF NOT EXISTS meta_categories (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    slug       VARCHAR(80)  NOT NULL UNIQUE,
    name       VARCHAR(120) NOT NULL,
    icon       VARCHAR(60)  NOT NULL DEFAULT 'code',
    sort_order INT          NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO meta_categories (slug, name, icon, sort_order) VALUES
('backend', 'Backend & API', 'server', 1),
('frontend', 'Frontend & UI/UX', 'layout', 2),
('ai-data', 'AI & Data Science', 'cpu', 3),
('devops-cloud', 'DevOps & Cloud', 'cloud', 4),
('mobile', 'Mobile App', 'smartphone', 5),
('qa-testing', 'QA & Automation', 'shield', 6)
ON DUPLICATE KEY UPDATE name = VALUES(name), icon = VALUES(icon), sort_order = VALUES(sort_order);

-- 2. Bảng saved_jobs
CREATE TABLE IF NOT EXISTS saved_jobs (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT      NOT NULL,
    job_id     INT      NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_saved_user_job (user_id, job_id),
    INDEX idx_saved_user_id (user_id),
    CONSTRAINT fk_saved_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_saved_job  FOREIGN KEY (job_id)  REFERENCES jobs(id)  ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Bổ sung cột FK + index + FULLTEXT cho jobs (an toàn nếu chạy lại)
DROP PROCEDURE IF EXISTS upgrade_jobs_schema;
DELIMITER $$
CREATE PROCEDURE upgrade_jobs_schema()
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = 'app_db' AND TABLE_NAME = 'jobs' AND COLUMN_NAME = 'location_id') THEN
        ALTER TABLE jobs
            ADD COLUMN location_id INT NULL AFTER company_id,
            ADD COLUMN level_id INT NULL AFTER location_id,
            ADD COLUMN work_type_id INT NULL AFTER level_id,
            ADD COLUMN category_id INT NULL AFTER work_type_id,
            ADD INDEX idx_jobs_location_id (location_id),
            ADD INDEX idx_jobs_level_id (level_id),
            ADD INDEX idx_jobs_category_id (category_id),
            ADD FULLTEXT INDEX ft_jobs_title (title);
    END IF;
END$$
DELIMITER ;
CALL upgrade_jobs_schema();
DROP PROCEDURE IF EXISTS upgrade_jobs_schema;

-- 4. Seed thêm các công ty đã duyệt (is_draft = FALSE)
SET @hr1_id = (SELECT id FROM users WHERE email = 'hr1@tuyendung.com' LIMIT 1);
SET @hr2_id = (SELECT id FROM users WHERE email = 'hr2@tuyendung.com' LIMIT 1);
SET @hr3_id = (SELECT id FROM users WHERE email = 'hr3@tuyendung.com' LIMIT 1);
SET @hr5_id = (SELECT id FROM users WHERE email = 'hr5@tuyendung.com' LIMIT 1);

UPDATE companies SET is_draft = FALSE WHERE employer_id IN (@hr1_id, @hr2_id, @hr3_id, @hr5_id);

INSERT INTO companies (name, employer_id, is_draft)
SELECT 'Rikkeisoft', @hr1_id, FALSE WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'Rikkeisoft');
INSERT INTO companies (name, employer_id, is_draft)
SELECT 'VNG Corporation', @hr2_id, FALSE WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'VNG Corporation');
INSERT INTO companies (name, employer_id, is_draft)
SELECT 'FPT Software', @hr3_id, FALSE WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'FPT Software');
INSERT INTO companies (name, employer_id, is_draft)
SELECT 'Viettel Solutions', @hr5_id, FALSE WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'Viettel Solutions');
INSERT INTO companies (name, employer_id, is_draft)
SELECT 'MoMo (M-Service)', @hr1_id, FALSE WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'MoMo (M-Service)');
INSERT INTO companies (name, employer_id, is_draft)
SELECT 'VNPT IT', @hr2_id, FALSE WHERE NOT EXISTS (SELECT 1 FROM companies WHERE name = 'VNPT IT');

SET @c_rikkei  = (SELECT id FROM companies WHERE name = 'Rikkeisoft' LIMIT 1);
SET @c_vng     = (SELECT id FROM companies WHERE name = 'VNG Corporation' LIMIT 1);
SET @c_fpt     = (SELECT id FROM companies WHERE name = 'FPT Software' LIMIT 1);
SET @c_viettel = (SELECT id FROM companies WHERE name = 'Viettel Solutions' LIMIT 1);
SET @c_momo    = (SELECT id FROM companies WHERE name = 'MoMo (M-Service)' LIMIT 1);
SET @c_vnpt    = (SELECT id FROM companies WHERE name = 'VNPT IT' LIMIT 1);

-- 5. Gán FK cho các tin hiện có dựa trên text location/level/work_type
UPDATE jobs j
LEFT JOIN meta_locations l ON j.location = l.name
LEFT JOIN meta_levels lv ON j.level = lv.name
LEFT JOIN meta_work_types wt ON j.work_type = wt.name
SET j.location_id = l.id, j.level_id = lv.id, j.work_type_id = wt.id
WHERE j.location_id IS NULL OR j.level_id IS NULL OR j.work_type_id IS NULL;

UPDATE jobs SET category_id = (SELECT id FROM meta_categories WHERE slug = 'backend' LIMIT 1)
WHERE category_id IS NULL AND (title LIKE '%Backend%' OR title LIKE '%Java%' OR title LIKE '%Go%' OR title LIKE '%Node%' OR title LIKE '%PHP%' OR title LIKE '%Database%');
UPDATE jobs SET category_id = (SELECT id FROM meta_categories WHERE slug = 'frontend' LIMIT 1)
WHERE category_id IS NULL AND (title LIKE '%Frontend%' OR title LIKE '%Vue%' OR title LIKE '%Next%' OR title LIKE '%UI/UX%');
UPDATE jobs SET category_id = (SELECT id FROM meta_categories WHERE slug = 'ai-data' LIMIT 1)
WHERE category_id IS NULL AND (title LIKE '%AI%' OR title LIKE '%Data%');
UPDATE jobs SET category_id = (SELECT id FROM meta_categories WHERE slug = 'devops-cloud' LIMIT 1)
WHERE category_id IS NULL AND (title LIKE '%DevOps%' OR title LIKE '%Cloud%' OR title LIKE '%Security%');
UPDATE jobs SET category_id = (SELECT id FROM meta_categories WHERE slug = 'mobile' LIMIT 1)
WHERE category_id IS NULL AND (title LIKE '%Mobile%' OR title LIKE '%React Native%');
UPDATE jobs SET category_id = (SELECT id FROM meta_categories WHERE slug = 'qa-testing' LIMIT 1)
WHERE category_id IS NULL;

-- Gán lại company_id đa dạng cho các tin published hiện có
UPDATE jobs SET company_id = @c_rikkei WHERE status = 'published' AND MOD(id, 6) = 0;
UPDATE jobs SET company_id = @c_vng WHERE status = 'published' AND MOD(id, 6) = 1;
UPDATE jobs SET company_id = @c_fpt WHERE status = 'published' AND MOD(id, 6) = 2;
UPDATE jobs SET company_id = @c_viettel WHERE status = 'published' AND MOD(id, 6) = 3;
UPDATE jobs SET company_id = @c_momo WHERE status = 'published' AND MOD(id, 6) = 4;
UPDATE jobs SET company_id = @c_vnpt WHERE status = 'published' AND MOD(id, 6) = 5;

-- 6. Seed thêm 32 tin published nữa để đạt >= 45 tin published (5 trang phân trang)
DELETE FROM jobs WHERE title LIKE '[Seed] %';

SET @l_hn  = (SELECT id FROM meta_locations WHERE slug = 'ha-noi' LIMIT 1);
SET @l_hcm = (SELECT id FROM meta_locations WHERE slug = 'ho-chi-minh' LIMIT 1);
SET @l_dn  = (SELECT id FROM meta_locations WHERE slug = 'da-nang' LIMIT 1);
SET @l_rm  = (SELECT id FROM meta_locations WHERE slug = 'remote-toan-quoc' LIMIT 1);

SET @lv_jr = (SELECT id FROM meta_levels WHERE slug = 'junior' LIMIT 1);
SET @lv_md = (SELECT id FROM meta_levels WHERE slug = 'middle' LIMIT 1);
SET @lv_sr = (SELECT id FROM meta_levels WHERE slug = 'senior' LIMIT 1);
SET @lv_ld = (SELECT id FROM meta_levels WHERE slug = 'lead-manager' LIMIT 1);

SET @wt_ft = (SELECT id FROM meta_work_types WHERE slug = 'full-time' LIMIT 1);
SET @wt_hb = (SELECT id FROM meta_work_types WHERE slug = 'hybrid' LIMIT 1);
SET @wt_rm = (SELECT id FROM meta_work_types WHERE slug = 'remote' LIMIT 1);

SET @cat_be = (SELECT id FROM meta_categories WHERE slug = 'backend' LIMIT 1);
SET @cat_fe = (SELECT id FROM meta_categories WHERE slug = 'frontend' LIMIT 1);
SET @cat_ai = (SELECT id FROM meta_categories WHERE slug = 'ai-data' LIMIT 1);
SET @cat_do = (SELECT id FROM meta_categories WHERE slug = 'devops-cloud' LIMIT 1);
SET @cat_mb = (SELECT id FROM meta_categories WHERE slug = 'mobile' LIMIT 1);
SET @cat_qa = (SELECT id FROM meta_categories WHERE slug = 'qa-testing' LIMIT 1);

INSERT INTO jobs (
    employer_id, company_id, location_id, level_id, work_type_id, category_id,
    title, level, work_type, location, quantity, deadline,
    description, requirements, skills, salary_min, salary_max, is_salary_negotiable, benefits,
    status, views_count, published_at, created_at
) VALUES
-- 4 tin đăng hôm nay (NOW() - INTERVAL 1..3 HOUR)
(@hr1_id, @c_rikkei, @l_hn, @lv_sr, @wt_hb, @cat_be, '[Seed] Principal Python Microservices Architect', 'Senior', 'Hybrid (Linh hoạt)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 20 DAY),
 'Thiết kế kiến trúc microservices chịu tải cao.', '5+ năm Python, FastAPI, Kafka.', JSON_ARRAY('Python', 'FastAPI', 'Docker', 'Kubernetes'), 48000000, 72000000, FALSE, JSON_ARRAY('Thưởng hiệu suất', 'MacBook Pro'), 'published', 210, NOW() - INTERVAL 1 HOUR, NOW() - INTERVAL 1 HOUR),

(@hr2_id, @c_vng, @l_hcm, @lv_sr, @wt_ft, @cat_fe, '[Seed] Senior React & Design System Engineer', 'Senior', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 2, DATE_ADD(CURDATE(), INTERVAL 18 DAY),
 'Phát triển thư viện UI dùng chung cho các sản phẩm VNG.', '3+ năm React, TypeScript, CSS Architecture.', JSON_ARRAY('React', 'TypeScript', 'Tailwind CSS'), 35000000, 52000000, FALSE, JSON_ARRAY('Bảo hiểm cao cấp', 'Thưởng quý'), 'published', 185, NOW() - INTERVAL 2 HOUR, NOW() - INTERVAL 2 HOUR),

(@hr3_id, @c_fpt, @l_dn, @lv_md, @wt_ft, @cat_ai, '[Seed] LLM & RAG Application Engineer', 'Middle', 'Toàn thời gian (Full-time)', 'Đà Nẵng', 3, DATE_ADD(CURDATE(), INTERVAL 25 DAY),
 'Xây dựng trợ lý AI doanh nghiệp với RAG và Vector DB.', '2+ năm Python, NLP, LLM.', JSON_ARRAY('Python', 'FastAPI', 'PostgreSQL', 'AWS'), 28000000, 44000000, FALSE, JSON_ARRAY('Đào tạo AI chuyên sâu'), 'published', 320, NOW() - INTERVAL 3 HOUR, NOW() - INTERVAL 3 HOUR),

(@hr5_id, @c_viettel, @l_hn, @lv_ld, @wt_ft, @cat_do, '[Seed] Cloud Platform Lead (Kubernetes & Terraform)', 'Tech Lead / Manager', 'Toàn thời gian (Full-time)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 15 DAY),
 'Xây dựng nền tảng cloud nội bộ cho hệ thống viễn thông.', '5+ năm K8s, AWS/OpenStack, CI/CD.', JSON_ARRAY('Kubernetes', 'Docker', 'AWS', 'CI/CD'), 55000000, 80000000, FALSE, JSON_ARRAY('Gói phúc lợi quản lý'), 'published', 275, NOW() - INTERVAL 4 HOUR, NOW() - INTERVAL 4 HOUR),

-- 28 tin thêm trải đều 1..28 ngày trước
(@hr1_id, @c_momo, @l_hcm, @lv_sr, @wt_ft, @cat_be, '[Seed] Senior Java Payment Core Engineer', 'Senior', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 2, DATE_ADD(CURDATE(), INTERVAL 22 DAY),
 'Phát triển lõi thanh toán ví điện tử.', '4+ năm Java Spring Boot, MySQL.', JSON_ARRAY('Java', 'Spring Boot', 'MySQL', 'Redis'), 40000000, 62000000, FALSE, JSON_ARRAY('ESOP', 'Thưởng tháng 13'), 'published', 410, NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY),

(@hr2_id, @c_vnpt, @l_hn, @lv_md, @wt_ft, @cat_be, '[Seed] Middle Golang Backend Developer', 'Middle', 'Toàn thời gian (Full-time)', 'Hà Nội', 2, DATE_ADD(CURDATE(), INTERVAL 19 DAY),
 'Xây dựng API gateway hiệu năng cao.', '2+ năm Go, Redis, PostgreSQL.', JSON_ARRAY('Go', 'PostgreSQL', 'Redis', 'Docker'), 25000000, 38000000, FALSE, JSON_ARRAY('Bảo hiểm sức khỏe'), 'published', 190, NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY),

(@hr3_id, @c_rikkei, @l_dn, @lv_jr, @wt_hb, @cat_fe, '[Seed] Junior Vue.js / Nuxt Developer', 'Junior', 'Hybrid (Linh hoạt)', 'Đà Nẵng', 3, DATE_ADD(CURDATE(), INTERVAL 24 DAY),
 'Phát triển giao diện web cho khách hàng Nhật Bản.', '1+ năm Vue.js, JavaScript.', JSON_ARRAY('Vue.js', 'JavaScript', 'Tailwind CSS'), 14000000, 21000000, FALSE, JSON_ARRAY('Phụ cấp tiếng Nhật'), 'published', 230, NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY),

(@hr5_id, @c_vng, @l_hcm, @lv_md, @wt_ft, @cat_mb, '[Seed] Senior iOS / React Native Developer', 'Senior', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 2, DATE_ADD(CURDATE(), INTERVAL 17 DAY),
 'Phát triển ứng dụng social & fintech.', '3+ năm React Native, TypeScript.', JSON_ARRAY('React', 'TypeScript', 'GraphQL'), 34000000, 50000000, FALSE, JSON_ARRAY('Review lương 2 lần/năm'), 'published', 295, NOW() - INTERVAL 4 DAY, NOW() - INTERVAL 4 DAY),

(@hr1_id, @c_fpt, @l_rm, @lv_md, @wt_rm, @cat_qa, '[Seed] Automation QA Engineer (Playwright / Cypress)', 'Middle', 'Remote (Từ xa)', 'Remote / Toàn quốc', 2, DATE_ADD(CURDATE(), INTERVAL 26 DAY),
 'Xây dựng framework kiểm thử tự động E2E.', '2+ năm TypeScript, Playwright, CI/CD.', JSON_ARRAY('TypeScript', 'JavaScript', 'CI/CD'), 20000000, 32000000, FALSE, JSON_ARRAY('Làm việc từ xa 100%'), 'published', 175, NOW() - INTERVAL 5 DAY, NOW() - INTERVAL 5 DAY),

(@hr2_id, @c_viettel, @l_hn, @lv_sr, @wt_ft, @cat_ai, '[Seed] Senior Data Platform Engineer', 'Senior', 'Toàn thời gian (Full-time)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 21 DAY),
 'Vận hành hệ thống dữ liệu lớn.', '4+ năm Python, PostgreSQL, AWS.', JSON_ARRAY('Python', 'PostgreSQL', 'AWS', 'Docker'), 38000000, 58000000, FALSE, JSON_ARRAY('Thưởng dự án'), 'published', 260, NOW() - INTERVAL 6 DAY, NOW() - INTERVAL 6 DAY),

(@hr3_id, @c_momo, @l_hcm, @lv_md, @wt_hb, @cat_fe, '[Seed] Next.js Growth Frontend Engineer', 'Middle', 'Hybrid (Linh hoạt)', 'TP. Hồ Chí Minh', 2, DATE_ADD(CURDATE(), INTERVAL 16 DAY),
 'Tối ưu chuyển đổi và SEO cho landing pages.', '2+ năm Next.js, React, TypeScript.', JSON_ARRAY('Next.js', 'React', 'TypeScript'), 24000000, 36000000, FALSE, JSON_ARRAY('Ăn trưa miễn phí'), 'published', 310, NOW() - INTERVAL 7 DAY, NOW() - INTERVAL 7 DAY),

(@hr5_id, @c_vnpt, @l_hn, @lv_jr, @wt_ft, @cat_be, '[Seed] Junior Node.js & TypeScript Developer', 'Junior', 'Toàn thời gian (Full-time)', 'Hà Nội', 3, DATE_ADD(CURDATE(), INTERVAL 28 DAY),
 'Phát triển RESTful APIs cho nền tảng chính phủ số.', '1+ năm Node.js, TypeScript, MySQL.', JSON_ARRAY('Node.js', 'TypeScript', 'MySQL'), 13000000, 20000000, FALSE, JSON_ARRAY('Đào tạo bài bản'), 'published', 280, NOW() - INTERVAL 8 DAY, NOW() - INTERVAL 8 DAY),

(@hr1_id, @c_rikkei, @l_hn, @lv_sr, @wt_ft, @cat_do, '[Seed] Senior AWS Solutions DevOps', 'Senior', 'Toàn thời gian (Full-time)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 14 DAY),
 'Tối ưu hạ tầng cloud và chi phí AWS.', '3+ năm AWS, Docker, Kubernetes.', JSON_ARRAY('AWS', 'Docker', 'Kubernetes', 'CI/CD'), 36000000, 55000000, FALSE, JSON_ARRAY('Chứng chỉ AWS miễn phí'), 'published', 240, NOW() - INTERVAL 9 DAY, NOW() - INTERVAL 9 DAY),

(@hr2_id, @c_vng, @l_hcm, @lv_ld, @wt_ft, @cat_be, '[Seed] Backend Engineering Manager (Gaming Platform)', 'Tech Lead / Manager', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 1, DATE_ADD(CURDATE(), INTERVAL 30 DAY),
 'Quản lý đội ngũ 15 kỹ sư backend.', '6+ năm Java/Go, hệ thống chịu tải cao.', JSON_ARRAY('Go', 'Java', 'Redis', 'Kubernetes'), NULL, NULL, TRUE, JSON_ARRAY('Thưởng KPI năm'), 'published', 340, NOW() - INTERVAL 10 DAY, NOW() - INTERVAL 10 DAY),

(@hr3_id, @c_fpt, @l_dn, @lv_md, @wt_ft, @cat_mb, '[Seed] Mobile Flutter / React Native Engineer', 'Middle', 'Toàn thời gian (Full-time)', 'Đà Nẵng', 2, DATE_ADD(CURDATE(), INTERVAL 23 DAY),
 'Phát triển app thương mại điện tử đa nền tảng.', '2+ năm React Native hoặc Flutter.', JSON_ARRAY('React', 'TypeScript', 'GraphQL'), 22000000, 34000000, FALSE, JSON_ARRAY('Du lịch hằng năm'), 'published', 195, NOW() - INTERVAL 11 DAY, NOW() - INTERVAL 11 DAY),

(@hr5_id, @c_viettel, @l_hn, @lv_md, @wt_ft, @cat_qa, '[Seed] Performance & Security QA Engineer', 'Middle', 'Toàn thời gian (Full-time)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 18 DAY),
 'Kiểm thử tải và bảo mật API.', '2+ năm JMeter/k6, OWASP.', JSON_ARRAY('Python', 'CI/CD', 'Docker'), 24000000, 35000000, FALSE, JSON_ARRAY('Phụ cấp chứng chỉ'), 'published', 160, NOW() - INTERVAL 12 DAY, NOW() - INTERVAL 12 DAY),

(@hr1_id, @c_momo, @l_hcm, @lv_sr, @wt_hb, @cat_ai, '[Seed] Senior Machine Learning Engineer (Fraud Detection)', 'Senior', 'Hybrid (Linh hoạt)', 'TP. Hồ Chí Minh', 1, DATE_ADD(CURDATE(), INTERVAL 20 DAY),
 'Xây dựng mô hình phát hiện gian lận giao dịch thời gian thực.', '3+ năm Python, ML, Redis.', JSON_ARRAY('Python', 'Redis', 'AWS', 'Docker'), 45000000, 70000000, FALSE, JSON_ARRAY('ESOP', 'MacBook Pro'), 'published', 390, NOW() - INTERVAL 13 DAY, NOW() - INTERVAL 13 DAY),

(@hr2_id, @c_vnpt, @l_hn, @lv_md, @wt_ft, @cat_fe, '[Seed] Frontend TypeScript Engineer (Enterprise Portal)', 'Middle', 'Toàn thời gian (Full-time)', 'Hà Nội', 2, DATE_ADD(CURDATE(), INTERVAL 27 DAY),
 'Phát triển cổng quản trị dữ liệu doanh nghiệp.', '2+ năm React, TypeScript.', JSON_ARRAY('React', 'TypeScript', 'Tailwind CSS'), 20000000, 30000000, FALSE, JSON_ARRAY('Nghỉ thứ 7 & CN'), 'published', 215, NOW() - INTERVAL 14 DAY, NOW() - INTERVAL 14 DAY),

(@hr3_id, @c_rikkei, @l_rm, @lv_sr, @wt_rm, @cat_be, '[Seed] Remote Senior Python FastAPI Engineer', 'Senior', 'Remote (Từ xa)', 'Remote / Toàn quốc', 2, DATE_ADD(CURDATE(), INTERVAL 29 DAY),
 'Phát triển nền tảng SaaS cho thị trường Mỹ.', '3+ năm Python, FastAPI, PostgreSQL.', JSON_ARRAY('Python', 'FastAPI', 'PostgreSQL', 'Docker'), 36000000, 54000000, FALSE, JSON_ARRAY('Remote 100%'), 'published', 420, NOW() - INTERVAL 15 DAY, NOW() - INTERVAL 15 DAY),

(@hr5_id, @c_vng, @l_hcm, @lv_jr, @wt_ft, @cat_do, '[Seed] Junior Cloud & Linux System Engineer', 'Junior', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 2, DATE_ADD(CURDATE(), INTERVAL 25 DAY),
 'Hỗ trợ vận hành cụm máy chủ và CI/CD.', '1+ năm Linux, Docker, CI/CD.', JSON_ARRAY('Docker', 'CI/CD', 'AWS'), 15000000, 22000000, FALSE, JSON_ARRAY('Mentor 1-1'), 'published', 180, NOW() - INTERVAL 16 DAY, NOW() - INTERVAL 16 DAY),

(@hr1_id, @c_fpt, @l_dn, @lv_sr, @wt_ft, @cat_be, '[Seed] Senior Java Spring Boot Microservices', 'Senior', 'Toàn thời gian (Full-time)', 'Đà Nẵng', 3, DATE_ADD(CURDATE(), INTERVAL 19 DAY),
 'Xây dựng hệ thống ngân hàng số.', '4+ năm Java, Spring Boot, MySQL.', JSON_ARRAY('Java', 'Spring Boot', 'MySQL', 'Kubernetes'), 35000000, 52000000, FALSE, JSON_ARRAY('Thưởng dự án'), 'published', 270, NOW() - INTERVAL 17 DAY, NOW() - INTERVAL 17 DAY),

(@hr2_id, @c_viettel, @l_hn, @lv_md, @wt_ft, @cat_be, '[Seed] Middle Backend Node.js & GraphQL', 'Middle', 'Toàn thời gian (Full-time)', 'Hà Nội', 2, DATE_ADD(CURDATE(), INTERVAL 22 DAY),
 'Phát triển GraphQL Federation API.', '2+ năm Node.js, GraphQL, PostgreSQL.', JSON_ARRAY('Node.js', 'GraphQL', 'PostgreSQL'), 24000000, 36000000, FALSE, JSON_ARRAY('Bảo hiểm PTI'), 'published', 205, NOW() - INTERVAL 18 DAY, NOW() - INTERVAL 18 DAY),

(@hr3_id, @c_momo, @l_hcm, @lv_md, @wt_hb, @cat_qa, '[Seed] Mobile QA Automation Engineer', 'Middle', 'Hybrid (Linh hoạt)', 'TP. Hồ Chí Minh', 2, DATE_ADD(CURDATE(), INTERVAL 21 DAY),
 'Kiểm thử tự động ứng dụng iOS/Android.', '2+ năm Appium, Python/Java.', JSON_ARRAY('Python', 'Java', 'CI/CD'), 22000000, 33000000, FALSE, JSON_ARRAY('Thưởng tháng 13'), 'published', 155, NOW() - INTERVAL 19 DAY, NOW() - INTERVAL 19 DAY),

(@hr5_id, @c_vnpt, @l_hn, @lv_sr, @wt_ft, @cat_fe, '[Seed] Senior Frontend Architect (React / Next.js)', 'Senior', 'Toàn thời gian (Full-time)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 24 DAY),
 'Định hướng kiến trúc frontend cho sản phẩm mới.', '4+ năm React, Next.js, TypeScript.', JSON_ARRAY('React', 'Next.js', 'TypeScript'), 38000000, 56000000, FALSE, JSON_ARRAY('Gói bảo hiểm VIP'), 'published', 250, NOW() - INTERVAL 20 DAY, NOW() - INTERVAL 20 DAY),

(@hr1_id, @c_rikkei, @l_hn, @lv_md, @wt_hb, @cat_be, '[Seed] Middle Python & Celery Distributed Systems', 'Middle', 'Hybrid (Linh hoạt)', 'Hà Nội', 2, DATE_ADD(CURDATE(), INTERVAL 21 DAY),
 'Xây dựng hàng đợi tác vụ bất đồng bộ.', '2+ năm Python, Redis, Docker.', JSON_ARRAY('Python', 'Redis', 'Docker'), 25000000, 38000000, FALSE, JSON_ARRAY('Thưởng tháng 13'), 'published', 140, NOW() - INTERVAL 21 DAY, NOW() - INTERVAL 21 DAY),

(@hr2_id, @c_vng, @l_hcm, @lv_md, @wt_ft, @cat_ai, '[Seed] Data Scientist (Recommendation Systems)', 'Middle', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 1, DATE_ADD(CURDATE(), INTERVAL 22 DAY),
 'Tối ưu thuật toán gợi ý nội dung.', '2+ năm Python, SQL, ML.', JSON_ARRAY('Python', 'PostgreSQL', 'AWS'), 30000000, 46000000, FALSE, JSON_ARRAY('Review lương 2 lần/năm'), 'published', 225, NOW() - INTERVAL 22 DAY, NOW() - INTERVAL 22 DAY),

(@hr3_id, @c_fpt, @l_dn, @lv_jr, @wt_ft, @cat_fe, '[Seed] Junior React & Tailwind Developer', 'Junior', 'Toàn thời gian (Full-time)', 'Đà Nẵng', 3, DATE_ADD(CURDATE(), INTERVAL 23 DAY),
 'Xây dựng giao diện dashboard quản trị.', '1+ năm React, Tailwind CSS.', JSON_ARRAY('React', 'Tailwind CSS', 'JavaScript'), 13000000, 19000000, FALSE, JSON_ARRAY('Hỗ trợ ăn trưa'), 'published', 190, NOW() - INTERVAL 23 DAY, NOW() - INTERVAL 23 DAY),

(@hr5_id, @c_viettel, @l_rm, @lv_sr, @wt_rm, @cat_do, '[Seed] Remote Site Reliability Engineer (SRE)', 'Senior', 'Remote (Từ xa)', 'Remote / Toàn quốc', 1, DATE_ADD(CURDATE(), INTERVAL 24 DAY),
 'Đảm bảo SLA 99.99% cho hệ thống cloud.', '3+ năm Kubernetes, AWS, CI/CD.', JSON_ARRAY('Kubernetes', 'AWS', 'CI/CD'), 42000000, 64000000, FALSE, JSON_ARRAY('Làm việc từ xa 100%'), 'published', 305, NOW() - INTERVAL 24 DAY, NOW() - INTERVAL 24 DAY),

(@hr1_id, @c_momo, @l_hcm, @lv_md, @wt_ft, @cat_mb, '[Seed] Android Kotlin Engineer (Fintech App)', 'Middle', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 2, DATE_ADD(CURDATE(), INTERVAL 25 DAY),
 'Phát triển tính năng thanh toán QR trên Android.', '2+ năm Kotlin, Android SDK.', JSON_ARRAY('Java', 'GraphQL'), 26000000, 40000000, FALSE, JSON_ARRAY('ESOP'), 'published', 178, NOW() - INTERVAL 25 DAY, NOW() - INTERVAL 25 DAY);
