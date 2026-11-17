---
name: playwright-author
description: Create maintainable Playwright tests for verified application behavior.
---

# Playwright authoring rules
- Inspect the actual DOM, app source, or accessible labels before choosing locators.
- Use pytest-playwright fixtures and web-first assertions.
- Prefer get_by_role, get_by_label, get_by_text, and stable test IDs.
- Keep one main behavior per test; name tests by expected behavior.
- Avoid fixed sleeps; wait for an observable state.
- Use isolated test data and never call a real payment provider.
- Include negative cases and validation messages.
- On failure, capture the error, screenshot/trace where configured, and likely cause.
- Do not silently update expected results to match broken behavior.
- Run the test with `python -m pytest` and report the exact command and result.
- Read the base URL from the BASE_URL environment variable; never hard-code it.
