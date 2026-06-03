#!/usr/bin/env bash
set -u

print_section() {
  printf '\n== %s ==\n' "$1"
}

run_check() {
  printf '\n$ %s\n' "$*"
  "$@" 2>&1 || true
}

check_git_repo() {
  repo_path="$1"
  repo_name="$2"
  print_section "$repo_name git"
  if [ -d "$repo_path/.git" ]; then
    run_check git -C "$repo_path" branch --show-current
    run_check git -C "$repo_path" status --short
  else
    printf 'Missing git repository: %s\n' "$repo_path"
  fi
}

check_path() {
  path="$1"
  label="$2"
  if [ -e "$path" ]; then
    printf '[ok] %s: %s\n' "$label" "$path"
  else
    printf '[missing] %s: %s\n' "$label" "$path"
  fi
}

check_ports() {
  print_section "Ports 80/443"
  if command -v ss >/dev/null 2>&1; then
    run_check ss -ltn
  elif command -v netstat >/dev/null 2>&1; then
    run_check netstat -ltn
  else
    printf 'Neither ss nor netstat is available; cannot inspect listening ports.\n'
  fi
}

ROOT_DIR="$(pwd)"
PARENT_DIR="$(dirname "$ROOT_DIR")"
PIRSII_DIR="$ROOT_DIR"
RIFE_DIR="$PARENT_DIR/video_interpolation_arch"

print_section "Current directory"
printf '%s\n' "$ROOT_DIR"

print_section "Expected sibling layout"
check_path "$PIRSII_DIR" "pirsii_interpolator"
check_path "$RIFE_DIR" "video_interpolation_arch"

check_git_repo "$PIRSII_DIR" "pirsii_interpolator"
check_git_repo "$RIFE_DIR" "video_interpolation_arch"

print_section "Docker"
run_check docker --version
run_check docker compose version
run_check systemctl status docker --no-pager

print_section "NVIDIA"
run_check nvidia-smi
run_check nvidia-smi -L

print_section "Environment and model paths"
check_path "$PIRSII_DIR/.env" ".env"
check_path "$RIFE_DIR/model_weights" "model_weights"
check_path "$RIFE_DIR/model_repos" "model_repos"
check_path "$RIFE_DIR/configs" "configs"

check_ports

print_section "Compose config"
if [ -f "$PIRSII_DIR/docker-compose.gpu.generated.yml" ]; then
  run_check docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml config
else
  printf 'docker-compose.gpu.generated.yml not found; generate it with tools/generate_gpu_compose.py before final config validation.\n'
  if [ -f "$PIRSII_DIR/docker-compose.server.yml" ]; then
    run_check docker compose -f docker-compose.server.yml config
  fi
fi
