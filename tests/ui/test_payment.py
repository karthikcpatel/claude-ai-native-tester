"""Mock payment tests: validation, approved/declined/timeout mapping, idempotency, and safety.

Nothing here touches a real provider or real card data. 'Was anyone charged?' is answered by the mock's own ledger.
"""
import pytest
from playwright.sync_api import Page, expect

from ui_support import APPROVED_CARD, DECLINED_CARD, TIMEOUT_CARD, fill_payment, open_payment_form, pay


def test_empty_form_is_rejected_before_any_charge(page: Page, charges):
    open_payment_form(page)
    pay(page)
    for message in ("Enter the cardholder name.", "Enter the card number.", "Enter the expiry date.",
                    "Enter the CVC.", "Enter an amount."):
        expect(page.get_by_text(message)).to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("No payment was made")
    assert charges() == []


@pytest.mark.parametrize("amount,accepted,message", [
    ("0.00", False, "Amount must be between 0.01 and 1000.00."),
    ("0.01", True, None),
    ("1000.00", True, None),
    ("1000.01", False, "Amount must be between 0.01 and 1000.00."),
    ("-5", False, "Amount must be a number such as 25.00."),
    ("abc", False, "Amount must be a number such as 25.00."),
])
def test_amount_boundaries(page: Page, charges, amount, accepted, message):
    open_payment_form(page)
    fill_payment(page, APPROVED_CARD, amount=amount)
    pay(page)
    if accepted:
        expect(page.get_by_role("status")).to_contain_text("Payment approved")
        assert len(charges()) == 1
    else:
        expect(page.get_by_text(message)).to_be_visible()
        assert charges() == []


@pytest.mark.parametrize("field,value,message", [
    ("expiry", "13/39", "Expiry must be a valid MM/YY."),
    ("expiry", "01/20", "This card has expired."),
    ("cvc", "12", "CVC must be 3 digits."),
])
def test_invalid_card_details_are_rejected(page: Page, charges, field, value, message):
    open_payment_form(page)
    fill_payment(page, APPROVED_CARD, **{field: value})
    pay(page)
    expect(page.get_by_text(message)).to_be_visible()
    assert charges() == []


def test_approved_payment_shows_success_and_records_one_charge(page: Page, charges):
    open_payment_form(page)
    fill_payment(page, APPROVED_CARD)
    pay(page)
    expect(page.get_by_role("status")).to_contain_text("Payment approved")
    recorded = charges()
    assert len(recorded) == 1 and recorded[0]["last4"] == "0000"


def test_declined_payment_never_shows_success(page: Page, charges):
    open_payment_form(page)
    fill_payment(page, DECLINED_CARD)
    pay(page)
    expect(page.get_by_role("status")).to_contain_text("Payment declined. You have not been charged.")
    expect(page.get_by_text("Payment approved")).to_have_count(0)
    assert charges() == []


def test_provider_timeout_shows_failure_and_no_charge(page: Page, charges):
    open_payment_form(page)
    fill_payment(page, TIMEOUT_CARD)
    pay(page)
    expect(page.get_by_role("status")).to_contain_text("timed out. You have not been charged.")
    expect(page.get_by_text("Payment approved")).to_have_count(0)
    assert charges() == []


def test_double_click_on_pay_creates_one_charge(page: Page, charges):
    open_payment_form(page)
    fill_payment(page, APPROVED_CARD)
    page.get_by_role("button", name="Pay").dblclick()
    expect(page.get_by_role("status")).to_contain_text("Payment approved")
    assert len(charges()) == 1


def test_replaying_the_same_idempotency_key_charges_once(page: Page, charges):
    open_payment_form(page)  # signed-in browser context supplies the session cookie
    payload = {"cardholder": "Test Cardholder", "card": APPROVED_CARD, "expiry": "12/39", "cvc": "123",
               "amount": "25.00"}
    headers = {"Idempotency-Key": "retry-key-0001"}
    first = page.request.post("/api/payments", data=payload, headers=headers)
    second = page.request.post("/api/payments", data=payload, headers=headers)
    assert first.status == 200 and second.status == 200
    assert second.headers.get("idempotent-replay") == "true"
    assert first.json()["payment_id"] == second.json()["payment_id"]
    assert len(charges()) == 1


def test_real_looking_card_number_is_refused_and_not_stored(page: Page, charges):
    real_looking = "4111 1111 1111 1111"
    open_payment_form(page)
    fill_payment(page, real_looking)
    pay(page)
    expect(page.get_by_text("Only synthetic test cards starting with 9999 are accepted.")).to_be_visible()
    assert charges() == []
    assert "4111" not in page.get_by_role("status").inner_text()  # the refusal must not echo the number back


def test_payment_api_requires_a_session(playwright, base_url):
    anonymous = playwright.request.new_context(base_url=base_url)  # no cookies: not signed in
    response = anonymous.post("/api/payments", data={"card": "9999 0000 0000 0000"},
                              headers={"Idempotency-Key": "k"})
    assert response.status == 401
    anonymous.dispose()
