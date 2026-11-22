"""Evidence checklist for reviewing third-party agent ecosystem resources.

This does not fetch repositories or assign a trust score. A reviewer must
verify each item against the current source, release and runtime behavior.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse


@dataclass(frozen=True)
class ResourceEvidence:
    name: str
    url: str
    checked_on: date
    archived: bool
    license_id: str | None
    version_or_commit_pinned: bool
    permissions_reviewed: bool
    network_behavior_reviewed: bool
    data_handling_reviewed: bool
    dependencies_reviewed: bool

    def gaps(self, *, today: date, max_age_days: int = 90) -> tuple[str, ...]:
        if not self.name.strip():
            raise ValueError("resource name is required")
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("resource URL must be HTTPS")
        if self.checked_on > today:
            raise ValueError("verification date cannot be in the future")
        if max_age_days < 0:
            raise ValueError("max_age_days cannot be negative")
        issues = []
        if self.archived:
            issues.append("repository is archived")
        if (today - self.checked_on).days > max_age_days:
            issues.append("evidence is stale; re-check current source and release")
        if not self.license_id or self.license_id.upper() in {"NOASSERTION", "UNKNOWN"}:
            issues.append("license has not been confirmed")
        if not self.version_or_commit_pinned:
            issues.append("installation is not pinned to a reviewed version or commit")
        if not self.permissions_reviewed:
            issues.append("hooks, scripts, binaries and tool permissions are unreviewed")
        if not self.network_behavior_reviewed:
            issues.append("network destinations and outbound data are unreviewed")
        if not self.data_handling_reviewed:
            issues.append("prompt, source-code and telemetry handling are unreviewed")
        if not self.dependencies_reviewed:
            issues.append("dependency and supply-chain review is incomplete")
        return tuple(issues)


if __name__ == "__main__":
    candidate = ResourceEvidence(
        name="example-plugin",
        url="https://github.com/example/plugin",
        checked_on=date(2026, 11, 22),
        archived=False,
        license_id=None,
        version_or_commit_pinned=False,
        permissions_reviewed=False,
        network_behavior_reviewed=False,
        data_handling_reviewed=False,
        dependencies_reviewed=False,
    )
    print("\n".join(candidate.gaps(today=date.today())) or "review checklist complete")
