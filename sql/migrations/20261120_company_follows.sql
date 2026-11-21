-- Bảng ứng viên theo dõi công ty.
CREATE TABLE IF NOT EXISTS company_follows (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    company_id INT NOT NULL,
    followed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_company_follows_user_company UNIQUE (user_id, company_id),
    CONSTRAINT fk_company_follows_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_company_follows_company
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    KEY idx_company_follows_company (company_id),
    KEY idx_company_follows_user_followed (user_id, followed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
