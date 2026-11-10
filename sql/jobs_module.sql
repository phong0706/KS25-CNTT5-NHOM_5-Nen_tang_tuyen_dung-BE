-- ============================================================
-- MODULE TIN TUYỂN DỤNG - Nguyễn Ngọc Hiển Vinh
-- Chạy SAU khi đã chạy init.sql
-- ============================================================

SET NAMES utf8mb4;
USE app_db;

-- ============================================================
-- BẢNG STUB cho các module khác (tạo nếu chưa có)
-- ============================================================

-- Module Tài khoản - Nguyễn Tấn Phong
CREATE TABLE IF NOT EXISTS users (
  id    BIGINT       AUTO_INCREMENT PRIMARY KEY,
  name  VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  role  VARCHAR(50)  NOT NULL DEFAULT 'CANDIDATE'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Module Doanh nghiệp - Tăng Thanh Tú
CREATE TABLE IF NOT EXISTS companies (
  id   BIGINT       AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Module Danh mục - Hoàng Văn Thắng
CREATE TABLE IF NOT EXISTS industries (
  id   BIGINT       AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS locations (
  id   BIGINT       AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS skills (
  id   BIGINT       AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- DỮ LIỆU MẪU CHO CÁC BẢNG STUB
-- ============================================================

INSERT IGNORE INTO users (id, name, email, role) VALUES
  (2,  'Employer A', 'employer_a@example.com', 'EMPLOYER'),
  (3,  'Employer B', 'employer_b@example.com', 'EMPLOYER'),
  (4,  'Employer C', 'employer_c@example.com', 'EMPLOYER'),
  (5,  'Employer D', 'employer_d@example.com', 'EMPLOYER'),
  (6,  'Employer E', 'employer_e@example.com', 'EMPLOYER'),
  (7,  'Employer F', 'employer_f@example.com', 'EMPLOYER'),
  (8,  'Employer G', 'employer_g@example.com', 'EMPLOYER'),
  (9,  'Employer H', 'employer_h@example.com', 'EMPLOYER'),
  (10, 'Employer I', 'employer_i@example.com', 'EMPLOYER'),
  (11, 'Employer J', 'employer_j@example.com', 'EMPLOYER');

INSERT IGNORE INTO companies (id, name) VALUES
  (1,  'Công ty Công nghệ Alpha'),
  (2,  'Công ty AI Beta'),
  (3,  'Công ty Marketing Gamma'),
  (4,  'Công ty Tài chính Delta'),
  (5,  'Công ty Logistics Epsilon'),
  (6,  'Phòng khám Zeta'),
  (7,  'Trung tâm giáo dục Eta'),
  (8,  'Công ty Xây dựng Theta'),
  (9,  'Công ty Dữ liệu Iota'),
  (10, 'Công ty Phần mềm Kappa');

INSERT IGNORE INTO industries (id, name) VALUES
  (1, 'Công nghệ thông tin'),
  (2, 'Marketing & Truyền thông'),
  (3, 'Tài chính - Kế toán'),
  (4, 'Logistics & Xuất nhập khẩu'),
  (5, 'Y tế - Dược'),
  (6, 'Giáo dục & Đào tạo'),
  (7, 'Xây dựng & Kiến trúc'),
  (8, 'Nhân sự & Hành chính');

INSERT IGNORE INTO locations (id, name) VALUES
  (1, 'Hồ Chí Minh'),
  (2, 'Hà Nội'),
  (3, 'Đà Nẵng');

INSERT IGNORE INTO skills (id, name) VALUES
  (1,  'Java'),          (2,  'Spring Boot'), (3,  'MySQL'),
  (4,  'ReactJS'),       (5,  'Redux'),        (6,  'TypeScript'),
  (7,  'Python'),        (8,  'AI/ML'),        (9,  'AWS'),
  (10, 'Kubernetes'),    (11, 'Terraform'),    (12, 'Google Ads'),
  (13, 'Facebook Ads'),  (14, 'SEO'),          (15, 'Canva'),
  (16, 'Kế toán'),       (17, 'MISA'),         (18, 'Tài chính'),
  (19, 'CPA'),           (20, 'Tiếng Anh'),    (21, 'Incoterms'),
  (22, 'Quản lý kho'),   (23, 'SQL'),          (24, 'PowerBI'),
  (25, 'Figma'),         (26, 'Adobe XD'),     (27, 'NodeJS'),
  (28, 'Flutter'),       (29, 'Dart'),         (30, 'Kiểm thử'),
  (31, 'Testcase'),      (32, 'PyTorch'),      (33, 'C++'),
  (34, 'RTOS');

-- ============================================================
-- BẢNG jobs
-- ============================================================
CREATE TABLE IF NOT EXISTS jobs (
  id               BIGINT        AUTO_INCREMENT PRIMARY KEY,
  company_id       BIGINT        NOT NULL,
  posted_by        BIGINT        NOT NULL,
  industry_id      BIGINT        NOT NULL,
  location_id      BIGINT        NOT NULL,
  title            VARCHAR(255)  NOT NULL,
  job_type         ENUM('FULLTIME','PARTTIME','INTERN','REMOTE') NOT NULL DEFAULT 'FULLTIME',
  experience_level VARCHAR(50)   NOT NULL DEFAULT 'Kiến thức/Chưa có kinh nghiệm',
  salary_min       DECIMAL(15,2) NULL,
  salary_max       DECIMAL(15,2) NULL,
  is_negotiable    BOOLEAN       NOT NULL DEFAULT FALSE,
  quantity         INT           NOT NULL DEFAULT 1,
  description      TEXT          NOT NULL,
  requirements     TEXT          NULL,
  benefits         TEXT          NULL,
  deadline         DATETIME      NULL,
  status           ENUM('DRAFT','PENDING','OPEN','HIDDEN','CLOSED','REJECTED') NOT NULL DEFAULT 'OPEN',
  views_count      INT           NOT NULL DEFAULT 0,
  created_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_jobs_company   FOREIGN KEY (company_id)  REFERENCES companies(id),
  CONSTRAINT fk_jobs_posted_by FOREIGN KEY (posted_by)   REFERENCES users(id),
  CONSTRAINT fk_jobs_industry  FOREIGN KEY (industry_id) REFERENCES industries(id),
  CONSTRAINT fk_jobs_location  FOREIGN KEY (location_id) REFERENCES locations(id),
  INDEX ix_jobs_status      (status),
  INDEX ix_jobs_industry_id (industry_id),
  INDEX ix_jobs_location_id (location_id),
  INDEX ix_jobs_job_type    (job_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- BẢNG job_skills
-- ============================================================
CREATE TABLE IF NOT EXISTS job_skills (
  id          BIGINT    AUTO_INCREMENT PRIMARY KEY,
  job_id      BIGINT    NOT NULL,
  skill_id    BIGINT    NOT NULL,
  is_required BOOLEAN   NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_job_skills_job   FOREIGN KEY (job_id)   REFERENCES jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_job_skills_skill FOREIGN KEY (skill_id) REFERENCES skills(id),
  UNIQUE KEY uq_job_skills_job_skill (job_id, skill_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tin tuyển dụng ID 1-10
INSERT INTO jobs (id, company_id, posted_by, industry_id, location_id, title, job_type, experience_level, salary_min, salary_max, is_negotiable, quantity, description, requirements, benefits, deadline, status, views_count, created_at) VALUES
(1,  1,  2,  1, 1, 'Lập Trình Viên Senior Java (Spring Boot)',    'FULLTIME', 'Senior (3-5 năm)',     25000000, 35000000, FALSE, 3, 'Phát triển hệ thống Backend quy mô lớn microservices.',   'Trên 3 năm kinh nghiệm Java, Spring Boot, MySQL, Redis.',  'Lương tháng 13, BHYT cao cấp, Du lịch hàng năm.',  '2026-12-31 23:59:59', 'OPEN',    142, NOW()),
(2,  1,  2,  1, 1, 'Lập Trình Viên Frontend ReactJS',             'FULLTIME', 'Middle (1-3 năm)',    15000000, 22000000, FALSE, 2, 'Xây dựng giao diện Web Application responsive.',         'Thành thạo ReactJS, Redux Toolkit, HTML5/CSS3.',           'Thưởng dự án, hỗ trợ laptop, làm việc Hybrid.',    '2026-12-15 23:59:59', 'OPEN',     98, NOW()),
(3,  2,  3,  1, 2, 'Thực Tập Sinh Lập Trình Python / AI',         'INTERN',   'Chưa có kinh nghiệm', NULL,     NULL,     TRUE,  5, 'Nghiên cứu phát triển mô hình AI/LLM cơ bản.',           'Sinh viên năm 3-4 CNTT, biết Python cơ bản.',             'Hỗ trợ mộc thực tập, phụ cấp 3-5 triệu/tháng.',   '2026-11-30 23:59:59', 'OPEN',    215, NOW()),
(4,  2,  3,  1, 2, 'Kỹ Sư DevOps / Cloud AWS',                    'FULLTIME', 'Senior (3-5 năm)',    30000000, 45000000, FALSE, 1, 'Quản trị hạ tầng Cloud, CI/CD pipeline và Kubernetes.',  'Kinh nghiệm AWS, Docker, Kubernetes, Terraform 3+ năm.',  'Lương thưởng cạnh tranh, tăng lương 2 lần/năm.',   '2026-12-20 23:59:59', 'OPEN',     76, NOW()),
(5,  3,  4,  2, 1, 'Chuyên Viên Marketing Digital',               'FULLTIME', 'Middle (1-3 năm)',    12000000, 18000000, FALSE, 2, 'Tối ưu chiến dịch Google Ads, Facebook Ads, TikTok Ads.','Kinh nghiệm chạy ads E-commerce tối thiểu 1 năm.',        'Thưởng KPIs doanh số, môi trường trẻ trung.',      '2026-11-25 23:59:59', 'OPEN',    110, NOW()),
(6,  3,  4,  2, 1, 'Thực Tập Sinh Content Marketing',             'PARTTIME', 'Chưa có kinh nghiệm', 3000000,  5000000,  FALSE, 3, 'Viết bài chuẩn SEO, sáng tạo nội dung Fanpage.',         'Yêu thích viết lách, chăm chỉ, biết Canva cơ bản.',      'Hỗ trợ dấu thực tập, thưởng bài viết hay.',        '2026-12-10 23:59:59', 'OPEN',    165, NOW()),
(7,  4,  5,  3, 3, 'Kế Toán Tổng Hợp Doanh Nghiệp',               'FULLTIME', 'Middle (1-3 năm)',    10000000, 15000000, FALSE, 1, 'Quản lý thu chi, lập báo cáo thuế và tài chính.',        'Tốt nghiệp Kế toán/Tài chính, biết phần mềm MISA.',      'Đóng BHXH đầy đủ, thưởng lễ tết.',                '2026-12-05 23:59:59', 'OPEN',     54, NOW()),
(8,  4,  5,  3, 3, 'Trưởng Phòng Tài Chính Doanh Nghiệp',         'FULLTIME', 'Leader / Manager',   40000000, 60000000, FALSE, 1, 'Hoạch định chiến lược tài chính tập đoàn.',              'Trên 5 năm kinh nghiệm, bằng CPA hoặc CFA.',              'Chế độ đãi ngộ cấp quản lý, xe đưa đón.',          '2026-12-31 23:59:59', 'OPEN',     89, NOW()),
(9,  5,  6,  4, 1, 'Chuyên Viên Nhập Khẩu & Logistics',           'FULLTIME', 'Middle (1-3 năm)',    14000000, 20000000, FALSE, 2, 'Theo dõi chứng từ xuất nhập khẩu, làm việc hải quan.',   'Tiếng Anh tốt, hiểu rõ quy trình Incoterms.',             'Phụ cấp ăn trưa, thưởng hiệu quả công việc.',      '2026-12-18 23:59:59', 'OPEN',     62, NOW()),
(10, 5,  6,  4, 1, 'Nhân Viên Kho Vận & Quản Lý Hàng Hoá',        'FULLTIME', 'Chưa có kinh nghiệm', 8000000,  11000000, FALSE, 4, 'Kiểm đếm hàng xuất nhập kho, quản lý tồn kho.',         'Sức khỏe tốt, trung thực, cẩn thận.',                     'Tăng ca có phụ cấp, phát đồng phục miễn phí.',     '2026-12-12 23:59:59', 'OPEN',     45, NOW());
-- Tin tuyển dụng ID 11-20
INSERT INTO jobs (id, company_id, posted_by, industry_id, location_id, title, job_type, experience_level, salary_min, salary_max, is_negotiable, quantity, description, requirements, benefits, deadline, status, views_count, created_at) VALUES
(11, 6,  7,  5, 2, 'Bác Sĩ Đa Khoa Phòng Khám Quốc Tế',           'FULLTIME', 'Senior (3-5 năm)',    NULL,     NULL,     TRUE,  2, 'Khám chữa bệnh và tư vấn sức khỏe cho bệnh nhân.',      'Chứng chỉ hành nghề y khoa, trên 3 năm kinh nghiệm.',    'Lương thỏa thuận cao, môi trường y tế hiện đại.',  '2026-12-31 23:59:59', 'OPEN',     92, NOW()),
(12, 6,  7,  5, 2, 'Dược Sĩ Bán Thuốc Nhà Thuốc',                  'FULLTIME', 'Middle (1-3 năm)',    9000000,  13000000, FALSE, 3, 'Tư vấn và bán thuốc theo đơn của bác sĩ.',              'Tốt nghiệp Cao đẳng/Đại học Dược, giao tiếp tốt.',       'Thưởng doanh số bán hàng, BHXH đầy đủ.',           '2026-12-15 23:59:59', 'OPEN',     38, NOW()),
(13, 7,  8,  6, 1, 'Giáo Viên Tiếng Anh IELTS (Band 7.5+)',         'PARTTIME', 'Middle (1-3 năm)',    15000000, 25000000, FALSE, 4, 'Giảng dạy ôn luyện IELTS cho học sinh, sinh viên.',     'IELTS 7.5 trở lên, chứng chỉ TESOL/CELTA là lợi thế.', 'Lương theo giờ cao, lịch học linh hoạt.',           '2026-12-25 23:59:59', 'OPEN',    180, NOW()),
(14, 7,  8,  6, 1, 'Chuyên Viên Tư Vấn Du Học',                    'FULLTIME', 'Junior (1 năm)',      10000000, 16000000, FALSE, 2, 'Tư vấn lộ trình du học các nước Anh, Mỹ, Úc.',         'Giao tiếp tốt, nhanh nhẹn, tiếng Anh khá.',             'Hoa hồng hồ sơ cao, cơ hội đi công tác nước ngoài.','2026-12-10 23:59:59', 'OPEN',     71, NOW()),
(15, 8,  9,  7, 2, 'Kiến Trúc Sư Thiết Kế Nội Thất',                'FULLTIME', 'Middle (1-3 năm)',    16000000, 24000000, FALSE, 2, 'Lập bản vẽ 3D thiết kế nội thất chung cư, biệt thự.',  'Thành thạo AutoCAD, 3ds Max, SketchUp, Photoshop.',     'Thưởng theo dự án công trình, nghỉ mát hàng năm.',  '2026-12-20 23:59:59', 'OPEN',    105, NOW()),
(16, 8,  9,  7, 2, 'Kỹ Sư Giám Sát Công Trình Xây Dựng',            'FULLTIME', 'Senior (3-5 năm)',    18000000, 28000000, FALSE, 2, 'Giám sát thi công và chất lượng công trình hiện trường.','Tốt nghiệp ĐH Xây dựng, chứng chỉ hành nghề giám sát.', 'Phụ cấp công tác phí, bảo hiểm tai nạn 24/7.',      '2026-12-30 23:59:59', 'OPEN',     64, NOW()),
(17, 9,  10, 8, 1, 'Chuyên Viên Phân Tích Dữ Liệu (Data Analyst)', 'REMOTE',   'Middle (1-3 năm)',    18000000, 26000000, FALSE, 2, 'Phân tích dữ liệu người dùng, xây dựng dashboard.',    'Thành thạo SQL, Python, PowerBI/Tableau, logic tốt.',   'Làm việc Remote 100%, trang bị Macbook.',           '2026-12-25 23:59:59', 'OPEN',    230, NOW()),
(18, 9,  10, 8, 1, 'Thiết Kế UI/UX Designer',                       'REMOTE',   'Middle (1-3 năm)',    17000000, 25000000, FALSE, 1, 'Thiết kế Wireframe, Prototype cho ứng dụng Mobile/Web.','Thành thạo Figma, Adobe XD, am hiểu Design System.',    'Thời gian tự do, thưởng hiệu suất công việc.',      '2026-12-20 23:59:59', 'OPEN',    195, NOW()),
(19, 10, 11, 1, 1, 'Lập Trình Viên NodeJS Backend',                 'FULLTIME', 'Junior (1 năm)',      12000000, 17000000, FALSE, 3, 'Xây dựng RESTful API bằng NodeJS (ExpressJS/NestJS).',  'Có 1 năm kinh nghiệm NodeJS, MongoDB/PostgreSQL.',      'Xét tăng lương 6 tháng/lần, trà đá cà phê miễn phí.','2026-12-15 23:59:59', 'OPEN',    112, NOW()),
(20, 10, 11, 1, 1, 'Lập Trình Viên Mobile Flutter',                 'FULLTIME', 'Middle (1-3 năm)',    16000000, 24000000, FALSE, 2, 'Phát triển ứng dụng di động đa nền tảng iOS/Android.',  'Kinh nghiệm Flutter/Dart tối thiểu 1.5 năm.',           'Thưởng dự án, hỗ trợ thiết bị test.',               '2026-12-28 23:59:59', 'OPEN',     87, NOW());
-- Tin tuyển dụng ID 21-30
INSERT INTO jobs (id, company_id, posted_by, industry_id, location_id, title, job_type, experience_level, salary_min, salary_max, is_negotiable, quantity, description, requirements, benefits, deadline, status, views_count, created_at) VALUES
(21, 1,  2,  1, 1, 'Tester / QA QC Software',                      'FULLTIME', 'Junior (1 năm)',      10000000, 15000000, FALSE, 2, 'Lập test plan, viết testcase, test manual ứng dụng.',   'Nắm vững quy trình kiểm thử phần mềm, cẩn thận.',      'Chế độ đãi ngộ tốt, môi trường thân thiện.',       '2026-12-10 23:59:59', 'OPEN',     79, NOW()),
(22, 2,  3,  1, 2, 'Kỹ Sư AI Computer Vision',                     'FULLTIME', 'Senior (3-5 năm)',    35000000, 50000000, FALSE, 1, 'Phát triển mô hình nhận diện khuôn mặt và xử lý ảnh.', 'Thành thạo PyTorch, OpenCV, CUDA; bài báo khoa học +.', 'Lương khủng, cổ phiếu ưu đãi cho nhân viên.',      '2026-12-31 23:59:59', 'OPEN',    145, NOW()),
(23, 3,  4,  2, 1, 'Chuyên Viên SEO Website Master',               'FULLTIME', 'Middle (1-3 năm)',    11000000, 16000000, FALSE, 1, 'Đẩy từ khóa Top Google, tối ưu SEO Onpage/Offpage.',   'Có sản phẩm SEO thành công chứng minh kết quả.',       'Thưởng KPI từ khóa đạt Top.',                       '2026-12-18 23:59:59', 'OPEN',     68, NOW()),
(24, 4,  5,  3, 3, 'Nhân Viên Kiểm Toán Nội Bộ',                   'FULLTIME', 'Middle (1-3 năm)',    13000000, 19000000, FALSE, 1, 'Kiểm tra quy trình vận hành và tuân thủ tài chính.',   'Tốt nghiệp chuyên ngành Kiểm toán, cẩn thận.',         'Du lịch hàng năm, phụ cấp công tác.',              '2026-12-22 23:59:59', 'OPEN',     41, NOW()),
(25, 5,  6,  4, 1, 'Chuyên Viên Mua Hàng International',           'FULLTIME', 'Middle (1-3 năm)',    15000000, 22000000, FALSE, 2, 'Tìm kiếm nhà cung cấp nước ngoài, đàm phán giá cả.',   'Tiếng Trung hoặc Anh lưu loát, kỹ năng đàm phán tốt.','Thưởng doanh số mua hàng tiết kiệm.',               '2026-12-25 23:59:59', 'OPEN',     53, NOW()),
(26, 6,  7,  5, 2, 'Kỹ Thuật Viên Xét Nghiệm Y Khoa',              'FULLTIME', 'Junior (1 năm)',      8500000,  12000000, FALSE, 2, 'Lấy mẫu và vận hành máy xét nghiệm máu, sinh hóa.',   'Có chứng chỉ kỹ thuật viên xét nghiệm y khoa.',        'Đóng BHXH, phụ cấp độc hại.',                      '2026-12-15 23:59:59', 'OPEN',     32, NOW()),
(27, 7,  8,  6, 1, 'Trợ Giảng Tiếng Anh Trẻ Em',                   'PARTTIME', 'Chưa có kinh nghiệm', 4000000,  6000000,  FALSE, 5, 'Hỗ trợ giáo viên nước ngoài quản lý lớp trẻ em.',      'Sinh viên các trường đại học, giao tiếp tiếng Anh khá.','Rèn kỹ năng sư phạm, môi trường năng động.',       '2026-12-05 23:59:59', 'OPEN',    140, NOW()),
(28, 8,  9,  7, 2, 'Kỹ Sư Cơ Điện MEP',                            'FULLTIME', 'Senior (3-5 năm)',    20000000, 30000000, FALSE, 2, 'Thiết kế và giám sát hệ thống điện nước công trình.',  'Tốt nghiệp ĐH Bách Khoa/Điện Lực, kinh nghiệm MEP 3+.','Chế độ thưởng công trình lớn.',                     '2026-12-28 23:59:59', 'OPEN',     58, NOW()),
(29, 9,  10, 8, 1, 'Chuyên Viên Tuyển Dụng Nhân Sự IT',            'FULLTIME', 'Middle (1-3 năm)',    13000000, 20000000, FALSE, 2, 'Sourcing và phỏng vấn ứng viên ngành CNTT.',           'Có network tốt cộng đồng IT, hiểu thuật ngữ công nghệ.','Thưởng nóng theo mỗi candidate onboard thành công.','2026-12-20 23:59:59', 'OPEN',    115, NOW()),
(30, 10, 11, 1, 1, 'Lập Trình Viên C++ Embedded System',           'FULLTIME', 'Senior (3-5 năm)',    25000000, 40000000, FALSE, 2, 'Phát triển phần mềm nhúng trên vi điều khiển STM32.',  'Thành thạo C/C++, RTOS, giao tiếp UART/SPI/I2C.',      'Thưởng bằng sáng chế, làm việc dự án quốc tế.',    '2026-12-31 23:59:59', 'OPEN',     61, NOW());
-- Tin tuyển dụng ID 31-40
INSERT INTO jobs (id, company_id, posted_by, industry_id, location_id, title, job_type, experience_level, salary_min, salary_max, is_negotiable, quantity, description, requirements, benefits, deadline, status, views_count, created_at) VALUES
(31, 1,  2,  1, 1, 'Lập Trình Viên Golang Backend (Nháp)',         'FULLTIME', 'Middle (1-3 năm)',    20000000, 30000000, FALSE, 1, 'Dự thảo mô tả công việc tuyển lập trình viên Golang.',  'Yêu cầu Golang, gRPC, Microservices.',                  'Bảo hiểm đầy đủ.',                                  '2027-01-15 23:59:59', 'DRAFT',      0, NOW()),
(32, 2,  3,  1, 2, 'Chuyên Viên An Ninh Mạng Pentest',            'FULLTIME', 'Senior (3-5 năm)',    25000000, 38000000, FALSE, 1, 'Kiểm thử xâm nhập hệ thống ngân hàng và web.',         'Có chứng chỉ CEH, OSCP là lợi thế lớn.',               'Lương thưởng hậu đĩnh.',                             '2027-01-10 23:59:59', 'PENDING',    5, NOW()),
(33, 3,  4,  2, 1, 'Nhân Viên Phủ Sóng TikTok Shop',              'FULLTIME', 'Junior (1 năm)',      9000000,  14000000, FALSE, 1, 'Quản lý livestream và đơn hàng trên kênh TikTok Shop.','Nhanh nhẹn, có kinh nghiệm livestream.',                'Hoa hồng sản phẩm bán được.',                        '2026-11-20 23:59:59', 'HIDDEN',    42, NOW()),
(34, 4,  5,  3, 3, 'Thực Tập Sinh Kế Toán',                        'INTERN',   'Chưa có kinh nghiệm', 2000000,  3000000,  FALSE, 2, 'Hỗ trợ lưu trữ chứng từ và nhập dữ liệu kế toán.',     'Sinh viên chuyên ngành kế toán.',                      'Hỗ trợ mộc thực tập.',                               '2026-10-31 23:59:59', 'CLOSED',   188, NOW()),
(35, 5,  6,  4, 1, 'Nhân Viên Bán Hàng Showroom',                  'FULLTIME', 'Chưa có kinh nghiệm', 7000000,  10000000, FALSE, 2, 'Nội dung tin tuyển dụng chứa từ ngữ không phù hợp.',   'Không yêu cầu.',                                       'Lương cứng + hoa hồng.',                             '2026-11-15 23:59:59', 'REJECTED',  12, NOW()),
(36, 6,  7,  5, 2, 'Bác Sĩ Răng Hàm Mặt',                          'FULLTIME', 'Senior (3-5 năm)',    30000000, 50000000, FALSE, 1, 'Khám và điều trị nha khoa kỹ thuật cao.',               'Có chứng chỉ hành nghề RHM.',                          'Thưởng phần trăm dịch vụ.',                          '2026-10-15 23:59:59', 'CLOSED',    76, NOW()),
(37, 7,  8,  6, 1, 'Giáo Viên Tiếng Trung HSK 5 (Nháp)',           'FULLTIME', 'Middle (1-3 năm)',    12000000, 18000000, FALSE, 2, 'Giảng dạy tiếng Trung giao tiếp và luyện thi HSK.',    'Có bằng HSK 5 trở lên.',                               'Lương cạnh tranh.',                                  '2027-01-20 23:59:59', 'DRAFT',      0, NOW()),
(38, 8,  9,  7, 2, 'Họa Sĩ 3D Render Kiến Trúc',                   'FULLTIME', 'Middle (1-3 năm)',    14000000, 20000000, FALSE, 1, 'Render hình ảnh 3D ngoại thất dự án bất động sản.',    'Sử dụng Vray, Corona Render thành thạo.',              'Thưởng sản phẩm đẹp.',                               '2027-01-05 23:59:59', 'PENDING',    8, NOW()),
(39, 9,  10, 8, 1, 'Chuyên Viên Đào Tạo Nội Bộ',                   'FULLTIME', 'Middle (1-3 năm)',    15000000, 22000000, FALSE, 1, 'Xây dựng chương trình đào tạo kỹ năng mềm nhân viên.', 'Có kỹ năng sư phạm doanh nghiệp.',                     'Môi trường làm việc nhân văn.',                      '2026-11-28 23:59:59', 'HIDDEN',    34, NOW()),
(40, 10, 11, 1, 1, 'Lập Trình Viên PHP Laravel',                   'FULLTIME', 'Middle (1-3 năm)',    14000000, 20000000, FALSE, 2, 'Bảo trì và phát triển ứng dụng Web thương mại điện tử.','Thành thạo PHP, Laravel framework, MySQL.',             'Đóng bảo hiểm đầy đủ.',                              '2026-10-30 23:59:59', 'CLOSED',   156, NOW());

-- ============================================================
-- SEED DATA: KỸ NĂNG YÊU CẦU (job_skills)
-- ============================================================
INSERT INTO job_skills (job_id, skill_id, is_required) VALUES
(1,  1,  TRUE),  (1,  2,  TRUE),  (1,  3,  FALSE),
(2,  4,  TRUE),  (2,  5,  TRUE),  (2,  6,  FALSE),
(3,  7,  TRUE),  (3,  8,  FALSE),
(4,  9,  TRUE),  (4,  10, TRUE),  (4,  11, FALSE),
(5,  12, TRUE),  (5,  13, TRUE),
(6,  14, TRUE),  (6,  15, FALSE),
(7,  16, TRUE),  (7,  17, TRUE),
(8,  18, TRUE),  (8,  19, TRUE),
(9,  20, TRUE),  (9,  21, FALSE),
(10, 22, TRUE),
(17, 23, TRUE),  (17, 7,  TRUE),  (17, 24, FALSE),
(18, 25, TRUE),  (18, 26, TRUE),
(19, 27, TRUE),  (19, 3,  TRUE),
(20, 28, TRUE),  (20, 29, FALSE),
(21, 30, TRUE),  (21, 31, TRUE),
(22, 7,  TRUE),  (22, 32, TRUE),
(30, 33, TRUE),  (30, 34, TRUE);

-- ============================================================
-- KIỂM TRA DỮ LIỆU SAU KHI NẠP
-- Các truy vấn dưới đây chỉ đọc dữ liệu.
-- ============================================================

-- Kỳ vọng: total_jobs = 40
SELECT COUNT(*) AS total_jobs FROM jobs;

-- Kỳ vọng: không trả về dòng nào (thiếu ID trong khoảng 1-40)
SELECT expected.id AS missing_job_id
FROM (
    SELECT 1 AS id UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5
    UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10
    UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14 UNION ALL SELECT 15
    UNION ALL SELECT 16 UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19 UNION ALL SELECT 20
    UNION ALL SELECT 21 UNION ALL SELECT 22 UNION ALL SELECT 23 UNION ALL SELECT 24 UNION ALL SELECT 25
    UNION ALL SELECT 26 UNION ALL SELECT 27 UNION ALL SELECT 28 UNION ALL SELECT 29 UNION ALL SELECT 30
    UNION ALL SELECT 31 UNION ALL SELECT 32 UNION ALL SELECT 33 UNION ALL SELECT 34 UNION ALL SELECT 35
    UNION ALL SELECT 36 UNION ALL SELECT 37 UNION ALL SELECT 38 UNION ALL SELECT 39 UNION ALL SELECT 40
) AS expected
LEFT JOIN jobs j ON j.id = expected.id
WHERE j.id IS NULL;

-- Kỳ vọng: không trả về dòng nào (không có job_skills mồ côi)
SELECT js.job_id, js.skill_id
FROM job_skills js
LEFT JOIN jobs j ON j.id = js.job_id
LEFT JOIN skills s ON s.id = js.skill_id
WHERE j.id IS NULL OR s.id IS NULL;

-- Kỳ vọng: không có dòng nào (lương âm hoặc lương tối thiểu lớn hơn tối đa)
SELECT id, salary_min, salary_max
FROM jobs
WHERE salary_min < 0
   OR salary_max < 0
   OR (salary_min IS NOT NULL AND salary_max IS NOT NULL AND salary_min > salary_max);
