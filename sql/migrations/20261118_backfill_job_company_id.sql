-- Migration backfill company_id cho các tin tuyển dụng chưa gắn công ty (idempotent).
-- Chỉ backfill khi có quan hệ rõ ràng giữa người đăng (employer_id) và công ty.
-- Không suy đoán. Dòng không chắc chắn giữ nguyên NULL.

-- 1. Backfill cho Employer ID 24 (hr1@tuyendung.com) gắn với Công ty ID 48 ('Đại Dương Digital Labs')
UPDATE jobs 
SET company_id = 48 
WHERE employer_id = 24 AND company_id IS NULL;

-- 2. Ghi chú kiểm toán:
-- Job #26 của Employer ID 25 (hr2@tuyendung.com) giữ nguyên company_id = NULL 
-- vì tài khoản này chưa sở hữu bất kỳ hồ sơ công ty nào trong hệ thống.
