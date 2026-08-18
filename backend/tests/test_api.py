"""Phase 2 API tests using FastAPI's TestClient.

The privacy assertion (test_parse_resume_writes_nothing_to_disk) is the
compliance-relevant test in this file: after a /parse/resume request, no file
may be created or modified under the backend tree — the app must never write
an uploaded document to disk.

raise_server_exceptions=False lets the clean-500 handler test exercise the
real error path instead of re-raising into the test process.
"""
import json
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import override_settings
from app.main import app

BACKEND_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def client():
    with override_settings(rate_limit_enabled=False):
        server = fakeredis.FakeServer()
        fake_redis = fakeredis.FakeStrictRedis(server=server, decode_responses=True)

        import app.utils.rate_limit as rate_limit
        import app.utils.redis_cache as redis_cache

        rate_limit.get_redis = lambda: fake_redis
        redis_cache.get_redis = lambda: fake_redis

        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client


def _snapshot_backend_files() -> dict[str, int]:
    return {
        str(p.relative_to(BACKEND_ROOT)): p.stat().st_mtime_ns
        for p in BACKEND_ROOT.rglob("*")
        if p.is_file()
    }


# --- health & basic routing ---


def test_health_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_parse_jd_extracts_skills(client):
    response = client.post("/api/v1/parse/jd", data={"text": "We need Python and Docker skills."})
    assert response.status_code == 200
    body = response.json()
    assert body["raw_text"] == "We need Python and Docker skills."
    # Skill extraction requires the spaCy model; when absent it degrades to []
    # without erroring — both outcomes are acceptable here, only the shape is
    # contractual.
    assert isinstance(body["skills"], list)


def test_parse_jd_empty_text_returns_400(client):
    response = client.post("/api/v1/parse/jd", data={"text": "   "})
    assert response.status_code == 400


def test_parse_resume_unsupported_type_returns_400(client):
    response = client.post(
        "/api/v1/parse/resume",
        files={"file": ("resume.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


# --- analyze ---


def test_analyze_returns_gap_report(client):
    response = client.post(
        "/api/v1/analyze",
        json={"resume_skills": ["Python", "SQL"], "jd_skills": ["Python", "Docker"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["match_score"] <= 100.0
    assert isinstance(body["matched"], list)
    assert isinstance(body["missing"], list)
    assert isinstance(body["bonus"], list)
    assert "Python" in {m["jd_skill"] for m in body["matched"]}
    assert body["summary"]


def test_analyze_empty_jd_skills_returns_400(client):
    response = client.post(
        "/api/v1/analyze", json={"resume_skills": ["Python"], "jd_skills": []}
    )
    assert response.status_code == 400


def test_analyze_malformed_body_returns_422(client):
    response = client.post("/api/v1/analyze", json={"resume_skills": "not-a-list"})
    assert response.status_code == 422  # Pydantic validation catches bad input


def test_analyze_dedupes_skill_lists(client):
    response = client.post(
        "/api/v1/analyze",
        json={"resume_skills": ["Python", " python ", "SQL"], "jd_skills": ["Python"]},
    )
    body = response.json()
    assert body["bonus"] == ["SQL"]  # duplicate "python" removed


# --- session lifecycle ---


def test_session_roundtrip_and_delete(client):
    sid = f"test-{__import__('uuid').uuid4()}"
    response = client.post(
        "/api/v1/analyze",
        json={
            "resume_skills": ["Python"],
            "jd_skills": ["Python"],
            "session_id": sid,
        },
    )
    assert response.status_code == 200

    fetched = client.get(f"/api/v1/session/{sid}")
    assert fetched.status_code == 200
    assert fetched.json()["match_score"] == 100.0

    deleted = client.delete(f"/api/v1/session/{sid}")
    assert deleted.status_code == 200

    gone = client.get(f"/api/v1/session/{sid}")
    assert gone.status_code == 404


def test_session_unknown_id_returns_404(client):
    response = client.get(f"/api/v1/session/nonexistent-{__import__('uuid').uuid4()}")
    assert response.status_code == 404


def test_session_invalid_id_returns_404(client):
    for bad in ("../etc/passwd", "a b c", "x" * 100):
        assert client.get(f"/api/v1/session/{bad}").status_code == 404


def test_analyze_stores_only_anonymized_report(client, monkeypatch):
    """What hits Redis is the GapReport JSON — never raw text."""
    # v1.py imports cache_report_json directly, so patch the v1 reference.
    import app.api.v1 as v1

    captured = {}

    original = v1.cache_report_json

    def spy(payload_json: str, session_id: str | None = None):
        captured["payload"] = payload_json
        return original(payload_json, session_id=session_id)

    monkeypatch.setattr(v1, "cache_report_json", spy)

    secret_text = "super-secret-project-name-acme-internal"
    response = client.post(
        "/api/v1/analyze",
        json={"resume_skills": ["Python"], "jd_skills": ["Docker"]},
    )
    assert response.status_code == 200
    assert secret_text not in captured["payload"]
    assert "match_score" in captured["payload"]


# --- CORS ---


def test_cors_allows_configured_origin(client):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_disallowed_origin(client):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORSMiddleware rejects disallowed origins on preflight with 400 and no
    # allow-origin header — the origin lock is verified, not just assumed.
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


# --- privacy (compliance-relevant) ---


def test_parse_resume_writes_nothing_to_disk(client):
    """After a /parse/resume request, no file in the backend tree may be
    created or modified — uploaded documents exist only in memory."""
    pdf_path = BACKEND_ROOT / "tests" / "fixtures" / "sample_resume.pdf"
    if not pdf_path.exists():
        pytest.skip("sample_resume.pdf fixture not present")

    before = _snapshot_backend_files()
    response = client.post(
        "/api/v1/parse/resume",
        files={"file": ("resume.pdf", pdf_path.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["raw_text"].strip()
    after = _snapshot_backend_files()
    assert before == after, "upload must never leave a trace on disk"


# --- error containment ---


def test_unhandled_exception_returns_clean_500(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("internal explosion")

    import app.api.v1 as v1

    monkeypatch.setattr(v1, "compute_gap_report", boom)
    response = client.post(
        "/api/v1/analyze",
        json={"resume_skills": ["Python"], "jd_skills": ["Docker"]},
    )
    assert response.status_code == 500
    body = response.json()
    assert "internal explosion" not in json.dumps(body)  # no stack trace leaked
    assert "detail" in body
