# LoginService.login() — consolidated test matrix

> **Status:** Draft analysis. Per-row coverage claims are **"by reading, not executed"**: they come from
> reading the source, not from test output. See section 2 for the separate executed evidence.
> Sources: read-only runs of the `test-analyst` and `security-reviewer` agents (2026-11-18), consolidated by Claude.
> Spec: `rag/knowledge/login_requirements.md` (LR-1..LR-8, **ASSUMPTION**, owner-approved 2026-11-17).
> Every expected result here depends on that assumption.

**Notation:** `PW` = the synthetic demo password for `demo.user` (see `UserRepository.java`); it is 12 characters long.
Passwords are described relative to PW. Existing test references point to method lines in
`java-app/src/test/java/com/technova/payment/auth/LoginServiceTest.java`.

## 1. Matrix (T01–T31, plus T02b)

| ID | Case | Username | Password | Expected | LR | Pri | Risk | Coverage (by reading, not executed) |
|----|------|----------|----------|----------|----|-----|------|-------------------------------------|
| T01 | Valid credentials | `demo.user` | PW | `true` | LR-1 | P1 | High | Covered by reading, not executed: `loginWithValidCredentialsShouldSucceed` L17 |
| T02 | Wrong password, different length | `demo.user` | an unrelated wrong password (`WrongPass123!`, 13 chars vs PW's 12) | `false` | LR-2 | P1 | High | Covered by reading, not executed: `loginWithInvalidPasswordShouldFail` L22 |
| T02b | Wrong password, same length as PW | `demo.user` | PW with its last character changed | `false` | LR-2 | P1 | High | Gap (not executed) |
| T03 | Password is a strict prefix of PW | `demo.user` | PW minus its last character (and shorter prefixes) | `false` | LR-2 | P1 | High | Gap (not executed) |
| T04 | Password is PW extended | `demo.user` | PW plus one extra character | `false` | LR-2 | P1 | High | Gap (not executed) |
| T05 | Password case variants | `demo.user` | PW in lowercase; PW in uppercase; PW with its first letter's case flipped | `false` | LR-2 (implied; see A1) | P1 | High | Gap (not executed) |
| T06 | Single-character password | `demo.user` | the first character of PW | `false` | LR-2 | P2 | Medium | Gap (not executed) |
| T07 | Internal space in password | `demo.user` | PW with a space inserted in the middle | `false` | LR-2 | P2 | Medium | Gap (not executed) |
| T08 | Field confusion | `demo.user`; or PW as username | `demo.user` as password; or swapped | `false` | LR-2/LR-3 | P3 | Low | Gap (not executed) |
| T09 | Another user's password | second user | that user's password vs `demo.user` | `false` | LR-2 | P2 | Medium | **Blocked**: needs an injectable `UserRepository` (production change) |
| T10 | Unknown username | `no.such.user` | PW | `false` | LR-3 | P1 | High | Covered by reading, not executed: `loginWithUnknownUsernameShouldFail` L27 |
| T11 | Injection-style username | `' OR '1'='1`, `demo.user' --`, `*`, `.*` | PW | `false`, no throw | LR-3 | P3 | Low | Gap (not executed) |
| T12 | Unknown user with blank password | `no.such.user` | `""` | `false` | LR-3/LR-5 | P3 | Low | Gap (not executed) |
| T13 | Blank username: null, `""`, `" "`, `"   "`, `\t`, `\n` | each | PW | `false`, no throw | LR-4, LR-6 | P1 | High | Covered by reading, not executed: `blankUsernameShouldFailWithoutThrowing` L34 |
| T14 | Blank password: same set | `demo.user` | each | `false`, no throw | LR-5, LR-6 | P1 | High | Covered by reading, not executed: `blankPasswordShouldFailWithoutThrowing` L41 |
| T15 | Null in one field, valid value in the other | null / `demo.user` | PW / null | `false`, no throw | LR-4/5/6 | P1 | High | Covered by reading, not executed: null rows of L34, L41 |
| T16 | Both null | null | null | `false`, no throw | LR-6 | P2 | Medium | Covered by reading, not executed: `bothNullShouldFailWithoutThrowing` L46 |
| T17 | Mixed null/empty, both ways | null / `""` | `""` / null | `false`, no throw | LR-4/5/6 | P2 | Low | Gap (not executed) |
| T18 | Other Java whitespace as blank input: `\r`, `\f`, `\u000B`, `\u2003`, `\u3000` | each / `demo.user` | PW / each | `false`, no throw | LR-4/5/6 | P2 | Medium | Gap (not executed) |
| T19 | Unicode "spaces" that `isBlank()` doesn't treat as blank: `\u00A0`, `\u200B`, `\uFEFF` (input made only of these) | each / `demo.user` | PW / each | `false`, no throw (rejected by lookup/compare, not by the blank guard) | LR-4/5/6 (see A2) | P2 | Medium | Gap (not executed) |
| T20 | Username case variants | `Demo.User`, `DEMO.USER` | PW | `false` | LR-7 | P1 | High | Covered by reading, not executed: `usernameIsCaseSensitive` L52 |
| T21 | Username with one letter's case changed, or a homoglyph | `demo.useR`, `d\u0435mo.user` (Cyrillic U+0435) | PW | `false` | LR-7/LR-3 | P3 | Low | Gap (not executed) |
| T22 | Username with leading/trailing space | `" demo.user"`, `"demo.user "` | PW | `false` | LR-8 | P1 | High | Covered by reading, not executed: `usernameIsNotTrimmed` L58 |
| T23 | Password with leading/trailing space | `demo.user` | PW with a leading space; PW with a trailing space | `false` | LR-8 | P1 | High | Covered by reading, not executed: `passwordIsNotTrimmed` L64 |
| T24 | Tab/newline/CRLF at the edges; internal space in username | `"\tdemo.user"`, `"demo.user\n"`, `"demo .user"` / `demo.user` | PW / PW + `\n`; PW + `\r\n`; `\t` + PW | `false` | LR-8 | P2 | Medium | Gap (not executed) |
| T25 | NBSP or zero-width padding around valid values | `"demo.user\u00A0"`, `"\u200Bdemo.user"` / `demo.user` | PW / PW + `\u00A0`; PW + `\u200B` | `false` | LR-8 (spirit) | P2 | Medium | Gap (not executed) |
| T26 | Embedded NUL | `"demo.user\u0000"` / `demo.user` | PW / PW + `\u0000` | `false` | LR-8 (spirit) | P2 | Medium | Gap (not executed) |
| T27 | Lookalike or fullwidth character in password (no normalisation) | `demo.user` | PW with its last character replaced by fullwidth U+FF01; PW with one `o` replaced by Cyrillic U+043E | `false` | not in spec | P3 | Low | Gap (not executed) |
| T28 | Lone surrogate in password | `demo.user` | PW with its last character replaced by `\uD800` | `false`, no throw | LR-2/LR-6 | P3 | Low | Gap (not executed) |
| T29 | Very long input (~1,000,000 chars) | `"a".repeat(1_000_000)` / `demo.user` | PW / PW padded with 999,988 extra characters | `false`, no throw | LR-2/LR-3 (LR-6 partly; see A4) | P2 | Medium | Gap (not executed) |
| T30 | No hidden state: valid ×3, and N wrong attempts then valid, on one instance | `demo.user` | as described | `true` on each valid call (asserts no state; **does not** assert any lockout policy) | LR-1 | P3 | Low | Gap (not executed) |
| T31 | Stored password is null | user with null password | any | `false`, no throw | LR-6 (defensive) | P2 | Medium | **Blocked**: `stored == null` branch (`LoginService.java` L36-38) can't be reached without an injectable repository |

**Totals, by reading only (not executed):** 32 rows: 10 covered, 20 gaps, 2 blocked.

## 2. Executed evidence

Reported by the project owner. These runs were **not re-run when this document was written**.

| Date | Command (in `java-app\`) | Code under test | Result |
|------|--------------------------|-----------------|--------|
| 2026-11-17 | `mvn -B clean test` | committed code | 30 run, 0 failures |
| 2026-11-17 | `mvn -B clean test` | deliberate mutation: `login()` always returns `true` | 30 run, 21 failures |

The 30 tests are 22 in `LoginServiceTest` plus 8 in `UserRepositoryTest`; that split was counted by reading.
21 failures means the 21 `LoginServiceTest` cases that expect `false` caught the mutation.
This shows the suite as a whole can detect an always-true bug. It does **not** prove that any individual
row above is covered: per-row claims stay "by reading".

## 3. Where the agents disagreed, and the verdicts

| ID | test-analyst | security-reviewer | Verdict | Reason |
|----|--------------|-------------------|---------|--------|
| T05 | P1 / High | P2 / Medium | **P1 / High** | A case-insensitive compare greatly weakens passwords, and it is a common regression. A1 asks the owner to make the spec explicit. |
| T16 | P1 / High | P2 / Medium | **P2 / Medium** | T15 already covers the crash risk for single-null input. Both-null adds little on top of it. |
| T20 | P1 / High | P2 / Medium | **P1 / High** | LR-7 states this explicitly, and getting it wrong confuses accounts. |
| T22, T23 | P1 / High | P2 / Medium | **P1 / High** | LR-8 states this explicitly. Trimming is the most likely regression. |
| T11 | P2 / Medium | P3 / Low | **P3 / Low** | An exact HashMap lookup can't be injected today. The test only guards a future backend change. |
| T19 | P3 / Low (NBSP username) | P2 / Medium | **P2 / Medium** | The result is `false` either way, but it reaches that result through a different code path than the spec implies (A2). |
| T21 | P2 / Medium | P3 / Low | **P3 / Low** | The code has no folding or normalisation, so this only guards against a future change. |
| T27 | P2 / Medium | P3 / Low | **P3 / Low** | Same reason as T21. |
| T28 | P2 / Medium | P3 / Low | **P3 / Low** | It can only produce a false `true` if the stored password contains `?`. PW doesn't. The finding is recorded as S4. |
| T31 | P3 / Low | P2 / Medium | **P2 / Medium** | A defensive branch with no test can break silently. It stays blocked until a production change is approved. |

T02b was added at owner review (2026-11-18) after checking that T02's wrong password differs in length from PW.
The agents agreed on all other rows.

## 4. Gaps only security-reviewer raised

| ID | Item | Severity | Spec status |
|----|------|----------|-------------|
| T06 | Single-character password (edge case of the unequal-length compare) | P2 / Medium | LR-2 |
| T19/T25 | U+FEFF (BOM) and zero-width characters as username input | Medium | LR-4/LR-8 ambiguous |
| T26 | NUL in the **username** (test-analyst only had it in the password) | Medium | LR-8 spirit |
| S1 | Hardcoded synthetic credential appears in 4 files (`UserRepository.java`, `LoginServiceTest.java`, `login_requirements.md`, `CLAUDE.md`). Recommendation: allowlist it in a secret scanner rather than let the pattern become normal. | Low | Not specified |
| S2 | No maximum length on input, so large inputs cost CPU and memory before rejection. Recommendation: define a limit in the spec. | Low | Not specified |
| S3 | Unknown-user path returns faster than wrong-password path, a possible username-enumeration timing channel. test-analyst also noted this as out of scope. | Low (local lib) | Not specified |
| S4 | The compare runs on lossy UTF-8 bytes: a lone surrogate becomes `?`, so different strings can match | Low | Not specified |
| S5 | `User` constructor accepts a null password. Recommendation: `Objects.requireNonNull`. | Low | Not specified |
| S6 | Argument order of `MessageDigest.isEqual` (stored first) keeps timing independent of the supplied input. Recommendation: keep it and add a comment. | Info / positive | Not specified |
| S7 | Nothing logs the password and `User` has no `toString`. Recommendation: guard against adding one later. | Info / positive | Not specified |

Out of scope, by the spec's "Not specified" list (no expected results invented): lockout/rate limiting, password hashing (plaintext today, `User.java`), logging/audit, payment behaviour, concurrent calls from many threads.

## 5. Missing evidence

1. **The per-row coverage was not executed.** Neither agent ran `mvn test`. The only executed evidence is the owner-reported suite totals in section 2, and those were not re-run for this document.
2. No coverage tool (e.g. JaCoCo) was run. The claim that the `stored == null` branch is never reached comes from reading the code.
3. JDK behaviour hasn't been checked on the installed JDK 21 or the Java 17 target. The expected results of T18, T19, T25 and T28 depend on it:
   - which characters `String.isBlank()` treats as blank;
   - `getBytes(UTF_8)` turning a lone surrogate into `?`;
   - the details of `MessageDigest.isEqual`.
4. Timing (S3, S6) wasn't measured. Showing it would need a JMH-style benchmark, not a unit test.
5. Heap use and latency for very large inputs (T29) weren't measured.
6. Whether Maven resolves `junit-jupiter-params` wasn't checked separately (the 2026-11-17 run suggests it does).
7. Git history wasn't searched for credentials. Only the working tree was.
8. T09 and T31 can't be tested without a production change (an injectable `UserRepository`), which needs approval.
9. `tests/ui`, CI configuration and `README.md` were not reviewed.

## 6. Spec ambiguities for the owner

- **A1:** LR-2 never says the password is case-sensitive. Only the username is covered by LR-7.
- **A2:** "Whitespace-only" (LR-4, LR-5) isn't defined. It could mean Java `isBlank`, Unicode `White_Space`, or ASCII only.
- **A3:** LR-8 names only leading and trailing spaces. Tabs, newlines, CR and Unicode spaces aren't addressed.
- **A4:** LR-6 covers only "the inputs above". It promises nothing for very long or malformed input, or for an `OutOfMemoryError`.
- **A5:** No rules on Unicode normalisation or input length.
