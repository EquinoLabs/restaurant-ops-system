from fastapi import HTTPException, status
from typing import Optional, Dict, Any


class APIException(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {}
                }
            }
        )


class NotFoundException(APIException):
    def __init__(self, code: str = "NOT_FOUND", message: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=code,
            message=message
        )


class NotFoundError(NotFoundException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(code=code, message=message)



class BusinessRuleException(APIException):
    def __init__(self, code: str = "BUSINESS_RULE_VIOLATION", message: str = "Operation violates business policy"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=code,
            message=message
        )


class AuthenticationError(APIException):
    def __init__(self, message: str = "Authentication required", code: str = "UNAUTHORIZED"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=code,
            message=message
        )


class ForbiddenError(APIException):
    def __init__(self, message: str = "Forbidden access", code: str = "FORBIDDEN"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
            message=message
        )


class ValidationError(APIException):
    def __init__(self, message: str = "Validation failed", code: str = "VALIDATION_ERROR"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=code,
            message=message
        )


class ConflictError(APIException):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            message=message
        )


class InternalServerError(APIException):
    def __init__(self, message: str = "Internal server error", code: str = "INTERNAL_SERVER_ERROR"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=code,
            message=message
        )


class ServiceUnavailableError(APIException):
    def __init__(self, message: str = "Service temporarily unavailable", code: str = "SERVICE_UNAVAILABLE"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=code,
            message=message
        )


class CommitOutcomeUncertainError(ServiceUnavailableError):
    def __init__(
        self,
        message: str = "Transaction commit outcome is uncertain due to a transport failure. Preserving state without speculation.",
        code: str = "COMMIT_OUTCOME_UNCERTAIN",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message=message, code=code)
        if details:
            self.detail["error"]["details"] = details



