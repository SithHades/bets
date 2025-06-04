# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BetFlow is a Flask-based betting platform where users can create, participate in, and resolve custom bets. The application uses SQLite database with Flask-SQLAlchemy ORM and features user authentication, session management, and a modern Bootstrap UI.

## Core Architecture

- **Single-file Flask application**: `app.py` contains all routes, models, and configuration
- **Database Models**: 
  - `User`: Authentication with bcrypt password hashing, tracks wins/losses
  - `Bet`: Bet creation with multiple outcomes, expiration dates, resolution status
  - `UserBet`: Junction table linking users to their bet choices with uniqueness constraint
- **Authentication Flow**: Access gate → Registration/Login → Protected routes
- **Access Control**: Two-tier system with `DEFAULT_SIGNUP_PASSWORD` for both site access and registration

## Development Commands

### Database Operations
```bash
# Initialize database (creates tables)
flask init-db

# Run the application
python app.py
# or
flask run
```

## Key Features

### Bet Details Pages
- Individual bet pages with shareable URLs at `/bet/<id>`
- Comprehensive statistics and participant breakdowns
- Direct betting and resolution from detail pages
- Homepage shows condensed bet cards linking to full details

### Docker Operations
```bash
# Build container
docker build -t betflow .

# Run container (requires DEFAULT_SIGNUP_PASSWORD env var)
docker run -p 5000:5000 -e DEFAULT_SIGNUP_PASSWORD=your_password betflow
```

## Key Implementation Details

- **Password Security**: Uses bcrypt for hashing with salt generation
- **Session Management**: Flask-Login with session-based access gate tracking
- **Database**: SQLite with automatic initialization via entrypoint script in Docker
- **UI Framework**: Bootstrap 5.3.2 with custom CSS variables and Inter font
- **Template Structure**: Jinja2 templates with base template containing complete styling

## Environment Variables

- `SECRET_KEY`: Flask session encryption (has fallback for development)
- `DEFAULT_SIGNUP_PASSWORD`: Required for both site access and user registration
- `FLASK_APP`: Set to `app.py` in Docker environment

## Database Schema Notes

- Users can only place one bet per betting item (enforced by unique constraint)
- Bet outcomes stored as comma-separated strings, parsed via `get_outcomes_list()`
- Win/loss tracking updated automatically when bets are resolved
- Only bet creators can resolve their own bets