"""Login and session tests against the local mock app (requirements: rag/knowledge/login_requirements.md)."""
import re

import pytest
from playwright.sync_api import Page, expect

from ui_support import TEST_EMAIL, sign_in


def test_valid_login_shows_the_account_page(page: Page):
    sign_in(page)
    expect(page).to_have_url(re.compile(r"/account$"))
    expect(page.get_by_role("heading", name="Your account")).to_be_visible()
    expect(page.get_by_text(TEST_EMAIL)).to_be_visible()


@pytest.mark.parametrize("email", [TEST_EMAIL, "someone.else@example.test"], ids=["known-email", "unknown-email"])
def test_wrong_credentials_show_one_safe_error_and_no_session(page: Page, email):
    sign_in(page, email=email, password="not-the-password")
    expect(page.get_by_role("alert")).to_have_text("Incorrect email or password.")  # same text: no user enumeration
    expect(page).to_have_url(re.compile(r"/login$"))
    page.goto("/account")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_empty_fields_show_required_messages(page: Page):
    page.goto("/login")
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_text("Enter your email.")).to_be_visible()
    expect(page.get_by_text("Enter your password.")).to_be_visible()
    expect(page).to_have_url(re.compile(r"/login$"))


@pytest.mark.parametrize("bad_email", ["plainaddress", "missing-at.example.test", "two@@example.test", "no-dot@host"])
def test_malformed_email_is_rejected_by_validation(page: Page, bad_email):
    sign_in(page, email=bad_email, password="anything")
    expect(page.get_by_text("Enter a valid email address.")).to_be_visible()
    expect(page.get_by_label("Email")).to_have_attribute("aria-invalid", "true")


def test_overlong_input_is_rejected_without_an_error_page(page: Page):
    sign_in(page, email="a" * 250 + "@example.test", password="p" * 500)  # 262-char email, 500-char password
    expect(page.get_by_text("Enter a valid email address.")).to_be_visible()
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()


def test_logout_ends_the_session_and_protected_pages_stay_closed(page: Page):
    sign_in(page)
    page.get_by_role("button", name="Sign out").click()
    expect(page).to_have_url(re.compile(r"/login$"))
    page.goto("/account")
    expect(page).to_have_url(re.compile(r"/login$"))
    page.go_back()  # regression: the back button must not reveal the account page after sign-out
    expect(page.get_by_text(TEST_EMAIL)).to_have_count(0)


def test_logout_invalidates_the_session_on_the_server(page: Page):
    """A copied session cookie must stop working after sign-out (the browser deleting it is not enough)."""
    sign_in(page)
    stolen = [c for c in page.context.cookies() if c["name"] == "sid"]
    assert stolen, "expected a session cookie after sign-in"
    page.get_by_role("button", name="Sign out").click()
    expect(page).to_have_url(re.compile(r"/login$"))
    page.context.add_cookies(stolen)  # replay the old cookie, as an attacker who copied it would
    page.goto("/account")
    expect(page).to_have_url(re.compile(r"/login$"))


@pytest.mark.parametrize("path", ["/account", "/pay"])
def test_protected_pages_redirect_when_signed_out(page: Page, path):
    page.goto(path)
    expect(page).to_have_url(re.compile(r"/login$"))


def test_keyboard_only_sign_in_and_accessible_names(page: Page):
    page.goto("/login")
    expect(page.get_by_label("Email")).to_be_visible()
    expect(page.get_by_label("Password")).to_be_visible()
    page.get_by_label("Email").focus()
    page.keyboard.type(TEST_EMAIL)
    page.keyboard.press("Tab")
    expect(page.get_by_label("Password")).to_be_focused()
    page.keyboard.type("Capstone-Demo-1!")
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Sign in")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"/account$"))
