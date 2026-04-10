"""Launch nanobot gateway and dashboard server as parallel processes.

Usage:
    python start.py

Starts both the Telegram bot (nanobot gateway) and the dashboard HTTP
server. Ctrl+C stops both. If either process dies, the other is also
terminated.
"""

import logging
import signal
import subprocess
import sys
import threading
from typing import NoReturn

from dashboard_api import create_dashboard_server, load_config_from_env

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("start")


def run_dashboard(shutdown_event: threading.Event) -> None:
    """Run the dashboard HTTP server until shutdown_event is set."""
    config = load_config_from_env()
    server = create_dashboard_server(config)
    server.timeout = 1.0
    while not shutdown_event.is_set():
        server.handle_request()
    server.server_close()
    log.info("Dashboard server stopped")


def main() -> NoReturn:
    shutdown_event = threading.Event()

    dashboard_thread = threading.Thread(
        target=run_dashboard,
        args=(shutdown_event,),
        daemon=True,
    )
    dashboard_thread.start()

    log.info("Starting nanobot gateway...")
    bot_process = subprocess.Popen(
        [sys.executable, "-m", "nanobot", "gateway"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    def handle_signal(signum: int, frame: object) -> None:
        log.info("Received signal %d, shutting down...", signum)
        shutdown_event.set()
        bot_process.terminate()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    exit_code = bot_process.wait()
    log.info("Nanobot exited with code %d", exit_code)

    shutdown_event.set()
    dashboard_thread.join(timeout=5)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
