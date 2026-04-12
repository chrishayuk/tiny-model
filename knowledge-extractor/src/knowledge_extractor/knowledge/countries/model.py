"""Hand-curated country reference data.

This dataset has no external source to download — the tables in ``_data.py``
are the authoritative copy. Edit in place to extend coverage. The
downloader is a no-op that always reports ready; the extractor walks the
tables and yields one triple per country-field pair.

Sources combined in ``_data.py``:

- **ISO 3166-1** — alpha-2, alpha-3, and numeric country codes
- **UN M49**    — region and subregion classification
- **ISO 4217**  — currency codes
- **E.164**     — international calling codes
- **IANA**      — country-code top-level domains
- **UN member list** — membership flag
"""

from __future__ import annotations

from ...base import DatasetMeta, RawLayout
from ._data import COUNTRIES


META = DatasetMeta(
    name="countries",
    category="knowledge",
    version="2026-04",
    license="public domain (hand-curated from ISO/UN/IANA sources)",
    url="https://www.iso.org/iso-3166-country-codes.html",
    layer_band="knowledge",
    description="ISO 3166 + UN country reference: codes, capitals, regions, currencies, languages",
)


class CountriesRawLayout(RawLayout):
    """Countries has no raw artifacts — layout is a marker only."""

    def verify(self) -> bool:
        return True


# Mapping from dict key → relation name. Keys not in this map are not
# emitted; this makes adding / renaming a relation a one-line change.
SCALAR_RELATIONS: list[tuple[str, str]] = [
    ("alpha2",        "iso_alpha2"),
    ("alpha3",        "iso_alpha3"),
    ("numeric",       "iso_numeric"),
    ("capital",       "capital"),
    ("continent",     "continent"),
    ("region",        "region"),
    ("subregion",     "subregion"),
    ("currency",      "currency"),
    ("currency_name", "currency_name"),
    ("calling_code",  "calling_code"),
    ("tld",           "tld"),
]


__all__ = ["META", "COUNTRIES", "CountriesRawLayout", "SCALAR_RELATIONS"]
