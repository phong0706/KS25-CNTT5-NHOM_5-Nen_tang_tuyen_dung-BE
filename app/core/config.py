"""Đọc cấu hình từ file .env (hoặc biến môi trường).

Muốn thêm cấu hình mới: thêm 1 dòng vào class Settings + thêm vào .env.example.
"""
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "KS25 Base API"

    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "21072007"
    DB_NAME: str = "app_db"

    # Chuỗi các origin cách nhau bằng dấu phẩy, hoặc "*"
    CORS_ORIGINS: str = "*"

# CV file upload settings
CV_UPLOAD_DIR: str = "storage/cvs" # Thư mục lưu CV (ngoài public)
CV_MAX_SIZE_MB: int = 5 # Kích thước tối đa 5MB
CV_MAX_FILES_PER_CANDIDATE: int = 3 # Tối đa 3 CV mỗi ứng viên

# JWT
JWT_SECRET: str = "CHANGE_ME_USE_RANDOM_32_CHARS_AT_LEAST"
JWT_EXPIRE_MINUTES: int = 60 * 24 # 1 ngày

    # Upload ảnh (logo / ảnh bìa công ty)
    # Thư mục lưu file upload (tương đối so với thư mục chạy uvicorn)
    UPLOAD_DIR: str = "uploads"
    # Dung lượng tối đa mỗi file (bytes). Mặc định 2 MB.
    MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024  # 2 MB

    @property
    def database_url(self) -> str:
        # mysql+pymysql://user:password@host:port/database
        # quote_plus: để mật khẩu có ký tự đặc biệt (@, #, /...) không làm hỏng URL
        return (
            f"mysql+pymysql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

