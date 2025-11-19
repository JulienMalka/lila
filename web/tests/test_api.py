import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from alembic import command
from alembic.config import Config
from pathlib import Path

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


def run_alembic_migrations():
    """Run alembic migrations on the test database"""
    # Get path to alembic.ini (in web/ directory, parent of tests/)
    web_dir = Path(__file__).parent.parent
    alembic_ini_path = web_dir / "alembic.ini"

    # Create alembic config
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)
    alembic_cfg.set_main_option("script_location", str(web_dir / "alembic"))

    # Upgrade to head
    # Pass the connection via attributes so alembic uses the same in-memory DB
    with engine.begin() as connection:
        alembic_cfg.attributes['connection'] = connection
        command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh database for each test using alembic migrations"""
    # Use alembic to create schema instead of Base.metadata.create_all
    run_alembic_migrations()

    yield

    # Clean up: drop all tables by explicitly listing them
    # This is more reliable for SQLite in-memory databases with StaticPool
    with engine.begin() as conn:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        # Drop all tables including alembic_version
        for table in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))


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


class TestJobsetEndpoints:
    """Test jobset API endpoints"""

    def test_create_jobset(self, client, test_user):
        """Test creating a new jobset"""
        jobset_data = {
            "name": "nixpkgs-unstable",
            "description": "NixOS unstable channel",
            "flakeref": "github:NixOS/nixpkgs/nixos-unstable",
            "enabled": True
        }
        response = client.post(
            "/api/jobsets",
            json=jobset_data,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "nixpkgs-unstable"
        assert data["flakeref"] == "github:NixOS/nixpkgs/nixos-unstable"
        assert data["enabled"] == True
        assert "id" in data

    def test_create_jobset_without_auth(self, client):
        """Test creating jobset without authentication fails"""
        jobset_data = {
            "name": "test-jobset",
            "flakeref": "github:test/test"
        }
        response = client.post("/api/jobsets", json=jobset_data)
        assert response.status_code == 401

    def test_create_duplicate_jobset(self, client, test_user):
        """Test creating duplicate jobset fails"""
        jobset_data = {
            "name": "duplicate-test",
            "flakeref": "github:test/test"
        }
        # Create first jobset
        response1 = client.post(
            "/api/jobsets",
            json=jobset_data,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response1.status_code == 200

        # Try to create duplicate
        response2 = client.post(
            "/api/jobsets",
            json=jobset_data,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"]

    def test_list_jobsets_empty(self, client):
        """Test listing jobsets when none exist"""
        response = client.get("/api/jobsets")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_jobsets(self, client, test_user):
        """Test listing jobsets"""
        # Create a couple of jobsets
        for i in range(3):
            jobset_data = {
                "name": f"jobset-{i}",
                "flakeref": f"github:test/test{i}"
            }
            client.post(
                "/api/jobsets",
                json=jobset_data,
                headers={"Authorization": f"Bearer {test_user['token']}"}
            )

        response = client.get("/api/jobsets")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("name" in jobset for jobset in data)

    def test_get_jobset(self, client, test_user):
        """Test getting a specific jobset"""
        # Create jobset
        jobset_data = {
            "name": "test-get",
            "flakeref": "github:test/test"
        }
        create_response = client.post(
            "/api/jobsets",
            json=jobset_data,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        jobset_id = create_response.json()["id"]

        # Get jobset
        response = client.get(f"/api/jobsets/{jobset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-get"
        assert data["id"] == jobset_id

    def test_get_jobset_not_found(self, client):
        """Test getting non-existent jobset"""
        response = client.get("/api/jobsets/99999")
        assert response.status_code == 404
    
    def test_delete_jobset(self, client, test_user):
        """Test deleting a jobset"""
        # Create jobset
        jobset_data = {"name": "test-delete", "flakeref": "github:test/test"}
        create_response = client.post(
            "/api/jobsets",
            json=jobset_data,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        jobset_id = create_response.json()["id"]

        # Delete jobset
        response = client.delete(
            f"/api/jobsets/{jobset_id}",
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

        # Verify it's gone
        get_response = client.get(f"/api/jobsets/{jobset_id}")
        assert get_response.status_code == 404

    def test_delete_jobset_without_auth(self, client, test_user):
        """Test deleting jobset without authentication fails"""
        # Create jobset
        jobset_data = {"name": "test", "flakeref": "github:test/test"}
        create_response = client.post(
            "/api/jobsets",
            json=jobset_data,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        jobset_id = create_response.json()["id"]

        # Try to delete without auth
        response = client.delete(f"/api/jobsets/{jobset_id}")
        assert response.status_code == 401

class TestEvaluationEndpoints:
    """Test evaluation API endpoints"""

    def test_trigger_evaluation_with_real_flake(self, client, test_user):
        """Test triggering a real evaluation"""
        import subprocess
        import shutil

        # Check if nix-eval-jobs is available
        if not shutil.which("nix-eval-jobs"):
            pytest.skip("nix-eval-jobs not available")

        # Create jobset pointing to local test fixture
        test_fixtures_path = Path(__file__).parent / "fixtures"
        jobset_data = {
            "name": "test-fixture-flake",
            "flakeref": f"path:{test_fixtures_path}#packages.x86_64-linux",
            "description": "Test flake",
            "enabled": True
        }

        create_response = client.post(
            "/api/jobsets",
            json=jobset_data,
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert create_response.status_code == 200, f"Failed to create jobset: {create_response.text}"
        jobset_id = create_response.json()["id"]

        # Trigger evaluation
        eval_response = client.post(
            f"/api/jobsets/{jobset_id}/evaluate",
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )

        # Check if evaluation was triggered
        assert eval_response.status_code in [200, 202], f"Failed to trigger evaluation: {eval_response.text}"

        if eval_response.status_code == 200:
            eval_data = eval_response.json()
            assert "id" in eval_data
            assert eval_data["jobset_id"] == jobset_id

            # Get the evaluation details
            eval_id = eval_data["id"]
            detail_response = client.get(f"/api/evaluations/{eval_id}")
            assert detail_response.status_code == 200
            detail = detail_response.json()

            print(f"\nEvaluation result: status={detail['status']}, " +
                  f"derivations={detail.get('derivation_count', 0)}, " +
                  f"error={detail.get('error_message', 'none')}")

            # If completed successfully, verify we have the expected derivations
            if detail["status"] == "completed":
                assert detail.get("derivation_count", 0) == 3, \
                    "Expected exactly 3 derivations: hello-src, curl-src, test-derivation"

                # Get the derivations for this evaluation via API
                derivations_response = client.get(f"/api/evaluations/{eval_id}/derivations")
                assert derivations_response.status_code == 200
                derivations = derivations_response.json()

                # Extract drv_hash values
                drv_hashes = {d["drv_hash"] for d in derivations}

                # Expected drv_hash values for the FODs in fixtures/flake.nix
                expected_hashes = {
                    "4sb1y1wjcfx0nznffnzfkiq7p5frydg0-hello-2.12.1.tar.gz.drv",
                    "78j7dal6hzmzvawifz5vm6yq8k3cwzvg-test.txt.drv",
                    "3b2n7367jx5mjqkay2wgcgw351dhk7b3-curl-8.4.0.tar.gz.drv"
                }

                print(f"Found drv_hashes: {drv_hashes}")
                assert expected_hashes == drv_hashes, \
                    f"Expected hashes {expected_hashes}, but got {drv_hashes}"
