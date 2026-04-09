# World Cup Family Competition - Requirements

## Project Overview

A web application for family members to bet on World Cup groop staga and knockout round outcomes. Users submit predictions for each round, view a leaderboard, and see what others predicted after each deadline.

## Core Requirements

- Two betting modes depending on the round:
  - **1X2** (Group stage MD1–MD3, Round of 32, Round of 16): Users pick the outcome — 1 (home win), X (draw), or 2 (away win). 3 points for a correct pick, 0 for wrong.
  - **Exact score** (Quarter-finals, Semi-finals, Final): Users predict the exact home and away goals. Points: 3 for correct outcome + 2 for correct home goals + 2 for correct away goals (max 7 per match).
- Users can update their predictions before each round's deadline
- Automatically fetch upcoming matches and results from official/reliable source
- Show a leaderboard ranking all participants by total points
- Reveal other users' predictions only after the round deadline has passed

## User Interface Requirements

### Public Pages
- **Registration**: Join with email address
- **Login**: Access via magic link sent to email
- **Betting Form**: For group stage and early knockout rounds, pick 1/X/2 per match. For Quarter-finals, Semi-finals and Final, enter exact predicted score.
- **Leaderboard**: View current standings with total points and breakdown per round
- **Results Page**: View what others predicted (only after deadline), with two display modes:
  - **Per Game** (default): All matches listed as collapsible cards. Click a match to see every player's prediction and points. Text filter to narrow by team name.
  - **Per User**: Searchable player list; select a player to see all their predictions, the actual results, and points per match. Players sorted by total points.
- **Deadline Timer**: Clear display of when current round closes

### Admin Pages
- **Admin Login**: Secure access at /admin
- **User Management**: View registered users
- **Deadline Management**: Set/update round deadlines
- **System Status**: View data sync status with match source

## Technical Requirements

- **Deployment**: Simple deployment, accessible via internet
- **Authentication**: Email-based magic link login (no passwords)
- **Data Storage**: Persist user predictions, match results, and scores
- **Match Data API**: Integration with official/reliable football data source for fixtures and results
- **Admin Access**: Protected admin interface at /admin route
- **Responsive**: Works on mobile and desktop browsers

## Architecture Requirements

- **Modular Structure**: Code organized into separate, independent modules
- **Clear Separation**:
  - Authentication module (login, magic links)
  - Match data module (API integration, data sync)
  - Prediction module (user bets, scoring logic)
  - User interface components (forms, leaderboard, views)
  - Database/storage layer
  - Admin functionality
- **Independent Updates**: Each module can be modified without breaking others
- **Clear Interfaces**: Well-defined functions/APIs between modules

## Future Enhancements

- AI sports journalist: Generate funny summaries of betting patterns each round
- AI sports journalist: Write entertaining commentary about the family competition
