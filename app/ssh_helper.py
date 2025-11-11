"""SSH operations helper using Paramiko."""
import io
import logging
import hashlib
import time
from typing import Optional, Tuple, List
from paramiko import SSHClient, AutoAddPolicy, RSAKey, Ed25519Key, ECDSAKey, DSSKey
from paramiko.ssh_exception import SSHException, AuthenticationException

from app.config import config

logger = logging.getLogger(__name__)


class SSHHelper:
    """Helper class for SSH operations using Paramiko."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        known_host_fingerprint: Optional[str] = None,
    ):
        """
        Initialize SSH helper.

        Args:
            host: Host address
            port: SSH port
            username: SSH username
            password: Password for authentication (optional)
            private_key: Private key string for authentication (optional)
            known_host_fingerprint: Expected host key fingerprint (optional)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key_str = private_key
        self.known_host_fingerprint = known_host_fingerprint
        self.client: Optional[SSHClient] = None

    def _load_private_key(self, key_string: str):
        """
        Load private key from string.

        Args:
            key_string: Private key as string

        Returns:
            Paramiko key object
        """
        key_file = io.StringIO(key_string)
        
        # Try different key types
        for key_class in [RSAKey, Ed25519Key, ECDSAKey, DSSKey]:
            try:
                key_file.seek(0)
                return key_class.from_private_key(key_file)
            except Exception:
                continue
        
        raise ValueError("Unable to load private key. Unsupported key type.")

    def connect(self) -> Tuple[bool, Optional[str]]:
        """
        Establish SSH connection.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            self.client = SSHClient()

            # Set host key policy based on config
            if config.SSH_HOST_KEY_POLICY == "auto_add":
                self.client.set_missing_host_key_policy(AutoAddPolicy())
                logger.info(f"Using AutoAddPolicy for host key verification (host={self.host})")
            else:
                # Strict mode - will fail if host key is unknown
                self.client.load_system_host_keys()
                logger.info(f"Using strict host key policy (host={self.host})")

            # Prepare authentication
            pkey = None
            if self.private_key_str:
                pkey = self._load_private_key(self.private_key_str)

            # Connect
            logger.info(f"Connecting to {self.username}@{self.host}:{self.port}")
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                pkey=pkey,
                timeout=10,
                banner_timeout=10,
            )

            # Verify host key fingerprint if provided
            if self.known_host_fingerprint:
                actual_fingerprint = self.get_host_fingerprint()
                if actual_fingerprint != self.known_host_fingerprint:
                    error_msg = (
                        f"Host key verification failed! "
                        f"Expected: {self.known_host_fingerprint}, "
                        f"Got: {actual_fingerprint}"
                    )
                    logger.error(error_msg)
                    self.close()
                    return False, error_msg
                logger.info(f"Host key verification successful (host={self.host})")

            logger.info(f"Successfully connected to {self.host}")
            return True, None

        except AuthenticationException as e:
            error_msg = f"Authentication failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except SSHException as e:
            error_msg = f"SSH error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def connect_with_password(self, password: str) -> None:
        """
        Connect using password authentication.
        
        Args:
            password: Password for authentication
            
        Raises:
            Exception: If connection fails
        """
        self.password = password
        success, error = self.connect()
        if not success:
            raise Exception(error or "Connection failed")
    
    def connect_with_key(self, private_key: str) -> None:
        """
        Connect using private key authentication.
        
        Args:
            private_key: Private key string
            
        Raises:
            Exception: If connection fails
        """
        self.private_key_str = private_key
        success, error = self.connect()
        if not success:
            raise Exception(error or "Connection failed")

    def get_host_fingerprint(self) -> Optional[str]:
        """
        Get current host key fingerprint.

        Returns:
            Host key fingerprint as hex string
        """
        if not self.client or not self.client.get_transport():
            return None

        key = self.client.get_transport().get_remote_server_key()
        fingerprint = hashlib.sha256(key.asbytes()).hexdigest()
        return fingerprint

    def execute_command(
        self, command: str, timeout: int = 60
    ) -> Tuple[int, str, str]:
        """
        Execute command on remote host.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        logger.info(f"Executing command: {command}")
        
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        
        exit_code = stdout.channel.recv_exit_status()
        stdout_data = stdout.read().decode("utf-8", errors="replace")
        stderr_data = stderr.read().decode("utf-8", errors="replace")

        logger.info(f"Command finished with exit code: {exit_code}")
        
        return exit_code, stdout_data, stderr_data

    def ensure_directory(self, path: str, mode: int = 0o700) -> bool:
        """
        Ensure directory exists with proper permissions.

        Args:
            path: Directory path
            mode: Permissions mode (octal)

        Returns:
            Success status
        """
        try:
            sftp = self.client.open_sftp()
            try:
                sftp.stat(path)
                logger.info(f"Directory already exists: {path}")
            except FileNotFoundError:
                logger.info(f"Creating directory: {path}")
                sftp.mkdir(path)
                sftp.chmod(path, mode)
            finally:
                sftp.close()
            return True
        except Exception as e:
            logger.error(f"Failed to ensure directory {path}: {e}")
            return False

    def read_file(self, path: str) -> Optional[str]:
        """
        Read file content from remote host.

        Args:
            path: File path

        Returns:
            File content or None if file doesn't exist
        """
        try:
            sftp = self.client.open_sftp()
            try:
                with sftp.file(path, "r") as f:
                    content = f.read().decode("utf-8")
                logger.info(f"Read file: {path}")
                return content
            finally:
                sftp.close()
        except FileNotFoundError:
            logger.info(f"File not found: {path}")
            return None
        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            return None

    def write_file_atomic(
        self, path: str, content: str, mode: int = 0o600
    ) -> bool:
        """
        Write file atomically using temporary file and rename.

        Args:
            path: Target file path
            content: File content
            mode: File permissions (octal)

        Returns:
            Success status
        """
        try:
            sftp = self.client.open_sftp()
            try:
                # Write to temporary file
                temp_path = f"{path}.tmp.{int(time.time())}"
                logger.info(f"Writing to temporary file: {temp_path}")
                
                with sftp.file(temp_path, "w") as f:
                    f.write(content)
                
                # Set permissions
                sftp.chmod(temp_path, mode)
                
                # Atomic rename
                logger.info(f"Renaming {temp_path} to {path}")
                sftp.rename(temp_path, path)
                
                logger.info(f"Successfully wrote file: {path}")
                return True
            finally:
                sftp.close()
        except Exception as e:
            logger.error(f"Failed to write file {path}: {e}")
            return False

    def deploy_authorized_keys(self, public_keys: List[str]) -> Tuple[bool, str]:
        """
        Deploy SSH public keys to authorized_keys file idempotently.

        Args:
            public_keys: List of public keys to deploy

        Returns:
            Tuple of (success, message)
        """
        try:
            # Ensure .ssh directory exists
            ssh_dir = f"/home/{self.username}/.ssh"
            if not self.ensure_directory(ssh_dir, 0o700):
                return False, "Failed to create .ssh directory"

            authorized_keys_path = f"{ssh_dir}/authorized_keys"

            # Read existing keys
            existing_content = self.read_file(authorized_keys_path) or ""
            existing_lines = set(
                line.strip()
                for line in existing_content.split("\n")
                if line.strip() and not line.strip().startswith("#")
            )

            # Prepare new keys
            new_keys = set(key.strip() for key in public_keys if key.strip())

            # Merge keys (idempotent)
            merged_keys = existing_lines.union(new_keys)
            new_content = "\n".join(sorted(merged_keys)) + "\n"

            # Write atomically
            if self.write_file_atomic(authorized_keys_path, new_content, 0o600):
                added_count = len(merged_keys) - len(existing_lines)
                message = f"Successfully deployed keys. Added {added_count} new key(s)."
                logger.info(message)
                return True, message
            else:
                return False, "Failed to write authorized_keys file"

        except Exception as e:
            error_msg = f"Failed to deploy keys: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def close(self):
        """Close SSH connection."""
        if self.client:
            self.client.close()
            logger.info(f"Closed connection to {self.host}")
            self.client = None
