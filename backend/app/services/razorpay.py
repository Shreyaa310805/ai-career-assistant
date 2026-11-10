"""Razorpay TEST-mode transport and signature verification."""
import hashlib
import hmac
import re

import httpx
from fastapi import HTTPException

from app.core.config import get_settings


def configured() -> bool:
    settings = get_settings()
    return settings.razorpay_key_id.startswith("rzp_test_") and bool(settings.razorpay_key_secret)


def api(method: str, path: str, payload: dict | None = None) -> dict:
    if not configured():
        raise HTTPException(503, "Configure Razorpay TEST credentials on the backend")
    settings = get_settings()
    try:
        response = httpx.request(
            method,
            f"https://api.razorpay.com/v1/{path.lstrip('/')}",
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Razorpay could not complete this request. Please retry.") from exc


def verify_signature(body: bytes, signature: str, secret: str) -> None:
    if not secret or not re.fullmatch(r"[0-9a-fA-F]{64}", signature) or not hmac.compare_digest(
        hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), signature.lower()
    ):
        raise HTTPException(400, "Invalid Razorpay signature")
