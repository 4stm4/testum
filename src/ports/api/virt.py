"""Virt API — libvirt/VM management endpoints backed by Platform records."""
import asyncio
import logging
import uuid
from datetime import datetime

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.audit import log_audit
from app.crypto import crypto
from app.db import SessionLocal
from app.models import Platform, SSHKey, TaskRun, TaskStatusEnum, TaskTypeEnum
from app.rbac import require_roles, ALL_ROLES, get_request_user

logger = logging.getLogger(__name__)


def _get_platform(platform_id: str):
    """Fetch platform by ID and build its libvirt URI.

    Returns (platform, uri, db) on success or (None, None, None) when not found.
    The caller is responsible for calling db.close() when the session is no longer needed.
    """
    db = SessionLocal()
    platform = db.query(Platform).filter(Platform.id == platform_id).first()
    if platform is None:
        db.close()
        return None, None, None
    uri = f"qemu+ssh://{platform.username}@{platform.host}/system"
    return platform, uri, db


def _resolve_credentials(platform: Platform, db):
    """Return (password, private_key_str) decrypted from platform record."""
    password = None
    private_key = None
    auth = platform.auth_method.value if hasattr(platform.auth_method, 'value') else str(platform.auth_method)
    if auth == "password" and platform.encrypted_password:
        password = crypto.decrypt_string(platform.encrypted_password)
    elif auth == "private_key":
        if platform.ssh_key_id:
            key_row = db.query(SSHKey).filter(SSHKey.id == platform.ssh_key_id).first()
            if key_row and key_row.encrypted_private_key:
                private_key = crypto.decrypt_string(key_row.encrypted_private_key)
        elif platform.encrypted_private_key:
            private_key = crypto.decrypt_string(platform.encrypted_private_key)
    return password, private_key


# ── VMs ───────────────────────────────────────────────────────────────────────

