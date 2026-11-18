# MCP setup: Playwright MCP (read-only use)

Capstone section 7. One MCP server is configured for this project: the official Playwright MCP server.
All evidence below was collected on 2026-11-18 on Windows 11 (Command Prompt / VS Code terminal).

## 1. Server and why it was chosen

| Item | Value |
|------|-------|
| Server | `@playwright/mcp`, pinned to `0.0.85` (reports itself as Playwright `1.66.0-alpha-2026-11-09`) |
| Publisher | Microsoft Playwright project (official package, not a third-party tutorial package) |
| Transport | stdio, started by Claude Code through `npx` |
| Runtime | Node.js v24.12.0, npx 11.6.2 (the server requires Node 18 or newer) |
| Claude Code | 2.1.327 |
| Scope | Project scope: `.mcp.json` at the repo root |

Why Playwright MCP and not GitHub MCP: it needs no token or other secret (secret hygiene is a mandatory
condition of this capstone), and it matches the browser-testing work. It is used only against local pages.

## 2. Configuration files

- `.mcp.json` (committed): server command, pinned version, `--isolated`, `--allowed-origins` limited to
  `http://localhost:8000` and `http://127.0.0.1:8000`, and `--output-dir reports/mcp`. The `env` block is empty:
  there are no credentials, tokens or environment variables.
- `.claude/settings.json` (committed): permission rules for all 25 tools (section 3).
- `.claude/settings.local.json` (NOT committed, ignored by a global git rule): holds the personal approval of the
  project server. It must contain only `"enabledMcpjsonServers": ["playwright"]`. Do not set
  `enableAllProjectMcpServers`, because that would auto-approve any server added to `.mcp.json` later.
- `reports/mcp/` (NOT committed, ignored by `reports/*` in `.gitignore`): page snapshots and console logs
  written by the server.
- The port 8000 in the origin list is a placeholder until the local mock app exists. Change it in `.mcp.json`
  if the app uses another port.

## 3. Permission scope (least privilege)

The 25 tools exposed by version 0.0.85 were listed directly from the server and match the `/mcp` tool list.

| Tier | Tools | Behaviour |
|------|-------|-----------|
| Allow (server marks them read-only) | `browser_snapshot`, `browser_take_screenshot`, `browser_console_messages`, `browser_network_requests`, `browser_network_request`, `browser_find`, `browser_wait_for` | Run without a prompt |
| Ask (every call needs approval) | `browser_navigate`, `browser_navigate_back`, `browser_tabs`, `browser_close`, `browser_resize`, `browser_click`, `browser_hover`, `browser_type`, `browser_press_key`, `browser_fill_form`, `browser_select_option` | Prompt each time; local mock app only |
| Deny | `browser_evaluate`, `browser_run_code_unsafe`, `browser_file_upload`, `browser_drop`, `browser_drag`, `browser_handle_dialog`, `browser_emulate_media` | Removed from the session |

No production sites, real credentials or live payment calls are involved: pages are local, data is synthetic.

## 4. Verification evidence

1. `/mcp` showed `playwright` as connected with 25 tools. The claude.ai connectors (Claude Docs, Gmail, Google
   Calendar, Google Drive) were not enabled. Other built-in plugin servers listed by `/mcp` were unconfigured,
   needed sign-in or failed to connect; none were used.
2. Read-only proof: a scratch page (`index.html`, synthetic, no forms or links) was served with
   `python -m http.server 8000 --bind 127.0.0.1`. Claude was asked to use only the playwright server, read-only.
   - Tools called: `browser_navigate` (approved by the owner), `browser_snapshot`, `browser_console_messages`
     (plus Claude Code's own tool-loading step, which does not touch the browser).
   - Result: heading "Capstone MCP read-only demo", page title "MCP Read-Only Demo", one console message
     `demo-page-loaded: read-only check`, no errors. Nothing was clicked, typed, evaluated or uploaded.
   - Output files written by the server: one console log and one page snapshot in `reports/mcp/`.
3. Negative test A (denied tool): asked to call `browser_evaluate`. Claude Code reported
   `No matching deferred tools found`: the denied tool is not available in the session at all.
4. Negative test B (origin not allowed): asked to navigate to `http://127.0.0.1:9000/`. The call needed
   approval, then failed with `net::ERR_BLOCKED_BY_CLIENT`. Port 9000 is not in `--allowed-origins`.
5. Secrets: no token or key is used. `git status` after the runs showed only the intended new files.

These runs were performed by the project owner in Claude Code; outputs were reviewed by the assistant.

## 5. Limitations

- `--allowed-origins` is not a security boundary according to the server's own help: it does not cover
  redirects. The permission rules above are the stronger control.
- The ask tier allows interaction (click, type) after approval. Approve only calls against the local mock app.
- The pinned server reports a pre-release Playwright core (1.66 alpha). It may need a browser build that the
  Python Playwright install does not contain. If a browser-not-found error appears, use `--browser chrome`
  (installed Chrome) in `.mcp.json` instead of changing certificates or proxy settings.
- Version pinning keeps runs repeatable but means updates are manual: re-list the tools after any version change
  and update the permission lists (a new tool is not covered by the deny list until it is added).
- Maven printed a certificate warning on this machine (probably a proxy); it did not affect MCP.

## 6. Fallback plan

The MCP server is optional for the test suites. `mvn test` and `pytest` do not use it, so if the server is
unavailable the local tests and CI still run. If `/mcp` shows playwright as failed:

1. Check `node --version` and `npx --version` work in the same terminal that starts Claude Code.
2. In `/mcp`, choose Reconnect. On native Windows, if the error mentions `ENOENT`, change the command to
   `cmd` with args `["/c", "npx", "@playwright/mcp@0.0.85", ...]`.
3. Run `claude --safe-mode` to check whether a plugin, hook or MCP server is the cause.
4. Otherwise continue without MCP: write and run the Playwright tests directly with pytest.

## 7. Reproduce

1. `cd` to the repo root and start `claude`; approve only the `playwright` server when asked.
2. Run `/mcp`; expect playwright connected with 25 tools.
3. Serve a local page on 127.0.0.1:8000 and ask Claude to navigate, take a snapshot and read the console.
4. Ask for `browser_evaluate` (expect: not available) and for another origin (expect: ERR_BLOCKED_BY_CLIENT).
