import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine.core import run_generator
from engine.parser import parse_timetable


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "auth.db")))
FRONTEND_DIR = BASE_DIR / "frontend"
SESSION_DAYS = 7
GOOGLE_CLIENT_ID = (
    os.getenv("GOOGLE_CLIENT_ID", "").strip()
    or "366323767441-fs8sijg4tnsgr6kj7mgatdmj4rorprsp.apps.googleusercontent.com"
)


app = FastAPI(
    title="Timetable Generator API",
    description="Backend API for parsing course data and generating ranked timetable options.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw timetable text copied from the source.")
    selected_courses: List[str] = Field(default_factory=list, description="Course names selected by the user.")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Constraint preferences used for ranking.")
    top_n: int = Field(default=3, ge=1, le=20, description="Number of timetable options to return.")
    return_debug: bool = Field(default=False, description="Include parser warnings and scheduler statistics.")


class CoursesRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw timetable text copied from the source.")


class ParseRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw timetable text copied from the source.")
    include_warnings: bool = Field(default=True, description="Include parser warnings in the response.")


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=5, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=1)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                google_sub TEXT UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        connection.commit()


init_db()


def unique_courses(parsed_sections: List[Dict[str, Any]]) -> List[str]:
    return sorted({section.get("course", "").strip() for section in parsed_sections if section.get("course")})


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return email


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 150000)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(derived).decode()}"


def verify_password(password: str, stored_value: str) -> bool:
    try:
        salt_encoded, hash_encoded = stored_value.split("$", 1)
        salt = base64.b64decode(salt_encoded.encode())
        expected_hash = base64.b64decode(hash_encoded.encode())
    except (ValueError, TypeError):
        return False

    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 150000)
    return hmac.compare_digest(derived, expected_hash)


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    created_at = now_utc()
    expires_at = created_at + timedelta(days=SESSION_DAYS)

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sessions (token, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_id, expires_at.isoformat(), created_at.isoformat()),
        )
        connection.commit()

    return token


def delete_session(token: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        connection.commit()


def serialize_user(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "has_password": bool(row["password_hash"]),
        "has_google": bool(row["google_sub"]),
    }


def get_bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = get_bearer_token(authorization)

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()
        session = connection.execute(
            "SELECT expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()

    if not row or not session:
        raise HTTPException(status_code=401, detail="Invalid session.")

    if datetime.fromisoformat(session["expires_at"]) <= now_utc():
        delete_session(token)
        raise HTTPException(status_code=401, detail="Session expired.")

    return serialize_user(row)


def create_auth_response(user_row: sqlite3.Row) -> Dict[str, Any]:
    token = create_session(user_row["id"])
    return {
        "token": token,
        "user": serialize_user(user_row),
    }


def verify_google_credential(credential: str) -> Dict[str, Any]:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google sign-in is not configured on the server.")

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="Google sign-in dependencies are incomplete on the server. Install google-auth and requests.",
        ) from exc

    try:
        payload = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Google credential.") from exc

    if payload.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=400, detail="Invalid Google issuer.")

    if not payload.get("email"):
        raise HTTPException(status_code=400, detail="Google account email is unavailable.")

    return payload


@app.get("/api")
def home() -> Dict[str, str]:
    return {"message": "Timetable Generator API is running"}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/config")
def auth_config() -> Dict[str, Any]:
    return {
        "google_client_id": GOOGLE_CLIENT_ID or None,
    }


@app.post("/auth/signup")
def signup(data: SignupRequest) -> Dict[str, Any]:
    email = normalize_email(data.email)

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists.")

        connection.execute(
            """
            INSERT INTO users (name, email, password_hash, google_sub, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                data.name.strip(),
                email,
                hash_password(data.password),
                None,
                now_utc().isoformat(),
            ),
        )
        connection.commit()

        user_row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    return create_auth_response(user_row)


@app.post("/auth/login")
def login(data: LoginRequest) -> Dict[str, Any]:
    email = normalize_email(data.email)

    with get_connection() as connection:
        user_row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if not user_row or not user_row["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(data.password, user_row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return create_auth_response(user_row)


@app.post("/auth/google")
def google_auth(data: GoogleAuthRequest) -> Dict[str, Any]:
    payload = verify_google_credential(data.credential)
    email = payload["email"].lower()
    name = payload.get("name") or email.split("@")[0]
    google_sub = payload.get("sub")

    with get_connection() as connection:
        user_row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if user_row:
            if not user_row["google_sub"]:
                connection.execute(
                    "UPDATE users SET google_sub = ? WHERE id = ?",
                    (google_sub, user_row["id"]),
                )
                connection.commit()
                user_row = connection.execute("SELECT * FROM users WHERE id = ?", (user_row["id"],)).fetchone()
        else:
            connection.execute(
                """
                INSERT INTO users (name, email, password_hash, google_sub, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name.strip(), email, None, google_sub, now_utc().isoformat()),
            )
            connection.commit()
            user_row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    return create_auth_response(user_row)


@app.get("/auth/me")
def auth_me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"user": user}


@app.post("/auth/logout")
def logout(authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    token = get_bearer_token(authorization)
    delete_session(token)
    return {"message": "Logged out successfully."}


@app.post("/courses")
def get_courses(
    data: CoursesRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        parsed_sections, warnings = parse_timetable(data.text, return_warnings=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to parse timetable text.") from exc

    return {
        "courses": unique_courses(parsed_sections),
        "section_count": len(parsed_sections),
        "warnings": warnings,
    }


@app.post("/parse")
def parse_input(
    data: ParseRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        parsed_sections, warnings = parse_timetable(data.text, return_warnings=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to parse timetable text.") from exc

    response = {
        "courses": unique_courses(parsed_sections),
        "sections": parsed_sections,
        "section_count": len(parsed_sections),
    }

    if data.include_warnings:
        response["warnings"] = warnings

    return response


@app.post("/generate")
def generate(
    data: GenerateRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not data.selected_courses:
        raise HTTPException(status_code=400, detail="At least one course must be selected.")

    try:
        result = run_generator(
            text=data.text,
            selected_courses=data.selected_courses,
            constraints=data.constraints,
            top_n=data.top_n,
            return_debug=data.return_debug,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to generate timetable options.") from exc

    if data.return_debug:
        return {
            "options": result.get("results", []),
            "warnings": result.get("warnings", []),
            "missing_courses": result.get("missing_courses", []),
            "scheduler_stats": result.get("scheduler_stats", {}),
        }

    return {"options": result}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
