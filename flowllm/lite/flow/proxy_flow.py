"""SSH SOCKS5 proxy flow for ``fl --proxy``."""

import os
import subprocess
import time

from loguru import logger

from ..cli import BaseConfig, BaseFlow, register

SSH_OPTS = {
    "StrictHostKeyChecking": "strict_host_key_checking",
    "ServerAliveInterval": "server_alive_interval",
    "ServerAliveCountMax": "server_alive_count_max",
    "ExitOnForwardFailure": "exit_on_forward_failure",
    "ConnectTimeout": "connect_timeout",
}


class ProxyConfig(BaseConfig):
    """Configuration for the SSH SOCKS5 proxy flow."""

    host: str = ""
    port: int = 12345
    user: str = "root"
    server_alive_interval: int = 30
    server_alive_count_max: int = 3
    connect_timeout: int = 10
    strict_host_key_checking: str = "no"
    exit_on_forward_failure: str = "yes"
    auto_restart: bool = True
    restart_interval: float = 3
    max_restarts: int = 0


@register("proxy")
class ProxyFlow(BaseFlow[ProxyConfig]):
    """Flow that starts an SSH dynamic SOCKS5 proxy."""

    output_keys = ["returncode"]

    def build_steps(self) -> list:
        """Return the proxy startup step."""
        return [self.build_cmd, self.run_proxy]

    def build_cmd(self) -> None:
        """Build the ssh command from flow configuration."""
        host = self.config.host or os.environ.get("DEFAULT_PROXY_HOST_ENV", "")
        if not host:
            raise ValueError("Proxy host is required. Set DEFAULT_PROXY_HOST_ENV or pass --host.")
        opts = [item for key, name in SSH_OPTS.items() for item in ("-o", f"{key}={getattr(self.config, name)}")]
        self.context["cmd"] = [
            "ssh",
            "-D",
            str(self.config.port),
            "-N",
            "-q",
            *opts,
            f"{self.config.user}@{host}",
        ]

    def run_proxy(self) -> None:
        """Start ssh and optionally restart it after unexpected exits."""
        cmd = self.context["cmd"]
        restarts = 0
        while True:
            logger.info("Starting ssh SOCKS5 proxy on port {} -> {}", cmd[2], cmd[-1])
            try:
                returncode = subprocess.run(cmd, check=False).returncode
            except KeyboardInterrupt:
                logger.info("Stopped")
                self.context["returncode"] = 0
                return

            self.context["returncode"] = returncode
            if not self.config.auto_restart or returncode == 0:
                return

            restarts += 1
            if self.config.max_restarts and restarts > self.config.max_restarts:
                return

            logger.warning("ssh exited with {}; restart #{}", returncode, restarts)
            time.sleep(self.config.restart_interval)
