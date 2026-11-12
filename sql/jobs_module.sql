-- ============================================================
-- MODULE TIN TUYỂN DỤNG & LƯU TIN - Nhóm 5 (KS25-CNTT5)
-- Chạy SAU khi đã chạy init.sql
-- ============================================================

SET NAMES utf8mb4;
USE app_db;

-- ============================================================
-- BẢNG STUB cho các module khác (tạo nếu chưa có, đồng bộ kiểu INT)
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
  id        INT          AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(255) NOT NULL DEFAULT '',
  email     VARCHAR(255) NOT NULL UNIQUE,
  password  VARCHAR(255) NOT NULL DEFAULT '',
  role      VARCHAR(50)  NOT NULL DEFAULT 'candidate'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS companies (
  id          INT          AUTO_INCREMENT PRIMARY KEY,
  employer_id INT          NOT NULL DEFAULT 1,
  name        VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS industries (
  id     INT          AUTO_INCREMENT PRIMARY KEY,
  name   VARCHAR(255) NOT NULL UNIQUE,
  status VARCHAR(50)  NOT NULL DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS locations (
  id     INT          AUTO_INCREMENT PRIMARY KEY,
  name   VARCHAR(255) NOT NULL UNIQUE,
  status VARCHAR(50)  NOT NULL DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS skills (
  id     INT          AUTO_INCREMENT PRIMARY KEY,
  name   VARCHAR(255) NOT NULL UNIQUE,
  status VARCHAR(50)  NOT NULL DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS candidate_profiles (
  id      INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- BẢNG jobs (Tin tuyển dụng + đầy đủ Index cho cột lọc & sắp xếp)
-- ============================================================
CREATE TABLE IF NOT EXISTS jobs (
  id               INT           AUTO_INCREMENT PRIMARY KEY,
  company_id       INT           NOT NULL,
  posted_by        INT           NOT NULL,
  industry_id      INT           NOT NULL,
  location_id      INT           NOT NULL,
  title            VARCHAR(255)  NOT NULL,
  job_type         ENUM('FULLTIME','PARTTIME','INTERN','REMOTE') NOT NULL DEFAULT 'FULLTIME',
  experience_level VARCHAR(50)   NOT NULL DEFAULT 'Kiến thức/Chưa có kinh nghiệm',
  salary_min       DECIMAL(15,2) NULL,
  salary_max       DECIMAL(15,2) NULL,
  is_negotiable    BOOLEAN       NOT NULL DEFAULT FALSE,
  currency         VARCHAR(10)   NOT NULL DEFAULT 'VND',
  quantity         INT           NOT NULL DEFAULT 1,
  description      TEXT          NOT NULL,
  requirements     TEXT          NULL,
  benefits         TEXT          NULL,
  deadline         DATETIME      NOT NULL,
  status           ENUM('DRAFT','PENDING','OPEN','HIDDEN','CLOSED','REJECTED') NOT NULL DEFAULT 'OPEN',
  views_count      INT           NOT NULL DEFAULT 0,
  created_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_jobs_company   FOREIGN KEY (company_id)  REFERENCES companies(id) ON DELETE CASCADE,
  CONSTRAINT fk_jobs_posted_by FOREIGN KEY (posted_by)   REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_jobs_industry  FOREIGN KEY (industry_id) REFERENCES industries(id),
  CONSTRAINT fk_jobs_location  FOREIGN KEY (location_id) REFERENCES locations(id),
  INDEX idx_jobs_status_deadline  (status, deadline),
  INDEX idx_jobs_company          (company_id),
  INDEX idx_jobs_industry         (industry_id),
  INDEX idx_jobs_location         (location_id),
  INDEX idx_jobs_job_type         (job_type),
  INDEX idx_jobs_experience_level (experience_level),
  INDEX idx_jobs_salary           (salary_min, salary_max),
  INDEX idx_jobs_created_at       (created_at),
  INDEX idx_jobs_title            (title)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- BẢNG job_skills (Kỹ năng yêu cầu của tin tuyển dụng)
-- ============================================================
CREATE TABLE IF NOT EXISTS job_skills (
  id          INT       AUTO_INCREMENT PRIMARY KEY,
  job_id      INT       NOT NULL,
  skill_id    INT       NOT NULL,
  is_required BOOLEAN   NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_job_skills_job   FOREIGN KEY (job_id)   REFERENCES jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_job_skills_skill FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
  UNIQUE KEY idx_job_skills_job_skill (job_id, skill_id),
  INDEX idx_job_skills_skill_job (skill_id, job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- BẢNG saved_jobs (Tin tuyển dụng đã lưu của ứng viên)
-- ============================================================
CREATE TABLE IF NOT EXISTS saved_jobs (
  id                   INT       AUTO_INCREMENT PRIMARY KEY,
  candidate_profile_id INT       NOT NULL,
  job_id               INT       NOT NULL,
  saved_at             DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_saved_jobs_candidate FOREIGN KEY (candidate_profile_id) REFERENCES candidate_profiles(id) ON DELETE CASCADE,
  CONSTRAINT fk_saved_jobs_job       FOREIGN KEY (job_id)               REFERENCES jobs(id)               ON DELETE CASCADE,
  CONSTRAINT uq_saved_profile_job    UNIQUE (candidate_profile_id, job_id),
  INDEX idx_saved_jobs_candidate (candidate_profile_id),
  INDEX idx_saved_jobs_job       (job_id),
  INDEX idx_saved_jobs_saved_at  (saved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- DỮ LIỆU MẪU TIN TUYỂN DỤNG (ID 1-40) & KỸ NĂNG YÊU CẦU
-- ============================================================
INSERT IGNORE INTO jobs (id, company_id, posted_by, industry_id, location_id, title, job_type, experience_level, salary_min, salary_max, is_negotiable, quantity, description, requirements, benefits, deadline, status, views_count, created_at) VALUES
(1,  1,  2,  1, 1, 'Lập Trình Viên Senior Java (Spring Boot)',    'FULLTIME', 'Senior (3-5 năm)',     25000000, 35000000, FALSE, 3, 'Phát triển hệ thống Backend quy mô lớn microservices.',   'Trên 3 năm kinh nghiệm Java, Spring Boot, MySQL, Redis.',  'Lương tháng 13, BHYT cao cấp, Du lịch hàng năm.',  '2027-12-31 23:59:59', 'OPEN',    142, NOW()),
(2,  1,  2,  1, 1, 'Lập Trình Viên Frontend ReactJS',             'FULLTIME', 'Middle (1-3 năm)',    15000000, 22000000, FALSE, 2, 'Xây dựng giao diện Web Application responsive.',         'Thành thạo ReactJS, Redux Toolkit, HTML5/CSS3.',           'Thưởng dự án, hỗ trợ laptop, làm việc Hybrid.',    '2027-12-15 23:59:59', 'OPEN',     98, NOW()),
(3,  2,  3,  1, 2, 'Thực Tập Sinh Lập Trình Python / AI',         'INTERN',   'Chưa có kinh nghiệm', NULL,     NULL,     TRUE,  5, 'Nghiên cứu phát triển mô hình AI/LLM cơ bản.',           'Sinh viên năm 3-4 CNTT, biết Python cơ bản.',             'Hỗ trợ mộc thực tập, phụ cấp 3-5 triệu/tháng.',   '2027-11-30 23:59:59', 'OPEN',    215, NOW()),
(4,  2,  3,  1, 2, 'Kỹ Sư DevOps / Cloud AWS',                    'FULLTIME', 'Senior (3-5 năm)',    30000000, 45000000, FALSE, 1, 'Quản trị hạ tầng Cloud, CI/CD pipeline và Kubernetes.',  'Kinh nghiệm AWS, Docker, Kubernetes, Terraform 3+ năm.',  'Lương thưởng cạnh tranh, tăng lương 2 lần/năm.',   '2027-12-20 23:59:59', 'OPEN',     76, NOW()),
(5,  3,  4,  2, 1, 'Chuyên Viên Marketing Digital',               'FULLTIME', 'Middle (1-3 năm)',    12000000, 18000000, FALSE, 2, 'Tối ưu chiến dịch Google Ads, Facebook Ads, TikTok Ads.','Kinh nghiệm chạy ads E-commerce tối thiểu 1 năm.',        'Thưởng KPIs doanh số, môi trường trẻ trung.',      '2027-11-25 23:59:59', 'OPEN',    110, NOW()),
(6,  3,  4,  2, 1, 'Thực Tập Sinh Content Marketing',             'PARTTIME', 'Chưa có kinh nghiệm', 3000000,  5000000,  FALSE, 3, 'Viết bài chuẩn SEO, sáng tạo nội dung Fanpage.',         'Yêu thích viết lách, chăm chỉ, biết Canva cơ bản.',      'Hỗ trợ dấu thực tập, thưởng bài viết hay.',        '2027-12-10 23:59:59', 'OPEN',    165, NOW()),
(7,  4,  5,  3, 3, 'Kế Toán Tổng Hợp Doanh Nghiệp',               'FULLTIME', 'Middle (1-3 năm)',    10000000, 15000000, FALSE, 1, 'Quản lý thu chi, lập báo cáo thuế và tài chính.',        'Tốt nghiệp Kế toán/Tài chính, biết phần mềm MISA.',      'Đóng BHXH đầy đủ, thưởng lễ tết.',                '2027-12-05 23:59:59', 'OPEN',     54, NOW()),
(8,  4,  5,  3, 3, 'Trưởng Phòng Tài Chính Doanh Nghiệp',         'FULLTIME', 'Leader / Manager',   40000000, 60000000, FALSE, 1, 'Hoạch định chiến lược tài chính tập đoàn.',              'Trên 5 năm kinh nghiệm, bằng CPA hoặc CFA.',              'Chế độ đãi ngộ cấp quản lý, xe đưa đón.',          '2027-12-31 23:59:59', 'OPEN',     89, NOW()),
(9,  5,  6,  4, 1, 'Chuyên Viên Nhập Khẩu & Logistics',           'FULLTIME', 'Middle (1-3 năm)',    14000000, 20000000, FALSE, 2, 'Theo dõi chứng từ xuất nhập khẩu, làm việc hải quan.',   'Tiếng Anh tốt, hiểu rõ quy trình Incoterms.',             'Phụ cấp ăn trưa, thưởng hiệu quả công việc.',      '2027-12-18 23:59:59', 'OPEN',     62, NOW()),
(10, 5,  6,  4, 1, 'Nhân Viên Kho Vận & Quản Lý Hàng Hoá',        'FULLTIME', 'Chưa có kinh nghiệm', 8000000,  11000000, FALSE, 4, 'Kiểm đếm hàng xuất nhập kho, quản lý tồn kho.',         'Sức khỏe tốt, trung thực, cẩn thận.',                     'Tăng ca có phụ cấp, phát đồng phục miễn phí.',     '2027-12-12 23:59:59', 'OPEN',     45, NOW()),
(17, 2,  3,  1, 1, 'Chuyên Viên Phân Tích Dữ Liệu (Data Analyst)', 'REMOTE',   'Middle (1-3 năm)',    18000000, 26000000, FALSE, 2, 'Phân tích dữ liệu người dùng, xây dựng dashboard.',    'Thành thạo SQL, Python, PowerBI/Tableau, logic tốt.',   'Làm việc Remote 100%, trang bị Macbook.',           '2027-12-25 23:59:59', 'OPEN',    230, NOW()),
(18, 2,  3,  1, 1, 'Thiết Kế UI/UX Designer',                       'REMOTE',   'Middle (1-3 năm)',    17000000, 25000000, FALSE, 1, 'Thiết kế Wireframe, Prototype cho ứng dụng Mobile/Web.','Thành thạo Figma, Adobe XD, am hiểu Design System.',    'Thời gian tự do, thưởng hiệu suất công việc.',      '2027-12-20 23:59:59', 'OPEN',    195, NOW()),
(31, 1,  2,  1, 1, 'Lập Trình Viên Golang Backend (Nháp)',         'FULLTIME', 'Middle (1-3 năm)',    20000000, 30000000, FALSE, 1, 'Dự thảo mô tả công việc tuyển lập trình viên Golang.',  'Yêu cầu Golang, gRPC, Microservices.',                  'Bảo hiểm đầy đủ.',                                  '2027-01-15 23:59:59', 'DRAFT',      0, NOW()),
(34, 4,  5,  3, 3, 'Thực Tập Sinh Kế Toán (Đã đóng)',              'INTERN',   'Chưa có kinh nghiệm', 2000000,  3000000,  FALSE, 2, 'Hỗ trợ lưu trữ chứng từ và nhập dữ liệu kế toán.',     'Sinh viên chuyên ngành kế toán.',                      'Hỗ trợ mộc thực tập.',                               '2025-10-31 23:59:59', 'CLOSED',   188, NOW());
