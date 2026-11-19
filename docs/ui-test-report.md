# UI test report - Playwright suite against the local mock app

All data is synthetic. The application under test is a small local mock (`mock-app/server.py`) written for this capstone;
it is not a production system and no real payment provider or card data is involved.

## Scope and assumption (needs trainer sign-off)

The repository had no web UI to drive (the Java project is a login service only). Following the guide's rule to add "a
deliberately scoped local mock service after approval", a mock app was built:

- loopback only (`127.0.0.1`), standard library only, nothing written to disk, no outbound calls;
- sign-in page, account page, sign-out, and a payment form backed by a mock provider;
- accepts only synthetic cards starting with `9999`; outcome is set by the last digits (`0000` approved, `0002` declined,
  `0003` timeout); real-looking card numbers are refused and never stored (only the last four digits of a mock charge);
- test-only routes (`/__test__/ledger`, `/__test__/reset`) exist only when `MOCK_APP_TEST_ROUTES=1`, which the suite sets.

**Open owner decision:** the trainer has not yet confirmed that a mock app is an acceptable test target. If they require a
specific application, the tests keep the same structure but selectors and expected messages will need adapting.

## How to run

```
.venv\Scripts\python -m pytest tests\ui -q --tracing retain-on-failure --screenshot only-on-failure --output reports\playwright
```

The suite starts the mock app itself on a free port (set `BASE_URL` to test an app that is already running).
On failure, a trace (`trace.zip`, open with `python -m playwright show-trace`) and a screenshot are kept in the output folder.

## Test inventory (31 test cases, 19 test functions)

| Guide scenario (section 10.1) | Tests | Type |
|---|---|---|
| Login with valid test account | `test_valid_login_shows_the_account_page` | positive |
| Login with invalid password | `test_wrong_credentials_show_one_safe_error_and_no_session` (known and unknown email) | negative, security |
| Empty username/password | `test_empty_fields_show_required_messages` | negative |
| Malformed email | `test_malformed_email_is_rejected_by_validation` (4 inputs) | negative |
| Overlong input | `test_overlong_input_is_rejected_without_an_error_page` | boundary |
| Logout | `test_logout_ends_the_session_and_protected_pages_stay_closed`, `test_logout_invalidates_the_session_on_the_server` | regression, security |
| Protected pages | `test_protected_pages_redirect_when_signed_out` (/account, /pay) | security |
| Keyboard/accessibility smoke | `test_keyboard_only_sign_in_and_accessible_names` | accessibility |
| Payment form validation | `test_empty_form_is_rejected_before_any_charge`, `test_invalid_card_details_are_rejected` (3) | negative |
| Amount limits | `test_amount_boundaries` (0.00, 0.01, 1000.00, 1000.01, -5, abc) | boundary |
| Mock payment success | `test_approved_payment_shows_success_and_records_one_charge` | positive |
| Mock decline / timeout | `test_declined_payment_never_shows_success`, `test_provider_timeout_shows_failure_and_no_charge` | negative, regression |
| Repeated submit / idempotency | `test_double_click_on_pay_creates_one_charge`, `test_replaying_the_same_idempotency_key_charges_once` | regression |
| Card-data safety | `test_real_looking_card_number_is_refused_and_not_stored` | security |
| Payment API requires a session | `test_payment_api_requires_a_session` | security |

Locators use accessible roles and labels (`get_by_role`, `get_by_label`) and web-first assertions. "Was anyone charged?" is
answered by the mock's own ledger, not by what the page says, so a wrong success message cannot hide a wrong charge.

## Result

31 passed on the clean app (local Windows run, Chromium, Playwright 1.65.2, pytest-playwright 0.10.0).

## Mutation challenge

The mock app contains three deliberately seeded faults, switched on with `MOCK_APP_FAULT`. Each was enabled in turn and the
whole suite run; the app code is unchanged between runs.

| Seeded fault | Failing test | Result |
|---|---|---|
| `decline_as_success` (a declined card is recorded as approved) | `test_declined_payment_never_shows_success` | 1 failed, 30 passed |
| `duplicate_charge` (idempotency key ignored) | `test_replaying_the_same_idempotency_key_charges_once` | 1 failed, 30 passed |
| `logout_keeps_session` (server keeps the session after sign-out) | `test_logout_invalidates_the_session_on_the_server` | 1 failed, 30 passed |

**Finding about the suite itself.** The first version of the suite did not catch `logout_keeps_session`: all tests passed with
the fault on. Sign-out also asks the browser to delete the cookie, so the browser looked signed out while the server still
honoured the old session. The fix was a test that replays the old session cookie after sign-out. This is why the mutation
challenge is worth doing: a green suite had a hole in it.

## Defect report

These defects are seeded, found by the mutation challenge; they are not defects in a production product.

```
ID:                 UI-DEF-1
Title:              Server keeps the session valid after sign-out (copied cookie still works)
Severity / Priority: High / High (session fixation-style exposure on shared computers)
Environment:        Windows 11, Chromium, mock app with MOCK_APP_FAULT=logout_keeps_session, branch feature/playwright-ui
Preconditions:      Signed in as the synthetic user qa.user@example.test
Reproduction steps: 1. Sign in and copy the sid cookie. 2. Click Sign out. 3. Add the old sid cookie back to the browser.
                    4. Open /account.
Expected result:    Redirect to /login; the old session is rejected.
Actual result:      The account page opens (session still valid on the server).
Evidence:           test_logout_invalidates_the_session_on_the_server failed; trace.zip and test-failed-1.png in
                    reports/playwright-mutation (local, git-ignored)
Likely component:   POST /logout handler (server-side session removal)
Regression test:    test_logout_invalidates_the_session_on_the_server
Status:             Reproduced with the seeded fault; passes on the clean app

ID:                 UI-DEF-2
Title:              Declined card is shown and recorded as an approved payment
Severity / Priority: Critical / High (false success; goods or services released without payment)
Preconditions:      Signed in; payment form open
Reproduction steps: Pay with test card 9999 0000 0000 0002 (declined).
Expected result:    "Payment declined. You have not been charged." and no ledger entry.
Actual result:      "Payment approved" and one ledger entry.
Evidence:           test_declined_payment_never_shows_success failed
Likely component:   Provider-outcome mapping in POST /api/payments
Regression test:    test_declined_payment_never_shows_success
Status:             Reproduced with the seeded fault; passes on the clean app

ID:                 UI-DEF-3
Title:              Retrying a payment with the same idempotency key charges twice
Severity / Priority: High / High
Preconditions:      Signed in
Reproduction steps: POST /api/payments twice with the same Idempotency-Key and an approved card.
Expected result:    Same payment id both times; one ledger entry; second response marked Idempotent-Replay.
Actual result:      Two ledger entries (duplicate charge).
Evidence:           test_replaying_the_same_idempotency_key_charges_once failed
Likely component:   Idempotency handling in POST /api/payments
Regression test:    test_replaying_the_same_idempotency_key_charges_once
Status:             Reproduced with the seeded fault; passes on the clean app
```

## Limitations

- The target is a mock written by the tester. It proves the test design and tooling, not the quality of any real product.
- Chromium only. The browser matrix is an open question in the QA standards (QA-11); Firefox and WebKit are not run.
- No lockout, password-reset or session-timeout tests: the requirements leave lockout unspecified and the mock does not implement it.
- Accessibility coverage is a smoke test (labels, focus order, keyboard submit), not a full audit.
- Trace and screenshot evidence is kept locally (`reports/` is git-ignored); only the last failure's artifacts survive per run.
