#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Heroku"
MODULE_NAME="heroku"
REPO_URL="${HEROKU_REPO_URL:-https://github.com/Heroku-userbot/Heroku.git}"
VENV_DIR="${HEROKU_VENV_DIR:-.venv}"
LOG_FILE="$PWD/heroku-install.log"

if [ "${SUDO_USER:-}" != "" ] && command -v sudo >/dev/null 2>&1; then
	RUN_AS_USER=(sudo -u "$SUDO_USER")
else
	RUN_AS_USER=()
fi

is_installed() {
	local dir="$1"

	[ -f "$dir/.setup_complete" ] && [ -d "$dir/$MODULE_NAME" ] && "$dir/$VENV_DIR/bin/python" -c "import sys" >/dev/null 2>&1
}

find_root() {
	local dir="$PWD"

	while [ "$dir" != "/" ]; do
		if [ -f "$dir/$MODULE_NAME/__main__.py" ] && [ -f "$dir/requirements.txt" ]; then
			printf "%s" "$dir"
			return 0
		fi
		dir="$(dirname "$dir")"
	done
	return 1
}

find_installed() {
	local dir

	for dir in "$PWD" "$PWD/$APP_NAME" "$HOME/$APP_NAME"; do
		if is_installed "$dir"; then
			printf "%s" "$dir"
			return 0
		fi
	done
	return 1
}

is_minimal() {
	case "${HEROKU_MINIMAL:-auto}" in
		1) return 0 ;;
		0) return 1 ;;
	esac

	[ -d /support ] || grep -qE "^TracerPid:[[:space:]]*[1-9]" /proc/self/status 2>/dev/null
}

info() {
	printf "\033[38;5;177m%s\033[0m\n" "$1"
}

warn() {
	printf "\033[1;33m%s\033[0m\n" "$1" >&2
}

ok() {
	printf "\033[0;32m%s\033[0m\n" "$1"
}

fail() {
	if [ -s "$LOG_FILE" ]; then
		printf "\n--- last lines of the log ---\n" >&2
		tail -n 25 "$LOG_FILE" >&2
		printf "\nFull log: %s\n\n" "$LOG_FILE" >&2
	fi
	printf "\033[1;31m%s\033[0m\n" "$1" >&2
	exit "${2:-1}"
}

run() {
	"$@" >>"$LOG_FILE" 2>&1 || fail "Command failed: $*" 5
}

sudo_run() {
	if [ "$(id -u)" -eq 0 ]; then
		run "$@"
	elif command -v sudo >/dev/null 2>&1; then
		run sudo "$@"
	else
		fail "Root privileges or sudo are required to install system packages." 2
	fi
}

python_cmd() {
	if command -v python3 >/dev/null 2>&1; then
		printf "python3"
	elif command -v python >/dev/null 2>&1; then
		printf "python"
	else
		fail "Python is not installed." 2
	fi
}

install_system_packages() {
	info "Installing system packages..."

	if echo "${OSTYPE:-}" | grep -qE "^linux-android"; then
		fail "Termux is not supported (some requirements can't be built for Android). Use UserLAnd or a VDS instead." 2
	elif command -v apt-get >/dev/null 2>&1 && is_minimal; then
		info "Minimal mode: installing only the required packages."
		sudo_run apt-get update
		sudo_run apt-get install -y git python3 python3-venv
	elif command -v apt-get >/dev/null 2>&1; then
		sudo_run apt-get update
		sudo_run apt-get install -y \
			build-essential \
			ffmpeg \
			git \
			imagemagick \
			libcairo2 \
			libffi-dev \
			libjpeg-dev \
			libmagic1 \
			libopenjp2-7 \
			libtiff-dev \
			libwebp-dev \
			libz-dev \
			python3 \
			python3-dev \
			python3-pip \
			python3-venv
	elif command -v pacman >/dev/null 2>&1; then
		sudo_run pacman -Sy --needed --noconfirm \
			base-devel \
			ffmpeg \
			file \
			git \
			imagemagick \
			python \
			python-pip
	elif command -v dnf >/dev/null 2>&1; then
		sudo_run dnf install -y \
			ffmpeg \
			file-libs \
			gcc \
			gcc-c++ \
			git \
			ImageMagick \
			python3 \
			python3-devel \
			python3-pip
	elif command -v brew >/dev/null 2>&1; then
		run brew install git jpeg webp
	else
		info "Unknown package manager, skipping system package installation."
	fi
}

check_python() {
	local py="$1"

	"$py" - <<'PY'
import sys

if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required")
PY
}

