"""Tiện ích kiểm tra file upload an toàn: kiểm tra MIME type thật, không chỉ đuôi file."""
import os
from pathlib import Path

import magic
from fastapi import HTTPException, UploadFile, status


class FileValidator:
    """Validator cho file upload với kiểm tra MIME type thực tế."""

    # MIME types được phép cho CV
    ALLOWED_CV_MIMES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/msword",  # .doc
    }

    # Extension mapping (chỉ để tham khảo, không dùng để validate)
    MIME_TO_EXT = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/msword": ".doc",
    }

    @staticmethod
    def validate_cv_file(file: UploadFile, max_size_bytes: int) -> dict:
        """
        Kiểm tra file CV có hợp lệ không.

        Args:
            file: File upload từ FastAPI
            max_size_bytes: Kích thước tối đa cho phép (bytes)

        Returns:
            dict với thông tin file đã validate: {
                'original_name': str,
                'mime_type': str,
                'file_size': int,
                'extension': str
            }

        Raises:
            HTTPException: Nếu file không hợp lệ
        """
        # Đọc nội dung file để kiểm tra MIME type thật
        file_content = file.file.read()
        file_size = len(file_content)

        # Reset file pointer về đầu để có thể đọc lại sau
        file.file.seek(0)

        # 1. Kiểm tra kích thước
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File trống, vui lòng chọn file hợp lệ",
            )

        if file_size > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File vượt quá {max_mb}MB. Kích thước hiện tại: {file_size / (1024 * 1024):.2f}MB",
            )

        # 2. Kiểm tra MIME type thực tế bằng python-magic (đọc magic bytes)
        mime = magic.from_buffer(file_content, mime=True)

        if mime not in FileValidator.ALLOWED_CV_MIMES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Định dạng file không được hỗ trợ. Chỉ chấp nhận PDF, DOC, DOCX. File của bạn: {mime}",
            )

        # 3. Lấy extension từ MIME type (an toàn hơn là dùng từ tên file)
        extension = FileValidator.MIME_TO_EXT.get(mime, ".bin")

        return {
            "original_name": file.filename or "unknown",
            "mime_type": mime,
            "file_size": file_size,
            "extension": extension,
        }

    @staticmethod
    def ensure_upload_dir(upload_dir: str) -> Path:
        """
        Đảm bảo thư mục upload tồn tại. Tạo mới nếu chưa có.

        Args:
            upload_dir: Đường dẫn thư mục

        Returns:
            Path object của thư mục
        """
        path = Path(upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def safe_delete_file(file_path: str | Path) -> bool:
        """
        Xóa file an toàn (không raise exception nếu file không tồn tại).

        Args:
            file_path: Đường dẫn file cần xóa

        Returns:
            True nếu xóa thành công, False nếu file không tồn tại
        """
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                os.remove(path)
                return True
            return False
        except Exception:
            return False
