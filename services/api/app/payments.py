"""Razorpay test-mode orders. Only authenticated captured webhooks confirm bookings."""
import hashlib
import hmac
import json
import re
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request


def verify_webhook(raw: bytes, signature: str, secret: str) -> bool:
    if not secret or not re.fullmatch(r"[0-9a-fA-F]{64}", signature):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower())


def captured_payment(document: dict) -> dict | None:
    if document.get("event") != "payment.captured":
        return None
    try:
        entity = document["payload"]["payment"]["entity"]
        if entity["status"] != "captured" or entity["currency"] != "INR" or type(entity["amount"]) is not int or entity["amount"] <= 0:
            raise ValueError()
        if not re.fullmatch(r"pay_[a-zA-Z0-9]+", entity["id"]) or not re.fullmatch(r"order_[a-zA-Z0-9]+", entity["order_id"]):
            raise ValueError()
        return {"payment_id": entity["id"], "order_id": entity["order_id"], "amount": entity["amount"], "currency": entity["currency"]}
    except (KeyError, ValueError, TypeError):
        raise HTTPException(422, "Invalid captured-payment event.") from None


class Razorpay:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    @property
    def configured(self):
        return bool(self.settings.razorpay_key_id.startswith("rzp_test_") and self.settings.razorpay_key_secret and self.settings.razorpay_webhook_secret)

    async def order(self, amount: int, receipt: str):
        try:
            async with httpx.AsyncClient(base_url="https://api.razorpay.com/v1/", auth=(self.settings.razorpay_key_id, self.settings.razorpay_key_secret), transport=self.transport, timeout=15, trust_env=False, follow_redirects=False) as client:
                response = await client.post("orders", json={"amount": amount, "currency": "INR", "receipt": receipt, "partial_payment": False})
                response.raise_for_status()
                order = response.json()
            if order.get("amount") != amount or order.get("currency") != "INR" or order.get("receipt") != receipt or not re.fullmatch(r"order_[a-zA-Z0-9]+", order.get("id", "")):
                raise ValueError()
            return order
        except (httpx.HTTPError, ValueError, TypeError):
            # A timeout may mean the provider created an order. Never blindly create another.
            raise HTTPException(503, "Payment order creation is uncertain. An operator must reconcile the booking receipt with Razorpay before retrying. No payment has been assumed.") from None


def install_payments(app, settings):
    r = APIRouter(prefix="/api/v1")
    provider = Razorpay(settings)
    app.state.payments = provider

    @r.post("/bookings/{booking_id}/checkout")
    async def checkout(booking_id: UUID, request: Request):
        user = await app.state.auth.identity(request)
        if not provider.configured:
            raise HTTPException(503, "Razorpay test credentials and webhook secret are not configured. No checkout or payment has been created.")
        intent = await app.state.database.call("checkout_prepare", {"booking_id": str(booking_id)}, user["id"])
        if intent["existing"]:
            return {"key_id": settings.razorpay_key_id, **intent}
        try:
            order = await provider.order(intent["amount"], intent["receipt"])
            await app.state.database.call("checkout_bind", {"booking_id": str(booking_id), "order_id": order["id"], "amount": order["amount"], "currency": order["currency"]}, user["id"])
        except Exception:
            # Persist an uncertain state; operator reconciliation is required, never an automatic second order.
            try:
                await app.state.database.call("checkout_unknown", {"booking_id": str(booking_id)}, user["id"])
            except Exception:
                pass  # The original committed 'creating' intent also prevents retries.
            raise
        return {"key_id": settings.razorpay_key_id, "order_id": order["id"], "amount": order["amount"], "currency": "INR"}

    @r.post("/payments/webhook")
    async def webhook(request: Request):
        if not provider.configured:
            raise HTTPException(503, "Payment webhook service is not configured.")
        raw = await request.body()
        if not verify_webhook(raw, request.headers.get("x-razorpay-signature", ""), settings.razorpay_webhook_secret):
            raise HTTPException(401, "Invalid webhook signature.")
        event_id = request.headers.get("x-razorpay-event-id", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", event_id):
            raise HTTPException(422, "A provider event ID is required.")
        try:
            document = json.loads(raw)
            if not isinstance(document, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(422, "Invalid webhook document.")
        payment = captured_payment(document)
        if payment is None:
            return {"received": True, "ignored": True}
        return await app.state.database.call("payment_capture", {**payment, "event_id": event_id, "body_sha256": hashlib.sha256(raw).hexdigest()})

    app.include_router(r)
