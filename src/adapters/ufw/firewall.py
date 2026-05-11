"""Async UFW adapter using AsyncSSHClient (asyncssh). No paramiko required."""
from app.ssh_helper import AsyncSSHClient
from adapters.ufw.status_parser import parse_ufw_numbered, UFWStatusResult


class FirewallManager:
    """Manage UFW on a remote host via SSH."""

    def __init__(self, hostname: str, port: int, username: str,
                 password: str | None = None, private_key: str | None = None,
                 known_host_fingerprint: str | None = None):
        self.hostname               = hostname
        self.port                   = port
        self.username               = username
        self.password               = password
        self.private_key            = private_key
        self.known_host_fingerprint = known_host_fingerprint

    # ── internal ──────────────────────────────────────────────────────────────

    def _client(self) -> AsyncSSHClient:
        return AsyncSSHClient(
            host=self.hostname,
            port=self.port,
            username=self.username,
            password=self.password,
            private_key=self.private_key,
            known_host_fingerprint=self.known_host_fingerprint,
        )

    async def _run(self, cmd: str, timeout: int = 30) -> tuple[int, str, str]:
        async with self._client() as ssh:
            return await ssh.execute_command(cmd, timeout=timeout)

    @staticmethod
    def _ok(stdout: str, stderr: str | None = None) -> dict:
        return {"message": (stdout or (stderr or "")).strip() or "OK"}

    @staticmethod
    def _err(stderr: str, rc: int) -> dict:
        return {"error": (stderr or f"exit code {rc}").strip()}

    # ── read operations ───────────────────────────────────────────────────────

    async def status(self) -> UFWStatusResult:
        """Return parsed `ufw status numbered` + verbose info."""
        rc, out, err = await self._run("sudo ufw status verbose && sudo ufw status numbered")
        if rc != 0:
            return {"error": err or f"ufw status failed (exit {rc})"}
        return parse_ufw_numbered(out)

    # ── firewall lifecycle ────────────────────────────────────────────────────

    async def enable(self) -> dict:
        rc, out, err = await self._run("sudo ufw --force enable")
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    async def disable(self) -> dict:
        rc, out, err = await self._run("sudo ufw disable")
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    async def reload(self) -> dict:
        rc, out, err = await self._run("sudo ufw reload")
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    async def reset(self) -> dict:
        """Reset all rules (destructive — use with care)."""
        rc, out, err = await self._run("sudo ufw --force reset")
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    # ── rule management ───────────────────────────────────────────────────────

    async def allow(self, target: str, proto: str | None = None,
                    from_ip: str | None = None, direction: str = "in") -> dict:
        """Add an ALLOW rule.

        Examples:
            allow("22", proto="tcp")
            allow("80", proto="tcp", direction="in")
            allow("22", from_ip="192.168.1.0/24")
            allow("http")       # named service
        """
        cmd = self._build_rule_cmd("allow", target, proto, from_ip, direction)
        rc, out, err = await self._run(cmd)
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    async def deny(self, target: str, proto: str | None = None,
                   from_ip: str | None = None, direction: str = "in") -> dict:
        cmd = self._build_rule_cmd("deny", target, proto, from_ip, direction)
        rc, out, err = await self._run(cmd)
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    async def limit(self, target: str, proto: str | None = None) -> dict:
        """Rate-limit connections to a port (brute-force protection)."""
        spec = f"{target}/{proto}" if proto and proto != "any" else target
        rc, out, err = await self._run(f"sudo ufw limit {spec}")
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    async def reject(self, target: str, proto: str | None = None,
                     from_ip: str | None = None, direction: str = "in") -> dict:
        cmd = self._build_rule_cmd("reject", target, proto, from_ip, direction)
        rc, out, err = await self._run(cmd)
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    async def delete_rule(self, number: int) -> dict:
        """Delete a rule by its number from `ufw status numbered`."""
        rc, out, err = await self._run(f"yes | sudo ufw delete {number}")
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    # ── default policies ──────────────────────────────────────────────────────

    async def set_default(self, direction: str, policy: str) -> dict:
        """direction: incoming | outgoing | routed.  policy: allow | deny | reject."""
        rc, out, err = await self._run(f"sudo ufw default {policy} {direction}")
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    # ── logging ───────────────────────────────────────────────────────────────

    async def set_logging(self, level: str) -> dict:
        """level: on | off | low | medium | high | full"""
        rc, out, err = await self._run(f"sudo ufw logging {level}")
        return self._ok(out, err) if rc == 0 else self._err(err, rc)

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_rule_cmd(action: str, target: str, proto: str | None,
                        from_ip: str | None, direction: str) -> str:
        if from_ip:
            # sudo ufw allow from 192.168.1.0/24 to any port 22 proto tcp
            cmd = f"sudo ufw {action} from {from_ip}"
            if target and target.lower() not in ("any", "anywhere"):
                cmd += f" to any port {target}"
                if proto and proto != "any":
                    cmd += f" proto {proto}"
        else:
            # sudo ufw allow 22/tcp
            spec = f"{target}/{proto}" if proto and proto != "any" else target
            cmd = f"sudo ufw {action} {spec}"
            if direction and direction.lower() == "out":
                cmd += " out"
        return cmd
