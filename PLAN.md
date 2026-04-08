# VM Tips - Project Plan

## What's already built

The full backend is implemented and tested locally:
- Magic link auth (register, login, logout, verify)
- Match sync from football-data.org API
- Predictions (submit, update, deadline enforcement)
- Scoring (outcome 3pts, home goals 2pts, away goals 2pts)
- Leaderboard (total and per-round)
- Admin panel (users, deadlines, match sync, score calculation)
- All templates (base layout, auth, predictions, admin)

---

## Phase 1 — Get it running (local)

Goal: full working app on your machine before anyone else uses it.

**Step 1: Fix config**
- Set a real SECRET_KEY in .env
- Verify FOOTBALL_API_KEY works (done)
- Verify Brevo SMTP works (untested — test by registering a user)

**Step 2: First admin user**
- Register at /register with your email
- Promote via sqlite: `UPDATE users SET is_admin = 1 WHERE email = '...'`

**Step 3: Load match data**
- Admin > Status > Sync Matches
- Confirm matches appear at /predict

**Step 4: Set deadlines**
- Admin > Deadlines
- Set deadline for each round before the first match of that round kicks off
- Deadlines control when predictions lock and when others' predictions become visible

**Step 5: Smoke test**
- Register a second test user (use another email)
- Submit predictions for upcoming matches
- Check /leaderboard shows both users
- After a round deadline passes, check /results shows everyone's predictions

---

## Phase 2 — Deploy

Goal: live on the internet so family can use it.

**Option A: Hetzner VPS (~€4/mo) — recommended**
- Create smallest VPS (CX11), Ubuntu 22.04
- SSH in, clone repo, copy .env
- Run with Docker: `docker-compose up -d`
- Point a domain or use the raw IP

**Option B: Railway (free tier)**
- Connect GitHub repo
- Set env vars in Railway dashboard
- Deploy — Railway handles the rest

**Either way:**
- Change APP_URL in .env to the real URL (magic links need this to be correct)
- Verify /health endpoint returns ok
- Test magic link email end-to-end from the live URL

---

## Phase 3 — Run the competition

**Before each round:**
1. Admin > Status > Sync Matches (fetch fixture list)
2. Admin > Deadlines > confirm deadline is set correctly
3. Share the URL with family — they register and predict

**After each round finishes:**
1. Admin > Status > Sync Matches (fetches results)
2. Admin > Status > Calculate Scores
3. Leaderboard updates automatically

**Ongoing:**
- Back up `database/vm_tips.db` regularly (just copy the file)
- SQLite handles up to ~20 users fine — no need for Postgres

---

## Known gaps / future improvements

- No profile page — users can't change their display name after registration
- No per-round deadline reminder email
- No automatic score calculation (currently manual trigger in admin)
- Index page (/) just renders a blank template — could redirect to /leaderboard
