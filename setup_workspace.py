"""Deploy workspace templates to ~/.nanobot/ for nanobot-ai.

Copies workspace files (SOUL.md, USER.md, HEARTBEAT.md) and config.json
from the repo's workspace/ directory to the nanobot home directory.

Requires a .env file with OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN,
and TELEGRAM_USER_ID. See .env.example for the format.

Usage:
    python setup_workspace.py
"""

import json
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent
WORKSPACE_SRC = REPO_ROOT / "workspace"
NANOBOT_HOME = Path.home() / ".nanobot"
NANOBOT_WORKSPACE = NANOBOT_HOME / "workspace"

TEMPLATE_FILES = ["SOUL.md", "USER.md", "HEARTBEAT.md"]

ENV_VARS = {
    "OPENROUTER_API_KEY": "OpenRouter API key",
    "TELEGRAM_BOT_TOKEN": "Telegram bot token",
    "TELEGRAM_USER_ID": "Telegram numeric user ID",
}


def load_env_file(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a dict of key-value pairs."""
    if not env_path.exists():
        raise FileNotFoundError(
            f".env file not found at {env_path}. "
            f"Copy .env.example to .env and fill in your credentials."
        )
    env_vars: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        env_vars[key.strip()] = value.strip()
    return env_vars


def validate_env_vars(env: dict[str, str]) -> None:
    """Ensure all required env vars are present and non-placeholder."""
    missing: list[str] = []
    for var_name, description in ENV_VARS.items():
        value = env.get(var_name, "")
        if not value or "your-key-here" in value or value == "123456789":
            missing.append(f"  {var_name} — {description}")
    if missing:
        raise ValueError(
            "Missing or placeholder values in .env:\n"
            + "\n".join(missing)
            + "\nSee .env.example for the expected format."
        )


def resolve_config_template(
    template_path: Path, env: dict[str, str]
) -> dict[str, object]:
    """Read config.json.template and resolve ${VAR} placeholders."""
    raw = template_path.read_text(encoding="utf-8")
    for var_name in ENV_VARS:
        placeholder = f"${{{var_name}}}"
        if placeholder in raw:
            raw = raw.replace(placeholder, env[var_name])
    return json.loads(raw)


def copy_workspace_files(target_dir: Path) -> list[str]:
    """Copy workspace template files to target directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for filename in TEMPLATE_FILES:
        src = WORKSPACE_SRC / filename
        if not src.exists():
            raise FileNotFoundError(
                f"Workspace template {filename} not found at {src}"
            )
        dst = target_dir / filename
        shutil.copy2(src, dst)
        copied.append(filename)
        log.info("Copied %s -> %s", filename, dst)
    return copied


def write_config(config: dict[str, object], target: Path) -> None:
    """Write resolved config.json to target path."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log.info("Wrote config.json -> %s", target)


def create_required_dirs() -> None:
    """Create nanobot directories that the framework expects."""
    for subdir in ["media", "cron", "logs", "sessions", "workspace/memory"]:
        path = NANOBOT_HOME / subdir
        path.mkdir(parents=True, exist_ok=True)


def setup_workspace() -> None:
    """Main setup: load env, resolve config, copy workspace files."""
    env_path = REPO_ROOT / ".env"
    env = load_env_file(env_path)
    validate_env_vars(env)

    config_template = WORKSPACE_SRC / "config.json.template"
    config = resolve_config_template(config_template, env)

    create_required_dirs()
    copy_workspace_files(NANOBOT_WORKSPACE)
    write_config(config, NANOBOT_HOME / "config.json")

    log.info("")
    log.info("Workspace deployed to %s", NANOBOT_HOME)
    log.info("Start the bot with: nanobot gateway")


if __name__ == "__main__":
    try:
        setup_workspace()
    except (FileNotFoundError, ValueError) as err:
        log.error("Setup failed: %s", err)
        sys.exit(1)
