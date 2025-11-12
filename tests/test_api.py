"""API endpoint tests."""
import pytest
from starlette.testclient import TestClient


def test_health_check(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_homepage(client: TestClient):
    """Test homepage."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Testum" in response.content


def test_create_ssh_key(client: TestClient):
    """Test creating SSH key."""
    key_data = {
        "name": "test-key",
        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC... test@example.com",
    }
    response = client.post("/api/keys/", json=key_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-key"
    assert "id" in data


def test_list_ssh_keys(client: TestClient):
    """Test listing SSH keys."""
    # Create a key first
    key_data = {
        "name": "test-key",
        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC... test@example.com",
    }
    client.post("/api/keys/", json=key_data)
    
    # List keys
    response = client.get("/api/keys/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_delete_ssh_key(client: TestClient):
    """Test deleting SSH key."""
    # Create a key
    key_data = {
        "name": "test-key-to-delete",
        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC... test@example.com",
    }
    create_response = client.post("/api/keys/", json=key_data)
    key_id = create_response.json()["id"]
    
    # Delete it
    response = client.delete(f"/api/keys/{key_id}")
    assert response.status_code == 200
    
    # Verify it's gone
    list_response = client.get("/api/keys/")
    keys = list_response.json()
    assert not any(k["id"] == key_id for k in keys)


def test_create_platform(client: TestClient):
    """Test creating platform."""
    platform_data = {
        "name": "test-platform",
        "host": "192.168.1.100",
        "port": 22,
        "username": "testuser",
        "auth_method": "password",
        "password": "testpass123",
    }
    response = client.post("/api/platforms/", json=platform_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-platform"
    assert data["host"] == "192.168.1.100"
    assert "id" in data


def test_list_platforms(client: TestClient):
    """Test listing platforms."""
    # Create a platform
    platform_data = {
        "name": "test-platform",
        "host": "192.168.1.100",
        "port": 22,
        "username": "testuser",
        "auth_method": "password",
        "password": "testpass123",
    }
    client.post("/api/platforms/", json=platform_data)
    
    # List platforms
    response = client.get("/api/platforms/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_platform(client: TestClient):
    """Test getting platform details."""
    # Create a platform
    platform_data = {
        "name": "test-platform",
        "host": "192.168.1.100",
        "port": 22,
        "username": "testuser",
        "auth_method": "password",
        "password": "testpass123",
    }
    create_response = client.post("/api/platforms/", json=platform_data)
    platform_id = create_response.json()["id"]
    
    # Get platform
    response = client.get(f"/api/platforms/{platform_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == platform_id
    assert data["name"] == "test-platform"


def test_delete_platform(client: TestClient):
    """Test deleting platform."""
    # Create a platform
    platform_data = {
        "name": "test-platform-delete",
        "host": "192.168.1.100",
        "port": 22,
        "username": "testuser",
        "auth_method": "password",
        "password": "testpass123",
    }
    create_response = client.post("/api/platforms/", json=platform_data)
    platform_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/api/platforms/{platform_id}")
    assert response.status_code == 200

    # Verify it's gone
    get_response = client.get(f"/api/platforms/{platform_id}")
    assert get_response.status_code == 404


def test_script_crud_flow(client: TestClient):
    """Test creating, updating, listing, and deleting scripts."""
    script_payload = {
        "name": "Deploy web",
        "language": "bash",
        "description": "Restart web service",
        "content": "#!/bin/bash\nsystemctl restart web.service",
    }

    # Create script
    create_response = client.post("/api/scripts/", json=script_payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == script_payload["name"]
    assert created["language"] == script_payload["language"]
    assert "id" in created

    script_id = created["id"]

    # Update script
    update_payload = {"description": "Restart the web application service"}
    update_response = client.put(f"/api/scripts/{script_id}", json=update_payload)
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["description"] == update_payload["description"]

    # Get single script
    get_response = client.get(f"/api/scripts/{script_id}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == script_id

    # List scripts
    list_response = client.get("/api/scripts/")
    assert list_response.status_code == 200
    scripts = list_response.json()
    assert any(item["id"] == script_id for item in scripts)

    # Delete script
    delete_response = client.delete(f"/api/scripts/{script_id}")
    assert delete_response.status_code == 200

    # Ensure removed
    verify_response = client.get(f"/api/scripts/{script_id}")
    assert verify_response.status_code == 404
