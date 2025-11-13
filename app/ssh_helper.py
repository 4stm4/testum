"""Asynchronous SSH helper built on top of asyncssh."""
import asyncio
import hashlib
import logging
from typing import List, Optional, Tuple

from app.config import config

try:  # pragma: no cover - runtime dependency
    import asyncssh  # type: ignore
except ImportError:  # pragma: no cover - fallback for environments without asyncssh
    asyncssh = None

logger = logging.getLogger(__name__)


def _require_asyncssh() -> None:
    if asyncssh is None:
        raise RuntimeError(
            "asyncssh is required for SSH operations. Install it via `pip install asyncssh`."
        )


class AsyncSSHClient:
    """Async SSH client for executing commands and managing authorized keys."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        known_host_fingerprint: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.known_host_fingerprint = known_host_fingerprint
        self._connection: Optional[asyncssh.SSHClientConnection] = None

    async def __aenter__(self) -> "AsyncSSHClient":
        _require_asyncssh()
        success, error = await self.connect()
        if not success:
            raise asyncssh.Error(error or "Unable to establish SSH connection")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> Tuple[bool, Optional[str]]:
        """Establish the SSH connection."""

        if self._connection and not self._connection.is_closing():
            return True, None

        _require_asyncssh()

        client_keys = None
        if self.private_key:
            try:
                client_keys = [asyncssh.import_private_key(self.private_key)]
            except (asyncssh.KeyImportError, ValueError) as exc:
                logger.error("Failed to import private key: %s", exc)
                return False, "Invalid private key"

        known_hosts = None if config.SSH_HOST_KEY_POLICY == "auto_add" else asyncssh.read_known_hosts()

        try:
            self._connection = await asyncssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                client_keys=client_keys,
                known_hosts=known_hosts,
                login_timeout=10,
            )

            if self.known_host_fingerprint:
                fingerprint = self.get_host_fingerprint()
                if fingerprint != self.known_host_fingerprint:
                    await self.close()
                    error_msg = (
                        "Host key verification failed: "
                        f"expected {self.known_host_fingerprint}, got {fingerprint}"
                    )
                    logger.error(error_msg)
                    return False, error_msg

            logger.info("Connected to %s@%s:%s", self.username, self.host, self.port)
            return True, None
        except (asyncssh.Error, OSError) as exc:
            logger.error("SSH connection error: %s", exc)
            return False, str(exc)

    def get_host_fingerprint(self) -> Optional[str]:
        """Return SHA256 fingerprint of remote host key."""

        if not self._connection:
            return None

        host_key = self._connection.get_server_host_key()
        if not host_key:
            return None
        return hashlib.sha256(host_key.asbytes()).hexdigest()

    async def execute_command(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """Execute a command on the remote host."""

        if not self._connection:
            raise RuntimeError("Not connected")

        _require_asyncssh()

        logger.info("Executing command on %s: %s", self.host, command)
        try:
            result = await asyncio.wait_for(
                self._connection.run(command, check=False), timeout=timeout
            )
        except asyncio.TimeoutError:
            return 255, "", "Command timed out"
        except asyncssh.Error as exc:
            return 255, "", str(exc)

        return result.exit_status, result.stdout or "", result.stderr or ""

    async def deploy_authorized_keys(self, public_keys: List[str]) -> Tuple[bool, str]:
        """Deploy public keys into authorized_keys for the remote user."""

        if not self._connection:
            raise RuntimeError("Not connected")

        _require_asyncssh()

        ssh_dir = f"/home/{self.username}/.ssh"
        authorized_path = f"{ssh_dir}/authorized_keys"
        key_content = "\n".join(pk.strip() for pk in public_keys if pk.strip()) + "\n"

        try:
            await self._connection.run(f"mkdir -p {ssh_dir} && chmod 700 {ssh_dir}", check=True)
            async with self._connection.start_sftp_client() as sftp:
                async with sftp.open(authorized_path, "w") as remote_file:
                    await remote_file.write(key_content)
            await self._connection.run(f"chmod 600 {authorized_path}", check=True)
            return True, f"Deployed {len(public_keys)} key(s)"
        except asyncssh.Error as exc:
            logger.error("Failed to deploy authorized keys: %s", exc)
            return False, str(exc)

    async def read_file(self, path: str) -> Optional[str]:
        """Read a file from the remote host via SFTP."""

        if not self._connection:
            raise RuntimeError("Not connected")

        _require_asyncssh()

        try:
            async with self._connection.start_sftp_client() as sftp:
                async with sftp.open(path, "r") as remote_file:
                    data = await remote_file.read()
                    return data.decode("utf-8")
        except FileNotFoundError:
            return None
        except asyncssh.Error as exc:
            logger.error("Failed to read remote file %s: %s", path, exc)
            return None

    async def close(self) -> None:
        """Close the SSH connection."""

        if self._connection:
            self._connection.close()
            try:
                await self._connection.wait_closed()
            finally:
                self._connection = None


class SSHHelper:
    """Synchronous SSH client using paramiko for basic operations."""

    def __init__(self, host: str, port: int, username: str) -> None:
        """Initialize SSH client."""
        import paramiko
        
        self.host = host
        self.port = port
        self.username = username
        self.client: Optional[paramiko.SSHClient] = None

    def connect_with_password(self, password: str) -> None:
        """Connect using password authentication."""
        import paramiko
        
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=password,
                timeout=10,
            )
            logger.info("Connected to %s@%s:%s with password", self.username, self.host, self.port)
        except Exception as exc:
            logger.error("SSH connection error: %s", exc)
            if self.client:
                self.client.close()
                self.client = None
            raise

    def connect_with_key(self, private_key_str: str) -> None:
        """Connect using private key authentication."""
        import paramiko
        from io import StringIO
        
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            private_key = paramiko.RSAKey.from_private_key(StringIO(private_key_str))
        except Exception:
            try:
                private_key = paramiko.Ed25519Key.from_private_key(StringIO(private_key_str))
            except Exception:
                try:
                    private_key = paramiko.ECDSAKey.from_private_key(StringIO(private_key_str))
                except Exception as exc:
                    logger.error("Failed to load private key: %s", exc)
                    raise ValueError("Invalid private key format")
        
        try:
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                pkey=private_key,
                timeout=10,
            )
            logger.info("Connected to %s@%s:%s with private key", self.username, self.host, self.port)
        except Exception as exc:
            logger.error("SSH connection error: %s", exc)
            if self.client:
                self.client.close()
                self.client = None
            raise

    def execute_command(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """Execute a command on the remote host."""
        if not self.client:
            raise RuntimeError("Not connected")
        
        logger.info("Executing command on %s: %s", self.host, command)
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode("utf-8")
            stderr_text = stderr.read().decode("utf-8")
            
            return exit_code, stdout_text, stderr_text
        except Exception as exc:
            logger.error("Command execution error: %s", exc)
            return 255, "", str(exc)

    def close(self) -> None:
        """Close the SSH connection."""
        if self.client:
            self.client.close()
            self.client = None
