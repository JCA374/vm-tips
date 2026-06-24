# How to run the Playwright tests

## First time setup

```bash
cd playwright
cp .env.example .env
```

Open `.env` and fill in:
```
TEST_EMAIL=your-email@storahultsvm.se
TEST_PASSWORD=your-password
ADMIN_EMAIL=your-admin-email@storahultsvm.se
ADMIN_PASSWORD=your-admin-password
```

Your account needs a password — set one at https://storahultsvm.se/auth/set-password

---

## Run the tests

**Against local dev server** (start `python app.py` first):
```bash
npm test
```

**Against production:**
```bash
npm run test:prod
```

**With visual UI** (see tests run in real time):
```bash
npm run test:ui
```

**Open the last test report:**
```bash
npm run report
```

---

## What gets tested

| File | What it covers |
|---|---|
| auth.spec.ts | Login tabs, wrong password, logout, redirect if not logged in |
| predictions.spec.ts | Predict page loads, saving bets, missing match warnings |
| leaderboard.spec.ts | Table shows, has correct columns |
| results.spec.ts | Page loads, locked behind login |
| admin.spec.ts | Regular user blocked, admin can reach all backstage pages |
| navigation.spec.ts | Header, nav links, ocean theme colour |