git_as_user() {
	${RUN_AS_USER[@]+"${RUN_AS_USER[@]}"} git "$@"
}

switch_branch() {
	local branch="${HEROKU_BRANCH:-}" current output

	if [ -z "$branch" ]; then
		return 0
	fi

	if ! git_as_user rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		warn "Can't switch to the branch $branch: this is not a git repository."
		return 0
	fi

	current="$(git_as_user rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
	if [ "$current" = "$branch" ]; then
		return 0
	fi

	if [ -n "$(git_as_user status --porcelain 2>/dev/null)" ]; then
		warn "Not switched to the branch $branch, staying on ${current:-the current one}: there are local changes. Commit or stash them and run again."
		return 0
	fi

	if ! output="$(git_as_user fetch --quiet origin "$branch" 2>&1 && git_as_user checkout --quiet "$branch" 2>&1)"; then
		warn "Not switched to the branch $branch, staying on ${current:-the current one}: $output"
		return 0
	fi

	info "Switched to the branch $branch."
}

prepare_repo() {
	if [ -d "$MODULE_NAME" ] && [ -f "requirements.txt" ]; then
		switch_branch
		return
	fi

	if [ -d "$APP_NAME/$MODULE_NAME" ]; then
		cd "$APP_NAME"
		switch_branch
		return
	fi

	local branch=()
	if [ -n "${HEROKU_BRANCH:-}" ]; then
		branch=(--branch "$HEROKU_BRANCH")
	fi

	info "Cloning repo..."
	rm -rf "$APP_NAME"
	${RUN_AS_USER[@]+"${RUN_AS_USER[@]}"} git clone ${branch[@]+"${branch[@]}"} "$REPO_URL" "$APP_NAME" >>"$LOG_FILE" 2>&1 || fail "Clone failed." 3
	cd "$APP_NAME"
}

create_venv() {
	local py="$1"

	info "Creating virtual environment..."
	${RUN_AS_USER[@]+"${RUN_AS_USER[@]}"} "$py" -m venv "$VENV_DIR" >>"$LOG_FILE" 2>&1 || fail "Virtual environment creation failed." 4
}

install_python_packages() {
	local venv_python="$VENV_DIR/bin/python"

	info "Installing Python dependencies..."
	${RUN_AS_USER[@]+"${RUN_AS_USER[@]}"} "$venv_python" -m pip install --upgrade pip setuptools wheel >>"$LOG_FILE" 2>&1 || fail "Pip upgrade failed." 4
	${RUN_AS_USER[@]+"${RUN_AS_USER[@]}"} "$venv_python" -m pip install --upgrade -r requirements.txt --disable-pip-version-check >>"$LOG_FILE" 2>&1 || fail "Requirements installation failed." 4

	${RUN_AS_USER[@]+"${RUN_AS_USER[@]}"} "$venv_python" - >>"$LOG_FILE" 2>&1 <<'PY' || true
import hashlib

with open("requirements.txt", "rb") as f, open(".requirements_hash", "w") as h:
    h.write(hashlib.sha256(f.read()).hexdigest())
PY
}

start_app() {
	info "Starting..."
	if [ ! -t 0 ] && (: </dev/tty) 2>/dev/null; then
		exec </dev/tty
	fi

	exec ${RUN_AS_USER[@]+"${RUN_AS_USER[@]}"} "$VENV_DIR/bin/python" -m "$MODULE_NAME" "$@"
}

main() {
	if root="$(find_root)"; then
		cd "$root"
	fi

	if [ "${HEROKU_FORCE_INSTALL:-0}" != "1" ] && existing="$(find_installed)"; then
		cd "$existing"
		info "Heroku is already installed, starting..."
		switch_branch
		start_app "$@"
		return
	fi

	clear || true
	printf "\033[3;38;5;177;40mInstalling %s...\033[0m\n\n" "$APP_NAME"

	: >"$LOG_FILE"

	if [ "${SUDO_USER:-}" != "" ]; then
		chown "$SUDO_USER:" "$LOG_FILE" >/dev/null 2>&1 || true
	fi

	install_system_packages
	PYTHON="$(python_cmd)"
	prepare_repo
	[ -f assets/download.txt ] && cat assets/download.txt
	check_python "$PYTHON"
	create_venv "$PYTHON"
	install_python_packages

	touch .setup_complete
	rm -f "$LOG_FILE"

	ok "Installation complete."
	start_app "$@"
}

main "$@"; exit $?
