# SPDX-License-Identifier: MIT
"""Tests for VM NIC → Nervum LogicalPort lifecycle (T7)."""
from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import types
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

# Stub libvirt before any imports touch it
if "libvirt" not in sys.modules:
    sys.modules["libvirt"] = MagicMock()


def _stub_vm_manager():
    """Return a context-manager patch that stubs VMManager.create_virtual_machine and delete."""
    from unittest.mock import patch, AsyncMock
    mock_manager_instance = MagicMock()
    mock_manager_instance.create_virtual_machine.return_value = None
    mock_manager_instance.delete.return_value = "deleted"
    return patch(
        "adapters.libvirt.VMManager",
        return_value=mock_manager_instance,
    )


def _make_platform(db):
    """Insert a test platform, return its id."""
    from adapters.postgres.orm_models import AuthMethodEnum
    from app.models import Platform
    from app.crypto import crypto

    p = Platform(
        id=uuid.uuid4(),
        name="test-host",
        host="10.0.0.99",
        port=22,
        username="root",
        auth_method=AuthMethodEnum.PASSWORD,
        encrypted_password=crypto.encrypt_string("secret"),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return str(p.id)


def _mock_vm_manager_create(mocker=None):
    """Patch VMManager so it doesn't touch libvirt."""
    with patch("ports.api.virt.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        yield mock_asyncio


# ── VmSdnPortRow ORM constraint ───────────────────────────────────────────

def test_vm_sdn_port_unique_constraint(tmp_path):
    import os
    os.environ.setdefault("FERNET_KEY", "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs=")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.exc import IntegrityError
    from adapters.postgres.session import Base
    import adapters.postgres.orm_models  # noqa: F401

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    from adapters.postgres.orm_models import VmSdnPortRow
    pid = uuid.uuid4()

    db.add(VmSdnPortRow(
        id=uuid.uuid4(), platform_id=pid, vm_name="vm-1",
        port_id="port-a", created_at=datetime.utcnow(),
    ))
    db.commit()

    db.add(VmSdnPortRow(
        id=uuid.uuid4(), platform_id=pid, vm_name="vm-1",  # дублирует
        port_id="port-b", created_at=datetime.utcnow(),
    ))
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()
    db.close()


def test_vm_sdn_port_different_platforms_ok(tmp_path):
    """Одно имя VM на разных платформах — допустимо."""
    import os
    os.environ.setdefault("FERNET_KEY", "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs=")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from adapters.postgres.session import Base
    import adapters.postgres.orm_models  # noqa: F401

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    from adapters.postgres.orm_models import VmSdnPortRow
    db.add(VmSdnPortRow(id=uuid.uuid4(), platform_id=uuid.uuid4(), vm_name="vm-1",
                         port_id="port-a", created_at=datetime.utcnow()))
    db.add(VmSdnPortRow(id=uuid.uuid4(), platform_id=uuid.uuid4(), vm_name="vm-1",
                         port_id="port-b", created_at=datetime.utcnow()))
    db.commit()  # не должно падать
    db.close()


# ── create_vm with SDN ────────────────────────────────────────────────────

def test_create_vm_without_sdn(client: TestClient, test_db):
    """create_vm без nervum_network_id — SDN не вызывается."""
    platform_id = _make_platform(test_db)

    with _stub_vm_manager(), \
         patch("ports.api.virt.config") as mock_cfg:
        mock_cfg.NERVUM_URL = None

        r = client.post(f"/api/virt/{platform_id}/vms/create", json={
            "name": "vm-no-sdn",
            "memory": 512,
            "vcpu": 1,
            "disk_path": "/var/lib/vms/vm.qcow2",
            "cdrom_iso_path": "/iso/ubuntu.iso",
        })

    assert r.status_code == 200
    from adapters.postgres.orm_models import VmSdnPortRow
    count = test_db.query(VmSdnPortRow).filter_by(vm_name="vm-no-sdn").count()
    assert count == 0


def test_create_vm_with_sdn_creates_port(client: TestClient, test_db):
    """create_vm с nervum_network_id создаёт VmSdnPortRow."""
    platform_id = _make_platform(test_db)

    mock_port = {
        "id": "port-new-001",
        "name": "vm-sdn-test",
        "status": "pending",
        "mac": "02:aa:bb:cc:00:01",
        "ip_address": "10.0.1.100",
    }

    with _stub_vm_manager(), \
         patch("ports.api.virt.config") as mock_cfg, \
         patch("adapters.nervum.client.NervumClient.create_logical_port",
               new_callable=AsyncMock, return_value=mock_port):
        mock_cfg.NERVUM_URL = "http://nervum:8080"

        r = client.post(f"/api/virt/{platform_id}/vms/create", json={
            "name": "vm-sdn-test",
            "memory": 512,
            "vcpu": 1,
            "disk_path": "/var/lib/vms/vm.qcow2",
            "cdrom_iso_path": "/iso/ubuntu.iso",
            "nervum_network_id": "net-1",
            "nervum_project_id": "proj-1",
        })

    assert r.status_code == 200
    data = r.json()
    assert data.get("sdn_port", {}).get("id") == "port-new-001"
    assert data.get("sdn_port", {}).get("mac") == "02:aa:bb:cc:00:01"

    from adapters.postgres.orm_models import VmSdnPortRow
    row = test_db.query(VmSdnPortRow).filter_by(vm_name="vm-sdn-test").first()
    assert row is not None
    assert row.port_id == "port-new-001"
    assert row.mac == "02:aa:bb:cc:00:01"


def test_create_vm_sdn_failure_does_not_block(client: TestClient, test_db):
    """Если Nervum недоступен — VM создаётся без SDN, не возвращает 500."""
    platform_id = _make_platform(test_db)

    with _stub_vm_manager(), \
         patch("ports.api.virt.config") as mock_cfg, \
         patch("adapters.nervum.client.NervumClient.create_logical_port",
               new_callable=AsyncMock, side_effect=Exception("connection refused")):
        mock_cfg.NERVUM_URL = "http://nervum:8080"

        r = client.post(f"/api/virt/{platform_id}/vms/create", json={
            "name": "vm-sdn-fail",
            "memory": 512,
            "vcpu": 1,
            "disk_path": "/var/lib/vms/vm.qcow2",
            "cdrom_iso_path": "/iso/ubuntu.iso",
            "nervum_network_id": "net-1",
        })

    assert r.status_code == 200
    assert "sdn_port" not in r.json()

    from adapters.postgres.orm_models import VmSdnPortRow
    assert test_db.query(VmSdnPortRow).filter_by(vm_name="vm-sdn-fail").count() == 0


def test_create_vm_port_rolled_back_on_vm_failure(client: TestClient, test_db):
    """Если libvirt упал — созданный LogicalPort удаляется."""
    platform_id = _make_platform(test_db)

    mock_port = {"id": "port-orphan", "name": "vm-fail", "mac": "02:ff:ff:ff:ff:ff"}

    delete_called = []

    async def mock_delete(self, port_id, **kw):
        delete_called.append(port_id)

    from unittest.mock import patch as _patch
    from adapters.libvirt import VMManager as _VMManager
    _stub_fail = MagicMock()
    _stub_fail.create_virtual_machine.side_effect = Exception("libvirt error")

    with _patch("adapters.libvirt.VMManager", return_value=_stub_fail), \
         patch("ports.api.virt.config") as mock_cfg, \
         patch("adapters.nervum.client.NervumClient.create_logical_port",
               new_callable=AsyncMock, return_value=mock_port), \
         patch("adapters.nervum.client.NervumClient.delete_logical_port", mock_delete):
        mock_cfg.NERVUM_URL = "http://nervum:8080"

        r = client.post(f"/api/virt/{platform_id}/vms/create", json={
            "name": "vm-fail",
            "memory": 512, "vcpu": 1,
            "disk_path": "/vms/x.qcow2",
            "cdrom_iso_path": "/iso/u.iso",
            "nervum_network_id": "net-1",
        })

    assert r.status_code == 500
    assert "port-orphan" in delete_called


# ── delete_vm with SDN ────────────────────────────────────────────────────

def test_delete_vm_removes_sdn_port(client: TestClient, test_db):
    """delete_vm удаляет LogicalPort и запись VmSdnPortRow."""
    platform_id = _make_platform(test_db)

    # Создаём запись о порте напрямую
    from adapters.postgres.orm_models import VmSdnPortRow
    test_db.add(VmSdnPortRow(
        id=uuid.uuid4(), platform_id=platform_id, vm_name="vm-to-delete",
        port_id="port-del-001", network_id="net-1",
        created_at=datetime.utcnow(),
    ))
    test_db.commit()

    delete_called = []

    async def mock_delete(self, port_id, **kw):
        delete_called.append(port_id)

    with _stub_vm_manager(), \
         patch("ports.api.virt.config") as mock_cfg, \
         patch("adapters.nervum.client.NervumClient.delete_logical_port", mock_delete):
        mock_cfg.NERVUM_URL = "http://nervum:8080"

        r = client.post(f"/api/virt/{platform_id}/vms/delete",
                        json={"name": "vm-to-delete"})

    assert r.status_code == 200
    assert "port-del-001" in delete_called

    test_db.expire_all()
    remaining = test_db.query(VmSdnPortRow).filter_by(vm_name="vm-to-delete").count()
    assert remaining == 0


def test_delete_vm_no_port_binding(client: TestClient, test_db):
    """delete_vm без привязки SDN — просто удаляет VM, не падает."""
    platform_id = _make_platform(test_db)

    with _stub_vm_manager(), \
         patch("ports.api.virt.config") as mock_cfg:
        mock_cfg.NERVUM_URL = None

        r = client.post(f"/api/virt/{platform_id}/vms/delete",
                        json={"name": "vm-no-port"})

    assert r.status_code == 200
