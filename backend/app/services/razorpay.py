"""Razorpay TEST-only transport. Secrets never leave the backend."""
import hashlib
import hmac
import re
import httpx
from fastapi import HTTPException
from app.core.config import get_settings


def configured():
    s = get_settings()
    return s.razorpay_key_id.startswith("rzp_test_") and bool(s.razorpay_key_secret)


def api(method: str, path: str, payload=None):
    if not configured():
        raise HTTPException(503, "Configure Razorpay TEST keys and a monthly plan on the backend")
    s = get_settings()
    try:
        response = httpx.request(method, "https://api.razorpay.com/v1/" + path,
            auth=(s.razorpay_key_id, s.razorpay_key_secret), json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Razorpay could not complete this request. Please retry.")


def verify_signature(body: bytes, signature: str, secret: str):
    if not secret or not re.fullmatch(r"[0-9a-fA-F]{64}", signature) or not hmac.compare_digest(
        hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), signature.lower()
    ):
        raise HTTPException(400, "Invalid Razorpay signature")
