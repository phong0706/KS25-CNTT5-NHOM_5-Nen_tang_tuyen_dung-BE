-- Tạo bảng quy tắc tính toán các công cụ (calc_rules)
CREATE TABLE IF NOT EXISTS calc_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tool_slug VARCHAR(50) NOT NULL,
    effective_from DATE NOT NULL,
    source VARCHAR(255) NOT NULL,
    rules_json JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tool_effective (tool_slug, effective_from)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bảng lưu bộ lọc tìm kiếm của ứng viên
-- (Trước đây thiếu hoàn toàn -> API /api/candidate/saved-searches luôn lỗi 500)
CREATE TABLE IF NOT EXISTS saved_searches (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NOT NULL,
    name         VARCHAR(255) NOT NULL,
    filters_json TEXT NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_saved_searches_user_id (user_id),
    INDEX idx_saved_searches_user_name (user_id, name),
    CONSTRAINT fk_saved_search_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bảng câu hỏi phỏng vấn (interview_questions)
CREATE TABLE IF NOT EXISTS interview_questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    field VARCHAR(100) NOT NULL,
    level VARCHAR(50) NOT NULL,
    question TEXT NOT NULL,
    sample_answer TEXT NOT NULL,
    tips TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_field_level (field, level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bảng lưu câu hỏi phỏng vấn đã luyện của ứng viên
CREATE TABLE IF NOT EXISTS user_practiced_questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    question_id INT NOT NULL,
    practiced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_q (user_id, question_id),
    CONSTRAINT fk_user_practiced_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_practiced_q FOREIGN KEY (question_id) REFERENCES interview_questions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bảng thư giới thiệu của ứng viên (candidate_cover_letters)
CREATE TABLE IF NOT EXISTS candidate_cover_letters (
    id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_cover_letter_candidate FOREIGN KEY (candidate_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_candidate_cover (candidate_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed dữ liệu mẫu cho calc_rules
INSERT INTO calc_rules (tool_slug, effective_from, source, rules_json) VALUES
('gross-net', '2024-07-01', 'Nghị định 73/2024/NĐ-CP & Luật Thuế TNCN', '{
  "personal_deduction": 11000000,
  "dependent_deduction": 4400000,
  "base_salary": 2340000,
  "regional_minimums": {
    "1": 4960000,
    "2": 4410000,
    "3": 3860000,
    "4": 3450000
  },
  "insurance_rates": {
    "social": 0.08,
    "health": 0.015,
    "unemployment": 0.01
  },
  "employer_insurance_rates": {
    "social": 0.175,
    "health": 0.03,
    "unemployment": 0.01
  },
  "tax_brackets": [
    {"threshold": 5000000, "rate": 0.05, "quick_subtract": 0},
    {"threshold": 10000000, "rate": 0.10, "quick_subtract": 250000},
    {"threshold": 18000000, "rate": 0.15, "quick_subtract": 750000},
    {"threshold": 32000000, "rate": 0.20, "quick_subtract": 1650000},
    {"threshold": 52000000, "rate": 0.25, "quick_subtract": 3250000},
    {"threshold": 80000000, "rate": 0.30, "quick_subtract": 5850000},
    {"threshold": 9999999999, "rate": 0.35, "quick_subtract": 9850000}
  ]
}'),
('tax', '2024-07-01', 'Luật Thuế Thu nhập Cá nhân hiện hành', '{
  "personal_deduction": 11000000,
  "dependent_deduction": 4400000,
  "tax_brackets": [
    {"from": 0, "to": 5000000, "rate": 0.05, "subtract": 0},
    {"from": 5000000, "to": 10000000, "rate": 0.10, "subtract": 250000},
    {"from": 10000000, "to": 18000000, "rate": 0.15, "subtract": 750000},
    {"from": 18000000, "to": 32000000, "rate": 0.20, "subtract": 1650000},
    {"from": 32000000, "to": 52000000, "rate": 0.25, "subtract": 3250000},
    {"from": 52000000, "to": 80000000, "rate": 0.30, "subtract": 5850000},
    {"from": 80000000, "to": null, "rate": 0.35, "subtract": 9850000}
  ]
}'),
('unemployment-insurance', '2024-07-01', 'Luật Việc làm 2013 & Nghị định 73/2024/NĐ-CP', '{
  "benefit_rate": 0.60,
  "max_cap_multiplier": 5,
  "min_months": 12,
  "base_months": 36,
  "base_benefit_months": 3
}'),
('one-time-social-insurance', '2024-07-01', 'Luật Bảo hiểm xã hội 2014', '{
  "rate_before_2014": 1.5,
  "rate_from_2014": 2.0,
  "minimum_months": 12
}')
ON DUPLICATE KEY UPDATE effective_from=VALUES(effective_from);

-- Seed dữ liệu mẫu câu hỏi phỏng vấn
INSERT INTO interview_questions (field, level, question, sample_answer, tips) VALUES
('backend', 'junior', 'Giải thích sự khác nhau giữa SQL và NoSQL database?', 'SQL là cơ sở dữ liệu quan hệ có cấu trúc bảng, ràng buộc khóa ngoại và tuân thủ ACID (như MySQL, PostgreSQL). NoSQL là cơ sở dữ liệu phi quan hệ, linh hoạt cấu trúc schema (Document, Key-Value, Graph) phù hợp mở rộng quy mô lớn (như MongoDB, Redis).', 'Nhấn mạnh khi nào nên dùng loại nào trong thực tế.'),
('backend', 'mid', 'Làm thế nào để xử lý Race Condition trong hệ thống giao dịch?', 'Sử dụng cơ chế Locking (Optimistic Lock với version hoặc Pessimistic Lock với SELECT ... FOR UPDATE), Transaction isolation level phù hợp, hoặc cơ chế phân tán như Redis Distributed Lock (Redlock).', 'Nêu rõ ưu nhược điểm giữa Optimistic và Pessimistic Locking.'),
('frontend', 'junior', 'Event Loop trong JavaScript hoạt động như thế nào?', 'JavaScript chạy đơn luồng (Single Thread). Call stack thực thi mã đồng bộ. Các tác vụ bất đồng bộ chuyển sang Web API, khi hoàn tất đẩy callback vào Callback Queue (Microtask như Promise được ưu tiên trước Macrotask như setTimeout). Event Loop liên tục kiểm tra Call Stack, nếu rỗng sẽ đẩy callback vào stack.', 'Vẽ sơ đồ luồng ngắn gọn nếu có phỏng vấn trực tiếp.'),
('frontend', 'mid', 'Tối ưu hiệu năng tải trang Web Vitals (FCP, LCP, CLS) như thế nào?', 'Tối ưu hình ảnh (WebP, lazy load), code-splitting và nén gzip/brotli, hạn chế render-blocking CSS/JS, đặt kích thước rõ ràng cho ảnh/banner tránh layout shift (CLS), và dùng CDN lưu cache.', 'Trích dẫn điểm số đo bằng Lighthouse.')
ON DUPLICATE KEY UPDATE question=VALUES(question);
