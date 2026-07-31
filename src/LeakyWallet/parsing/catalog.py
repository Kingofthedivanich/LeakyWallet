import functools
from dataclasses import dataclass
from pathlib import Path

import yaml

_SERVICES_YAML_PATH = Path(__file__).resolve().parents[3] / "data" / "services.yaml"


@dataclass(frozen=True)
class CatalogEntry:
    slug: str
    name: str
    domain_patterns: tuple[str, ...]
    cancel_url: str | None


@functools.lru_cache
def load_catalog() -> tuple[CatalogEntry, ...]:
    if not _SERVICES_YAML_PATH.exists():
        return ()
    with _SERVICES_YAML_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    entries = []
    for raw in data.get("services", []):
        entries.append(
            CatalogEntry(
                slug=raw["slug"],
                name=raw["name"],
                domain_patterns=tuple(raw.get("domain_patterns", [])),
                cancel_url=raw.get("cancel_url"),
            )
        )
    return tuple(entries)


def all_domains() -> tuple[str, ...]:
    domains: list[str] = []
    for entry in load_catalog():
        domains.extend(entry.domain_patterns)
    return tuple(domains)


def get_entry(slug: str) -> CatalogEntry | None:
    for entry in load_catalog():
        if entry.slug == slug:
            return entry
    return None


def match_sender(sender: str) -> CatalogEntry | None:
    sender_lower = sender.lower()
    for entry in load_catalog():
        if any(domain.lower() in sender_lower for domain in entry.domain_patterns):
            return entry
    return None
