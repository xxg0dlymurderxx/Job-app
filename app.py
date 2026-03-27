from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR))).resolve()
DB_PATH = Path(os.environ.get("DB_PATH", str(DATA_DIR / "hirepatch.db"))).resolve()


def load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if value[:1] == value[-1:] and value[:1] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


load_dotenv(BASE_DIR / ".env")

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "").strip()
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "").strip()

SEED_LISTINGS = [
    {
        "id": str(uuid4()),
        "title": "Need a deep apartment clean before move-out",
        "pay": 180,
        "category": "Cleaning",
        "location": "Jersey City, NJ",
        "deadline": "2026-03-30",
        "description": (
            "Studio apartment needs floors, bathroom, and kitchen cleaned "
            "for a move-out inspection."
        ),
        "contact": "Maya",
        "email": "maya@example.com",
        "phone": "(201) 555-0148",
        "status": "Urgent",
        "posted_at": 1_775_304_000_000,
        "closed_at": None,
    },
    {
        "id": str(uuid4()),
        "title": "Move a couch and two bookshelves upstairs",
        "pay": 120,
        "category": "Moving",
        "location": "Harlem, NY",
        "deadline": "2026-04-01",
        "description": (
            "Two-person job. Need help carrying furniture from street level "
            "to a third-floor walk-up."
        ),
        "contact": "Andre",
        "email": "andre@example.com",
        "phone": "(646) 555-0117",
        "status": "Open",
        "posted_at": 1_775_214_000_000,
        "closed_at": None,
    },
    {
        "id": str(uuid4()),
        "title": "Refresh logo for neighborhood bakery flyer",
        "pay": 90,
        "category": "Design",
        "location": "Remote",
        "deadline": "2026-04-04",
        "description": (
            "Looking for a quick but polished logo update for menus, posters, "
            "and social graphics."
        ),
        "contact": "Lena",
        "email": "lena@example.com",
        "phone": "(212) 555-0183",
        "status": "Flexible",
        "posted_at": 1_775_124_000_000,
        "closed_at": None,
    },
    {
        "id": str(uuid4()),
        "title": "Assemble patio chairs for cafe reopening",
        "pay": 140,
        "category": "Home services",
        "location": "Astoria, NY",
        "deadline": "2026-03-25",
        "description": (
            "Six outdoor chairs needed assembly and placement before a spring patio launch."
        ),
        "contact": "Niko",
        "email": "niko@example.com",
        "phone": "(718) 555-0129",
        "status": "Open",
        "posted_at": 1_775_034_000_000,
        "closed_at": 1_775_106_000_000,
    },
]

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/script.js": ("script.js", "application/javascript; charset=utf-8"),
}


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def serialize_listing(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "pay": row["pay"],
        "pay_type": row["pay_type"] if row["pay_type"] else "fixed",
        "category": row["category"],
        "location": row["location"],
        "deadline": row["deadline"],
        "description": row["description"],
        "contact": row["contact"],
        "email": row["email"],
        "phone": row["phone"],
        "status": row["status"],
        "posted_at": row["posted_at"],
        "closed_at": row["closed_at"],
    }


def init_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                pay INTEGER NOT NULL,
                pay_type TEXT NOT NULL DEFAULT 'fixed',
                category TEXT NOT NULL,
                location TEXT NOT NULL,
                deadline TEXT NOT NULL,
                description TEXT NOT NULL,
                contact TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                status TEXT NOT NULL,
                posted_at INTEGER NOT NULL,
                closed_at INTEGER,
                owner_token TEXT
            )
            """
        )

        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(listings)").fetchall()
        }
        if "closed_at" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN closed_at INTEGER")
        if "owner_token" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN owner_token TEXT")
        if "pay_type" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN pay_type TEXT NOT NULL DEFAULT 'fixed'")
        if "email" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN email TEXT")
        if "phone" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN phone TEXT")

        existing = connection.execute("SELECT COUNT(*) AS count FROM listings").fetchone()
        if existing["count"] == 0:
            connection.executemany(
                """
                INSERT INTO listings (
                    id, title, pay, pay_type, category, location, deadline,
                    description, contact, email, phone, status, posted_at, closed_at, owner_token
                ) VALUES (
                    :id, :title, :pay, :pay_type, :category, :location, :deadline,
                    :description, :contact, :email, :phone, :status, :posted_at, :closed_at, :owner_token
                )
                """,
                [
                    {**listing, "pay_type": "fixed", "owner_token": None}
                    for listing in SEED_LISTINGS
                ],
            )


def fetch_listings() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id, title, pay, pay_type, category, location,
                deadline, description, contact, email, phone, status, posted_at, closed_at
            FROM listings
            ORDER BY posted_at DESC
            """
        ).fetchall()

    return [serialize_listing(row) for row in rows]


