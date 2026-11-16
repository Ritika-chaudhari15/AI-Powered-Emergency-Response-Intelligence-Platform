"""Run a live, multilingual smoke test against the Disaster Response API.

Start the API in another terminal before running this script:
    cd backend
    uvicorn app.main:app --reload

Then run:
    python scripts/test_multilingual_api_workflow.py

The script is deliberately a live test: it uses the configured database and
creates one uniquely named test user, volunteer, team, knowledge entry, and
(when external data/model dependencies are available) disaster report.  It
never deletes records or changes existing ones.  A JSON report is written to
backend/test-results/ and the terminal prints a concise summary.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_LANGUAGES = ("en", "hi", "ta", "te", "ml", "kn")
ALL_LANGUAGES = (
    "en", "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai",
    "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
)
ROOT = Path(__file__).resolve().parents[1]


class Workflow:
    def __init__(self, base_url: str, languages: tuple[str, ...], output: Path, request_timeout: int):
        self.base_url = base_url.rstrip("/")
        self.languages = languages
        self.output = output
        self.request_timeout = request_timeout
        self.results: list[dict[str, Any]] = []
        self.token = ""
        self.run_id = uuid.uuid4().hex[:10]

    @staticmethod
    def report_input(body: dict[str, Any] | None) -> dict[str, Any] | None:
        """Keep the evidence file useful without writing passwords or tokens to disk."""
        if body is None:
            return None
        return {key: ("[redacted]" if key.lower() in {"password", "token"} else value) for key, value in body.items()}

    def request(
        self,
        name: str,
        method: str,
        path: str,
        *,
        language: str = "en",
        body: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
        authenticated: bool = False,
    ) -> dict[str, Any] | None:
        headers = {"Accept-Language": f"{language}-IN", "Accept": "application/json"}
        data = None
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        print(f"  Running [{language}] {method} {path} ...", flush=True)
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self.request_timeout) as response:
                status = response.status
                response_headers = dict(response.headers.items())
                raw_body = response.read().decode("utf-8")
        except HTTPError as error:
            status = error.code
            response_headers = dict(error.headers.items())
            raw_body = error.read().decode("utf-8")
        except URLError as error:
            self.results.append({"name": name, "method": method, "path": path, "language": language,
                                 "request_input": self.report_input(body), "status": None, "outcome": "FAIL",
                                 "reason": f"Cannot reach API: {error.reason}"})
            self.save_checkpoint()
            return None
        except TimeoutError:
            self.results.append({"name": name, "method": method, "path": path, "language": language,
                                 "request_input": self.report_input(body), "status": None, "outcome": "FAIL",
                                 "reason": f"Request timed out after {self.request_timeout} seconds"})
            self.save_checkpoint()
            return None

        try:
            payload: Any = json.loads(raw_body) if raw_body else None
        except json.JSONDecodeError:
            payload = raw_body
        # HTTP header names are case-insensitive.  Some ASGI servers serialize this
        # header as ``content-language`` rather than ``Content-Language``.
        content_language = next(
            (value for key, value in response_headers.items() if key.lower() == "content-language"), ""
        )
        outcome = "PASS" if status in expected else "FAIL"
        record = {
            "name": name, "method": method, "path": path, "language": language, "status": status,
            "expected_status": list(expected), "content_language": content_language, "outcome": outcome,
            "request_input": self.report_input(body), "elapsed_ms": round((time.perf_counter() - started) * 1000), "response": payload,
        }
        self.results.append(record)
        self.save_checkpoint()
        print(f"    -> {status} ({record['elapsed_ms']} ms)", flush=True)
        return payload if outcome == "PASS" else None

    def _report_data(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(), "base_url": self.base_url,
            "languages_tested": self.languages, "summary": {
                "passed": sum(item["outcome"] == "PASS" for item in self.results),
                "failed": sum(item["outcome"] == "FAIL" for item in self.results),
            }, "results": self.results,
        }

    def save_checkpoint(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        report = self._report_data()
        self.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_report(self) -> None:
        self.save_checkpoint()
        report = self._report_data()
        print("\nMultilingual API workflow summary")
        print(f"  PASS: {report['summary']['passed']}   FAIL: {report['summary']['failed']}")
        print(f"  Report: {self.output}")
        for item in self.results:
            marker = "✓" if item["outcome"] == "PASS" else "✗"
            print(f"  {marker} [{item['language']}] {item['method']} {item['path']} -> {item['status']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Test live API language support and workflow coverage.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API URL (default: %(default)s)")
    parser.add_argument("--all-languages", action="store_true", help="Test all 23 supported locales (can be slow on a cold translation cache).")
    parser.add_argument(
        "--request-timeout", type=int, default=300,
        help="Per-request timeout in seconds (default: %(default)s). No delay is inserted between requests.",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "test-results" / "multilingual_api_workflow.json")
    args = parser.parse_args()
    if args.request_timeout < 1:
        parser.error("--request-timeout must be at least 1 second")
    workflow = Workflow(
        args.base_url, ALL_LANGUAGES if args.all_languages else DEFAULT_LANGUAGES,
        args.output, args.request_timeout,
    )

    # Public localization API: verifies discovery, runtime status, and every selected language bundle.
    workflow.request("health check", "GET", "/health")
    languages = workflow.request("language discovery", "GET", "/api/v1/i18n/languages", language="en")
    if isinstance(languages, dict) and len(languages.get("supported", [])) != 23:
        workflow.results[-1]["outcome"] = "FAIL"
        workflow.results[-1]["reason"] = "Expected English plus 22 scheduled Indian languages"
    workflow.request("translation runtime status", "GET", "/api/v1/i18n/status", language="en")
    for language in workflow.languages:
        bundle = workflow.request("localized UI bundle", "GET", "/api/v1/i18n/bundle", language=language)
        if isinstance(bundle, dict) and bundle.get("locale") != language:
            workflow.results[-1]["outcome"] = "FAIL"
            workflow.results[-1]["reason"] = "Bundle locale does not match requested locale"

    # Each locale must receive a localized API error, not merely a localized UI bundle.
    for language in workflow.languages:
        error = workflow.request("localized invalid-login error", "POST", "/api/v1/auth/login", language=language,
                                 body={"email": f"missing-{workflow.run_id}@gmail.com", "password": "wrong-password"},
                                 expected=(401,))
        record = workflow.results[-1]
        if record.get("content_language") != language:
            record["outcome"] = "FAIL"
            record["reason"] = "Content-Language did not match requested locale"
        if language != "en" and not (isinstance(error, dict) and error.get("detail")):
            record["outcome"] = "FAIL"
            record["reason"] = "Localized error response had no detail"

    # One authenticated workflow uses Unicode input.  API codes such as flood and status values intentionally remain English.
    # ``.test`` is a reserved domain and EmailStr correctly rejects it.  The
    # generated Gmail address is unique and is never used to send email.
    email = f"multilingual-check-{workflow.run_id}@gmail.com"
    user = workflow.request("register multilingual user", "POST", "/api/v1/auth/register", language="ta",
                            body={"email": email, "full_name": "மொழி சோதனை ஒருங்கிணைப்பாளர்", "password": "safe-password-123"},
                            expected=(201,))
    login = workflow.request("login multilingual user", "POST", "/api/v1/auth/login", language="hi",
                             body={"email": email, "password": "safe-password-123"})
    if not isinstance(login, dict) or not login.get("access_token"):
        workflow.write_report()
        return 1
    workflow.token = login["access_token"]

    # Read-only authenticated endpoints, spread across languages.
    for index, (name, path) in enumerate((
        ("current user", "/api/v1/users/me"), ("warehouse directory", "/api/v1/warehouses"),
        ("operational stock", "/api/v1/operational-stock"), ("volunteer list", "/api/v1/volunteers"),
        ("notifications", "/api/v1/notifications"), ("analytics trends", "/api/v1/analytics/trends"),
        ("analytics priority queue", "/api/v1/analytics/priority-queue"), ("knowledge-base list", "/api/v1/knowledge-base"),
    )):
        workflow.request(name, "GET", path, language=workflow.languages[index % len(workflow.languages)], authenticated=True)

    # This deliberately malformed request documents the current validation-message behaviour.
    # It is informational: FastAPI validation details are not translated by the HTTPException handler.
    workflow.request("validation error (localization boundary)", "GET", "/api/v1/analytics/trends?days=not-a-number",
                     language="hi", authenticated=True, expected=(422,))
    workflow.results[-1]["note"] = "Content-Language is localized, but validation detail may remain English."

    volunteer = workflow.request("create Unicode volunteer", "POST", "/api/v1/volunteers", language="te", authenticated=True,
                                 body={"name": "రవి సహాయకుడు", "email": f"volunteer-{workflow.run_id}@gmail.com", "phone": "+919876543210", "latitude": 13.0827, "longitude": 80.2707, "skill": "முதலுதவி"}, expected=(201,))
    if isinstance(volunteer, dict):
        workflow.request("read volunteer", "GET", f"/api/v1/volunteers/{volunteer['id']}", language="ml", authenticated=True)
        workflow.request("update volunteer status", "PATCH", f"/api/v1/volunteers/{volunteer['id']}/status", language="kn", authenticated=True, body={"availability": "Busy"})

    entry = workflow.request("create Unicode knowledge entry", "POST", "/api/v1/knowledge-base", language="ta", authenticated=True,
                             body={"title": "வெள்ள நிவாரண வழிகாட்டுதல்", "entry_type": "best_practice", "content": "குடிநீர், மருந்து மற்றும் பாதுகாப்பான தங்குமிடத்தை உடனடியாக ஏற்பாடு செய்யவும்.", "disaster_type": "flood", "severity": "High", "tags": ["வெள்ளம்", "relief"]}, expected=(201,))

    # This report calls live weather/model/dataset services.  Failures are recorded, while later dependent calls are skipped.
    report = workflow.request("create disaster report", "POST", "/api/v1/disaster-reports", language="hi", authenticated=True,
                              body={"disaster_type": "flood", "latitude": 13.0827, "longitude": 80.2707, "magnitude": 6.2, "affected_population": 1200}, expected=(201,))
    if isinstance(report, dict):
        report_id = report["id"]
        workflow.request("list disaster reports", "GET", "/api/v1/disaster-reports", language="te", authenticated=True)
        workflow.request("read disaster report", "GET", f"/api/v1/disaster-reports/{report_id}", language="ml", authenticated=True)
        prediction = workflow.request("predict report impact", "POST", f"/api/v1/disaster-reports/{report_id}/predict", language="kn", authenticated=True)
        workflow.request("report timeline", "GET", f"/api/v1/disaster-reports/{report_id}/timeline", language="ta", authenticated=True)
        workflow.request("route plan", "GET", f"/api/v1/disaster-reports/{report_id}/route", language="hi", authenticated=True)
        workflow.request("shelter recommendations", "GET", f"/api/v1/disaster-reports/{report_id}/shelters", language="te", authenticated=True)
        workflow.request("recommendations", "GET", f"/api/v1/disaster-reports/{report_id}/recommendations", language="ml", authenticated=True)
        if isinstance(entry, dict):
            workflow.request("recommendation feedback", "POST", f"/api/v1/disaster-reports/{report_id}/recommendations/{entry['id']}/feedback", language="kn", authenticated=True, body={"rating": 5, "comment": "உதவிகரமான வழிகாட்டுதல்"}, expected=(201,))
        if isinstance(prediction, dict):
            workflow.request("calculate allocation", "POST", f"/api/v1/disaster-reports/{report_id}/allocate", language="ta", authenticated=True)

    workflow.request("logout", "POST", "/api/v1/auth/logout", language="te", authenticated=True)
    workflow.write_report()
    return 0 if not any(item["outcome"] == "FAIL" for item in workflow.results) else 1


if __name__ == "__main__":
    sys.exit(main())
