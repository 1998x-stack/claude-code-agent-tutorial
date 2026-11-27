"""Fail-closed sandbox *manifest checker*, not a sandbox or shell executor.

Even a safe argv array is not a security boundary: execution needs an actual
OS sandbox, filesystem/network confinement, resource accounting and testing.
"""
from __future__ import annotations
from dataclasses import dataclass
import ipaddress
import re
from pathlib import PurePosixPath, PureWindowsPath


def _valid_host(host: str) -> bool:
    if not isinstance(host, str) or not host or len(host) > 253 or host != host.strip():
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    if any(ch in host for ch in "/\\:@*?#") or any(ord(ch) < 33 for ch in host):
        return False
    value = host[:-1] if host.endswith(".") else host
    labels = value.split(".")
    return bool(value) and all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in labels
    )


def _safe_relative_path(value: str) -> bool:
    if not isinstance(value, str) or not value or len(value) > 512:
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value) or "\\" in value or ":" in value:
        return False
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    return (not posix.is_absolute() and not windows.is_absolute() and not windows.drive
            and bool(posix.parts) and all(p not in {"..", "."} for p in posix.parts))


@dataclass(frozen=True)
class SandboxManifest:
    enabled: bool
    fail_if_unavailable: bool
    allow_unsandboxed_retry: bool
    network_hosts: frozenset[str]
    writable_subdirs: frozenset[str]

    def validate(self) -> None:
        if type(self.enabled) is not bool or type(self.fail_if_unavailable) is not bool:
            raise ValueError("sandbox flags must be booleans")
        if type(self.allow_unsandboxed_retry) is not bool:
            raise ValueError("unsandboxed retry flag must be a boolean")
        if not self.enabled or not self.fail_if_unavailable:
            raise ValueError("refuse without a required sandbox")
        if self.allow_unsandboxed_retry:
            raise ValueError("unsandboxed retry is forbidden")
        if not isinstance(self.network_hosts, frozenset) or any(
                not _valid_host(host) for host in self.network_hosts):
            raise ValueError("network_hosts must be a set of valid hostnames or IPs")
        if not isinstance(self.writable_subdirs, frozenset) or any(
                not _safe_relative_path(folder) for folder in self.writable_subdirs):
            raise ValueError("writable directories must be safe relative paths")


@dataclass(frozen=True)
class EffectRequest:
    command_label: str
    writes_to: str | None = None
    connects_to: str | None = None
    unsandboxed: bool = False

    def __post_init__(self):
        if not isinstance(self.command_label, str) or not self.command_label:
            raise ValueError("command_label must be nonempty text")
        if self.writes_to is not None and not isinstance(self.writes_to, str):
            raise ValueError("writes_to must be text or None")
        if self.connects_to is not None and not isinstance(self.connects_to, str):
            raise ValueError("connects_to must be text or None")
        if type(self.unsandboxed) is not bool:
            raise ValueError("unsandboxed must be a boolean")


def preview(manifest: SandboxManifest, request: EffectRequest) -> tuple[bool, str]:
    """A defense-in-depth preflight. NEVER pass this result as OS authorization."""
    if not isinstance(manifest, SandboxManifest) or not isinstance(request, EffectRequest):
        return False, "invalid manifest or request"
    manifest.validate()
    if request.unsandboxed:
        return False, "unsandboxed execution denied"
    if request.command_label not in {"inspect", "test", "format-preview"}:
        return False, "unknown command profile"
    if request.connects_to:
        allowed = {host.casefold() for host in manifest.network_hosts}
        if request.connects_to.casefold() not in allowed:
            return False, "unapproved network destination"
    if request.writes_to:
        if not _safe_relative_path(request.writes_to):
            return False, "unsafe or absolute write path"
        path = PurePosixPath(request.writes_to)
        if not any(path == PurePosixPath(subdir)
                   or PurePosixPath(subdir) in path.parents
                   for subdir in manifest.writable_subdirs):
            return False, "outside writable workspace"
    return True, "manifest preflight accepts this declared effect; OS still enforces"


if __name__ == "__main__":
    cfg = SandboxManifest(True, True, False, frozenset(), frozenset({"scratch"}))
    print(preview(cfg, EffectRequest("test", writes_to="scratch/results.txt")))
