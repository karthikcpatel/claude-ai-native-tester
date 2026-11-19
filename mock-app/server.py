"""Local mock app for the capstone UI tests: sign-in plus a mock payment form.

SYNTHETIC ONLY. It binds to 127.0.0.1, stores nothing on disk, accepts only fake test cards that start with 9999,
and never calls a real payment provider. Run:  python mock-app/server.py --port 8000

Mock provider rules (card number -> outcome):
  9999 0000 0000 0000  approved
  9999 0000 0000 0002  declined
  9999 0000 0000 0003  provider timeout (HTTP 504)
  any other number     rejected before any charge (real-looking card numbers are never accepted)

Environment:
  MOCK_APP_PASSWORD     password of the synthetic test user (default below, not a real secret)
  MOCK_APP_TEST_ROUTES  "1" enables /__test__/ledger and /__test__/reset (the test suite sets it)
  MOCK_APP_FAULT        decline_as_success | duplicate_charge | logout_keeps_session
                        deliberately seeded defects used to prove the tests can fail (mutation challenge)
"""
from __future__ import annotations

import argparse
import hmac
import html
import json
import os
import re
import secrets
import threading
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TEST_EMAIL = "qa.user@example.test"
TEST_PASSWORD = os.environ.get("MOCK_APP_PASSWORD", "Capstone-Demo-1!")
FAULT = os.environ.get("MOCK_APP_FAULT", "").strip()
TEST_ROUTES = os.environ.get("MOCK_APP_TEST_ROUTES") == "1"
STATIC = Path(__file__).parent / "static"
MAX_BODY = 10_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SESSIONS: dict[str, str] = {}
LEDGER: list[dict] = []          # successful mock charges (last four digits only)
IDEMPOTENT: dict[str, tuple[int, dict]] = {}
LOCK = threading.Lock()

CSS_LINK = '<link rel="stylesheet" href="/static/app.css">'


def page(title: str, body: str, script: str = "") -> bytes:
    tag = f'<script src="/static/{script}" defer></script>' if script else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">{CSS_LINK}{tag}</head>'
            f"<body><main>{body}</main></body></html>").encode("utf-8")


def login_page(email: str = "", errors: dict | None = None, banner: str = "") -> bytes:
    errors = errors or {}

    def field(name, label, kind, value, autocomplete):
        err = errors.get(name)
        described = f' aria-describedby="{name}-error" aria-invalid="true"' if err else ""
        message = f'<p class="field-error" id="{name}-error">{html.escape(err)}</p>' if err else ""
        return (f'<div class="field"><label for="{name}">{label}</label>'
                f'<input id="{name}" name="{name}" type="{kind}" value="{html.escape(value)}" '
                f'autocomplete="{autocomplete}"{described}>{message}</div>')

    alert = f'<p role="alert" class="alert">{html.escape(banner)}</p>' if banner else ""
    body = ("<h1>Sign in</h1>" + alert +
            '<form method="post" action="/login" novalidate>' +
            field("email", "Email", "text", email, "username") +
            field("password", "Password", "password", "", "current-password") +
            '<button type="submit">Sign in</button></form>')
    return page("Sign in", body)


def account_page(email: str) -> bytes:
    body = (f"<h1>Your account</h1><p>Signed in as <strong>{html.escape(email)}</strong></p>"
            '<p><a href="/pay">Make a payment</a></p>'
            '<form method="post" action="/logout"><button type="submit">Sign out</button></form>')
    return page("Your account", body)