def create_listing(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    owner_token = secrets.token_urlsafe(24)
    listing = {
        "id": str(uuid4()),
        "title": read_text(payload, "title", 80),
        "pay": read_pay(payload),
        "pay_type": read_pay_type(payload),
        "category": read_text(payload, "category", 40),
        "location": read_text(payload, "location", 60),
        "deadline": read_deadline(payload),
        "description": read_text(payload, "description", 280),
        "contact": read_text(payload, "contact", 40),
        "email": read_email(payload),
        "phone": read_phone(payload),
        "status": read_text(payload, "status", 20),
        "posted_at": int(datetime.now().timestamp() * 1000),
        "closed_at": None,
        "owner_token": owner_token,
    }

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO listings (
                id, title, pay, pay_type, category, location,
                deadline, description, contact, email, phone, status, posted_at, closed_at, owner_token
            ) VALUES (
                :id, :title, :pay, :pay_type, :category, :location,
                :deadline, :description, :contact, :email, :phone, :status, :posted_at, :closed_at, :owner_token
            )
            """,
            listing,
        )

    return serialize_listing(listing), owner_token


def close_listing(listing_id: str, owner_token: str) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id, title, pay, pay_type, category, location, deadline,
                description, contact, email, phone, status, posted_at, closed_at, owner_token
            FROM listings
            WHERE id = ?
            """,
            (listing_id,),
        ).fetchone()

        if row is None:
            raise LookupError("Listing not found.")

        if not row["owner_token"] or row["owner_token"] != owner_token:
            raise PermissionError("Only the person who published this listing can close it.")

        if row["closed_at"] is None:
            closed_at = int(datetime.now().timestamp() * 1000)
            connection.execute(
                "UPDATE listings SET closed_at = ? WHERE id = ?",
                (closed_at, listing_id),
            )
            row = connection.execute(
                """
                SELECT
                    id, title, pay, pay_type, category, location, deadline,
                    description, contact, email, phone, status, posted_at, closed_at, owner_token
                FROM listings
                WHERE id = ?
                """,
                (listing_id,),
            ).fetchone()

    return serialize_listing(row)


