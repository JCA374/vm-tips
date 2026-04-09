# Security Plan — VM Tips

Family World Cup betting app. ~30 users, invite-only.  
Threat model: spam/abuse from the open internet, not targeted attacks.

---

## Tier 1 — Implemented

### 1. Max 30 users
- New accounts are rejected once the user count reaches `MAX_USERS` (default: 30)
- Controlled via `MAX_USERS` environment variable
- Checked in `send_magic_link()` before creating a new account
- Returns a clear error message to the user

### 2. Rate-limit magic link requests
- Max **3 requests per email address per hour**
- Max **10 requests per IP address per hour**
- Implemented via `Flask-Limiter` on the `POST /login` endpoint
- Exceeding the limit returns HTTP 429 with a friendly error page

### 3. Magic link 24-hour hard expiry
- Links expire 24 hours after creation (previously: year 9999)
- Controlled via `MAGIC_LINK_EXPIRY_HOURS` environment variable (default: 24)
- Old links in email inboxes cannot be replayed after expiry
- `verify_magic_link()` checks both `used=False` and `expires_at > now`

### 4. Protect /results behind login
- `/results` previously exposed all user predictions and names to any visitor
- Now requires an active session; unauthenticated requests redirect to login

---

## Tier 2 — Implemented

### 5. Remove public /auth/check-email endpoint
- Previously any visitor could check which emails are registered (enumeration)
- Endpoint removed; the new/existing user check now happens server-side only
- The login form handles both cases in a single POST — no AJAX needed

### 6. Rate-limit /auth/verify
- Max **20 token attempts per IP per hour**
- Prevents brute-force guessing of magic link tokens
- Exceeding returns HTTP 429

### 7. Secret key enforcement
- App refuses to start in production (`FLASK_ENV=production`) if `SECRET_KEY`
  is the insecure default value
- Logged as a warning in development mode

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-...` | Flask session signing key — **must be changed in production** |
| `MAX_USERS` | `30` | Hard cap on total registered users |
| `MAGIC_LINK_EXPIRY_HOURS` | `24` | Hours before a magic link expires |
| `RATELIMIT_STORAGE_URI` | `memory://` | Rate-limit storage (`redis://...` for multi-process) |

---

## Tier 3 — Not implemented (overkill for this use case)

- CSRF tokens (would require Flask-WTF across all forms)
- IP blocklist / geo-blocking
- CAPTCHA on login
- Audit log for admin actions

---

## Notes

- Admin access is email-based (`ADMIN_EMAIL` env var), not password-based
- The admin URL (`/backstage`) is not linked publicly and returns 404 to non-admins
- Sessions are permanent only when the user ticks "Keep me logged in" (6 months)
- Magic links are single-use and invalidated when a new one is requested
