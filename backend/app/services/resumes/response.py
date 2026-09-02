"""
Unified API response contract (per ISSUE-04):

    {"success": true,  "data": {...}, "error": null}
    {"success": false, "data": null,  "error": {"code": "...", "message": "..."}}

Every route handler in app/api/v1/resumes.py returns via `success_response`;
every error path raises `ApiError` (or a FastAPI/Pydantic validation error),
both of which are normalized to this contract by the exception handlers
registered in app/main.py.
"""
from typing import Any

from fastapi.responses import JSONResponse


def success_response(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": data, "error": None},
    )


def error_payload(code: str, message: str, details: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"success": False, "data": None, "error": err}
