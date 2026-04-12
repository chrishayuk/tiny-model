# knowledge/countries

Hand-curated country reference data combining ISO 3166-1 codes, UN M49
region classifications, ISO 4217 currencies, E.164 calling codes, IANA
ccTLDs, and UN membership. Every country gets ~13 triples, no external
downloads, ~200 lines of data that can be edited by hand.

This is the **foundation layer** of the spatial-coverage cluster:
everything else — natural-earth, osm-boundaries, geonames, postcodes —
references country codes that this dataset owns.

- **Upstream**: [ISO 3166-1](https://www.iso.org/iso-3166-country-codes.html), [UN M49](https://unstats.un.org/unsd/methodology/m49/), [ISO 4217](https://www.iso.org/iso-4217-currency-codes.html), [E.164](https://www.itu.int/rec/T-REC-E.164), [IANA root zone](https://www.iana.org/domains/root/db)
- **Access**: hand-curated Python literals in `_data.py`
- **Licence**: public domain (facts), extractor code Apache-2.0
- **Layer band**: `knowledge`
- **Scale**: ~900 pairs across 13 relations on the v1 data (70 countries)

## Relations produced

| relation | example | source field |
|---|---|---|
| `iso_alpha2` | (United Kingdom, GB) | ISO 3166-1 alpha-2 |
| `iso_alpha3` | (United Kingdom, GBR) | ISO 3166-1 alpha-3 |
| `iso_numeric` | (United Kingdom, 826) | ISO 3166-1 numeric |
| `capital` | (United Kingdom, London) | canonical capital city |
| `continent` | (United Kingdom, Europe) | continental landmass |
| `region` | (United Kingdom, Europe) | UN M49 region |
| `subregion` | (United Kingdom, Northern Europe) | UN M49 subregion |
| `currency` | (United Kingdom, GBP) | ISO 4217 code |
| `currency_name` | (United Kingdom, Pound sterling) | ISO 4217 full name |
| `calling_code` | (United Kingdom, +44) | E.164 country code |
| `tld` | (United Kingdom, .uk) | IANA ccTLD |
| `official_language` | (Switzerland, German), (Switzerland, French), ... | multi-valued, one triple per language |
| `un_member` | (United Kingdom, yes) | UN member states only; non-members get no triple |

## Provenance

Every emitted triple carries `provenance = "iso3166:<alpha3>"` (e.g.
`iso3166:GBR`). The alpha3 code is globally unique and more robust as a
join key than the country name, which can drift between English
variants.

## Dependencies

None. Reads Python literals. Runs in ~1 ms.

## Coverage

v1 covers 70 countries: the complete G20 plus all major European,
Asian, African, and American countries plus a handful of notable micro-
states (Monaco, Vatican City, Luxembourg). Every continent is
represented.

Extending to the full 249 ISO 3166-1 entries is a **data-only change**:
append a dict to `COUNTRIES` in
`src/knowledge_extractor/knowledge/countries/_data.py` with the same
keys as existing entries. The extractor and tests pick it up
automatically (the parametrised integrity tests run against every
country in the list).

Acceptance for "v2 coverage": every UN member state present (193
countries → ~2,500 triples) plus the commonly-queried dependent
territories.

## Caveats

- **City-states emit no `capital` triple.** Monaco, Vatican City, and
  Singapore all have a capital that equals their country name, which
  the normaliser's self-loop filter drops. This is semantically
  unavoidable without changing the self-loop rule, and the information
  is recoverable: anything with `iso_alpha2` is implicitly its own
  capital if no other is given. Luxembourg avoided this by using
  "Luxembourg City" as the canonical capital.
- **Taiwan is included as a non-UN-member.** Political status is
  complex; the dataset models it with the ISO 3166-1 codes that exist
  (`TW`, `TWN`, `158`) and `un_member = False`. Downstream consumers
  can decide how to handle the distinction.
- **Name is the canonical short English form**, not the official full
  name. So "United Kingdom" not "United Kingdom of Great Britain and
  Northern Ireland"; "South Korea" not "Republic of Korea"; "Russia"
  not "Russian Federation". This matches what models see in training
  data.
- **One language per triple.** Countries with multiple official
  languages (Switzerland: German/French/Italian/Romansh; Canada:
  English/French; South Africa: 4 listed) emit one triple per
  language. Order is the order in `_data.py` which is not normative.
- **Capital is a single canonical choice.** Some countries have
  multiple de jure / de facto capitals (South Africa: Pretoria /
  Cape Town / Bloemfontein). The dataset emits one; the others are
  omitted. Fix in `_data.py` if this matters for a probe.
- **Currency is the ISO 4217 primary.** Countries that accept multiple
  currencies (Zimbabwe pre-2019, Panama with USD+PAB) get the primary
  only.

## Example output

`datasets/extracted/knowledge/countries/capital.json`:
```json
{
  "source": "countries",
  "relation": "capital",
  "layer_band": "knowledge",
  "pair_count": 65,
  "pairs": [
    ["united kingdom", "london"],
    ["france", "paris"],
    ["germany", "berlin"]
  ]
}
```

`datasets/extracted/knowledge/countries/official_language.json`:
```json
{
  "source": "countries",
  "relation": "official_language",
  "layer_band": "knowledge",
  "pair_count": 95,
  "pairs": [
    ["switzerland", "german"],
    ["switzerland", "french"],
    ["switzerland", "italian"],
    ["switzerland", "romansh"]
  ]
}
```

(Subjects and objects come out lowercased by the permissive normaliser.)

## Extending

To add a country:

1. Open `src/knowledge_extractor/knowledge/countries/_data.py`
2. Append a new dict at the appropriate section:
   ```python
   {
       "name": "Eswatini",
       "alpha2": "SZ", "alpha3": "SWZ", "numeric": "748",
       "capital": "Mbabane",
       "continent": "Africa", "region": "Africa", "subregion": "Southern Africa",
       "currency": "SZL", "currency_name": "Swazi lilangeni",
       "calling_code": "+268", "tld": ".sz",
       "languages": ["Swazi", "English"], "un_member": True,
   },
   ```
3. Re-run: `make run-countries`
4. `pytest tests/test_countries.py` re-validates.

The parametrised integrity tests (`test_country_has_required_fields`,
`test_iso_code_shapes`) run against every entry, so a missing field or
wrong-shape code is caught immediately.
