from __future__ import annotations

import pytest

from engine.sandbox.policy.network import (
    NetworkMode,
    NetworkPolicy,
    NetworkPolicyError,
)


def test_default_network_is_disabled() -> None:
    policy = NetworkPolicy()

    policy.validate()

    assert not policy.network_enabled
    assert not policy.permits_ip("127.0.0.1", 80)
    assert not policy.permits_ip("8.8.8.8", 443)


def test_loopback_policy_only_allows_loopback() -> None:
    policy = NetworkPolicy(
        mode=NetworkMode.LOOPBACK,
    )

    assert policy.permits_ip("127.0.0.1", 8080)
    assert not policy.permits_ip("8.8.8.8", 8080)


def test_allowlist_is_explicit() -> None:
    policy = NetworkPolicy(
        mode=NetworkMode.ALLOWLIST,
        allow_hosts=("10.0.0.0/24",),
        allow_ports=(443,),
    )

    assert policy.permits_ip("10.0.0.25", 443)
    assert not policy.permits_ip("10.0.1.25", 443)
    assert not policy.permits_ip("10.0.0.25", 80)


def test_disabled_mode_rejects_allowlist() -> None:
    with pytest.raises(NetworkPolicyError):
        NetworkPolicy(
            allow_hosts=("10.0.0.1",),
        ).validate()
