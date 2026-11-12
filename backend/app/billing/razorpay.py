"""Thin Razorpay client: Orders API, payment lookup and signature checks."""
import hashlib
import hmac

import httpx
from fastapi import HTTPException

from app.core.config import settings

API = "https://api.razorpay.com/v1"


def configured() -> bool:
    return bool(settings.razorpay_key_id and settings.razorpay_key_secret)


def call(method: str, path: str, **kwargs) -> dict:
    if not configured():
        raise HTTPException(503, "Online payment is not available right now. Please contact support.")
    try:
        response = httpx.request(method, f"{API}{path}", auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
                                 timeout=15, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Could not reach the payment provider. Try again.") from exc
    if response.status_code >= 400:
        raise HTTPException(502, "The payment provider rejected the request.")
    return response.json()


def _matches(secret: str, message: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def checkout_signature_ok(order_id: str, payment_id: str, signature: str) -> bool:
    return _matches(settings.razorpay_key_secret or "", f"{order_id}|{payment_id}".encode(), signature)


def webhook_signature_ok(body: bytes, signature: str) -> bool:
    return bool(settings.razorpay_webhook_secret) and _matches(settings.razorpay_webhook_secret, body, signature)


def subscription_signature_ok(payment_id: str, subscription_id: str, signature: str) -> bool:
    return _matches(settings.razorpay_key_secret or "", f"{payment_id}|{subscription_id}".encode(), signature)
