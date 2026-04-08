# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

World Cup Family Competition betting application. Users predict exact scores for knockout round matches, earn points for correct predictions, and compete on a leaderboard.

## Architecture

This codebase follows a **modular architecture** where components are separated into independent modules that can be updated without breaking each other. See REQUIREMENTS.md for full details.

### Key Modules

1. **Authentication** - Email-based magic link login (no passwords)
2. **Match Data** - API integration to fetch fixtures and results from official football data source
3. **Prediction** - User score predictions and points calculation logic
4. **User Interface** - Forms, leaderboard, and views (public and admin at /admin)
5. **Database/Storage** - Persistence layer for users, predictions, matches, and scores
6. **Admin** - User management, deadline management, system status

### Scoring System

Points awarded for each prediction:
- Correct outcome (win/loss/tie)
- Correct home team goals
- Correct away team goals

### Critical Rules

- Users can only update predictions before round deadline
- Other users' predictions only visible after deadline passes
- Matches and results fetched automatically from external API (not manual admin input)
- All modules must have clear interfaces to allow independent updates

## Development Approach

When building or modifying:
1. Keep modules independent with well-defined interfaces
2. Changes to one module should not require changes to others
3. Use REQUIREMENTS.md as the single source of truth for features