def pay_page(key: str) -> bytes:
    def field(name, label, hint="", extra=""):
        h = f'<span class="hint" id="{name}-hint">{hint}</span>' if hint else ""
        return (f'<div class="field"><label for="{name}">{label}</label>{h}'
                f'<input id="{name}" name="{name}" type="text" autocomplete="off" {extra}>'
                f'<p class="field-error" id="{name}-error" hidden></p></div>')

    body = ("<h1>Make a payment</h1>"
            '<p class="note">Synthetic test environment. Use test card 9999 0000 0000 0000 (approved), '
            "...0002 (declined) or ...0003 (timeout). Never enter a real card.</p>"
            '<form id="pay-form" novalidate>' +
            f'<input type="hidden" id="idempotency-key" value="{key}">' +
            field("cardholder", "Cardholder name") + field("card", "Card number") +
            field("expiry", "Expiry (MM/YY)") + field("cvc", "CVC") + field("amount", "Amount (USD)") +
            '<button type="submit" id="pay-button">Pay</button></form>'
            '<div id="result" role="status" aria-live="polite"></div>'
            '<p><a href="/account">Back to account</a></p>')
    return page("Make a payment", body, script="pay.js")


def validate_payment(data: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    name = str(data.get("cardholder", "")).strip()
    if not name:
        errors["cardholder"] = "Enter the cardholder name."
    elif len(name) > 60:
        errors["cardholder"] = "Cardholder name must be 60 characters or fewer."
    card = re.sub(r"[ -]", "", str(data.get("card", "")))
    if not card:
        errors["card"] = "Enter the card number."
    elif not re.fullmatch(r"\d{16}", card):
        errors["card"] = "Card number must be 16 digits."
    elif not card.startswith("9999"):
        errors["card"] = "Only synthetic test cards starting with 9999 are accepted."
    expiry = str(data.get("expiry", "")).strip()
    match = re.fullmatch(r"(\d{2})/(\d{2})", expiry)
    if not expiry:
        errors["expiry"] = "Enter the expiry date."
    elif not match or not 1 <= int(match.group(1)) <= 12:
        errors["expiry"] = "Expiry must be a valid MM/YY."
    elif (2000 + int(match.group(2)), int(match.group(1))) < (date.today().year, date.today().month):
        errors["expiry"] = "This card has expired."
    cvc = str(data.get("cvc", "")).strip()
    if not cvc:
        errors["cvc"] = "Enter the CVC."
    elif not re.fullmatch(r"\d{3}", cvc):
        errors["cvc"] = "CVC must be 3 digits."
    amount = str(data.get("amount", "")).strip()
    if not amount:
        errors["amount"] = "Enter an amount."
    elif not re.fullmatch(r"\d{1,4}(\.\d{1,2})?", amount):
        errors["amount"] = "Amount must be a number such as 25.00."
    elif not 0 < float(amount) <= 1000:
        errors["amount"] = "Amount must be between 0.01 and 1000.00."
    return errors


def provider(card_digits: str) -> str:
    """The mock payment provider: outcome is decided only by the last four digits of a 9999 test card."""
    return {"0000": "approved", "0002": "declined", "0003": "timeout"}.get(card_digits[-4:], "declined")


class Handler(BaseHTTPRequestHandler):
    server_version = "CapstoneMock/1"

    def log_message(self, fmt, *args):  # never log bodies, queries or headers
        if os.environ.get("MOCK_APP_QUIET") != "1":
            print(f"{self.command} {urlparse(self.path).path} -> {args[1] if len(args) > 1 else ''}")

    # -- helpers ---------------------------------------------------------------------------------------------
    def _send(self, status, body: bytes, content_type="text/html; charset=utf-8", headers=None, cache=True):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if not cache:
            self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location, headers=None):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _json(self, status, payload, headers=None):
        self._send(status, json.dumps(payload).encode(), "application/json", headers, cache=False)

    def _session_email(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie["sid"].value if "sid" in cookie else ""
        return SESSIONS.get(token)

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return b""
        return self.rfile.read(length)

    # -- routes ----------------------------------------------------------------------------------------------
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._redirect("/login")
        if path == "/healthz":
            return self._json(200, {"ok": True})
        if path == "/login":
            return self._send(200, login_page(), cache=False)
        if path == "/account":
            email = self._session_email()
            return self._send(200, account_page(email), cache=False) if email else self._redirect("/login")
        if path == "/pay":
            if not self._session_email():
                return self._redirect("/login")
            return self._send(200, pay_page(secrets.token_hex(16)), cache=False)
        if path in ("/static/app.css", "/static/pay.js"):
            file = STATIC / path.rsplit("/", 1)[1]
            kind = "text/css" if path.endswith(".css") else "text/javascript"
            return self._send(200, file.read_bytes(), kind)
        if TEST_ROUTES and path == "/__test__/ledger":
            return self._json(200, {"charges": LEDGER})
        self._send(404, page("Not found", "<h1>Not found</h1>"))

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/login":
            return self._login()
        if path == "/logout":
            return self._logout()
        if path == "/api/payments":
            return self._payment()
        if TEST_ROUTES and path == "/__test__/reset":
            with LOCK:
                LEDGER.clear()
                IDEMPOTENT.clear()
            return self._json(200, {"ok": True})
        self._send(404, page("Not found", "<h1>Not found</h1>"))

    def _login(self):
        form = {k: v[0] for k, v in parse_qs(self._body().decode("utf-8", "replace")).items()}
        email, password = form.get("email", "").strip(), form.get("password", "")
        errors = {}
        if not email:
            errors["email"] = "Enter your email."
        elif len(email) > 254 or not EMAIL_RE.match(email):
            errors["email"] = "Enter a valid email address."
        if not password:
            errors["password"] = "Enter your password."
        if errors:
            return self._send(400, login_page(email[:254], errors), cache=False)
        ok = hmac.compare_digest(email.lower(), TEST_EMAIL) & hmac.compare_digest(password, TEST_PASSWORD)
        if not ok or len(password) > 128:  # one generic message: no hint whether the email exists
            return self._send(401, login_page(email, banner="Incorrect email or password."), cache=False)
        token = secrets.token_urlsafe(24)
        SESSIONS[token] = TEST_EMAIL
        self._redirect("/account", {"Set-Cookie": f"sid={token}; HttpOnly; SameSite=Strict; Path=/"})

    def _logout(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        if "sid" in cookie and FAULT != "logout_keeps_session":
            SESSIONS.pop(cookie["sid"].value, None)
        self._redirect("/login", {"Set-Cookie": "sid=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})

    def _payment(self):
        if not self._session_email():
            return self._json(401, {"status": "error", "message": "Sign in to make a payment."})
        try:
            data = json.loads(self._body() or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"status": "error", "message": "Request body must be JSON."})
        key = str(self.headers.get("Idempotency-Key") or data.get("idempotency_key") or "")
        if not key:
            return self._json(400, {"status": "error", "message": "An idempotency key is required."})
        errors = validate_payment(data)
        if errors:
            return self._json(422, {"status": "invalid", "errors": errors})
        card = re.sub(r"[ -]", "", data["card"])
        with LOCK:
            if key in IDEMPOTENT and FAULT != "duplicate_charge":
                status, payload = IDEMPOTENT[key]
                return self._json(status, payload, {"Idempotent-Replay": "true"})
            outcome = provider(card)
            if outcome == "approved" or (outcome == "declined" and FAULT == "decline_as_success"):
                payment_id = "pay_" + secrets.token_hex(6)
                LEDGER.append({"payment_id": payment_id, "last4": card[-4:], "amount": data["amount"], "key": key})
                status, payload = 200, {"status": "approved", "payment_id": payment_id,
                                        "message": "Payment approved."}
            elif outcome == "declined":
                status, payload = 402, {"status": "declined",
                                        "message": "Payment declined. You have not been charged."}
            else:
                status, payload = 504, {"status": "timeout",
                                        "message": "The payment service timed out. You have not been charged."}
            IDEMPOTENT[key] = (status, payload)
        self._json(status, payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    port = parser.parse_args().port
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # loopback only, by design
    if FAULT:
        print(f"WARNING: seeded fault active: {FAULT}")
    print(f"Mock app on http://127.0.0.1:{port}  (synthetic data only, Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
