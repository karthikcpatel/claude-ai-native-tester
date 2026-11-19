# Known defects (synthetic past defects)

Version: v1 (2026-11-18). All defects below are invented for the capstone.

## D-1: Declined payment shown as success

- Symptom: a declined card showed a success message.
- Expected regression check: a declined payment must show a safe error and must not be reported as successful.

## D-2: Duplicate charge on retry

- Symptom: submitting the same request twice with the same idempotency key created two charges.
- Expected regression check: repeating the same idempotency key must not create a second charge.

## D-3: Password in debug log

- Symptom: a debug log line contained a password value.
- Expected regression check: logs and test artifacts must not contain passwords, tokens, or full card numbers.

## D-4: Endless spinner after timeout

- Symptom: after a payment timeout the page kept a spinner and showed no message.
- Expected regression check: a timeout must show a safe, user-readable message and must not claim success.
