# Login requirements: `LoginService.login(String username, String password)`

> **Status: ASSUMPTION.** No official requirements exist in the starter project
> (`LoginService.java` only says "TODO: Implement authentication and input validation").
> This spec was given by the project owner on 2026-11-17 as a working assumption.
> Treat it as provisional and replace it if real requirements appear.

## Scope
- Class under test: `java-app/src/main/java/com/technova/payment/auth/LoginService.java`
- User store: `UserRepository` (in-memory). The only account is the synthetic `demo.user` / `DemoPass123!`.

## Rules
| ID | Rule |
|----|------|
| LR-1 | Correct username and correct password → returns `true`. |
| LR-2 | Known username with a wrong password → returns `false`. |
| LR-3 | Unknown username → returns `false`. |
| LR-4 | `null`, empty (`""`), or whitespace-only username → returns `false`. |
| LR-5 | `null`, empty (`""`), or whitespace-only password → returns `false`. |
| LR-6 | `login()` never throws for any of the inputs above (it returns `false` instead). |
| LR-7 | Username is case-sensitive (`Demo.User` ≠ `demo.user`), so a case mismatch → `false`. |
| LR-8 | Inputs are not trimmed (`" demo.user"`, `"DemoPass123! "` → `false`). |

## Not specified (do not assume or test)
- Lockout or rate limiting after failed attempts: no rule specified.
- Password hashing, logging and audit behaviour.
- Any payment behaviour.
