"""Framework-independent errors shared by service and storage boundaries."""

from aplomb.contracts.catalog import ERROR_HTTP_STATUS, ErrorCode
from aplomb.contracts.models import ApiError, ErrorDetail


class ServiceError(Exception):
    def __init__(self, code: ErrorCode | str, message: str, details: dict | None = None):
        self.code = ErrorCode(code)
        self.message = message
        self.details = details
        super().__init__(message)

    @property
    def status(self) -> int:
        return ERROR_HTTP_STATUS[self.code]

    def envelope(self, request_id: str) -> ApiError:
        fields = {"code": self.code, "message": self.message, "request_id": request_id}
        if self.details is not None:
            fields["details"] = self.details
        return ApiError(error=ErrorDetail(**fields))


class Conflict(ServiceError):
    def __init__(self, message: str = "The resource changed; read it again"):
        super().__init__(ErrorCode.CONFLICT, message)


class NotFound(ServiceError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(ErrorCode.NOT_FOUND, message)


def unavailable(service: str) -> ServiceError:
    return ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, f"{service} is unavailable")