@require_roles(*ALL_ROLES)
async def list_vms(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    try:
        from adapters.libvirt import VMManager
        vms = await asyncio.to_thread(lambda: VMManager(uri).list_all())
        result = []
        for vm in vms:
            result.append({
                "id": vm.id,
                "name": vm.name,
                "uuid": vm.uuid,
                "os_type": vm.os_type,
                "autostart": vm.autostart,
                "state": vm.domain_info.state,
                "max_mem_kb": vm.domain_info.max_mem,
                "memory_kb": vm.domain_info.memory,
                "vcpus": vm.domain_info.cpu_numb,
            })
        return JSONResponse(result)
    except Exception as exc:
        logger.exception("list_vms failed for platform %s", platform_id)
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def create_vm(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name          = body.get("name", "").strip()
    memory        = body.get("memory")
    vcpu          = body.get("vcpu")
    disk_path     = body.get("disk_path", "").strip()
    cdrom_iso_path = body.get("cdrom_iso_path", "").strip()
    bridge        = body.get("bridge", "virbr0").strip() or "virbr0"
    mac_address   = body.get("mac_address", "").strip() or None

    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    if not memory or int(memory) <= 0:
        return JSONResponse({"error": "memory (MiB) must be > 0"}, status_code=400)
    if not vcpu or int(vcpu) <= 0:
        return JSONResponse({"error": "vcpu must be > 0"}, status_code=400)
    if not disk_path:
        return JSONResponse({"error": "disk_path is required"}, status_code=400)
    if not cdrom_iso_path:
        return JSONResponse({"error": "cdrom_iso_path is required"}, status_code=400)

    try:
        from adapters.libvirt import VMManager
        from adapters.libvirt.models import VMConfig
        if mac_address is None:
            mac_address = VMConfig.generate_mac_address()
        config = VMConfig(
            name=name,
            memory=int(memory),
            vcpu=int(vcpu),
            disk_size=int(body.get("disk_size") or 1),  # не используется генератором, нужен модели
            disk_path=disk_path,
            cdrom_iso_path=cdrom_iso_path,
            bridge=bridge,
            mac_address=mac_address,
        )
        await asyncio.to_thread(lambda: VMManager(uri).create_virtual_machine(config))
        return JSONResponse({"message": f"VM {name!r} defined successfully"})
    except Exception as exc:
        logger.exception("create_vm failed for platform %s", platform_id)
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def start_vm(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from adapters.libvirt import VMManager
        msg = await asyncio.to_thread(lambda: VMManager(uri).run(name))
        return JSONResponse({"message": msg})
    except Exception as exc:
        logger.exception("start_vm failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def stop_vm(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from adapters.libvirt import VMManager
        msg = await asyncio.to_thread(lambda: VMManager(uri).stop(name))
        return JSONResponse({"message": msg})
    except Exception as exc:
        logger.exception("stop_vm failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def delete_vm(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from adapters.libvirt import VMManager
        msg = await asyncio.to_thread(lambda: VMManager(uri).delete(name))
        return JSONResponse({"message": msg})
    except Exception as exc:
        logger.exception("delete_vm failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Pools ─────────────────────────────────────────────────────────────────────

@require_roles(*ALL_ROLES)
async def list_pools(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    states = [int(s) for s in request.query_params.getlist("state")] or [2]  # default: ACTIVE
    try:
        from adapters.libvirt import StoragePoolManager
        pools = await asyncio.to_thread(lambda: StoragePoolManager(uri).list_all(states))
        result = [
            {
                "name": p.name,
                "uuid": p.uuid,
                "auto_start": p.auto_start,
                "is_active": p.is_active,
                "is_persistent": p.is_persistent,
                "num_volumes": p.num_volumes,
                "pool_state": p.pool_state,
                "capacity": p.capacity,
                "allocation": p.allocation,
                "available": p.available,
            }
            for p in pools
        ]
        return JSONResponse(result)
    except Exception as exc:
        logger.exception("list_pools failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def create_pool(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name = body.get("name")
    pool_type = body.get("pool_type")
    if not name or not pool_type:
        return JSONResponse({"error": "name and pool_type are required"}, status_code=400)
    try:
        from adapters.libvirt import StoragePoolManager
        await asyncio.to_thread(lambda: StoragePoolManager(uri).create(
            name=name,
            pool_type=pool_type,
            source=body.get("source"),
            target=body.get("target"),
            host=body.get("host"),
        ))
        return JSONResponse({"message": f"Pool {name} created"})
    except Exception as exc:
        logger.exception("create_pool failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def activate_pool(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from adapters.libvirt import StoragePoolManager
        await asyncio.to_thread(lambda: StoragePoolManager(uri).activate(name))
        return JSONResponse({"message": f"Pool {name} activated"})
    except Exception as exc:
        logger.exception("activate_pool failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def deactivate_pool(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from adapters.libvirt import StoragePoolManager
        await asyncio.to_thread(lambda: StoragePoolManager(uri).deactivate(name))
        return JSONResponse({"message": f"Pool {name} deactivated"})
    except Exception as exc:
        logger.exception("deactivate_pool failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def delete_pool(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from adapters.libvirt import StoragePoolManager
        await asyncio.to_thread(lambda: StoragePoolManager(uri).delete(name))
        return JSONResponse({"message": f"Pool {name} deleted"})
    except Exception as exc:
        logger.exception("delete_pool failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def pool_usage(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    name = request.query_params.get("name")
    if not name:
        return JSONResponse({"error": "name query param is required"}, status_code=400)
    try:
        from adapters.libvirt import StoragePoolManager
        usage = await asyncio.to_thread(lambda: StoragePoolManager(uri).monitor_usage(name))
        return JSONResponse(usage)
    except Exception as exc:
        logger.exception("pool_usage failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Volumes ───────────────────────────────────────────────────────────────────

@require_roles(*ALL_ROLES)
async def list_volumes(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    pool_name = request.query_params.get("pool_name")
    if not pool_name:
        return JSONResponse({"error": "pool_name query param is required"}, status_code=400)
    try:
        from adapters.libvirt import VolumesManager
        volumes = await asyncio.to_thread(lambda: VolumesManager(uri).list_all(pool_name))
        result = [
            {"name": v.name, "type": v.type, "capacity_gb": v.capacity, "allocation_gb": v.allocation}
            for v in volumes
        ]
        return JSONResponse(result)
    except Exception as exc:
        logger.exception("list_volumes failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def create_volume(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name = body.get("name")
    pool_name = body.get("pool_name")
    path = body.get("path")
    capacity = body.get("capacity")
    if not all([name, pool_name, path, capacity]):
        return JSONResponse({"error": "name, pool_name, path, capacity are required"}, status_code=400)
    try:
        from adapters.libvirt import VolumesManager
        await asyncio.to_thread(lambda: VolumesManager(uri).create(
            pool_name=pool_name, name=name, path=path, capacity=int(capacity)
        ))
        return JSONResponse({"message": f"Volume {name} created in pool {pool_name}"})
    except Exception as exc:
        logger.exception("create_volume failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def delete_volume(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    body = await request.json()
    name = body.get("name")
    pool_name = body.get("pool_name")
    if not name or not pool_name:
        return JSONResponse({"error": "name and pool_name are required"}, status_code=400)
    try:
        from adapters.libvirt import VolumesManager
        await asyncio.to_thread(lambda: VolumesManager(uri).delete(name=name, pool_name=pool_name))
        return JSONResponse({"message": f"Volume {name} deleted from pool {pool_name}"})
    except Exception as exc:
        logger.exception("delete_volume failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Host ──────────────────────────────────────────────────────────────────────

@require_roles(*ALL_ROLES)
async def host_capabilities(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    db.close()
    try:
        from adapters.libvirt import HostManager
        caps = await asyncio.to_thread(lambda: HostManager(uri).get_capabilities())
        return JSONResponse(caps)
    except Exception as exc:
        logger.exception("host_capabilities failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Firewall ──────────────────────────────────────────────────────────────────

def _get_firewall(platform_id: str):
    """Return (FirewallManager, db) or (None, None) if platform not found."""
    from adapters.ufw.firewall import FirewallManager
    platform, _, db = _get_platform(platform_id)
    if platform is None:
        return None, None
    password, private_key = _resolve_credentials(platform, db)
    db.close()
    return FirewallManager(
        hostname=platform.host,
        port=platform.port,
        username=platform.username,
        password=password,
        private_key=private_key,
        known_host_fingerprint=platform.known_host_fingerprint,
    ), None


@require_roles(*ALL_ROLES)
async def firewall_status(request: Request):
    fw, _ = _get_firewall(request.path_params["platform_id"])
    if fw is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    try:
        return JSONResponse(await fw.status())
    except Exception as exc:
        logger.exception("firewall_status failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def firewall_enable(request: Request):
    fw, _ = _get_firewall(request.path_params["platform_id"])
    if fw is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    try:
        return JSONResponse(await fw.enable())
    except Exception as exc:
        logger.exception("firewall_enable failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def firewall_disable(request: Request):
    fw, _ = _get_firewall(request.path_params["platform_id"])
    if fw is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    try:
        return JSONResponse(await fw.disable())
    except Exception as exc:
        logger.exception("firewall_disable failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def firewall_reload(request: Request):
    fw, _ = _get_firewall(request.path_params["platform_id"])
    if fw is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    try:
        return JSONResponse(await fw.reload())
    except Exception as exc:
        logger.exception("firewall_reload failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def firewall_add_rule(request: Request):
    fw, _ = _get_firewall(request.path_params["platform_id"])
    if fw is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    body    = await request.json()
    action  = body.get("action", "allow").lower()   # allow | deny | reject | limit
    target  = body.get("target", "").strip()
    proto   = body.get("proto", "any")               # tcp | udp | any
    from_ip = body.get("from_ip", "").strip() or None
    direction = body.get("direction", "in")          # in | out

    if not target:
        return JSONResponse({"error": "target (port or service) is required"}, status_code=400)
    if action not in ("allow", "deny", "reject", "limit"):
        return JSONResponse({"error": "action must be allow | deny | reject | limit"}, status_code=400)

    try:
        if action == "limit":
            result = await fw.limit(target, proto=proto if proto != "any" else None)
        elif action == "allow":
            result = await fw.allow(target, proto=proto if proto != "any" else None,
                                    from_ip=from_ip, direction=direction)
        elif action == "deny":
            result = await fw.deny(target, proto=proto if proto != "any" else None,
                                   from_ip=from_ip, direction=direction)
        else:
            result = await fw.reject(target, proto=proto if proto != "any" else None,
                                     from_ip=from_ip, direction=direction)
        return JSONResponse(result, status_code=400 if "error" in result else 200)
    except Exception as exc:
        logger.exception("firewall_add_rule failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def firewall_delete_rule(request: Request):
    fw, _ = _get_firewall(request.path_params["platform_id"])
    if fw is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    body = await request.json()
    number = body.get("number")
    if not number:
        return JSONResponse({"error": "rule number is required"}, status_code=400)
    try:
        result = await fw.delete_rule(int(number))
        return JSONResponse(result, status_code=400 if "error" in result else 200)
    except Exception as exc:
        logger.exception("firewall_delete_rule failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@require_roles(*ALL_ROLES)
async def firewall_set_default(request: Request):
    fw, _ = _get_firewall(request.path_params["platform_id"])
    if fw is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    body      = await request.json()
    direction = body.get("direction", "")   # incoming | outgoing
    policy    = body.get("policy", "")      # allow | deny | reject
    if direction not in ("incoming", "outgoing", "routed"):
        return JSONResponse({"error": "direction: incoming | outgoing | routed"}, status_code=400)
    if policy not in ("allow", "deny", "reject"):
        return JSONResponse({"error": "policy: allow | deny | reject"}, status_code=400)
    try:
        result = await fw.set_default(direction, policy)
        return JSONResponse(result, status_code=400 if "error" in result else 200)
    except Exception as exc:
        logger.exception("firewall_set_default failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Install ───────────────────────────────────────────────────────────────────

# Commands to detect OS id from /etc/os-release and install everything needed
_INSTALL_STEPS: dict[str, list[str]] = {
    # Debian / Ubuntu
    "ubuntu": [
        "export DEBIAN_FRONTEND=noninteractive",
        "sudo apt-get update -y",
        "sudo apt-get install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils virtinst cpu-checker",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
    "debian": [
        "export DEBIAN_FRONTEND=noninteractive",
        "sudo apt-get update -y",
        "sudo apt-get install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils virtinst",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
    # RHEL / CentOS / Rocky / Alma (8+)
    "rhel": [
        "sudo dnf install -y qemu-kvm libvirt libvirt-client virt-install bridge-utils",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
    "centos": [
        "sudo dnf install -y qemu-kvm libvirt libvirt-client virt-install bridge-utils || "
        "sudo yum install -y qemu-kvm libvirt libvirt-python libvirt-client virt-install bridge-utils",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
    "rocky": [
        "sudo dnf install -y qemu-kvm libvirt libvirt-client virt-install bridge-utils",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
    "almalinux": [
        "sudo dnf install -y qemu-kvm libvirt libvirt-client virt-install bridge-utils",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
    "fedora": [
        "sudo dnf install -y @virtualization",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
    # Arch
    "arch": [
        "sudo pacman -S --noconfirm qemu libvirt bridge-utils dnsmasq openbsd-netcat",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
    # openSUSE
    "opensuse-leap": [
        "sudo zypper install -y qemu-kvm libvirt bridge-utils",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
    "opensuse-tumbleweed": [
        "sudo zypper install -y qemu-kvm libvirt bridge-utils",
        "sudo systemctl enable --now libvirtd",
        "sudo usermod -aG libvirt,kvm $(whoami) || true",
    ],
}

_DEFAULT_INSTALL_STEPS = [
    "echo 'Unknown OS — attempting generic install via apt-get'",
    "sudo apt-get update -y && sudo apt-get install -y qemu-kvm libvirt-daemon-system libvirt-clients || true",
    "sudo dnf install -y qemu-kvm libvirt || sudo yum install -y qemu-kvm libvirt || true",
    "sudo systemctl enable --now libvirtd || true",
    "sudo usermod -aG libvirt,kvm $(whoami) || true",
]


def _detect_os_id(os_release: str) -> str:
    """Parse /etc/os-release and return the lowercase ID field."""
    for line in os_release.splitlines():
        if line.startswith("ID="):
            return line.split("=", 1)[1].strip().strip('"').lower()
    return "unknown"


async def _bg_install_libvirt(platform_id: str, task_id: str) -> None:
    """Background task: SSH into platform, detect OS, run install steps, update TaskRun."""
    from adapters.ssh.client import AsyncSSHClient

    db = SessionLocal()
    try:
        task = db.query(TaskRun).filter(TaskRun.id == task_id).first()
        if not task:
            return

        task.status = TaskStatusEnum.RUNNING
        task.started_at = datetime.utcnow()
        task.stdout = ""
        db.commit()

        def _append(text: str) -> None:
            task.stdout = (task.stdout or "") + text

        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            task.stdout = "[Platform not found]\n"
            task.status = TaskStatusEnum.FAILED
            task.finished_at = datetime.utcnow()
            db.commit()
            return

        password, private_key = _resolve_credentials(platform, db)

        try:
            async with AsyncSSHClient(
                host=platform.host,
                port=platform.port,
                username=platform.username,
                password=password,
                private_key=private_key,
                known_host_fingerprint=platform.known_host_fingerprint,
            ) as ssh:
                rc, stdout, stderr = await ssh.execute_command("cat /etc/os-release")
                os_id = _detect_os_id(stdout) if rc == 0 else "unknown"
                _append(f"=== Detected OS: {os_id} ===\n")
                db.commit()

                steps = _INSTALL_STEPS.get(os_id, _DEFAULT_INSTALL_STEPS)

                failed = False
                for cmd in steps:
                    _append(f"\n$ {cmd}\n")
                    rc, stdout, stderr = await ssh.execute_command(cmd, timeout=300)
                    if stdout:
                        _append(stdout)
                    if stderr:
                        _append(stderr)
                    if rc != 0:
                        _append(f"[exit code {rc}]\n")
                        failed = True
                    db.commit()  # one commit per command, not per append

                rc, stdout, stderr = await ssh.execute_command("virsh version 2>&1", timeout=30)
                _append(f"\n=== virsh version ===\n{stdout or stderr}\n")
                if rc != 0:
                    failed = True
                db.commit()

            task.status = TaskStatusEnum.FAILED if failed else TaskStatusEnum.SUCCESS

        except Exception as exc:
            logger.exception("bg install_libvirt ssh error")
            _append(f"\n[SSH error: {exc}]\n")
            task.status = TaskStatusEnum.FAILED

        task.finished_at = datetime.utcnow()
        db.commit()

    except Exception:
        logger.exception("bg install_libvirt unexpected error")
    finally:
        db.close()


@require_roles(*ALL_ROLES)
async def install_libvirt(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, _, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)

    task_run = TaskRun(
        id=uuid.uuid4(),
        type=TaskTypeEnum.RUN_COMMAND,
        platform_id=platform.id,
        status=TaskStatusEnum.PENDING,
        task_metadata={"install_type": "libvirt"},
    )
    db.add(task_run)
    db.commit()
    db.refresh(task_run)
    task_id = str(task_run.id)

    user = get_request_user(request)
    log_audit(
        db,
        user=user.username if user else "system",
        action="install_libvirt",
        object_type="platform",
        object_id=str(platform.id),
        meta={"task_id": task_id},
    )
    db.close()

    asyncio.create_task(_bg_install_libvirt(str(platform.id), task_id))

    return JSONResponse({
        "task_id": task_id,
        "job_url": f"/jobs/{task_id}",
        "message": "Install started",
    })


# ── Router ────────────────────────────────────────────────────────────────────

virt_router = Router(routes=[
    Route("/{platform_id}/vms",              list_vms,           methods=["GET"]),
    Route("/{platform_id}/vms/create",       create_vm,          methods=["POST"]),
    Route("/{platform_id}/vms/start",        start_vm,           methods=["POST"]),
    Route("/{platform_id}/vms/stop",         stop_vm,            methods=["POST"]),
    Route("/{platform_id}/vms/delete",       delete_vm,          methods=["POST"]),
    Route("/{platform_id}/pools",            list_pools,         methods=["GET"]),
    Route("/{platform_id}/pools/create",     create_pool,        methods=["POST"]),
    Route("/{platform_id}/pools/activate",   activate_pool,      methods=["POST"]),
    Route("/{platform_id}/pools/deactivate", deactivate_pool,    methods=["POST"]),
    Route("/{platform_id}/pools/delete",     delete_pool,        methods=["POST"]),
    Route("/{platform_id}/pools/usage",      pool_usage,         methods=["GET"]),
    Route("/{platform_id}/volumes",          list_volumes,       methods=["GET"]),
    Route("/{platform_id}/volumes/create",   create_volume,      methods=["POST"]),
    Route("/{platform_id}/volumes/delete",   delete_volume,      methods=["POST"]),
    Route("/{platform_id}/host/capabilities",    host_capabilities,    methods=["GET"]),
    Route("/{platform_id}/firewall/status",      firewall_status,      methods=["GET"]),
    Route("/{platform_id}/firewall/enable",      firewall_enable,      methods=["POST"]),
    Route("/{platform_id}/firewall/disable",     firewall_disable,     methods=["POST"]),
    Route("/{platform_id}/firewall/reload",      firewall_reload,      methods=["POST"]),
    Route("/{platform_id}/firewall/rule/add",    firewall_add_rule,    methods=["POST"]),
    Route("/{platform_id}/firewall/rule/delete", firewall_delete_rule, methods=["POST"]),
    Route("/{platform_id}/firewall/default",     firewall_set_default, methods=["POST"]),
    Route("/{platform_id}/install",              install_libvirt,      methods=["POST"]),
])
