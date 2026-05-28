"""
OptiProcess - Manejo centralizado de excepciones
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)


class OptiProcessException(Exception):
    def __init__(self, message: str, code: str = "ERROR", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class DataValidationError(OptiProcessException):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR", 422)


class StatisticalError(OptiProcessException):
    def __init__(self, message: str):
        super().__init__(message, "STATISTICAL_ERROR", 400)


class InsufficientDataError(OptiProcessException):
    def __init__(self, message: str):
        super().__init__(message, "INSUFFICIENT_DATA", 400)


class AuthenticationError(OptiProcessException):
    def __init__(self, message: str = "Credenciales inválidas"):
        super().__init__(message, "AUTH_ERROR", 401)


class PermissionError(OptiProcessException):
    def __init__(self, message: str = "No tiene permisos para esta acción"):
        super().__init__(message, "PERMISSION_ERROR", 403)


async def optiprocess_exception_handler(request: Request, exc: OptiProcessException):
    logger.error(f"OptiProcessException [{exc.code}]: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": exc.code,
            "message": exc.message,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(x) for x in error["loc"])
        errors.append({"campo": field, "mensaje": error["msg"]})
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": "Error de validación en los datos enviados",
            "detalles": errors,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
        },
    )
