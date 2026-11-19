# QA standards (synthetic capstone standards)

Version: v1 (2026-11-18). Synthetic document for the capstone.

## Test naming (QA-1 to QA-2)

- QA-1: Test names describe behaviour, for example `loginWithInvalidPasswordShouldFail` or
  `test_declined_payment_shows_error`.
- QA-2: Each test checks one behaviour and has a clear, specific failure message.

## Assertions (QA-3 to QA-4)

- QA-3: Every test asserts an expected result. A test without an assertion does not count as coverage.
- QA-4: Negative cases assert the exact expected outcome, not only that no exception was thrown.

## Locators for browser tests (QA-5 to QA-7)

- QA-5: Prefer role, label or visible-text locators observed in the real page.
- QA-6: Use a test id only when no accessible locator exists.
- QA-7: Do not use fixed sleeps. Use the framework's auto-waiting and explicit conditions.

## Evidence (QA-8 to QA-9)

- QA-8: Failed browser tests keep a trace and a screenshot.
- QA-9: Evidence files must not contain passwords, tokens, or full card numbers.

## Test data (QA-10)

- QA-10: Use synthetic data only. Never use real customer data.

## Open questions (QA-11)

- QA-11: The browser engines to cover have not been decided. This is an open question; do not assume a matrix.
