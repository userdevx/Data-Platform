from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum


class NetworkPolicyError(ValueError):
    pass


class NetworkMode(str, Enum):
    DISABLED = "disabled"
    LOOPBACK = "loopback"
    ALLOWLIST = "allowlist"


@dataclass(frozen=True)
class NetworkPolicy:
    mode: NetworkMode = NetworkMode.DISABLED
    allow_hosts: tuple[str, ...] = ()
    allow_ports: tuple[int, ...] = ()

    def validate(self) -> None:
        if self.mode is NetworkMode.DISABLED:
            if self.allow_hosts or self.allow_ports:
                raise NetworkPolicyError(
                    "disabled networking cannot have allowlists"
                )
            return

        if self.mode is NetworkMode.LOOPBACK:
            if self.allow_hosts or self.allow_ports:
                raise NetworkPolicyError(
                    "loopback mode cannot have external allowlists"
                )
            return

        if self.mode is NetworkMode.ALLOWLIST:
            if not self.allow_hosts:
                raise NetworkPolicyError(
                    "allowlist mode requires at least one host"
                )

            if not self.allow_ports:
                raise NetworkPolicyError(
                    "allowlist mode requires at least one port"
                )

            for port in self.allow_ports:
                if not isinstance(port, int) or not 1 <= port <= 65535:
                    raise NetworkPolicyError(
                        f"invalid network port: {port}"
                    )

    @property
    def network_enabled(self) -> bool:
        return self.mode is not NetworkMode.DISABLED

    def permits_ip(self, address: str, port: int) -> bool:
        self.validate()

        if self.mode is NetworkMode.DISABLED:
            return False

        ip = ipaddress.ip_address(address)

        if self.mode is NetworkMode.LOOPBACK:
            return ip.is_loopback

        if port not in self.allow_ports:
            return False

        for entry in self.allow_hosts:
            try:
                network = ipaddress.ip_network(
                    entry,
                    strict=False,
                )
            except ValueError:
                if entry == address:
                    return True
            else:
                if ip in network:
                    return True

        return False


DEFAULT_NETWORK_POLICY = NetworkPolicy()
