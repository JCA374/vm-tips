# World Cup Family Competition - Requirements

## Project Overview

A web application for family members to bet on World Cup groop staga and knockout round outcomes. Users submit predictions for each round, view a leaderboard, and see what others predicted after each deadline.

## Core Requirements

- Users predict exact scores (home goals and away goals) for knockout round matches: Round of 16, Quarter-finals, Semi-finals, and Final
- Users can update their predictions before each round's deadline
- Automatically fetch upcoming matches and results from official/reliable source
- Award points for: correct outcome (win/loss/tie), correct home goals, correct away goals
- Show a leaderboard ranking all participants by total points
- Reveal other users' predictions only after the round deadline has passed

## User Interface Requirements

### Public Pages
- **Registration**: Join with email address
- **Login**: Access via magic link sent to email
- **Betting Form**: Enter predicted score (home goals and away goals) for each match in current round
- **Leaderboard**: View current standings with total points and breakdown per round
- **Other Bets**: View what others predicted (only after deadline)
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
