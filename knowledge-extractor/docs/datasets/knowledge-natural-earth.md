# knowledge/natural-earth

Sovereignty chains and subnational admin hierarchies from the
[Natural Earth](https://www.naturalearthdata.com/) 10m cultural vector
dataset. The headline feature is the **sovereignty relation**: 45 real
dependency chains like French Guiana→France, Greenland→Denmark, Hong
Kong→China — information that no other dataset in this project carries.

The secondary value is **admin-1 coverage**: 4,500 subnational regions
(states, provinces, counties, regions) linked to their parent countries
with ISO 3166-2 codes where available. This bridges the gap between
country-level data (`knowledge/countries`) and point-level data
(`knowledge/osm-gb`) in the spatial hierarchy.

- **Upstream**: https://www.naturalearthdata.com/ via the naciscdn mirror
- **Access**: two shapefile ZIPs (~20 MB total): `ne_10m_admin_0_countries` and `ne_10m_admin_1_states_provinces`
- **Licence**: public domain (Natural Earth). No attribution required.
- **Layer band**: `knowledge`
- **Scale**: ~15,400 triples across 15 relations

## Relations produced

### admin_0 (countries + dependencies)

| relation | example | source column |
|---|---|---|
| `sovereignty` | (French Guiana, France) | NAME → SOVEREIGNT, gated on ADM0_A3 ≠ SOV_A3 |
| `ne_type` | (French Guiana, Dependency) | TYPE |
| `continent_ne` | (French Guiana, South America) | CONTINENT |
| `region_un` | (French Guiana, Americas) | REGION_UN |
| `subregion_un` | (French Guiana, South America) | SUBREGION |
| `region_wb` | (French Guiana, Latin America & Caribbean) | REGION_WB |
| `economy_class` | (Indonesia, Emerging region: MIKT) | ECONOMY (numeric prefix stripped) |
| `income_group` | (Indonesia, Lower middle income) | INCOME_GRP (numeric prefix stripped) |
| `iso_alpha2` | (French Guiana, GF) | ISO_A2 |
| `iso_alpha3` | (French Guiana, GUF) | ISO_A3 |
| `iso_numeric` | (French Guiana, 254) | ISO_N3 |
| `wikidata_id` | (French Guiana, Q3769) | WIKIDATAID |

### admin_1 (subnational regions)

| relation | example | source column |
|---|---|---|
| `within` | (England, United Kingdom) | NAME → ADMIN |
| `iso_3166_2` | (England, GB-ENG) | ISO_3166_2 |
| `admin_type` | (England, Country) | TYPE_EN |

## Sovereignty logic

Not every entity with a `SOVEREIGNT` column gets a sovereignty triple.
The extractor checks:

1. **`ADM0_A3 ≠ SOV_A3`** — NE assigns each entity its own admin code
   and a separate sovereign code. When they differ, the entity is a real
   dependency. When they match, NAME may still differ from SOVEREIGNT
   (e.g. "Tanzania" vs "United Republic of Tanzania") but it's the
   same political entity — not a sovereignty chain.
2. **`TYPE ∉ {Indeterminate, Disputed}`** — NE marks contested
   territories with these types. We don't emit a sovereignty triple
   because the relationship is unresolved. The TYPE itself is still
   emitted via `ne_type` so consumers can see the status.

This produces 45 clean sovereignty chains — all genuine dependencies
like British Overseas Territories, French overseas departments, US
territories, Danish self-governing territories, Chinese SARs.

## Provenance

- **admin_0**: `ne_admin0:<ADM0_A3>` (e.g. `ne_admin0:GUF`). Uses
  ADM0_A3 rather than ISO_A3 because many dependencies have `ISO_A3=-99`
  (no ISO code assigned) but always have an NE admin code.
- **admin_1**: `ne_admin1:<ISO_3166_2>` when available (e.g.
  `ne_admin1:GB-ENG`), otherwise bare `ne_admin1`.

## Dependencies

This dataset is behind the `natural-earth` optional extra because
`pyshp` (pure Python shapefile reader) is needed:

```bash
cd knowledge-extractor && uv sync --extra natural-earth
```

## Running

```bash
make run-natural-earth              # from the monorepo root
# or
uv run knowledge-extractor run knowledge/natural-earth
```

The download phase fetches two shapefile ZIPs (~20 MB total) from the
naciscdn mirror and extracts them. The extract phase reads the DBF
attribute tables — no geometry is used — and yields triples. Both
phases take a few seconds.

## Caveats

- **No geometry emitted.** The shapefiles contain detailed polygons
  (country and admin-1 boundaries) but we only read the DBF attribute
  tables. If geometry is needed later, extend the extractor to produce
  centroid triples in the same `at_coords` / `in_geohash` style as
  `knowledge/osm-gb`.
- **NE name conventions.** Natural Earth uses abbreviated short names
  (`S. Sudan`, `Fr. Polynesia`, `N. Mariana Is.`) that differ from
  ISO/UN canonical names. The normaliser lowercases them, which is
  fine, but downstream joiners matching against `knowledge/countries`
  should be fuzzy — `"s. sudan"` ≠ `"south sudan"`.
- **REGION_WB is sparse.** Only ~67 entities have the World Bank region
  column populated. Other region/subregion columns are fuller.
- **admin_1 coverage varies by country.** Well-mapped countries like
  the UK, US, France have complete admin-1 records. Less-mapped ones
  may be missing subdivisions entirely.
- **NE's TYPE for disputed territories.** Palestine, Western Sahara,
  Northern Cyprus, Kosovo, etc. are present in admin_0 with
  `ne_type=Indeterminate` or `ne_type=Disputed` but do not get a
  sovereignty triple (see logic above). They do get iso/continent/
  region triples if available.
- **Numeric prefixes stripped.** NE's ECONOMY and INCOME_GRP columns
  carry sort prefixes like `"2. Developed region: non-G7"`. The
  extractor strips the `"2. "` prefix so the triple object is a clean
  text token. If you need the ordinal for sorting, read the raw DBF
  directly.

## Example output

`datasets/extracted/knowledge/natural-earth/sovereignty.json`:
```json
{
  "source": "natural-earth",
  "relation": "sovereignty",
  "layer_band": "knowledge",
  "pair_count": 45,
  "pairs": [
    ["french guiana", "france"],
    ["greenland", "denmark"],
    ["hong kong", "china"],
    ["dhekelia", "united kingdom"]
  ]
}
```

`datasets/extracted/knowledge/natural-earth/within.json`:
```json
{
  "source": "natural-earth",
  "relation": "within",
  "layer_band": "knowledge",
  "pair_count": 4505,
  "pairs": [
    ["england", "united kingdom"],
    ["scotland", "united kingdom"],
    ["bavaria", "germany"],
    ["california", "united states of america"]
  ]
}
```
