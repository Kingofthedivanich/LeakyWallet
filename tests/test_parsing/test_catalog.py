from LeakyWallet.db.models.service import ServiceCategory
from LeakyWallet.parsing.catalog import all_domains, get_entry, load_catalog, match_sender


def test_load_catalog_returns_real_entries() -> None:
    catalog = load_catalog()
    slugs = {entry.slug for entry in catalog}
    assert "netflix" in slugs
    assert "spotify" in slugs


def test_load_catalog_assigns_category_to_every_entry() -> None:
    for entry in load_catalog():
        assert isinstance(entry.category, ServiceCategory)


def test_get_entry_category() -> None:
    entry = get_entry("netflix")
    assert entry is not None
    assert entry.category == ServiceCategory.STREAMING


def test_all_domains_flattens_catalog() -> None:
    domains = all_domains()
    assert "netflix.com" in domains
    assert "spotify.com" in domains


def test_get_entry_by_slug() -> None:
    entry = get_entry("netflix")
    assert entry is not None
    assert entry.name == "Netflix"
    assert "netflix.com" in entry.domain_patterns


def test_get_entry_unknown_slug_returns_none() -> None:
    assert get_entry("does-not-exist") is None


def test_match_sender_finds_known_domain() -> None:
    entry = match_sender("Netflix <billing@netflix.com>")
    assert entry is not None
    assert entry.slug == "netflix"


def test_match_sender_returns_none_for_unknown_domain() -> None:
    assert match_sender("Someone <hi@unrelated-domain.example>") is None
