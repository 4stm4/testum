"""Virt API — libvirt/VM management endpoints backed by Platform records."""
import asyncio
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.crypto import crypto
from app.db import get_db
from app.models import Platform, SSHKey
from app.rbac import require_roles, ALL_ROLES

logger = logging.getLogger(__name__)


def _get_platform(platform_id: str):
    db = next(get_db())
    platform = db.query(Platform).filter(Platform.id == platform_id).first()
    if platform is None:
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
    try:
        from virt_base.adapters.libvirt import VMManager
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
async def start_vm(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import VMManager
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
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import VMManager
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
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import VMManager
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
    states = [int(s) for s in request.query_params.getlist("state")] or [2]  # default: ACTIVE
    try:
        from virt_base.adapters.libvirt import StoragePoolManager
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
    body = await request.json()
    name = body.get("name")
    pool_type = body.get("pool_type")
    if not name or not pool_type:
        return JSONResponse({"error": "name and pool_type are required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import StoragePoolManager
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
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import StoragePoolManager
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
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import StoragePoolManager
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
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import StoragePoolManager
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
    name = request.query_params.get("name")
    if not name:
        return JSONResponse({"error": "name query param is required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import StoragePoolManager
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
    pool_name = request.query_params.get("pool_name")
    if not pool_name:
        return JSONResponse({"error": "pool_name query param is required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import VolumesManager
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
    body = await request.json()
    name = body.get("name")
    pool_name = body.get("pool_name")
    path = body.get("path")
    capacity = body.get("capacity")
    if not all([name, pool_name, path, capacity]):
        return JSONResponse({"error": "name, pool_name, path, capacity are required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import VolumesManager
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
    body = await request.json()
    name = body.get("name")
    pool_name = body.get("pool_name")
    if not name or not pool_name:
        return JSONResponse({"error": "name and pool_name are required"}, status_code=400)
    try:
        from virt_base.adapters.libvirt import VolumesManager
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
    try:
        from virt_base.adapters.libvirt import HostManager
        caps = await asyncio.to_thread(lambda: HostManager(uri).get_capabilities())
        return JSONResponse(caps)
    except Exception as exc:
        logger.exception("host_capabilities failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Firewall ──────────────────────────────────────────────────────────────────

@require_roles(*ALL_ROLES)
async def firewall_status(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, uri, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    password, _ = _resolve_credentials(platform, db)
    if password is None:
        return JSONResponse(
            {"error": "Platform has no password credential; firewall status requires password auth"},
            status_code=400,
        )
    try:
        from virt_base.adapters.ufw.firewall import FirewallManager
        fw = FirewallManager(
            hostname=platform.host,
            port=platform.port,
            username=platform.username,
            password=password,
        )
        status = await asyncio.to_thread(fw.status)
        return JSONResponse(status)
    except Exception as exc:
        logger.exception("firewall_status failed")
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


async def _run_install_over_ssh(platform, db) -> tuple[bool, str]:
    """SSH into platform, detect OS, run install steps. Returns (ok, output)."""
    from app.ssh_helper import AsyncSSHClient

    password, private_key = _resolve_credentials(platform, db)
    output_lines: list[str] = []

    async with AsyncSSHClient(
        host=platform.host,
        port=platform.port,
        username=platform.username,
        password=password,
        private_key=private_key,
        known_host_fingerprint=platform.known_host_fingerprint,
    ) as ssh:
        # 1. detect OS
        rc, stdout, stderr = await ssh.execute_command("cat /etc/os-release")
        os_id = _detect_os_id(stdout) if rc == 0 else "unknown"
        output_lines.append(f"=== Detected OS: {os_id} ===\n")

        steps = _INSTALL_STEPS.get(os_id, _DEFAULT_INSTALL_STEPS)

        # 2. run install steps
        for cmd in steps:
            output_lines.append(f"\n$ {cmd}\n")
            rc, stdout, stderr = await ssh.execute_command(cmd, timeout=300)
            if stdout:
                output_lines.append(stdout)
            if stderr:
                output_lines.append(stderr)
            if rc != 0:
                output_lines.append(f"[exit code {rc}]\n")

        # 3. verify libvirt is available
        rc, stdout, stderr = await ssh.execute_command("virsh version 2>&1", timeout=30)
        output_lines.append(f"\n=== virsh version ===\n{stdout or stderr}\n")

    return True, "".join(output_lines)


@require_roles(*ALL_ROLES)
async def install_libvirt(request: Request):
    platform_id = request.path_params["platform_id"]
    platform, _, db = _get_platform(platform_id)
    if platform is None:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    try:
        ok, output = await _run_install_over_ssh(platform, db)
        return JSONResponse({"ok": ok, "output": output})
    except Exception as exc:
        logger.exception("install_libvirt failed for platform %s", platform_id)
        return JSONResponse({"ok": False, "output": str(exc)}, status_code=500)


# ── Router ────────────────────────────────────────────────────────────────────

virt_router = Router(routes=[
    Route("/{platform_id}/vms",              list_vms,           methods=["GET"]),
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
    Route("/{platform_id}/host/capabilities", host_capabilities, methods=["GET"]),
    Route("/{platform_id}/firewall/status",  firewall_status,    methods=["GET"]),
    Route("/{platform_id}/install",          install_libvirt,    methods=["POST"]),
])
