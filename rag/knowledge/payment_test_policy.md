# Payment test policy (synthetic capstone policy)

Version: v1 (2026-11-18). Synthetic document for the capstone; not a real company policy.

## Test environment rules (PT-1 to PT-3)

- PT-1: All payment tests must run in local test mode or against a mock provider.
- PT-2: Never use real cardholder data or a live payment gateway.
- PT-3: Test data must be synthetic. Card numbers used in tests must be documented test values only.

## Failure handling (PT-4 to PT-6)

- PT-4: A declined or timed-out payment must not be reported as successful.
- PT-5: A payment failure should show a safe, user-readable message.
- PT-6: After a timeout, the test must verify that no duplicate charge was created.

## Idempotency (PT-7)

- PT-7: Repeating the same idempotency key must not create a second charge.

## Logging and artifacts (PT-8)

- PT-8: Logs and test artifacts must not contain passwords, tokens, or full card numbers.

## Open questions (PT-9)

- PT-9: If a requirement is not documented, mark it as an open question; do not invent policy.