def fetch_listing_by_id(listing_id: str) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id, title, pay, pay_type, category, location, deadline,
                description, contact, email, phone, status, posted_at, closed_at
            FROM listings
            WHERE id = ?
            """,
            (listing_id,),
        ).fetchone()

    if row is None:
        raise LookupError("Listing not found.")
    return serialize_listing(row)


def healthcheck() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "HirePatch",
    }


def read_text(payload: dict[str, Any], key: str, max_length: int) -> str:
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text.")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{key} is required.")
    if len(cleaned) > max_length:
        raise ValueError(f"{key} must be {max_length} characters or fewer.")
    return cleaned


def read_pay(payload: dict[str, Any]) -> int:
    value = payload.get("pay")

    try:
        pay = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("pay must be a whole number.") from error

    if pay < 1:
        raise ValueError("pay must be at least 1.")
    return pay


def read_pay_type(payload: dict[str, Any]) -> str:
    value = read_text(payload, "pay_type", 20).lower()
    if value not in {"fixed", "hourly"}:
        raise ValueError("pay_type must be fixed or hourly.")
    return value


def read_deadline(payload: dict[str, Any]) -> str:
    value = payload.get("deadline", "")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("deadline is required.")

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("deadline must use YYYY-MM-DD format.") from error

    return parsed.strftime("%Y-%m-%d")


def read_email(payload: dict[str, Any]) -> str:
    value = read_text(payload, "email", 120)
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("email must be valid.")
    return value


def read_phone(payload: dict[str, Any]) -> str:
    value = read_text(payload, "phone", 25)
    digit_count = sum(character.isdigit() for character in value)
    if digit_count < 7:
        raise ValueError("phone must be valid.")
    return value


def read_listing_id(payload: dict[str, Any]) -> str:
    return read_text(payload, "listing_id", 80)


def normalize_phone_for_sms(value: str) -> str:
    cleaned = "".join(character for character in value if character.isdigit() or character == "+")
    if not cleaned:
        raise ValueError("Listing phone number is missing.")
    return cleaned


def require_message_delivery_config() -> None:
    missing = []
    if not TWILIO_ACCOUNT_SID:
        missing.append("TWILIO_ACCOUNT_SID")
    if not TWILIO_AUTH_TOKEN:
        missing.append("TWILIO_AUTH_TOKEN")
    if not TWILIO_FROM_NUMBER:
        missing.append("TWILIO_FROM_NUMBER")
    if not RESEND_API_KEY:
        missing.append("RESEND_API_KEY")
    if not RESEND_FROM_EMAIL:
        missing.append("RESEND_FROM_EMAIL")

    if missing:
        raise RuntimeError(
            "Messaging is not configured. Set: " + ", ".join(missing)
        )


def send_sms_via_twilio(to_phone: str, body: str) -> None:
    form_body = urllib.parse.urlencode(
        {
            "To": to_phone,
            "From": TWILIO_FROM_NUMBER,
            "Body": body,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
        data=form_body,
        headers={
            "Authorization": "Basic "
            + base64.b64encode(
                f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode("utf-8")
            ).decode("ascii"),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 400:
                raise RuntimeError("Twilio rejected the SMS request.")
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Twilio SMS failed: {details or error.reason}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Twilio SMS failed: {error.reason}") from error


def send_email_via_resend(to_email: str, subject: str, body: str, reply_to: str) -> None:
    request_body = json.dumps(
        {
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "text": body,
            "reply_to": [reply_to],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=request_body,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "HirePatch/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 400:
                raise RuntimeError("Resend rejected the email request.")
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Email send failed: {details or error.reason}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Email send failed: {error.reason}") from error


def send_listing_message(payload: dict[str, Any]) -> dict[str, Any]:
    require_message_delivery_config()

    listing = fetch_listing_by_id(read_listing_id(payload))
    sender_name = read_text(payload, "sender_name", 60)
    sender_contact = read_text(payload, "sender_contact", 120)
    sender_reply_email = read_email({"email": payload.get("sender_email")})
    message = read_text(payload, "message", 500)

    subject = f"HirePatch response for {listing['title']}"
    composed_body = "\n".join(
        [
            f"Hi {listing['contact']},",
            "",
            f"{sender_name} is responding to your HirePatch listing.",
            f"Reply contact: {sender_contact}",
            f"Reply email: {sender_reply_email}",
            "",
            message,
            "",
            f"Listing: {listing['title']}",
            f"Location: {listing['location']}",
            f"Needed by: {listing['deadline']}",
        ]
    )

    send_email_via_resend(listing["email"], subject, composed_body, sender_reply_email)
    send_sms_via_twilio(normalize_phone_for_sms(listing["phone"]), composed_body)

    return {"ok": True}


class HirePatchHandler(BaseHTTPRequestHandler):
    server_version = "HirePatch/1.0"

    def do_GET(self) -> None:
        if self.path == "/health":
            self.respond_json(healthcheck())
            return

        if self.path == "/api/listings":
            self.respond_json(fetch_listings())
            return

        self.serve_static()

    def do_HEAD(self) -> None:
        if self.path == "/health":
            self.respond_json(healthcheck(), include_body=False)
            return

        if self.path == "/api/listings":
            self.respond_json(fetch_listings(), include_body=False)
            return

        self.serve_static(include_body=False)

    def do_POST(self) -> None:
        close_target = self.get_close_target()
        if close_target is not None:
            try:
                listing = close_listing(close_target, self.read_owner_token())
            except LookupError as error:
                self.respond_json({"error": str(error)}, status=HTTPStatus.NOT_FOUND)
                return
            except PermissionError as error:
                self.respond_json({"error": str(error)}, status=HTTPStatus.FORBIDDEN)
                return

            self.respond_json(listing)
            return

        if self.path == "/api/messages":
            try:
                payload = self.read_json_body()
                result = send_listing_message(payload)
            except LookupError as error:
                self.respond_json({"error": str(error)}, status=HTTPStatus.NOT_FOUND)
                return
            except ValueError as error:
                self.respond_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                return
            except RuntimeError as error:
                self.respond_json({"error": str(error)}, status=HTTPStatus.BAD_GATEWAY)
                return

            self.respond_json(result, status=HTTPStatus.CREATED)
            return

        if self.path != "/api/listings":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            payload = self.read_json_body()
            listing, owner_token = create_listing(payload)
        except ValueError as error:
            self.respond_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return

        self.respond_json(
            {"listing": listing, "owner_token": owner_token},
            status=HTTPStatus.CREATED,
        )

    def serve_static(self, include_body: bool = True) -> None:
        static_file = STATIC_FILES.get(self.path)
        if static_file is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        filename, content_type = static_file
        content = (BASE_DIR / filename).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()

        if include_body:
            self.wfile.write(content)

    def read_json_body(self) -> dict[str, Any]:
        length_header = self.headers.get("Content-Length", "0")

        try:
            content_length = int(length_header)
        except ValueError as error:
            raise ValueError("Invalid request body.") from error

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Request body must be valid JSON.") from error

        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def respond_json(
        self,
        payload: Any,
        status: HTTPStatus = HTTPStatus.OK,
        include_body: bool = True,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        if include_body:
            self.wfile.write(body)

    def get_close_target(self) -> str | None:
        prefix = "/api/listings/"
        suffix = "/close"

        if not self.path.startswith(prefix) or not self.path.endswith(suffix):
            return None

        listing_id = self.path[len(prefix) : -len(suffix)]
        if not listing_id or "/" in listing_id:
            return None

        return listing_id

    def read_owner_token(self) -> str:
        token = self.headers.get("X-Owner-Token", "").strip()
        if not token:
            raise PermissionError("Only the person who published this listing can close it.")
        return token


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_database()
    server = ThreadingHTTPServer((HOST, PORT), HirePatchHandler)
    print(f"HirePatch running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
