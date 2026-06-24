# Playwright Test Suite — Notes for Claude

## What this folder is

Standalone Node.js/TypeScript Playwright project for end-to-end browser testing of the VM Tips Flask app. Completely separate from the Python pytest suite in `../tests/`.

## Key design decisions

**Auth via password login, not magic link**
Tests use the Password tab on the login page. Magic links require email delivery which can't be automated. Users must have a password set via `/auth/set-password` before tests can run.

**Single auth setup, shared cookie state**
`tests/auth.setup.ts` runs first and saves browser storage to `.auth/user.json`. All other tests reuse that file so they start already logged in — no repeated logins. Auth tests (`auth.spec.ts`) explicitly clear cookies so they can test the login flow itself.

**Two credential pairs in .env**
- `TEST_EMAIL` / `TEST_PASSWORD` — regular user, used for most tests
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — admin user, used in `admin.spec.ts`
Admin tests skip gracefully if ADMIN_* vars are not set.

**Sequential execution (`fullyParallel: false`)**
The app uses SQLite (single file). Parallel tests writing predictions would cause conflicts.

**Project order in playwright.config.ts**
The `setup` project runs before `chromium`. This is enforced via `dependencies: ['setup']`.

## File structure

```
playwright/
  playwright.config.ts   — baseURL, projects (setup → chromium), reporter
  fixtures/
    login.ts             — loginAs(page, email, password) helper
  tests/
    auth.setup.ts        — one-time login, saves .auth/user.json
    auth.spec.ts         — login UI, wrong password, redirects, logout
    predictions.spec.ts  — predict page, saving, warning messages
    leaderboard.spec.ts  — table presence, columns, row count
    results.spec.ts      — load, auth guard, deadline filtering
    admin.spec.ts        — access control, dashboard, deadlines, users
    navigation.spec.ts   — header, nav links, ocean theme colour check
```

## What is NOT tested here

- Magic link email delivery (no way to automate without email access)
- Match data API sync (external dependency)
- Score calculation logic (covered by Python unit tests in `../tests/`)
- Database migrations

## Running against production

```bash
npm run test:prod
# = BASE_URL=https://storahultsvm.se playwright test
```
Uses the same .env credentials — make sure TEST_EMAIL/ADMIN_EMAIL exist on prod with passwords set.

## When tests fail

- **auth.setup fails** — credentials in .env are wrong or user has no password set
- **admin tests skip** — ADMIN_EMAIL / ADMIN_PASSWORD not set in .env (intentional, not a bug)
- **predictions tests skip** — active round has no score inputs (e.g. only 1X2 outcomes)
- **.auth/user.json missing** — run `npm test` once first to generate it; it is git-ignored

## Extending

Add new test files to `tests/`. They automatically pick up the saved auth state. If a test needs a fresh unauthenticated browser use:
```ts
test.use({ storageState: { cookies: [], origins: [] } });
```
