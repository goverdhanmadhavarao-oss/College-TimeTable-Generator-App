# College Timetable Generator

Smart timetable generator for college students that creates personalized class schedules based on course selection, faculty preferences, day-off goals, and avoided time slots.

## Project Description

This project is a full-stack web application built to simplify the process of creating an optimized college timetable. Instead of manually comparing sections, checking faculty options, and avoiding clashes by hand, the system automatically parses timetable data, evaluates valid combinations, and ranks the best possible schedules based on user preferences.

The application is designed to help students make smarter timetable choices by allowing them to:

- select the courses they want to include
- choose preferred faculty for specific subjects
- avoid certain days or time slots
- prioritize what matters most, such as faculty, compactness, or free days

The backend handles timetable parsing, clash-free scheduling, and scoring, while the frontend provides a guided multi-step experience for selecting constraints and reviewing generated options in a clean visual timetable view.

## Live App

- Production: https://web-production-eb6c2.up.railway.app

## Features

- Smart timetable generation
  Generates clash-free timetable combinations automatically from uploaded timetable data.

- Preference-based ranking
  Scores and ranks timetable options based on faculty choices, days off, avoided slots, and compactness.

- Multi-step guided workflow
  Walks users through timetable input, course selection, preference setup, and final result review.

- Course selection tools
  Supports course search, bulk selection, and a structured course selection flow.

- Faculty preference selection
  Lets users choose preferred faculty members for individual courses.

- Free-day and slot avoidance
  Allows users to avoid specific days and fixed 2-hour time windows.

- Visual timetable results
  Displays ranked timetable options in a clean day-and-slot layout for easier comparison.

- Authentication system
  Includes email/password login and Google sign-in support.

- Production deployment
  Hosted on Railway with environment-based configuration and persistent database storage.

## Tech Stack

- FastAPI
- Python
- Vanilla HTML, CSS, JavaScript
- SQLite
- Railway

## Project Structure

```text
engine/
  core.py
  parser.py
  scheduler.py
  scorer.py
  utils.py
frontend/
  index.html
  script.js
  style.css
main.py
requirements.txt
Procfile
```

## Local Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open:

- http://127.0.0.1:8000/

## Environment Variables

Create these variables for production:

```text
GOOGLE_CLIENT_ID=your_google_client_id
DATABASE_PATH=/app/data/auth.db
```

## Railway Deployment

This app is deployed as a single FastAPI service with the frontend served by the backend.

### Required Railway setup

1. Deploy from the GitHub repository.
2. Set the start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

3. Add environment variables:

```text
GOOGLE_CLIENT_ID=your_google_client_id
DATABASE_PATH=/app/data/auth.db
```

4. Attach a persistent volume at:

```text
/app/data
```

## Google Sign-In Setup

In Google Cloud Console:

1. Create a Web OAuth client.
2. Add the production origin:

```text
https://web-production-eb6c2.up.railway.app
```

3. Add your local origin for development:

```text
http://127.0.0.1:8000
http://localhost:8000
```

## Notes

- `auth.db` is ignored from Git and should be persisted through the Railway volume in production.
- The frontend uses same-origin API calls, so local and production environments both work with the same client code.
