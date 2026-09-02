"""Domain-specific exceptions for Module 1, each carrying an HTTP status
code and a machine-readable error code so the global handler in
app/main.py can translate them into the standard response contract."""
from fastapi import status


class ApiError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"

    def __init__(self, message: str, *, details=None, status_code: int | None = None,
                 code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class UnsupportedFileTypeError(ApiError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "UNSUPPORTED_FILE_TYPE"


class FileTooLargeError(ApiError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "FILE_TOO_LARGE"


class ExtractionError(ApiError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "EXTRACTION_FAILED"


class ResumeNotFoundError(ApiError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "RESUME_NOT_FOUND"


class ApplicationMismatchError(ApiError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "APPLICATION_MISMATCH"


class InvalidRequestError(ApiError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_REQUEST"


class StorageError(ApiError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "STORAGE_ERROR"
