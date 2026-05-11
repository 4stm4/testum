"""Async UFW status adapter using the app's AsyncSSHClient."""
from app.ssh_helper import AsyncSSHClient
from adapters.ufw.status_parser import parse_ufw_status


class FirewallManager:
    """Async UFW manager. Uses AsyncSSHClient (asyncssh) — no paramiko required."""

    def __init__(self, hostname: str, port: int, username: str,
                 password: str | None = None, private_key: str | None = None,
                 known_host_fingerprint: str | None = None):
        self.hostname               = hostname
        self.port                   = port
        self.username               = username
        self.password               = password
        self.private_key            = private_key
        self.known_host_fingerprint = known_host_fingerprint

    async def status(self) -> dict:
        async with AsyncSSHClient(
            host=self.hostname,
            port=self.port,
            username=self.username,
            password=self.password,
            private_key=self.private_key,
            known_host_fingerprint=self.known_host_fingerprint,
        ) as ssh:
            rc, stdout, stderr = await ssh.execute_command("sudo ufw status")
            if rc != 0:
                return {"error": stderr or f"ufw status exited with code {rc}"}
            lines = stdout.splitlines(keepends=True)
            if not lines:
                return {"error": "Empty ufw output"}
            return parse_ufw_status(lines).dict()

    async def add_rule(self, rule: str) -> dict:
        async with AsyncSSHClient(
            host=self.hostname, port=self.port, username=self.username,
            password=self.password, private_key=self.private_key,
            known_host_fingerprint=self.known_host_fingerprint,
        ) as ssh:
            rc, stdout, stderr = await ssh.execute_command(f"sudo ufw {rule}")
            if rc != 0:
                return {"error": stderr or f"ufw rule failed (exit {rc})"}
            return {"message": stdout.strip() or f"Rule '{rule}' applied"}

    async def delete_rule(self, rule: str) -> dict:
        async with AsyncSSHClient(
            host=self.hostname, port=self.port, username=self.username,
            password=self.password, private_key=self.private_key,
            known_host_fingerprint=self.known_host_fingerprint,
        ) as ssh:
            rc, stdout, stderr = await ssh.execute_command(f"sudo ufw delete {rule}")
            if rc != 0:
                return {"error": stderr or f"ufw delete failed (exit {rc})"}
            return {"message": stdout.strip() or f"Rule '{rule}' deleted"}
