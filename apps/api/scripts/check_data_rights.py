"""Checks export and deletion against the real Supabase project, with a temporary account.

Usage, from apps/api: uv run --extra dev python -m scripts.check_data_rights

It creates a throwaway user, accepts the agreement, uploads a made-up resume, runs one analysis, registers
a push token, downloads the export, deletes the account through the API, and then counts what is left in
every table that holds personal data (store.USER_TABLES and store.DOCUMENT_TABLES) and in storage.
Everything should be 0. It prints counts and ids only, never keys or resume text, and deletes the user
even if a step fails. The analysis uses the configured AI model, so it takes a minute or two.
"""

import io
import json
import secrets
import sys
import time
import zipfile
from pathlib import Path

import docx
import httpx
from fastapi.testclient import TestClient

from app import consent, store
from app.config import settings
from app.main import app

RESUME = """Robin Example
Ottawa, ON | robin.example@example.com

EXPERIENCE
Registered Nurse, General Hospital of Exampleville - 2019 to present
- Cared for 6 patients per shift on a surgical unit; trained 4 new graduates.
- Led the unit's falls-prevention audit, cutting falls by 20% in a year.

EDUCATION
BScN, University of Exampleville, 2019

SKILLS
Patient assessment, wound care, medication administration, Epic charting, BLS, ACLS
"""


def main() -> int:
    if not settings.supabase_url or not settings.supabase_secret_key:
        print("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in apps/api/.env")
        return 1
    publishable = next(
        line.split("=", 1)[1].strip()
        for line in Path("../web/.env.local").read_text().splitlines()
        if line.startswith("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=")
    )
    admin = {
        "apikey": settings.supabase_secret_key,
        "Authorization": f"Bearer {settings.supabase_secret_key}",
    }
    http = httpx.Client(base_url=settings.supabase_url, timeout=60)
    client = TestClient(app, raise_server_exceptions=False)
    user_id = None
    failures = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name} {detail}")

    try:
        email = f"careerfit-check-{secrets.token_hex(6)}@example.com"
        password = secrets.token_urlsafe(24)
        created = http.post(
            "/auth/v1/admin/users",
            headers=admin,
            json={"email": email, "password": password, "email_confirm": True},
        )
        created.raise_for_status()
        user_id = created.json()["id"]
        token = http.post(
            "/auth/v1/token?grant_type=password",
            headers={"apikey": publishable},
            json={"email": email, "password": password},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        refused = client.post(
            "/documents",
            headers=headers,
            data={"type": "resume"},
            files={"file": ("cv.pdf", b"%PDF-1.7", "application/pdf")},
        )
        check(
            "uploads wait for the agreement",
            refused.status_code == 403,
            f"HTTP {refused.status_code}",
        )
        accepted = client.post(
            "/account/consent", headers=headers, json={"version": consent.current_version()}
        )
        check("agreement recorded", accepted.status_code == 204, f"HTTP {accepted.status_code}")

        document = docx.Document()
        for line in RESUME.strip().splitlines():
            document.add_paragraph(line)
        buffer = io.BytesIO()
        document.save(buffer)
        upload = client.post(
            "/documents",
            headers=headers,
            data={"type": "resume"},
            files={
                "file": (
                    "robin-example.docx",
                    buffer.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        check("upload", upload.status_code == 202, f"HTTP {upload.status_code}")
        document_id = upload.json()["id"]
        for _ in range(150):
            status = client.get(f"/documents/{document_id}/status", headers=headers).json()
            if status["extractionStatus"] in ("ready", "failed"):
                break
            time.sleep(2)
        check("resume read", status["extractionStatus"] == "ready", status["extractionStatus"])
        kept = client.patch(f"/documents/{document_id}", headers=headers, json={"keep": True})
        check("file kept past 90 days", kept.status_code == 200 and kept.json()["keep"] is True)

        started = client.post(
            "/analyses",
            headers=headers,
            json={"documentId": document_id, "role": "registered nurse", "region": "Ontario"},
        )
        if started.status_code == 202:
            analysis_id = started.json()["analysisId"]
            for _ in range(300):
                analysis = client.get(f"/analyses/{analysis_id}", headers=headers).json()
                if analysis["status"] in ("completed", "failed"):
                    break
                time.sleep(2)
            check("analysis", analysis["status"] == "completed", analysis["status"])
        else:
            check("analysis started", False, f"HTTP {started.status_code}")
        client.put(
            "/push-tokens",
            headers=headers,
            json={
                "token": "ExponentPushToken[check-data-rights]",
                "platform": "android",
                "language": "en",
            },
        )

        exported = client.get("/account/export", headers=headers)
        check("export", exported.status_code == 200, f"HTTP {exported.status_code}")
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            names = archive.namelist()
            data = json.loads(archive.read("data.json"))
        filled = sorted(table for table, rows in data["tables"].items() if rows)
        print(f"      export holds rows from: {', '.join(filled)}")
        check("export has the uploaded file", any(name.startswith("files/") for name in names))
        check(
            "export has the resume's text", bool(data["tables"]["documents"][0].get("parsed_text"))
        )

        before = {
            table: len(
                http.get(
                    f"/rest/v1/{table}",
                    headers=admin,
                    params={column: f"eq.{user_id}", "select": "*"},
                ).json()
            )
            for table, column in store.USER_TABLES.items()
        }
        print(f"      rows before deletion: {before}")

        deleted = client.delete("/account", headers=headers)
        check("account deleted", deleted.status_code == 204, f"HTTP {deleted.status_code}")

        for table, column in store.USER_TABLES.items():
            left = http.get(
                f"/rest/v1/{table}", headers=admin, params={column: f"eq.{user_id}", "select": "*"}
            ).json()
            check(f"nothing left in {table}", left == [], f"{len(left)} rows")
        for table, column in store.DOCUMENT_TABLES.items():
            left = http.get(
                f"/rest/v1/{table}",
                headers=admin,
                params={column: f"eq.{document_id}", "select": "*"},
            ).json()
            check(f"nothing left in {table}", left == [], f"{len(left)} rows")
        files = http.post(
            f"/storage/v1/object/list/{settings.storage_bucket}",
            headers=admin,
            json={"prefix": user_id, "limit": 100},
        ).json()
        check("nothing left in storage", files == [], f"{len(files)} files")
        gone = http.get(f"/auth/v1/admin/users/{user_id}", headers=admin)
        check("sign-in account gone", gone.status_code == 404, f"HTTP {gone.status_code}")
        if gone.status_code == 404:
            user_id = None
    finally:
        if user_id:
            http.delete(f"/auth/v1/admin/users/{user_id}", headers=admin)
            print("cleanup: removed the temporary user after a failure")
    print(f"failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
