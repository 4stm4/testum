#!/bin/bash
# SPDX-License-Identifier: MIT
# Testum installer — Docker (recommended) or bare-metal
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/4stm4/testum/main/install.sh | bash
#   bash install.sh [--bare-metal] [--port PORT] [--admin-password PASS] [--data-dir DIR]
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
MODE=auto               # auto | docker | bare-metal
PORT=8000               # public port
ADMIN_PASSWORD=""       # generated if empty
DATA_DIR=/opt/testum    # installation root
REPO=https://github.com/4stm4/testum.git
BRANCH=main

# ── Colors ────────────────────────────────────────────────────────────────────
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'
ok()   { echo -e "${G}  ✓ $*${N}"; }
info() { echo -e "${C}  · $*${N}"; }
warn() { echo -e "${Y}  ! $*${N}"; }
die()  { echo -e "${R}  ✗ $*${N}" >&2; exit 1; }

# ── Arg parsing ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --bare-metal)     MODE=bare-metal;;
    --docker)         MODE=docker;;
    --port)           PORT=$2;      shift;;
    --admin-password) ADMIN_PASSWORD=$2; shift;;
    --data-dir)       DATA_DIR=$2;  shift;;
    --branch)         BRANCH=$2;    shift;;
    -h|--help)
      echo "Usage: install.sh [--bare-metal|--docker] [--port N] [--admin-password P] [--data-dir DIR]"
      exit 0;;
    *) warn "Unknown option: $1";;
  esac
  shift
done

echo ""
echo -e "${G}>_ testum installer${N}"
echo -e "${C}   https://github.com/4stm4/testum${N}"
echo ""

# ── Root check ────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && die "Run as root (or with sudo)"

# ── Generate secrets ──────────────────────────────────────────────────────────
gen_key()  { python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
             || openssl rand -base64 32; }
gen_pass() { openssl rand -base64 16 | tr -d '=/+' | head -c 20; }

[[ -z "$ADMIN_PASSWORD" ]] && ADMIN_PASSWORD=$(gen_pass)

