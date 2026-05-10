# SPDX-License-Identifier: MIT
"""Pure Python domain enums — no external dependencies."""
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AuthMethod(str, enum.Enum):
    PASSWORD = "password"
    PRIVATE_KEY = "private_key"


class TaskType(str, enum.Enum):
    DEPLOY = "deploy"
    RUN_COMMAND = "run_command"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ExecutionType(str, enum.Enum):
    COMMAND = "command"
    SCRIPT = "script"


class TriggerType(str, enum.Enum):
    MANUAL = "manual"
    CRON = "cron"
    GITHUB_PUSH = "github_push"
    WEBHOOK = "webhook"
