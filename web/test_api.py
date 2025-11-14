import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from web import app, models, get_db
from web.db import Base


# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override the database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """Create a test client with overridden database"""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(test_db):
    """Create a test user with authentication token"""
    db = TestingSessionLocal()
    try:
        user = models.User(name="test_user")
        db.add(user)
        db.commit()
        db.refresh(user)

        token = models.Token(user=user, value="test_token_123")
        db.add(token)
        db.commit()

        # Store the values before closing the session to avoid DetachedInstanceError
        user_id = user.id
        user_name = user.name
        return {"user_id": user_id, "user_name": user_name, "token": "test_token_123"}
    finally:
        db.close()


@pytest.fixture
def test_derivation(client, test_user):
    """
    Create a test derivation via the API (by posting an attestation).
    This is the proper E2E way - derivations are created when attestations are posted.

    Note: In the real system, derivations ONLY exist when attestations are posted,
    so this is the authentic way to create test data.
    """
    drv_hash = "test123abc-hello-1.0"
    payload = [
        {
            "output_digest": "test123",
            "output_name": "hello",
            "output_hash": "sha256:abc123",
            "output_sig": "sig1"
        }
    ]
    response = client.post(
        f"/attestation/{drv_hash}",
        json=payload,
        headers={"Authorization": f"Bearer {test_user['token']}"}
    )
    assert response.status_code == 200
    # Return dict with drv_hash for compatibility with test expectations
    return type('obj', (object,), {'drv_hash': drv_hash})()


@pytest.fixture
def test_report(client, test_user):
    """
    Create a test report via the API using PUT /reports endpoint.
    This is the proper E2E way - no direct database access.
    """
    report_data = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": "urn:uuid:test-123",
        "version": 1,
        "metadata": {
            "component": {
                "bom-ref": "/nix/store/test123-root-package",
                "type": "application",
                "name": "test-package"
            }
        },
        "components": [
            {
                "bom-ref": "/nix/store/test456-dep1",
                "type": "library",
                "name": "dep1",
                "properties": [
                    {"name": "nix:out_path", "value": "/nix/store/test456-dep1"},
                    {"name": "nix:drv_path", "value": "/nix/store/test456-dep1.drv"}
                ]
            }
        ],
        "dependencies": [
            {
                "ref": "/nix/store/test123-root-package",
                "dependsOn": ["/nix/store/test456-dep1"]
            }
        ]
    }

    response = client.put(
        "/reports/test_report",
        json=report_data,
        headers={"Authorization": f"Bearer {test_user['token']}"}
    )
    assert response.status_code == 200
    # Return object-like dict for compatibility
    return type('obj', (object,), {'name': 'test_report'})()


