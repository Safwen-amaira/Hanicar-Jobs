"""Integration-style unit tests for identity + exclusion behaviour."""

from uuid import uuid4

from app.services.company_identity import normalize_name


def test_orange_aliases_collapse():
    variants = [
        "Orange Tunisie",
        "Orange Tunisia",
        "Orange TN",
        "Orange SA",
        "ORANGE",
    ]
    norms = {normalize_name(v) for v in variants}
    # All should share the same core token "orange"
    assert all("orange" == n or n.startswith("orange") for n in norms)
    assert len({normalize_name(v) for v in ["Orange Tunisie", "Orange Tunisia", "Orange TN", "Orange SA"]}) == 1


def test_exclusion_statuses_defined():
    from app.services.exclusion import SUPPRESSING_STATUSES
    from app.models import ContactStatus

    assert ContactStatus.contacted in SUPPRESSING_STATUSES
    assert ContactStatus.applied in SUPPRESSING_STATUSES
    assert ContactStatus.none not in SUPPRESSING_STATUSES