# ── Detect mode ───────────────────────────────────────────────────────────────
if [[ "$MODE" == "auto" ]]; then
  if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
    MODE=docker
    info "Docker detected → using Docker mode"
  elif command -v docker &>/dev/null && docker-compose version &>/dev/null 2>&1; then
    MODE=docker
    info "docker-compose detected → using Docker mode"
  else
    MODE=bare-metal
    info "Docker not found → using bare-metal mode"
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# DOCKER MODE
# ═══════════════════════════════════════════════════════════════════════════════
install_docker() {
  # ── Dependencies ──────────────────────────────────────────────────────────
  if ! command -v git &>/dev/null; then
    info "Installing git…"
    apt-get install -y -qq git || yum install -y -q git || die "Cannot install git"
  fi

  # ── Clone / update ────────────────────────────────────────────────────────
  if [[ -d "$DATA_DIR/.git" ]]; then
    info "Updating existing installation at $DATA_DIR…"
    git -C "$DATA_DIR" fetch origin "$BRANCH"
    git -C "$DATA_DIR" reset --hard "origin/$BRANCH"
  else
    info "Cloning testum → $DATA_DIR…"
    git clone --depth 1 --branch "$BRANCH" "$REPO" "$DATA_DIR"
  fi

  # ── Write .env ────────────────────────────────────────────────────────────
  ENV_FILE="$DATA_DIR/.env"
  if [[ ! -f "$ENV_FILE" ]]; then
    FERNET_KEY=$(gen_key)
    SECRET_KEY=$(gen_pass)
    cat > "$ENV_FILE" <<EOF
# Testum production environment — $(date -u +%Y-%m-%dT%H:%M:%SZ)
APP_ENV=production
PORT=$PORT

ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD

FERNET_KEY=$FERNET_KEY
SECRET_KEY=$SECRET_KEY

DATABASE_URL=postgresql://postgres:postgres@db:5432/testum
POSTGRES_PASSWORD=postgres

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=testum-artifacts
MINIO_SECURE=false

SSH_HOST_KEY_POLICY=auto_add
EOF
    ok "Generated $ENV_FILE"
  else
    warn ".env already exists — skipping generation (delete to regenerate)"
  fi

  # ── Patch public port in compose if non-default ───────────────────────────
  if [[ "$PORT" != "8000" ]]; then
    sed -i "s|\"8000:8000\"|\"${PORT}:8000\"|g" "$DATA_DIR/docker-compose.yml"
  fi

  # ── Build loading page with correct port ─────────────────────────────────
  if [[ -f "$DATA_DIR/loading/index.html" ]]; then
    sed -i "s|:8001/|:$((PORT+1))/|g" "$DATA_DIR/loading/index.html" 2>/dev/null || true
  fi

  # ── Start ─────────────────────────────────────────────────────────────────
  info "Starting services…"
  cd "$DATA_DIR"
  if docker compose version &>/dev/null 2>&1; then
    docker compose pull --quiet
    docker compose up -d
  else
    docker-compose pull --quiet
    docker-compose up -d
  fi

  # ── Systemd auto-start ────────────────────────────────────────────────────
  if command -v systemctl &>/dev/null; then
    cat > /etc/systemd/system/testum.service <<EOF
[Unit]
Description=Testum
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$DATA_DIR
ExecStart=/bin/sh -c 'docker compose up -d 2>/dev/null || docker-compose up -d'
ExecStop=/bin/sh -c 'docker compose down 2>/dev/null || docker-compose down'

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable testum &>/dev/null
    ok "systemd service enabled (testum.service)"
  fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# BARE-METAL MODE  (Debian/Ubuntu — Python 3.11+)
# ═══════════════════════════════════════════════════════════════════════════════
install_bare() {
  # ── System packages ───────────────────────────────────────────────────────
  info "Installing system packages…"
  if command -v apt-get &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv git libpq-dev gcc
  elif command -v yum &>/dev/null; then
    yum install -y -q python3 python3-pip git postgresql-devel gcc
  elif command -v apk &>/dev/null; then
    apk add --no-cache python3 py3-pip git postgresql-dev gcc musl-dev
  else
    die "Unsupported package manager — install python3, pip, git, libpq-dev manually"
  fi

  # ── SQLite fallback if no postgres ────────────────────────────────────────
  DB_URL="sqlite:///$DATA_DIR/testum.db"
  if command -v psql &>/dev/null; then
    DB_URL="postgresql://testum:testum@localhost:5432/testum"
    warn "PostgreSQL detected. Create DB manually if needed:"
    warn "  createuser -s testum; createdb -O testum testum; alter user testum password 'testum';"
  else
    info "PostgreSQL not found — using SQLite (fine for single-node)"
  fi

  # ── Clone / update ────────────────────────────────────────────────────────
  if [[ -d "$DATA_DIR/.git" ]]; then
    info "Updating existing installation…"
    git -C "$DATA_DIR" fetch origin "$BRANCH"
    git -C "$DATA_DIR" reset --hard "origin/$BRANCH"
  else
    info "Cloning testum → $DATA_DIR…"
    git clone --depth 1 --branch "$BRANCH" "$REPO" "$DATA_DIR"
  fi

  # ── Virtualenv ────────────────────────────────────────────────────────────
  VENV="$DATA_DIR/.venv"
  if [[ ! -d "$VENV" ]]; then
    info "Creating virtualenv…"
    python3 -m venv "$VENV"
  fi
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet --no-cache-dir -r "$DATA_DIR/requirements.txt"
  ok "Python dependencies installed"

  # ── .env ──────────────────────────────────────────────────────────────────
  ENV_FILE="$DATA_DIR/.env"
  if [[ ! -f "$ENV_FILE" ]]; then
    FERNET_KEY=$("$VENV/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
    SECRET_KEY=$(gen_pass)
    cat > "$ENV_FILE" <<EOF
APP_ENV=production
PORT=$PORT

ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD

FERNET_KEY=$FERNET_KEY
SECRET_KEY=$SECRET_KEY

DATABASE_URL=$DB_URL

SSH_HOST_KEY_POLICY=auto_add
EOF
    ok "Generated $ENV_FILE"
  else
    warn ".env already exists — skipping generation"
  fi

  # ── Migrations ────────────────────────────────────────────────────────────
  info "Running database migrations…"
  (
    set -a; source "$ENV_FILE"; set +a
    export PYTHONPATH="$DATA_DIR/src"
    cd "$DATA_DIR"
    "$VENV/bin/alembic" upgrade head
  )
  ok "Migrations complete"

  # ── Systemd service ───────────────────────────────────────────────────────
  if command -v systemctl &>/dev/null; then
    cat > /etc/systemd/system/testum.service <<EOF
[Unit]
Description=Testum
After=network.target

[Service]
Type=simple
WorkingDirectory=$DATA_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONPATH=$DATA_DIR/src
ExecStart=$VENV/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable testum
    systemctl start testum
    ok "testum.service started"
  else
    # Fallback: background launch
    info "systemd not found — launching in background"
    (
      set -a; source "$ENV_FILE"; set +a
      export PYTHONPATH="$DATA_DIR/src"
      cd "$DATA_DIR"
      nohup "$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$PORT" \
        >> "$DATA_DIR/testum.log" 2>&1 &
      echo $! > "$DATA_DIR/testum.pid"
    )
    ok "Started (PID $(cat $DATA_DIR/testum.pid))"
    info "Logs: tail -f $DATA_DIR/testum.log"
  fi
}

# ── Run selected mode ─────────────────────────────────────────────────────────
case $MODE in
  docker)     install_docker;;
  bare-metal) install_bare;;
  *)          die "Unknown mode: $MODE";;
esac

# ── Summary ───────────────────────────────────────────────────────────────────
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_IP")
echo ""
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "${G}  >_ testum installed${N}"
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo ""
echo -e "  URL      ${C}http://${HOST_IP}:${PORT}${N}"
echo -e "  Login    ${C}admin${N} / ${C}${ADMIN_PASSWORD}${N}"
echo -e "  Data     ${C}${DATA_DIR}${N}"
echo -e "  Mode     ${C}${MODE}${N}"
echo ""
echo -e "  ${Y}Save your password — it won't be shown again${N}"
echo ""