class TestDerivationEndpoints:
    """Tests for /derivations endpoints"""

    def test_get_derivations_empty(self, client):
        """Test getting derivations when database is empty"""
        response = client.get("/derivations/")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_derivations_with_data(self, client, test_derivation):
        """Test getting derivations with data"""
        response = client.get("/derivations/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["drv_hash"] == "test123abc-hello-1.0"

    def test_get_derivation_not_found(self, client):
        """Test getting a derivation that doesn't exist"""
        response = client.get("/derivations/nonexistent")
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"

    def test_get_derivation_exists(self, client, test_derivation):
        """Test getting an existing derivation (created via attestation)"""
        response = client.get(f"/derivations/{test_derivation.drv_hash}")
        assert response.status_code == 200
        # The test_derivation fixture creates one attestation, so we should see it
        data = response.json()
        assert "/nix/store/test123-hello" in data
        assert data["/nix/store/test123-hello"]["sha256:abc123"] == 1

    def test_get_derivation_with_attestations(self, client, test_derivation, test_user):
        """Test getting derivation with multiple attestations (added via API)"""
        # test_derivation already has one attestation, add another via API
        payload = [
            {
                "output_digest": "test123",
                "output_name": "hello",
                "output_hash": "sha256:abc123",  # Same hash as existing
                "output_sig": "sig2"
            }
        ]
        response = client.post(
            f"/attestation/{test_derivation.drv_hash}",
            json=payload,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 200

        # Now query the derivation - should show 2 attestations with same hash
        response = client.get(f"/derivations/{test_derivation.drv_hash}")
        assert response.status_code == 200
        data = response.json()
        assert "/nix/store/test123-hello" in data
        assert data["/nix/store/test123-hello"]["sha256:abc123"] == 2

    def test_get_derivation_full_mode(self, client, test_derivation, test_user):
        """Test getting derivation with full=true (returns full attestation list)"""
        # test_derivation already has one attestation from fixture
        response = client.get(f"/derivations/{test_derivation.drv_hash}?full=true")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1


class TestAttestationEndpoints:
    """Tests for /attestation endpoints"""

    def test_post_attestation_without_auth(self, client, test_derivation):
        """Test posting attestation without authentication"""
        payload = [
            {
                "output_digest": "test123",
                "output_name": "hello",
                "output_hash": "sha256:abc123",
                "output_sig": "sig1"
            }
        ]
        response = client.post(
            f"/attestation/{test_derivation.drv_hash}",
            json=payload
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "User not found"

    def test_post_attestation_with_auth(self, client, test_derivation, test_user):
        """Test posting attestation with valid authentication"""
        payload = [
            {
                "output_digest": "test123",
                "output_name": "hello",
                "output_hash": "sha256:abc123",
                "output_sig": "sig1"
            }
        ]
        response = client.post(
            f"/attestation/{test_derivation.drv_hash}",
            json=payload,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 200
        assert "Attestation accepted" in response.json()

    def test_get_attestations_by_output(self, client, test_derivation, test_user):
        """Test getting attestations by output path"""
        # test_derivation already created an attestation via API
        response = client.get("/attestations/by-output/test123-hello")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["output_path"] == "/nix/store/test123-hello"


class TestReportEndpoints:
    """Tests for /reports endpoints"""

    def test_get_reports_empty(self, client):
        """Test getting reports list when empty"""
        response = client.get("/reports")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_reports_list(self, client, test_report):
        """Test getting list of report names"""
        response = client.get("/reports")
        assert response.status_code == 200
        assert response.json() == ["test_report"]

    def test_get_report_not_found(self, client):
        """Test getting a report that doesn't exist"""
        response = client.get("/reports/nonexistent")
        assert response.status_code == 404
        assert response.json()["detail"] == "Report not found"

    def test_get_report_cyclonedx_format(self, client, test_report):
        """Test getting report in CycloneDX format"""
        response = client.get(
            "/reports/test_report",
            headers={"Accept": "application/vnd.cyclonedx+json"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.cyclonedx+json"
        data = response.json()
        assert data["bomFormat"] == "CycloneDX"
        assert data["metadata"]["component"]["bom-ref"] == "/nix/store/test123-root-package"

    def test_get_report_text_format(self, client, test_report):
        """Test getting report in text format"""
        response = client.get(
            "/reports/test_report",
            headers={"Accept": "text/plain"}
        )
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "root-package" in response.text

    def test_get_report_html_format(self, client, test_report):
        """Test getting report in HTML format"""
        response = client.get(
            "/reports/test_report",
            headers={"Accept": "text/html"}
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_put_report_without_auth(self, client):
        """Test creating/updating report without authentication"""
        report_data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "metadata": {
                "component": {
                    "bom-ref": "/nix/store/new-package",
                    "type": "application"
                }
            }
        }
        response = client.put("/reports/new_report", json=report_data)
        assert response.status_code == 401
        assert response.json()["detail"] == "User not found"

    def test_put_report_with_auth(self, client, test_user):
        """Test creating/updating report with authentication"""
        report_data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "metadata": {
                "component": {
                    "bom-ref": "/nix/store/new-package",
                    "type": "application"
                }
            }
        }
        response = client.put(
            "/reports/new_report",
            json=report_data,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 200
        assert "Report defined" in response.json()

    def test_get_report_suggest(self, client, test_report, test_user):
        """Test /suggest endpoint"""
        response = client.get(
            "/reports/test_report/suggest",
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 50


class TestLinkPatternEndpoints:
    """Tests for /link_patterns endpoints"""

    def test_get_link_patterns_empty(self, client):
        """Test getting link patterns when empty"""
        response = client.get("/link_patterns")
        assert response.status_code == 200
        assert response.json() == []

    def test_post_link_pattern_without_auth(self, client):
        """Test posting link pattern without authentication"""
        response = client.post(
            "/link_patterns",
            params={"pattern": ".*firefox.*", "link": "https://bugzilla.mozilla.org"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "User not found"

    def test_post_link_pattern_with_auth(self, client, test_user):
        """Test posting link pattern with authentication"""
        response = client.post(
            "/link_patterns",
            params={"pattern": ".*firefox.*", "link": "https://bugzilla.mozilla.org"},
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 200
        assert response.json() == "OK"

    def test_get_link_patterns_with_data(self, client, test_user):
        """Test getting link patterns after adding some"""
        # Add a pattern
        client.post(
            "/link_patterns",
            params={"pattern": ".*chromium.*", "link": "https://bugs.chromium.org"},
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )

        response = client.get("/link_patterns")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["pattern"] == ".*chromium.*"
        assert data[0]["link"] == "https://bugs.chromium.org"


class TestSignatureEndpoints:
    """Tests for /signatures endpoints (NAR info format)"""

    def test_get_signature_user_not_found(self, client):
        """Test getting signature for non-existent user"""
        response = client.get("/signatures/nonexistent_user/test123.narinfo")
        assert response.status_code == 401
        assert response.json()["detail"] == "User not found"

    def test_get_signature_attestation_not_found(self, client, test_user):
        """Test getting signature for non-existent attestation"""
        response = client.get(
            f"/signatures/{test_user['user_name']}/nonexistent.narinfo"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"

    def test_get_signature_success(self, client, test_derivation, test_user):
        """Test getting signature successfully"""
        # test_derivation already created attestation via API
        response = client.get(
            f"/signatures/{test_user['user_name']}/test123.narinfo"
        )
        assert response.status_code == 200
        assert "text/x-nix-narinfo" in response.headers["content-type"]

        content = response.text
        assert "StorePath: /nix/store/test123-hello" in content
        assert "NarHash: sha256:abc123" in content
        assert f"Deriver: {test_derivation.drv_hash}.drv" in content

    def test_get_signature_without_deriver(self, client, test_user):
        """Test getting signature when derivation doesn't exist"""
        # Create attestation without valid derivation
        db = TestingSessionLocal()
        try:
            att = models.Attestation(
                drv_id=99999,  # Non-existent derivation
                output_path="/nix/store/orphan123-package",
                output_hash="sha256:orphanhash",
                output_digest="orphan123",
                output_name="package",
                output_sig="sig",
                user_id=test_user["user_id"]
            )
            db.add(att)
            db.commit()
        finally:
            db.close()

        response = client.get(
            f"/signatures/{test_user['user_name']}/orphan123.narinfo"
        )
        assert response.status_code == 200
        content = response.text
        # Should not have Deriver line or should be empty
        assert "Deriver:" not in content or "Deriver: \n" in content

