# Security Reference — VM Tips

Family World Cup betting app. ~30 users, invite-only.  
Threat model: spam/abuse from the open internet, not targeted attacks.

---

## Authentication Model

Two login methods:

1. **Magic link** — a one-time token emailed to the user. 32-byte URL-safe random (`secrets.token_urlsafe(32)` = 256 bits of entropy), expires after `MAGIC_LINK_EXPIRY_HOURS` (default: 24 h), marked `used=True` on first POST to `/auth/verify`. Requesting a new link invalidates all previous unused links for that user.

2. **Password** — optional, set by the user after first magic-link login. Stored as a bcrypt hash via `werkzeug.security.generate_password_hash`. No plaintext is ever stored or logged.

Admin access: session email is compared to `ADMIN_EMAIL` env var. Admin routes return 404 to non-admins so the URL appears not to exist.

---

## Security Controls

| Control | Detail |
|---------|--------|
| Password hashing | `werkzeug.security` (bcrypt) — no plaintext stored |
| Magic link entropy | `secrets.token_urlsafe(32)` — 256 bits |
| Token expiry | 24 h hard expiry in `expires_at`, checked on every verify (peek and consume) |
| Token one-time use | Marked `used=True` on first successful POST to `/auth/verify` |
| Token invalidation | All unused tokens voided when user requests a new one |
| Email scanner protection | GET `/auth/verify` peeks without consuming; POST consumes |
| Rate limiting — login | 10 requests / IP / hour |
| Rate limiting — verify | 20 attempts / IP / hour |
| Rate limiting — invite | 10 / IP / hour |
| Per-user invite cap | `INVITE_LIMIT_PER_USER` (default: 10), error message is intentionally vague |
| Session cookie `HttpOnly` | `SESSION_COOKIE_HTTPONLY = True` — no JS access |
| Session cookie `SameSite` | `SESSION_COOKIE_SAMESITE = 'Lax'` — CSRF mitigation |
| Session cookie `Secure` | `SESSION_COOKIE_SECURE = True` in production — HTTPS only |
| Secret key guard | Hard error on startup if default key used with `FLASK_ENV=production` |
| SQL injection | SQLAlchemy ORM parameterised queries throughout |
| Debug mode | `debug=False` — Werkzeug debugger/console disabled |
| Open redirect | `/lang/` always redirects to `/` — never follows `Referer` header |
| User cap | New accounts rejected when `MAX_USERS` reached |
| Admin URL obscurity | `/backstage` not linked publicly, returns 404 to non-admins |

---

## Production Deployment Checklist

Set these environment variables before going live:

```
SECRET_KEY=<long random string>          # python -c "import secrets; print(secrets.token_hex(32))"
ADMIN_EMAIL=your@email.com               # no hardcoded default
APP_URL=https://your-domain.com          # used in magic link URLs
SESSION_COOKIE_SECURE=true               # requires HTTPS termination
MAIL_API_KEY=...                         # Brevo API key
MAIL_DEFAULT_SENDER=noreply@your-domain.com
FLASK_ENV=production                     # enforces SECRET_KEY check on startup
```

Verify on the server:
- [ ] HTTPS/TLS configured (nginx + certbot)
- [ ] `SESSION_COOKIE_SECURE=true` set
- [ ] `SECRET_KEY` is unique and not the dev default
- [ ] `ADMIN_EMAIL` is set (no default — omitting leaves admin access effectively disabled)
- [ ] gunicorn is serving Flask, not `python app.py`

---

## Known Limitations / Future Work

### Rate limiting uses in-memory storage (current)
`RATELIMIT_STORAGE_URI=memory://` means each gunicorn worker tracks limits independently and limits reset on restart. An attacker with persistent connections to the same worker can hit the limit; a restart resets it.

**Upgrade:** Set `RATELIMIT_STORAGE_URI=redis://localhost:6379/0` and install `flask-limiter[redis]`. Counters are then shared across all workers and survive restarts.

### No CSRF tokens on forms
`SESSION_COOKIE_SAMESITE=Lax` blocks cross-origin POST requests from sending the session cookie, which covers the practical CSRF risk for this app. Full token-based CSRF protection is not implemented.

**Upgrade path:** Add `flask-wtf` and `{{ form.hidden_tag() }}` to every form for explicit per-request CSRF tokens.

### No per-account password lockout
The rate limiter is IP-based. An attacker rotating IPs could attempt unlimited password guesses. Magic-link login is unaffected (no password to guess).

**Mitigation if needed:** Track failed attempts per email in the database and lock the account after N failures.

---

## Environment Variables Reference

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-...` | **Change in production.** Flask session signing key. |
| `ADMIN_EMAIL` | *(empty)* | Admin's email address. No default — must be set explicitly. |
| `APP_URL` | `http://localhost:5000` | Base URL used in magic link emails. Must be `https://` in production. |
| `SESSION_COOKIE_SECURE` | `false` | Set `true` in production (requires HTTPS). |
| `MAX_USERS` | `50` | Hard cap on total registered users. |
| `MAGIC_LINK_EXPIRY_HOURS` | `24` | Hours before a magic link token expires. |
| `INVITE_EXPIRY_DAYS` | `7` | Days before an invite link expires. |
| `RATELIMIT_STORAGE_URI` | `memory://` | Use `redis://...` in production for shared counters. |
| `FLASK_ENV` | *(unset)* | Set to `production` to enforce `SECRET_KEY` check on startup. |

---

## Secrets Management

- All secrets live in `.env` (gitignored)
- `.env.example` contains placeholder keys only
- Brevo API key: rotate at https://app.brevo.com if compromised
- Football API key: read-only; rotate at https://www.football-data.org if compromised
- Rotating `SECRET_KEY` immediately invalidates all active sessions (users must log in again)

---

## Incident Response

| Threat | Response |
|--------|----------|
| Magic link token intercepted | User requests a new link — old token is immediately invalidated |
| Session hijacked | Rotate `SECRET_KEY` env var and restart app — all sessions invalidated |
| Database file leaked | No plaintext passwords; notify users to change passwords elsewhere if reused |
| Brevo API key leaked | Rotate in Brevo dashboard, update `MAIL_API_KEY`, restart app |
| Admin account session hijacked | Change `ADMIN_EMAIL` env var + rotate `SECRET_KEY`, restart app |
