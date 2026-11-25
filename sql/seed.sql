-- Seed dữ liệu danh mục meta, tin tuyển dụng (jobs) và hồ sơ ứng tuyển (job_applications)
-- Yêu cầu: chạy sau khi đã có bảng users và companies (init.sql).

SET NAMES utf8mb4;
USE app_db;

-- ------------------------------------------------------------------ --
-- 1. Bảng danh mục Meta
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS meta_locations (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    slug       VARCHAR(80)  NOT NULL UNIQUE,
    name       VARCHAR(120) NOT NULL,
    sort_order INT          NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meta_levels (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    slug       VARCHAR(80)  NOT NULL UNIQUE,
    name       VARCHAR(120) NOT NULL,
    sort_order INT          NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meta_work_types (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    slug       VARCHAR(80)  NOT NULL UNIQUE,
    name       VARCHAR(120) NOT NULL,
    sort_order INT          NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meta_skills (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    usage_count INT          NOT NULL DEFAULT 0,
    INDEX idx_meta_skills_usage (usage_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------ --
-- 2. Bảng jobs và job_applications
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS jobs (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    employer_id          INT          NOT NULL,
    company_id           INT          NULL,
    title                VARCHAR(255) NOT NULL,
    level                VARCHAR(100) NULL,
    work_type            VARCHAR(100) NULL,
    location             VARCHAR(120) NULL,
    quantity             INT          NOT NULL DEFAULT 1,
    deadline             DATE         NULL,
    description          TEXT         NULL,
    requirements         TEXT         NULL,
    skills               JSON         NULL,
    salary_min           BIGINT       NULL,
    salary_max           BIGINT       NULL,
    is_salary_negotiable BOOLEAN      NOT NULL DEFAULT FALSE,
    benefits             JSON         NULL,
    status               VARCHAR(20)  NOT NULL DEFAULT 'draft',
    views_count          INT          NOT NULL DEFAULT 0,
    published_at         DATETIME     NULL,
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_jobs_employer FOREIGN KEY (employer_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_jobs_company  FOREIGN KEY (company_id)  REFERENCES companies(id) ON DELETE SET NULL,
    INDEX idx_jobs_employer_id (employer_id),
    INDEX idx_jobs_status (status),
    INDEX idx_jobs_created_at (created_at),
    INDEX idx_jobs_employer_status_created (employer_id, status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS job_applications (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    job_id       INT      NOT NULL,
    candidate_id INT      NOT NULL,
    is_viewed    BOOLEAN  NOT NULL DEFAULT FALSE,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_job_app_job       FOREIGN KEY (job_id)       REFERENCES jobs(id) ON DELETE CASCADE,
    CONSTRAINT fk_job_app_candidate FOREIGN KEY (candidate_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_job_app_job_viewed (job_id, is_viewed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------ --
-- 3. Seed dữ liệu Meta
-- ------------------------------------------------------------------ --
INSERT INTO meta_locations (slug, name, sort_order) VALUES
('ha-noi', 'Hà Nội', 1),
('ho-chi-minh', 'TP. Hồ Chí Minh', 2),
('da-nang', 'Đà Nẵng', 3),
('hai-phong', 'Hải Phòng', 4),
('can-tho', 'Cần Thơ', 5),
('binh-duong', 'Bình Dương', 6),
('remote-toan-quoc', 'Remote / Toàn quốc', 7)
ON DUPLICATE KEY UPDATE name = VALUES(name), sort_order = VALUES(sort_order);

INSERT INTO meta_levels (slug, name, sort_order) VALUES
('intern', 'Intern / Thực tập sinh', 1),
('fresher', 'Fresher', 2),
('junior', 'Junior', 3),
('middle', 'Middle', 4),
('senior', 'Senior', 5),
('lead-manager', 'Tech Lead / Manager', 6)
ON DUPLICATE KEY UPDATE name = VALUES(name), sort_order = VALUES(sort_order);

INSERT INTO meta_work_types (slug, name, sort_order) VALUES
('full-time', 'Toàn thời gian (Full-time)', 1),
('part-time', 'Bán thời gian (Part-time)', 2),
('hybrid', 'Hybrid (Linh hoạt)', 3),
('remote', 'Remote (Từ xa)', 4),
('contract', 'Hợp đồng / Freelance', 5)
ON DUPLICATE KEY UPDATE name = VALUES(name), sort_order = VALUES(sort_order);

INSERT INTO meta_skills (name, usage_count) VALUES
('React', 420),
('TypeScript', 385),
('JavaScript', 360),
('Python', 340),
('Java', 310),
('Node.js', 295),
('FastAPI', 240),
('Spring Boot', 225),
('MySQL', 215),
('PostgreSQL', 205),
('Docker', 198),
('Kubernetes', 170),
('AWS', 165),
('Vue.js', 150),
('Next.js', 142),
('Go', 135),
('Redis', 128),
('GraphQL', 110),
('Tailwind CSS', 105),
('CI/CD', 95)
ON DUPLICATE KEY UPDATE usage_count = VALUES(usage_count);

-- ------------------------------------------------------------------ --
-- 4. Seed Jobs & Applications (ngày tương đối với NOW())
-- ------------------------------------------------------------------ --
DELETE FROM job_applications;
DELETE FROM jobs;

SET @hr1_id = (SELECT id FROM users WHERE email = 'hr1@tuyendung.com' LIMIT 1);
SET @hr2_id = (SELECT id FROM users WHERE email = 'hr2@tuyendung.com' LIMIT 1);
SET @comp1_id = (SELECT id FROM companies WHERE employer_id = @hr1_id LIMIT 1);
SET @comp2_id = (SELECT id FROM companies WHERE employer_id = @hr2_id LIMIT 1);

SET @uv1_id = (SELECT id FROM users WHERE email = 'ungvien1@gmail.com' LIMIT 1);
SET @uv2_id = (SELECT id FROM users WHERE email = 'ungvien2@gmail.com' LIMIT 1);
SET @uv3_id = (SELECT id FROM users WHERE email = 'ungvien3@gmail.com' LIMIT 1);
SET @uv4_id = (SELECT id FROM users WHERE email = 'ungvien4@gmail.com' LIMIT 1);
SET @uv5_id = (SELECT id FROM users WHERE email = 'ungvien5@gmail.com' LIMIT 1);

-- 24 tin cho hr1@tuyendung.com (đủ 3 trang, đủ các trạng thái)
INSERT INTO jobs (
    employer_id, company_id, title, level, work_type, location, quantity, deadline,
    description, requirements, skills, salary_min, salary_max, is_salary_negotiable, benefits,
    status, views_count, published_at, created_at
) VALUES
-- 12 tin Đang tuyển (published)
(@hr1_id, @comp1_id, 'Senior Backend Engineer (Python / FastAPI)', 'Senior', 'Toàn thời gian (Full-time)', 'Hà Nội', 2, DATE_ADD(CURDATE(), INTERVAL 18 DAY),
 'Phát triển hệ thống API hiệu năng cao phục vụ hàng triệu lượt truy cập mỗi ngày.',
 'Từ 4 năm kinh nghiệm Python, thành thạo FastAPI, MySQL, Redis và kiến trúc microservices.',
 JSON_ARRAY('Python', 'FastAPI', 'MySQL', 'Redis', 'Docker'), 35000000, 55000000, FALSE,
 JSON_ARRAY('Thưởng tháng 13 và thưởng hiệu suất', 'Bảo hiểm sức khỏe cao cấp', 'Làm việc hybrid 2 ngày/tuần'),
 'published', 642, NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY),

(@hr1_id, @comp1_id, 'Frontend Developer (React / TypeScript)', 'Middle', 'Hybrid (Linh hoạt)', 'TP. Hồ Chí Minh', 3, DATE_ADD(CURDATE(), INTERVAL 10 DAY),
 'Xây dựng giao diện web ứng dụng tuyển dụng với trải nghiệm mượt mà, chuẩn truy cập.',
 'Từ 2 năm kinh nghiệm React, TypeScript, nắm vững HTML/CSS và tối ưu Core Web Vitals.',
 JSON_ARRAY('React', 'TypeScript', 'Tailwind CSS', 'Next.js'), 22000000, 35000000, FALSE,
 JSON_ARRAY('Cấp MacBook Pro', 'Hỗ trợ ăn trưa & gửi xe', 'Review lương 2 lần/năm'),
 'published', 518, NOW() - INTERVAL 4 DAY, NOW() - INTERVAL 4 DAY),

(@hr1_id, @comp1_id, 'Fullstack Engineer (Node.js & Vue.js)', 'Middle', 'Toàn thời gian (Full-time)', 'Đà Nẵng', 2, DATE_ADD(CURDATE(), INTERVAL 25 DAY),
 'Tham gia phát triển nền tảng SaaS quản trị nhân sự cho doanh nghiệp vừa và nhỏ.',
 'Thành thạo Node.js, Vue.js, PostgreSQL và có tư duy sản phẩm tốt.',
 JSON_ARRAY('Node.js', 'Vue.js', 'PostgreSQL', 'Docker'), 20000000, 32000000, FALSE,
 JSON_ARRAY('Du lịch công ty hằng năm', '15 ngày phép năm'),
 'published', 389, NOW() - INTERVAL 5 DAY, NOW() - INTERVAL 5 DAY),

(@hr1_id, @comp1_id, 'DevOps / SRE Engineer (AWS & Kubernetes)', 'Senior', 'Remote (Từ xa)', 'Remote / Toàn quốc', 1, DATE_ADD(CURDATE(), INTERVAL 6 DAY),
 'Vận hành hạ tầng cloud trên AWS, tối ưu CI/CD pipeline và giám sát hệ thống 24/7.',
 'Kinh nghiệm thực chiến Kubernetes, Terraform, AWS và Prometheus/Grafana.',
 JSON_ARRAY('AWS', 'Kubernetes', 'Docker', 'CI/CD'), 40000000, 65000000, FALSE,
 JSON_ARRAY('Làm việc từ xa 100%', 'Ngân sách đào tạo 15 triệu/năm'),
 'published', 475, NOW() - INTERVAL 7 DAY, NOW() - INTERVAL 7 DAY),

(@hr1_id, @comp1_id, 'Tech Lead Java Spring Boot (Fintech Core)', 'Tech Lead / Manager', 'Toàn thời gian (Full-time)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 14 DAY),
 'Dẫn dắt team 8 kỹ sư backend xây dựng lõi thanh toán an toàn và mở rộng.',
 'Ít nhất 6 năm Java/Spring Boot, am hiểu phân tán, Kafka và bảo mật hệ thống tài chính.',
 JSON_ARRAY('Java', 'Spring Boot', 'MySQL', 'Redis', 'Kubernetes'), NULL, NULL, TRUE,
 JSON_ARRAY('Gói ESOP hấp dẫn', 'Bảo hiểm cho cả gia đình'),
 'published', 710, NOW() - INTERVAL 8 DAY, NOW() - INTERVAL 8 DAY),

(@hr1_id, @comp1_id, 'Junior QA / Automation Tester (Playwright)', 'Junior', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 2, DATE_ADD(CURDATE(), INTERVAL 21 DAY),
 'Thiết kế test case và viết kịch bản kiểm thử tự động E2E cho các luồng nghiệp vụ chính.',
 '1+ năm kinh nghiệm QA, biết TypeScript hoặc JavaScript với Playwright/Cypress.',
 JSON_ARRAY('TypeScript', 'JavaScript', 'CI/CD'), 14000000, 20000000, FALSE,
 JSON_ARRAY('Được mentor 1-1', 'Phụ cấp chứng chỉ ISTQB'),
 'published', 294, NOW() - INTERVAL 10 DAY, NOW() - INTERVAL 10 DAY),

(@hr1_id, @comp1_id, 'Golang Microservices Developer', 'Middle', 'Hybrid (Linh hoạt)', 'Hà Nội', 2, DATE_ADD(CURDATE(), INTERVAL 3 DAY),
 'Xây dựng các service xử lý dữ liệu thời gian thực độ trễ thấp bằng Go.',
 'Từ 2 năm kinh nghiệm Golang, gRPC, Redis và MySQL.',
 JSON_ARRAY('Go', 'MySQL', 'Redis', 'Docker'), 28000000, 42000000, FALSE,
 JSON_ARRAY('Thưởng dự án theo quý', 'Khám sức khỏe định kỳ'),
 'published', 402, NOW() - INTERVAL 11 DAY, NOW() - INTERVAL 11 DAY),

(@hr1_id, @comp1_id, 'Fresher Frontend ReactJS (Chương trình Đào tạo)', 'Fresher', 'Toàn thời gian (Full-time)', 'Đà Nẵng', 4, DATE_ADD(CURDATE(), INTERVAL 19 DAY),
 'Tham gia dự án thực tế cùng đội ngũ sản phẩm, được hướng dẫn bài bản từ Senior.',
 'Nắm vững JavaScript ES6+, React cơ bản và có sản phẩm cá nhân.',
 JSON_ARRAY('React', 'JavaScript', 'Tailwind CSS'), 9000000, 13000000, FALSE,
 JSON_ARRAY('Lộ trình lên Junior sau 6 tháng', 'Hỗ trợ ăn trưa'),
 'published', 860, NOW() - INTERVAL 13 DAY, NOW() - INTERVAL 13 DAY),

(@hr1_id, @comp1_id, 'Data Engineer (Python / Airflow / BigQuery)', 'Middle', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 1, DATE_ADD(CURDATE(), INTERVAL 12 DAY),
 'Xây dựng pipeline ETL/ELT thu thập và chuẩn hóa dữ liệu hành vi người dùng.',
 'Thành thạo Python, SQL nâng cao và kinh nghiệm vận hành data warehouse.',
 JSON_ARRAY('Python', 'PostgreSQL', 'AWS', 'Docker'), 26000000, 40000000, FALSE,
 JSON_ARRAY('Thưởng tháng 13', 'Team building 2 lần/năm'),
 'published', 312, NOW() - INTERVAL 15 DAY, NOW() - INTERVAL 15 DAY),

(@hr1_id, @comp1_id, 'UI/UX Designer (Design System & Web App)', 'Middle', 'Hybrid (Linh hoạt)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 22 DAY),
 'Thiết kế giao diện B2B SaaS gọn gàng, xây dựng và duy trì Design System.',
 'Thành thạo Figma, có portfolio sản phẩm web/mobile đã triển khai thực tế.',
 JSON_ARRAY('Tailwind CSS', 'React'), 18000000, 28000000, FALSE,
 JSON_ARRAY('Môi trường cởi mở', 'Nghỉ thứ 7 & Chủ nhật'),
 'published', 265, NOW() - INTERVAL 16 DAY, NOW() - INTERVAL 16 DAY),

(@hr1_id, @comp1_id, 'Mobile Developer (React Native / iOS & Android)', 'Senior', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 1, DATE_ADD(CURDATE(), INTERVAL 9 DAY),
 'Phát triển và tối ưu ứng dụng di động cho hàng trăm nghìn ứng viên.',
 '3+ năm React Native, nắm vững native bridge và quy trình release App Store/Play Store.',
 JSON_ARRAY('React', 'TypeScript', 'GraphQL'), 32000000, 48000000, FALSE,
 JSON_ARRAY('Bảo hiểm sức khỏe PTI', 'Phụ cấp thiết bị'),
 'published', 351, NOW() - INTERVAL 18 DAY, NOW() - INTERVAL 18 DAY),

(@hr1_id, @comp1_id, 'Intern Backend Python (Hỗ trợ thực tập có lương)', 'Intern / Thực tập sinh', 'Bán thời gian (Part-time)', 'Hà Nội', 5, DATE_ADD(CURDATE(), INTERVAL 27 DAY),
 'Học hỏi và tham gia phát triển tính năng phụ trợ dưới sự hướng dẫn của Mentor.',
 'Sinh viên năm 3-4 CNTT, biết Python và SQL cơ bản, đi làm tối thiểu 24h/tuần.',
 JSON_ARRAY('Python', 'MySQL', 'FastAPI'), 5000000, 7000000, FALSE,
 JSON_ARRAY('Trợ cấp thực tập hàng tháng', 'Cơ hội lên chính thức'),
 'published', 530, NOW() - INTERVAL 20 DAY, NOW() - INTERVAL 20 DAY),

-- 4 tin Nháp (draft)
(@hr1_id, @comp1_id, 'AI / Machine Learning Engineer (NLP & Matching)', 'Senior', 'Toàn thời gian (Full-time)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 30 DAY),
 'Nghiên cứu mô hình gợi ý việc làm phù hợp dựa trên CV và lịch sử ứng tuyển.',
 'Kinh nghiệm triển khai mô hình NLP/LLM trong production.',
 JSON_ARRAY('Python', 'Docker', 'AWS'), NULL, NULL, TRUE,
 JSON_ARRAY('Ngân sách GPU riêng cho R&D'),
 'draft', 0, NULL, NOW() - INTERVAL 1 DAY),

(@hr1_id, @comp1_id, 'Product Manager (HR Tech Platform)', 'Tech Lead / Manager', 'Hybrid (Linh hoạt)', 'TP. Hồ Chí Minh', 1, DATE_ADD(CURDATE(), INTERVAL 28 DAY),
 'Định hướng lộ trình sản phẩm cho phân hệ nhà tuyển dụng.',
 '3+ năm làm Product Manager sản phẩm B2B SaaS.',
 JSON_ARRAY('GraphQL', 'MySQL'), 38000000, 55000000, FALSE,
 JSON_ARRAY('Thưởng KPI sản phẩm'),
 'draft', 0, NULL, NOW() - INTERVAL 3 DAY),

(@hr1_id, @comp1_id, 'Junior Node.js Backend Developer', 'Junior', 'Toàn thời gian (Full-time)', 'Cần Thơ', 2, DATE_ADD(CURDATE(), INTERVAL 24 DAY),
 'Phát triển RESTful API và webhook tích hợp đối tác.',
 '1 năm kinh nghiệm Node.js/Express hoặc NestJS.',
 JSON_ARRAY('Node.js', 'TypeScript', 'PostgreSQL'), 13000000, 19000000, FALSE,
 JSON_ARRAY('Hỗ trợ ăn trưa'),
 'draft', 0, NULL, NOW() - INTERVAL 6 DAY),

(@hr1_id, @comp1_id, 'Security Engineer (AppSec & Pentest)', 'Middle', 'Remote (Từ xa)', 'Remote / Toàn quốc', 1, DATE_ADD(CURDATE(), INTERVAL 35 DAY),
 'Kiểm tra bảo mật định kỳ hệ thống web và API.',
 'Am hiểu OWASP Top 10, có chứng chỉ CEH hoặc OSCP là lợi thế.',
 JSON_ARRAY('CI/CD', 'Docker', 'AWS'), 28000000, 42000000, FALSE,
 JSON_ARRAY('Làm việc từ xa linh hoạt'),
 'draft', 0, NULL, NOW() - INTERVAL 9 DAY),

-- 3 tin Chờ duyệt (pending)
(@hr1_id, @comp1_id, 'Solutions Architect (Cloud & Enterprise)', 'Tech Lead / Manager', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 1, DATE_ADD(CURDATE(), INTERVAL 20 DAY),
 'Tư vấn kiến trúc hệ thống cho khách hàng doanh nghiệp lớn.',
 '5+ năm thiết kế hệ thống phân tán trên AWS/GCP.',
 JSON_ARRAY('AWS', 'Kubernetes', 'Go', 'PostgreSQL'), 50000000, 75000000, FALSE,
 JSON_ARRAY('Gói phúc lợi quản lý cấp cao'),
 'pending', 12, NULL, NOW() - INTERVAL 1 DAY),

(@hr1_id, @comp1_id, 'Next.js Frontend Engineer (SEO & Performance)', 'Middle', 'Hybrid (Linh hoạt)', 'Hà Nội', 2, DATE_ADD(CURDATE(), INTERVAL 15 DAY),
 'Tối ưu SSR/ISR cho cổng thông tin việc làm tốc độ cao.',
 '2+ năm kinh nghiệm Next.js, TypeScript, Core Web Vitals.',
 JSON_ARRAY('Next.js', 'React', 'TypeScript'), 24000000, 36000000, FALSE,
 JSON_ARRAY('Thưởng hiệu suất quý'),
 'pending', 5, NULL, NOW() - INTERVAL 3 DAY),

(@hr1_id, @comp1_id, 'Database Administrator (MySQL / PostgreSQL)', 'Senior', 'Toàn thời gian (Full-time)', 'Hà Nội', 1, DATE_ADD(CURDATE(), INTERVAL 26 DAY),
 'Quản trị, tối ưu truy vấn và đảm bảo High Availability cho cụm database.',
 '3+ năm DBA MySQL/PostgreSQL quy mô lớn.',
 JSON_ARRAY('MySQL', 'PostgreSQL', 'Redis'), 30000000, 45000000, FALSE,
 JSON_ARRAY('Phụ cấp trực on-call'),
 'pending', 8, NULL, NOW() - INTERVAL 5 DAY),

-- 2 tin Đang ẩn (hidden)
(@hr1_id, @comp1_id, 'Java Developer (Spring Boot / Microservices)', 'Middle', 'Toàn thời gian (Full-time)', 'Hải Phòng', 2, DATE_ADD(CURDATE(), INTERVAL 17 DAY),
 'Phát triển hệ thống quản lý vận tải và kho bãi.',
 '2+ năm Java Spring Boot, MySQL.',
 JSON_ARRAY('Java', 'Spring Boot', 'MySQL'), 22000000, 34000000, FALSE,
 JSON_ARRAY('Xe đưa đón nhân viên'),
 'hidden', 198, NOW() - INTERVAL 19 DAY, NOW() - INTERVAL 19 DAY),

(@hr1_id, @comp1_id, 'Technical Writer (API & Developer Docs)', 'Junior', 'Hợp đồng / Freelance', 'Remote / Toàn quốc', 1, DATE_ADD(CURDATE(), INTERVAL 11 DAY),
 'Biên soạn tài liệu hướng dẫn tích hợp API cho đối tác.',
 'Tiếng Anh đọc viết tốt, hiểu REST API và OpenAPI.',
 JSON_ARRAY('FastAPI', 'GraphQL'), 15000000, 22000000, FALSE,
 JSON_ARRAY('Thời gian linh hoạt'),
 'hidden', 112, NOW() - INTERVAL 22 DAY, NOW() - INTERVAL 22 DAY),

-- 3 tin Đã đóng (closed)
(@hr1_id, @comp1_id, 'Senior Vue.js Engineer (Dashboard Analytics)', 'Senior', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 1, DATE_SUB(CURDATE(), INTERVAL 3 DAY),
 'Xây dựng hệ thống biểu đồ phân tích dữ liệu tuyển dụng.',
 '3+ năm Vue 3, TypeScript, ECharts/Canvas.',
 JSON_ARRAY('Vue.js', 'TypeScript', 'JavaScript'), 30000000, 45000000, FALSE,
 JSON_ARRAY('Thưởng tháng 13'),
 'closed', 940, NOW() - INTERVAL 35 DAY, NOW() - INTERVAL 35 DAY),

(@hr1_id, @comp1_id, 'IT Business Analyst (ERP & CRM)', 'Middle', 'Toàn thời gian (Full-time)', 'Hà Nội', 2, DATE_SUB(CURDATE(), INTERVAL 8 DAY),
 'Phân tích nghiệp vụ và viết tài liệu đặc tả cho team kỹ thuật.',
 '2+ năm BA trong dự án phần mềm.',
 JSON_ARRAY('MySQL', 'PostgreSQL'), 20000000, 30000000, FALSE,
 JSON_ARRAY('Bảo hiểm sức khỏe'),
 'closed', 615, NOW() - INTERVAL 42 DAY, NOW() - INTERVAL 42 DAY),

(@hr1_id, @comp1_id, 'Scrum Master / Agile Coach', 'Senior', 'Hybrid (Linh hoạt)', 'Đà Nẵng', 1, DATE_SUB(CURDATE(), INTERVAL 12 DAY),
 'Điều phối quy trình Scrum cho 3 squad phát triển sản phẩm.',
 'Chứng chỉ PSM/CSM, 3+ năm kinh nghiệm Scrum Master.',
 JSON_ARRAY('CI/CD'), NULL, NULL, TRUE,
 JSON_ARRAY('Môi trường Agile chuẩn mực'),
 'closed', 488, NOW() - INTERVAL 50 DAY, NOW() - INTERVAL 50 DAY),

-- 2 tin của hr2@tuyendung.com để kiểm tra phân quyền tách biệt theo employer_id
(@hr2_id, @comp2_id, 'Backend PHP Laravel Engineer', 'Middle', 'Toàn thời gian (Full-time)', 'Bình Dương', 2, DATE_ADD(CURDATE(), INTERVAL 15 DAY),
 'Phát triển hệ thống thương mại điện tử.',
 '2+ năm PHP Laravel, MySQL.',
 JSON_ARRAY('MySQL', 'Redis'), 18000000, 26000000, FALSE,
 JSON_ARRAY('Thưởng doanh số'),
 'published', 120, NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY),

(@hr2_id, @comp2_id, 'Manual QA Tester', 'Fresher', 'Toàn thời gian (Full-time)', 'TP. Hồ Chí Minh', 1, DATE_ADD(CURDATE(), INTERVAL 20 DAY),
 'Kiểm thử chức năng web và mobile.',
 'Cẩn thận, nắm vững quy trình test.',
 JSON_ARRAY('JavaScript'), 10000000, 14000000, FALSE,
 JSON_ARRAY('Phụ cấp gửi xe'),
 'draft', 0, NULL, NOW() - INTERVAL 2 DAY);

-- Seed hồ sơ ứng tuyển cho các tin của hr1 (để COUNT/GROUP BY ra số thực)
INSERT INTO job_applications (job_id, candidate_id, is_viewed, created_at)
SELECT j.id, @uv1_id, FALSE, NOW() - INTERVAL 1 HOUR FROM jobs j WHERE j.employer_id = @hr1_id AND j.status = 'published' ORDER BY j.id ASC LIMIT 6;

INSERT INTO job_applications (job_id, candidate_id, is_viewed, created_at)
SELECT j.id, @uv2_id, FALSE, NOW() - INTERVAL 3 HOUR FROM jobs j WHERE j.employer_id = @hr1_id AND j.status = 'published' ORDER BY j.id ASC LIMIT 4;

INSERT INTO job_applications (job_id, candidate_id, is_viewed, created_at)
SELECT j.id, @uv3_id, TRUE, NOW() - INTERVAL 1 DAY FROM jobs j WHERE j.employer_id = @hr1_id AND j.status = 'published' ORDER BY j.id ASC LIMIT 9;

INSERT INTO job_applications (job_id, candidate_id, is_viewed, created_at)
SELECT j.id, @uv4_id, TRUE, NOW() - INTERVAL 2 DAY FROM jobs j WHERE j.employer_id = @hr1_id AND j.status IN ('published', 'closed', 'hidden') ORDER BY j.id ASC LIMIT 12;

INSERT INTO job_applications (job_id, candidate_id, is_viewed, created_at)
SELECT j.id, @uv5_id, TRUE, NOW() - INTERVAL 3 DAY FROM jobs j WHERE j.employer_id = @hr1_id AND j.status IN ('published', 'closed') ORDER BY j.id ASC LIMIT 8;


-- ================================================================== --
-- 3. Bảng và Seed dữ liệu hồ sơ ứng tuyển (applications, cvs, v.v.)
-- ================================================================== --

CREATE TABLE IF NOT EXISTS meta_application_statuses (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    slug        VARCHAR(40)  NOT NULL UNIQUE,
    name        VARCHAR(80)  NOT NULL,
    tone        VARCHAR(30)  NOT NULL,
    sort_order  INT          NOT NULL,
    is_terminal BOOLEAN      NOT NULL DEFAULT FALSE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meta_withdraw_reasons (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    slug       VARCHAR(60)  NOT NULL UNIQUE,
    name       VARCHAR(160) NOT NULL,
    sort_order INT          NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cover_letter_templates (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    title      VARCHAR(120) NOT NULL,
    content    TEXT         NOT NULL,
    sort_order INT          NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cvs (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id  INT          NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    stored_name   VARCHAR(255) NOT NULL,
    mime_type     VARCHAR(120) NOT NULL,
    size_bytes    INT          NOT NULL,
    is_default    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cv_user FOREIGN KEY (candidate_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_cvs_candidate_id (candidate_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS applications (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id       INT          NOT NULL,
    job_id             INT          NOT NULL,
    cv_id              INT          NULL,
    cv_name_snapshot   VARCHAR(255) NOT NULL,
    cover_letter       TEXT         NULL,
    status             VARCHAR(32)  NOT NULL,
    active_flag        INT          NULL,
    idempotency_key    VARCHAR(100) NULL,
    withdraw_reason    VARCHAR(255) NULL,
    withdrawn_at       DATETIME     NULL,
    interview_at       DATETIME     NULL,
    interview_mode     VARCHAR(80)  NULL,
    interview_location VARCHAR(255) NULL,
    created_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_app_user FOREIGN KEY (candidate_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_app_job  FOREIGN KEY (job_id)       REFERENCES jobs(id)  ON DELETE CASCADE,
    CONSTRAINT fk_app_cv   FOREIGN KEY (cv_id)        REFERENCES cvs(id)   ON DELETE SET NULL,
    UNIQUE KEY uq_app_cand_job_active (candidate_id, job_id, active_flag),
    UNIQUE KEY uq_app_idempotency (candidate_id, idempotency_key),
    INDEX idx_apps_candidate_id (candidate_id),
    INDEX idx_apps_status (status),
    INDEX idx_apps_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS application_status_history (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT          NOT NULL,
    status         VARCHAR(32)  NOT NULL,
    note           VARCHAR(500) NULL,
    changed_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ash_app FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
    INDEX idx_ash_app_id (application_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS application_drafts (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id INT       NOT NULL,
    job_id       INT       NOT NULL,
    cover_letter TEXT      NOT NULL,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ad_user FOREIGN KEY (candidate_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_ad_job  FOREIGN KEY (job_id)       REFERENCES jobs(id)  ON DELETE CASCADE,
    UNIQUE KEY uq_ad_candidate_job (candidate_id, job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Meta Application Statuses
INSERT INTO meta_application_statuses (slug, name, tone, sort_order, is_terminal) VALUES ('submitted', 'Đã nộp', 'info', 1, 0) ON DUPLICATE KEY UPDATE name=VALUES(name), tone=VALUES(tone), sort_order=VALUES(sort_order), is_terminal=VALUES(is_terminal);
INSERT INTO meta_application_statuses (slug, name, tone, sort_order, is_terminal) VALUES ('screening', 'Đang xem xét', 'warning', 2, 0) ON DUPLICATE KEY UPDATE name=VALUES(name), tone=VALUES(tone), sort_order=VALUES(sort_order), is_terminal=VALUES(is_terminal);
INSERT INTO meta_application_statuses (slug, name, tone, sort_order, is_terminal) VALUES ('interview', 'Phỏng vấn', 'teal', 3, 0) ON DUPLICATE KEY UPDATE name=VALUES(name), tone=VALUES(tone), sort_order=VALUES(sort_order), is_terminal=VALUES(is_terminal);
INSERT INTO meta_application_statuses (slug, name, tone, sort_order, is_terminal) VALUES ('offered', 'Đề nghị nhận việc', 'success', 4, 0) ON DUPLICATE KEY UPDATE name=VALUES(name), tone=VALUES(tone), sort_order=VALUES(sort_order), is_terminal=VALUES(is_terminal);
INSERT INTO meta_application_statuses (slug, name, tone, sort_order, is_terminal) VALUES ('rejected', 'Không phù hợp', 'danger', 5, 1) ON DUPLICATE KEY UPDATE name=VALUES(name), tone=VALUES(tone), sort_order=VALUES(sort_order), is_terminal=VALUES(is_terminal);
INSERT INTO meta_application_statuses (slug, name, tone, sort_order, is_terminal) VALUES ('withdrawn', 'Đã rút', 'neutral', 6, 1) ON DUPLICATE KEY UPDATE name=VALUES(name), tone=VALUES(tone), sort_order=VALUES(sort_order), is_terminal=VALUES(is_terminal);

-- Meta Withdraw Reasons
INSERT INTO meta_withdraw_reasons (slug, name, sort_order) VALUES ('accepted_other', 'Đã nhận được lời mời làm việc khác', 1) ON DUPLICATE KEY UPDATE name=VALUES(name), sort_order=VALUES(sort_order);
INSERT INTO meta_withdraw_reasons (slug, name, sort_order) VALUES ('salary_mismatch', 'Mức lương / phúc lợi chưa phù hợp', 2) ON DUPLICATE KEY UPDATE name=VALUES(name), sort_order=VALUES(sort_order);
INSERT INTO meta_withdraw_reasons (slug, name, sort_order) VALUES ('location_mismatch', 'Địa điểm hoặc hình thức làm việc chưa thuận tiện', 3) ON DUPLICATE KEY UPDATE name=VALUES(name), sort_order=VALUES(sort_order);
INSERT INTO meta_withdraw_reasons (slug, name, sort_order) VALUES ('personal_plan', 'Thay đổi kế hoạch cá nhân', 4) ON DUPLICATE KEY UPDATE name=VALUES(name), sort_order=VALUES(sort_order);
INSERT INTO meta_withdraw_reasons (slug, name, sort_order) VALUES ('other', 'Lý do khác', 5) ON DUPLICATE KEY UPDATE name=VALUES(name), sort_order=VALUES(sort_order);

-- Cover Letter Templates
INSERT INTO cover_letter_templates (title, content, sort_order) VALUES ('Mẫu ứng tuyển kỹ thuật ngắn gọn', 'Kính gửi Anh/Chị bộ phận Tuyển dụng,

Tôi rất quan tâm đến vị trí này và tin rằng kinh nghiệm thực tế về phát triển phần mềm, tối ưu hiệu năng và làm việc nhóm Agile của mình sẽ đóng góp tích cực cho đội ngũ. Đính kèm là CV chi tiết của tôi. Rất mong có cơ hội trao đổi thêm trong buổi phỏng vấn.

Trân trọng!', 1) ON DUPLICATE KEY UPDATE content=VALUES(content);
INSERT INTO cover_letter_templates (title, content, sort_order) VALUES ('Mẫu nhấn mạnh dự án & kết quả', 'Kính gửi Quý Công ty,

Qua tìm hiểu sản phẩm và định hướng công nghệ của Quý Công ty, tôi mong muốn được ứng tuyển để đồng hành cùng team trong các bài toán quy mô lớn. Trong các dự án gần đây, tôi trực tiếp thiết kế API, cải thiện tốc độ tải trang và phối hợp chặt chẽ với Product/QA để bàn giao đúng tiến độ.

Rất mong nhận được phản hồi từ Anh/Chị.', 2) ON DUPLICATE KEY UPDATE content=VALUES(content);
INSERT INTO cover_letter_templates (title, content, sort_order) VALUES ('Mẫu chuyển hướng / Fresher cầu tiến', 'Kính gửi Anh/Chị,

Dù kinh nghiệm ở vị trí chuyên sâu còn đang mở rộng, tôi đã chủ động hoàn thành nhiều dự án thực hành, nắm vững nền tảng kỹ thuật và sẵn sàng học hỏi nhanh trong môi trường thực tế. Tôi rất trân trọng nếu có cơ hội được thử sức và cống hiến.

Xin chân thành cảm ơn!', 3) ON DUPLICATE KEY UPDATE content=VALUES(content);

-- Seed CVs cho ungvien1
DELETE FROM cvs WHERE candidate_id = @uv1_id;
INSERT INTO cvs (id, candidate_id, original_name, stored_name, mime_type, size_bytes, is_default, created_at) VALUES (4, @uv1_id, 'CV_NguyenVanAn_Fullstack_2026.pdf', 'cv_seed_1.pdf', 'application/pdf', 428150, 1, NOW() - INTERVAL 45 DAY) ON DUPLICATE KEY UPDATE original_name=VALUES(original_name);
INSERT INTO cvs (id, candidate_id, original_name, stored_name, mime_type, size_bytes, is_default, created_at) VALUES (5, @uv1_id, 'CV_NguyenVanAn_Backend_Python.pdf', 'cv_seed_2.pdf', 'application/pdf', 362900, 0, NOW() - INTERVAL 20 DAY) ON DUPLICATE KEY UPDATE original_name=VALUES(original_name);
INSERT INTO cvs (id, candidate_id, original_name, stored_name, mime_type, size_bytes, is_default, created_at) VALUES (6, @uv1_id, 'CV_NguyenVanAn_English.pdf', 'cv_seed_3.pdf', 'application/pdf', 512400, 0, NOW() - INTERVAL 5 DAY) ON DUPLICATE KEY UPDATE original_name=VALUES(original_name);

-- Seed >= 25 Hồ sơ ứng tuyển cho ungvien1 (ngày tương đối, đủ mọi trạng thái)
DELETE FROM applications WHERE candidate_id = @uv1_id;
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (1, @uv1_id, 3, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', 'Tôi có kinh nghiệm thực chiến với REST API, tối ưu truy vấn MySQL và làm việc chặt chẽ cùng team Product.', 'submitted', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 1 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (2, @uv1_id, 4, 5, 'CV_NguyenVanAn_Backend_Python.pdf', NULL, 'submitted', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 4 DAY, NOW() - INTERVAL 2 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (3, @uv1_id, 5, 6, 'CV_NguyenVanAn_English.pdf', 'Đính kèm là CV cập nhật mới nhất của tôi. Rất mong có dịp trao đổi chi tiết hơn về định hướng vị trí này.', 'submitted', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 6 DAY, NOW() - INTERVAL 3 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (4, @uv1_id, 6, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', 'Kính gửi Anh/Chị, tôi rất ấn tượng với sản phẩm của công ty và mong muốn đóng góp kinh nghiệm xây dựng hệ thống ổn định, dễ bảo trì.', 'submitted', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 8 DAY, NOW() - INTERVAL 4 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (5, @uv1_id, 7, 5, 'CV_NguyenVanAn_Backend_Python.pdf', 'Tôi có kinh nghiệm thực chiến với REST API, tối ưu truy vấn MySQL và làm việc chặt chẽ cùng team Product.', 'submitted', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 10 DAY, NOW() - INTERVAL 5 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (6, @uv1_id, 8, 6, 'CV_NguyenVanAn_English.pdf', NULL, 'submitted', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 12 DAY, NOW() - INTERVAL 6 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (7, @uv1_id, 9, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', 'Đính kèm là CV cập nhật mới nhất của tôi. Rất mong có dịp trao đổi chi tiết hơn về định hướng vị trí này.', 'screening', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 14 DAY, NOW() - INTERVAL 7 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (8, @uv1_id, 10, 5, 'CV_NguyenVanAn_Backend_Python.pdf', 'Kính gửi Anh/Chị, tôi rất ấn tượng với sản phẩm của công ty và mong muốn đóng góp kinh nghiệm xây dựng hệ thống ổn định, dễ bảo trì.', 'screening', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 16 DAY, NOW() - INTERVAL 8 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (9, @uv1_id, 11, 6, 'CV_NguyenVanAn_English.pdf', 'Tôi có kinh nghiệm thực chiến với REST API, tối ưu truy vấn MySQL và làm việc chặt chẽ cùng team Product.', 'screening', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 18 DAY, NOW() - INTERVAL 9 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (10, @uv1_id, 12, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', NULL, 'screening', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 20 DAY, NOW() - INTERVAL 10 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (11, @uv1_id, 25, 5, 'CV_NguyenVanAn_Backend_Python.pdf', 'Đính kèm là CV cập nhật mới nhất của tôi. Rất mong có dịp trao đổi chi tiết hơn về định hướng vị trí này.', 'screening', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 22 DAY, NOW() - INTERVAL 11 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (12, @uv1_id, 53, 6, 'CV_NguyenVanAn_English.pdf', 'Kính gửi Anh/Chị, tôi rất ấn tượng với sản phẩm của công ty và mong muốn đóng góp kinh nghiệm xây dựng hệ thống ổn định, dễ bảo trì.', 'screening', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 24 DAY, NOW() - INTERVAL 12 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (13, @uv1_id, 54, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', 'Tôi có kinh nghiệm thực chiến với REST API, tối ưu truy vấn MySQL và làm việc chặt chẽ cùng team Product.', 'interview', 1, NULL, NULL, NULL, NOW() + INTERVAL 3 DAY, 'Trực tiếp tại văn phòng', 'Tầng 8, Tòa nhà TechHub, Cầu Giấy, Hà Nội', NOW() - INTERVAL 26 DAY, NOW() - INTERVAL 13 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (14, @uv1_id, 55, 5, 'CV_NguyenVanAn_Backend_Python.pdf', NULL, 'interview', 1, NULL, NULL, NULL, NOW() + INTERVAL 3 DAY, 'Trực tuyến (Google Meet)', 'Link Google Meet sẽ gửi qua email trước 30 phút', NOW() - INTERVAL 28 DAY, NOW() - INTERVAL 14 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (15, @uv1_id, 56, 6, 'CV_NguyenVanAn_English.pdf', 'Đính kèm là CV cập nhật mới nhất của tôi. Rất mong có dịp trao đổi chi tiết hơn về định hướng vị trí này.', 'interview', 1, NULL, NULL, NULL, NOW() + INTERVAL 3 DAY, 'Trực tiếp tại văn phòng', 'Tầng 8, Tòa nhà TechHub, Cầu Giấy, Hà Nội', NOW() - INTERVAL 30 DAY, NOW() - INTERVAL 15 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (16, @uv1_id, 57, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', 'Kính gửi Anh/Chị, tôi rất ấn tượng với sản phẩm của công ty và mong muốn đóng góp kinh nghiệm xây dựng hệ thống ổn định, dễ bảo trì.', 'interview', 1, NULL, NULL, NULL, NOW() + INTERVAL 3 DAY, 'Trực tuyến (Google Meet)', 'Link Google Meet sẽ gửi qua email trước 30 phút', NOW() - INTERVAL 32 DAY, NOW() - INTERVAL 16 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (17, @uv1_id, 58, 5, 'CV_NguyenVanAn_Backend_Python.pdf', 'Tôi có kinh nghiệm thực chiến với REST API, tối ưu truy vấn MySQL và làm việc chặt chẽ cùng team Product.', 'interview', 1, NULL, NULL, NULL, NOW() + INTERVAL 3 DAY, 'Trực tiếp tại văn phòng', 'Tầng 8, Tòa nhà TechHub, Cầu Giấy, Hà Nội', NOW() - INTERVAL 34 DAY, NOW() - INTERVAL 17 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (18, @uv1_id, 59, 6, 'CV_NguyenVanAn_English.pdf', NULL, 'offered', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 36 DAY, NOW() - INTERVAL 18 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (19, @uv1_id, 60, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', 'Đính kèm là CV cập nhật mới nhất của tôi. Rất mong có dịp trao đổi chi tiết hơn về định hướng vị trí này.', 'offered', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 38 DAY, NOW() - INTERVAL 19 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (20, @uv1_id, 61, 5, 'CV_NguyenVanAn_Backend_Python.pdf', 'Kính gửi Anh/Chị, tôi rất ấn tượng với sản phẩm của công ty và mong muốn đóng góp kinh nghiệm xây dựng hệ thống ổn định, dễ bảo trì.', 'offered', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 40 DAY, NOW() - INTERVAL 20 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (21, @uv1_id, 62, 6, 'CV_NguyenVanAn_English.pdf', 'Tôi có kinh nghiệm thực chiến với REST API, tối ưu truy vấn MySQL và làm việc chặt chẽ cùng team Product.', 'rejected', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 42 DAY, NOW() - INTERVAL 21 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (22, @uv1_id, 63, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', NULL, 'rejected', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 44 DAY, NOW() - INTERVAL 22 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (23, @uv1_id, 64, 5, 'CV_NguyenVanAn_Backend_Python.pdf', 'Đính kèm là CV cập nhật mới nhất của tôi. Rất mong có dịp trao đổi chi tiết hơn về định hướng vị trí này.', 'rejected', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 46 DAY, NOW() - INTERVAL 23 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (24, @uv1_id, 65, 6, 'CV_NguyenVanAn_English.pdf', 'Kính gửi Anh/Chị, tôi rất ấn tượng với sản phẩm của công ty và mong muốn đóng góp kinh nghiệm xây dựng hệ thống ổn định, dễ bảo trì.', 'rejected', 1, NULL, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 48 DAY, NOW() - INTERVAL 24 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (25, @uv1_id, 66, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', 'Tôi có kinh nghiệm thực chiến với REST API, tối ưu truy vấn MySQL và làm việc chặt chẽ cùng team Product.', 'withdrawn', NULL, NULL, 'Đã nhận được lời mời làm việc khác', NOW() - INTERVAL 1 DAY, NULL, NULL, NULL, NOW() - INTERVAL 50 DAY, NOW() - INTERVAL 25 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (26, @uv1_id, 67, 5, 'CV_NguyenVanAn_Backend_Python.pdf', NULL, 'withdrawn', NULL, NULL, 'Đã nhận được lời mời làm việc khác', NOW() - INTERVAL 1 DAY, NULL, NULL, NULL, NOW() - INTERVAL 52 DAY, NOW() - INTERVAL 26 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (27, @uv1_id, 68, 6, 'CV_NguyenVanAn_English.pdf', 'Đính kèm là CV cập nhật mới nhất của tôi. Rất mong có dịp trao đổi chi tiết hơn về định hướng vị trí này.', 'withdrawn', NULL, NULL, 'Đã nhận được lời mời làm việc khác', NOW() - INTERVAL 1 DAY, NULL, NULL, NULL, NOW() - INTERVAL 54 DAY, NOW() - INTERVAL 27 DAY);
INSERT INTO applications (id, candidate_id, job_id, cv_id, cv_name_snapshot, cover_letter, status, active_flag, idempotency_key, withdraw_reason, withdrawn_at, interview_at, interview_mode, interview_location, created_at, updated_at) VALUES (28, @uv1_id, 69, 4, 'CV_NguyenVanAn_Fullstack_2026.pdf', 'Kính gửi Anh/Chị, tôi rất ấn tượng với sản phẩm của công ty và mong muốn đóng góp kinh nghiệm xây dựng hệ thống ổn định, dễ bảo trì.', 'withdrawn', NULL, NULL, 'Đã nhận được lời mời làm việc khác', NOW() - INTERVAL 1 DAY, NULL, NULL, NULL, NOW() - INTERVAL 56 DAY, NOW() - INTERVAL 28 DAY);

-- Seed Application Status History (nhiều mốc thời gian cho mỗi hồ sơ)
DELETE FROM application_status_history WHERE application_id IN (SELECT id FROM applications WHERE candidate_id = @uv1_id);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (1, 1, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 2 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (2, 2, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 4 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (3, 3, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 6 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (4, 4, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 8 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (5, 5, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 10 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (6, 6, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 12 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (7, 7, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 14 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (8, 8, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 16 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (9, 9, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 18 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (10, 10, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 20 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (11, 11, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 22 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (12, 12, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 24 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (13, 13, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 26 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (14, 14, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 28 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (15, 15, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 30 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (16, 16, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 32 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (17, 17, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 34 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (18, 18, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 36 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (19, 19, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 38 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (20, 20, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 40 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (21, 21, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 42 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (22, 22, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 44 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (23, 23, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 46 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (24, 24, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 48 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (25, 25, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 50 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (26, 26, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 52 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (27, 27, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 54 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (28, 28, 'submitted', 'Ứng viên đã gửi hồ sơ ứng tuyển', NOW() - INTERVAL 56 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (32, 7, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 13 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (33, 8, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 15 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (34, 9, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 17 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (35, 10, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 19 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (36, 11, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 21 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (37, 12, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 23 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (38, 13, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 25 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (39, 14, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 27 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (40, 15, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 29 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (41, 16, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 31 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (42, 17, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 33 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (43, 18, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 35 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (44, 19, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 37 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (45, 20, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 39 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (46, 21, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 41 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (47, 22, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 43 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (48, 23, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 45 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (49, 24, 'screening', 'Nhà tuyển dụng đã tiếp nhận và đang xem xét CV', NOW() - INTERVAL 47 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (63, 13, 'interview', 'Mời tham gia phỏng vấn chuyên môn cùng Tech Lead', NOW() - INTERVAL 23 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (64, 14, 'interview', 'Mời tham gia phỏng vấn chuyên môn cùng Tech Lead', NOW() - INTERVAL 25 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (65, 15, 'interview', 'Mời tham gia phỏng vấn chuyên môn cùng Tech Lead', NOW() - INTERVAL 27 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (66, 16, 'interview', 'Mời tham gia phỏng vấn chuyên môn cùng Tech Lead', NOW() - INTERVAL 29 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (67, 17, 'interview', 'Mời tham gia phỏng vấn chuyên môn cùng Tech Lead', NOW() - INTERVAL 31 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (68, 18, 'interview', 'Mời tham gia phỏng vấn chuyên môn cùng Tech Lead', NOW() - INTERVAL 33 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (69, 19, 'interview', 'Mời tham gia phỏng vấn chuyên môn cùng Tech Lead', NOW() - INTERVAL 35 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (70, 20, 'interview', 'Mời tham gia phỏng vấn chuyên môn cùng Tech Lead', NOW() - INTERVAL 37 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (78, 18, 'offered', 'Chúc mừng! Công ty đã gửi thư mời nhận việc qua email', NOW() - INTERVAL 30 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (79, 19, 'offered', 'Chúc mừng! Công ty đã gửi thư mời nhận việc qua email', NOW() - INTERVAL 32 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (80, 20, 'offered', 'Chúc mừng! Công ty đã gửi thư mời nhận việc qua email', NOW() - INTERVAL 34 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (81, 21, 'rejected', 'Hồ sơ chưa phù hợp với yêu cầu hiện tại của vị trí', NOW() - INTERVAL 38 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (82, 22, 'rejected', 'Hồ sơ chưa phù hợp với yêu cầu hiện tại của vị trí', NOW() - INTERVAL 40 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (83, 23, 'rejected', 'Hồ sơ chưa phù hợp với yêu cầu hiện tại của vị trí', NOW() - INTERVAL 42 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (84, 24, 'rejected', 'Hồ sơ chưa phù hợp với yêu cầu hiện tại của vị trí', NOW() - INTERVAL 44 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (88, 25, 'withdrawn', 'Đã nhận được lời mời làm việc khác', NOW() - INTERVAL 5 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (89, 26, 'withdrawn', 'Đã nhận được lời mời làm việc khác', NOW() - INTERVAL 6 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (90, 27, 'withdrawn', 'Đã nhận được lời mời làm việc khác', NOW() - INTERVAL 7 DAY);
INSERT INTO application_status_history (id, application_id, status, note, changed_at) VALUES (91, 28, 'withdrawn', 'Đã nhận được lời mời làm việc khác', NOW() - INTERVAL 8 DAY);
