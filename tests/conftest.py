"""Cấu hình pytest dùng chung: cô lập database test riêng (app_db_test)."""
import os

# Ép biến môi trường DB_NAME sang app_db_test trước khi bất kỳ module nào nạp settings
os.environ["DB_NAME"] = os.getenv("TEST_DB_NAME", "app_db_test")
