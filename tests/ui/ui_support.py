"""Shared constants and page helpers for the UI tests. Locators use accessible roles and labels only."""
import os

from playwright.sync_api import Page, expect

TEST_EMAIL = "qa.user@example.test"
TEST_PASSWORD = os.environ.get("MOCK_APP_PASSWORD", "Capstone-Demo-1!")

APPROVED_CARD = "9999 0000 0000 0000"
DECLINED_CARD = "9999 0000 0000 0002"
TIMEOUT_CARD = "9999 0000 0000 0003"


def sign_in(page: Page, email: str = TEST_EMAIL, password: str = TEST_PASSWORD) -> None:
    page.goto("/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def open_payment_form(page: Page) -> None:
    sign_in(page)
    expect(page.get_by_role("heading", name="Your account")).to_be_visible()
    page.get_by_role("link", name="Make a payment").click()
    expect(page.get_by_role("heading", name="Make a payment")).to_be_visible()


def fill_payment(page: Page, card: str, name: str = "Test Cardholder", expiry: str = "12/39",
                 cvc: str = "123", amount: str = "25.00") -> None:
    page.get_by_label("Cardholder name").fill(name)
    page.get_by_label("Card number").fill(card)
    page.get_by_label("Expiry (MM/YY)").fill(expiry)
    page.get_by_label("CVC").fill(cvc)
    page.get_by_label("Amount (USD)").fill(amount)


def pay(page: Page) -> None:
    page.get_by_role("button", name="Pay").click()
