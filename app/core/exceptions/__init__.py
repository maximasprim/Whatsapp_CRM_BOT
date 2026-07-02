from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base exception for all application errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        detail: Any = None,
        error_code: str | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.detail = detail
        self.error_code = error_code or self.__class__.error_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "detail": self.detail,
        }


# ── 400 Bad Request ───────────────────────────────────────────────────────────
class BadRequestException(AppException):
    status_code = 400
    error_code = "BAD_REQUEST"
    message = "Bad request."


class ValidationException(AppException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Validation failed."


# ── 401 Unauthorized ──────────────────────────────────────────────────────────
class UnauthorizedException(AppException):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Authentication required."


class InvalidTokenException(UnauthorizedException):
    error_code = "INVALID_TOKEN"
    message = "Token is invalid or expired."


class ExpiredTokenException(UnauthorizedException):
    error_code = "EXPIRED_TOKEN"
    message = "Token has expired."


# ── 403 Forbidden ─────────────────────────────────────────────────────────────
class ForbiddenException(AppException):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


# ── 404 Not Found ─────────────────────────────────────────────────────────────
class NotFoundException(AppException):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found."


# ── 409 Conflict ──────────────────────────────────────────────────────────────
class ConflictException(AppException):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource already exists."


# ── 429 Too Many Requests ─────────────────────────────────────────────────────
class RateLimitException(AppException):
    status_code = 429
    error_code = "RATE_LIMITED"
    message = "Too many requests. Please slow down."


# ── AI-specific ───────────────────────────────────────────────────────────────
class AIProviderException(AppException):
    status_code = 502
    error_code = "AI_PROVIDER_ERROR"
    message = "AI provider returned an error."


class AIRateLimitException(AIProviderException):
    error_code = "AI_RATE_LIMIT"
    message = "AI provider rate limit reached."


class AIContextLengthException(AIProviderException):
    error_code = "AI_CONTEXT_LENGTH"
    message = "Prompt exceeded maximum context length."


# ── WhatsApp-specific ─────────────────────────────────────────────────────────
class WhatsAppException(AppException):
    status_code = 502
    error_code = "WHATSAPP_ERROR"
    message = "WhatsApp API returned an error."


class WhatsAppWebhookException(BadRequestException):
    error_code = "WHATSAPP_WEBHOOK_ERROR"
    message = "Invalid WhatsApp webhook payload."


# ── Storage ───────────────────────────────────────────────────────────────────
class FileUploadException(BadRequestException):
    error_code = "FILE_UPLOAD_ERROR"
    message = "File upload failed."


class FileSizeException(FileUploadException):
    error_code = "FILE_TOO_LARGE"
    message = "File exceeds maximum allowed size."


class FileTypeException(FileUploadException):
    error_code = "FILE_TYPE_NOT_ALLOWED"
    message = "File type is not allowed."
