"""Fail-closed sandbox *manifest checker*, not a sandbox or shell executor.

Even a safe argv array is not a security boundary: execution needs an actual
OS sandbox, filesystem/network confinement, resource accounting and testing.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class SandboxManifest:
    enabled: bool
    fail_if_unavailable: bool
    allow_unsandboxed_retry: bool
    network_hosts: frozenset[str]
    writable_subdirs: frozenset[str]

    def validate(self) -> None:
        if not self.enabled or not self.fail_if_unavailable:
            raise ValueError("refuse without a required sandbox")
        if self.allow_unsandboxed_retry:
            raise ValueError("unsandboxed retry is forbidden")
        for folder in self.writable_subdirs:
            path = PurePosixPath(folder)
            if (not folder or path.is_absolute()
                    or ".." in path.parts or "." in path.parts):
                raise ValueError("writable directory must be a safe relative path")
        if any(not host or "/" in host or ":" in host for host in self.network_hosts):
            raise ValueError("network hosts must be host names only")


@dataclass(frozen=True)
class EffectRequest:
    command_label: str
    writes_to: str | None = None
    connects_to: str | None = None
    unsandboxed: bool = False


def preview(manifest: SandboxManifest, request: EffectRequest) -> tuple[bool, str]:
    """A defense-in-depth *preflight*. NEVER pass this result as OS authorization."""
    manifest.validate()
    if request.unsandboxed:
        return False, "unsandboxed execution denied"
    if request.command_label not in {"inspect", "test", "format-preview"}:
        return False, "unknown command profile"
    if request.connects_to and request.connects_to not in manifest.network_hosts:
        return False, "unapproved network destination"
    if request.writes_to:
        path = PurePosixPath(request.writes_to)
        if (path.is_absolute() or ".." in path.parts or "." in path.parts
                or not path.parts):
            return False, "path escape"
        if not any(path == PurePosixPath(subdir)
                   or PurePosixPath(subdir) in path.parents
                   for subdir in manifest.writable_subdirs):
            return False, "outside writable workspace"
    return True, "manifest preflight accepts this declared effect; OS still enforces"


if __name__ == "__main__":
    cfg = SandboxManifest(True, True, False, frozenset(), frozenset({"scratch"}))
    print(preview(cfg, EffectRequest("test", writes_to="scratch/results.txt")))
