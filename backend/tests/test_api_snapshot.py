from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app import main


class FakeSnapshotService:
    def create_snapshot(self):
        return {
            "status": "success",
            "bucket": "test-bucket",
            "key": "newspulse/snapshots/2026/09/27/articles-test.json",
            "article_count": 2,
            "generated_at": datetime(2026, 9, 27, tzinfo=timezone.utc),
        }


def test_snapshot_endpoint_returns_safe_summary() -> None:
    main.app.dependency_overrides[main.snapshots.get_snapshot_service] = lambda: FakeSnapshotService()
    try:
        response = TestClient(main.app).post("/articles/snapshot")
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["article_count"] == 2
    assert response.json()["key"].startswith("newspulse/snapshots/")
    assert "DATABASE_URL" not in response.text
    assert "CURRENTS_API_KEY" not in response.text


def test_snapshot_endpoint_reports_missing_configuration(monkeypatch) -> None:
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.setattr("backend.app.services.aws_storage.load_dotenv", lambda: None)
    try:
        response = TestClient(main.app).post("/articles/snapshot")
    finally:
        main.app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "S3_BUCKET_NAME is not configured"}
