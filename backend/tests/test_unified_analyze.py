"""API tests for the unified /analyze/resume endpoint (3-engine report).

Covers: full flow with JD, no-JD mode (match_score null + re-weighted overall),
the report shape contracts, and the privacy assertion (no disk writes).
"""
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import override_settings
from app.main import app

BACKEND_ROOT = Path(__file__).parent.parent
FIXTURES = BACKEND_ROOT / "tests" / "fixtures"

SAMPLE_JD = (
    "We need a Python Developer with Docker, Kubernetes and AWS experience. "
    "Requirements: strong Python, SQL and REST API skills. Knowledge of "
    "Machine Learning is a plus."
)


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


def _resume_bytes() -> bytes:
    pdf = FIXTURES / "sample_resume.pdf"
    if not pdf.exists():
        return b""
    return pdf.read_bytes()


def test_analyze_resume_with_jd_returns_full_report(client):
    payload = _resume_bytes()
    if not payload:
        pytest.skip("sample_resume.pdf fixture not present")
    response = client.post(
        "/api/v1/analyze/resume",
        data={"jd_text": SAMPLE_JD},
        files={"file": ("resume.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # Sub-scores present and in range
    assert 0.0 <= body["ats_score"]["score"] <= 100.0
    assert 0.0 <= body["content_score"]["score"] <= 100.0
    assert body["match_score"] is not None
    assert 0.0 <= body["match_score"]["score"] <= 100.0
    assert 0.0 <= body["overall_score"] <= 100.0

    # Unified report fields
    assert isinstance(body["findings"], list)
    assert isinstance(body["top_fixes"], list)
    assert isinstance(body["section_summary"], dict)
    assert isinstance(body["metadata"], dict)
    assert "raw_text" in body and body["raw_text"].strip()
    assert body["summary"]

    # Skill-gap data embedded
    assert isinstance(body["matched"], list)
    assert isinstance(body["missing"], list)
    assert isinstance(body["bonus"], list)
    assert isinstance(body["recommendations"], list)


def test_analyze_resume_without_jd_sets_no_jd_mode(client):
    payload = _resume_bytes()
    if not payload:
        pytest.skip("sample_resume.pdf fixture not present")
    response = client.post(
        "/api/v1/analyze/resume",
        files={"file": ("resume.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # No JD → match_score null, no-JD mode flagged, overall = ATS+Content only
    assert body["match_score"] is None
    assert body["metadata"].get("no_jd_mode") is True
    assert body["overall_score"] > 0
    assert body["summary"]


def test_analyze_resume_bad_file_returns_400(client):
    response = client.post(
        "/api/v1/analyze/resume",
        files={"file": ("resume.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400


def _snapshot_backend_files() -> dict[str, int]:
    return {
        str(p.relative_to(BACKEND_ROOT)): p.stat().st_mtime_ns
        for p in BACKEND_ROOT.rglob("*")
        if p.is_file()
    }


def test_analyze_resume_writes_nothing_to_disk(client):
    """Privacy contract: the unified endpoint never writes the upload to disk."""
    payload = _resume_bytes()
    if not payload:
        pytest.skip("sample_resume.pdf fixture not present")
    before = _snapshot_backend_files()
    response = client.post(
        "/api/v1/analyze/resume",
        data={"jd_text": SAMPLE_JD},
        files={"file": ("resume.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 200
    after = _snapshot_backend_files()
    assert before == after, "unified analyze must never leave a trace on disk"
