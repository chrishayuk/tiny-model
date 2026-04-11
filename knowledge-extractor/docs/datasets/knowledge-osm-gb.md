# knowledge/osm-gb

Named places and points of interest from the Geofabrik Great Britain
extract of OpenStreetMap. This is the **breadth** layer of the knowledge
band: where `knowledge/wikidata` has curated facts about famous entities,
this dataset has every kebab shop, every village hall, every named hill.
Entities carry per-instance geometry (lat/lon plus a 7-character geohash)
so the model can learn geographic proximity, not just membership.

- **Upstream**: https://download.geofabrik.de/europe/great-britain.html
- **Access**: single PBF file (`great-britain-latest.osm.pbf`, ~2 GB as of 2026-04), read with [pyosmium](https://osmcode.org/pyosmium/)
- **Licence**: [Open Database License 1.0](https://www.openstreetmap.org/copyright) — share-alike with attribution to OpenStreetMap contributors
- **Layer band**: `knowledge`
- **Scale**: ~2–5M pairs on a full GB extract (see calibration note below)

## Relations produced

Two relation families are emitted, using two different subject schemes.

**Semantic** — bare `<name>` subjects. Chain stores collapse on dedup so
`"Starbucks is_a cafe"` appears once regardless of how many branches are
tagged. This is the "type view" of an entity.

| relation | direction | example | source tag |
|---|---|---|---|
| `is_a` | directed | (The British Museum, museum) | primary tag value |
| `located_in` | directed | (The British Museum, London) | `addr:city` |
| `has_cuisine` | directed | (Pizza Express, italian) | `cuisine` (splits on `;`) |
| `has_brand` | directed | (Pizza Express Soho, Pizza Express) | `brand` (only when ≠ name) |
| `wikidata_id` | directed | (The British Museum, Q6373) | `wikidata` |

**Geometry** — per-instance subjects `<name>#<kind><osm_id>` (e.g.
`The British Museum#w16217891`). Every branch of a chain keeps its own
geometry. A `has_name` bridge triple lets you join the two views.

| relation | direction | example | source |
|---|---|---|---|
| `has_name` | directed | (Pizza Express Soho#n123, Pizza Express Soho) | bridge back to the semantic view |
| `at_coords` | directed | (The British Museum#w16217891, `51.51943,-0.12700`) | node location or way centroid, 5-dp precision |
| `in_geohash` | directed | (The British Museum#w16217891, `gcpvj4g`) | 7-char geohash (~150 m cell) |

All directional relations are emitted once. Chain-store collapse is
intentional at the semantic level — it's the dedup of `(subject, object)`
pairs that does it.

## Entity filter

Not every OSM node becomes a triple. The extractor skips anything without
a usable `name` tag or whose primary tag isn't in the whitelist.

| key | accepted values |
|---|---|
| `amenity` | restaurant, cafe, pub, bar, fast_food, bank, pharmacy, hospital, clinic, school, university, college, library, theatre, cinema, museum, arts_centre, place_of_worship, post_office, townhall |
| `shop` | any value |
| `tourism` | hotel, guest_house, hostel, motel, attraction, museum, gallery, viewpoint, artwork, zoo, aquarium, theme_park |
| `historic` | castle, monument, memorial, ruins, church, archaeological_site, fort, manor, tower, wayside_cross |
| `leisure` | park, stadium, sports_centre, nature_reserve, golf_course, garden |
| `natural` | peak, water, cape, bay, beach |

Name filter: 3 ≤ `len(name)` ≤ 100, not purely numeric, trimmed. To
extend coverage, edit `PRIMARY_TAGS` in
`src/knowledge_extractor/knowledge/osm_gb/model.py` and re-run.

## Geometry resolution

- **Nodes**: `node.location.{lat,lon}` used directly.
- **Ways** (most named buildings and parks): centroid = arithmetic mean
  of the constituent nodes' coordinates. Requires the pbf to be walked
  with `locations=True`, which pyosmium resolves inline.
- **Relations** (large multi-polygon features): **skipped.** Resolving
  multi-polygon geometry requires a second pass and an area manager;
  most named POIs are nodes or ways, so this is a deliberate deferral.

## Provenance

Every emitted triple carries `provenance = "osm:<kind>:<osm_id>"` where
kind is `n` for node, `w` for way. Instance subjects embed the same
information in `<name>#<kind><osm_id>`, so you can always trace a
geometry triple back to the originating OSM element.

## Dependencies

- `pip` (optional extra): `osmium>=3.7`
  ```bash
  cd knowledge-extractor && uv sync --extra osm
  ```
- **Build deps** (only when osmium falls back to source): libosmium,
  expat, zlib headers. Mainstream platforms get binary wheels from PyPI
  and don't need these.

The import is deferred — `osmium` is only loaded inside `extract()` so
the rest of the registry keeps working on an install without the extra.

## Calibration

Smoke-tested against the Isle of Man Geofabrik extract (5.6 MB PBF):

| relation | count |
|---|---:|
| `is_a` | 2,052 |
| `has_name` | 2,052 |
| `at_coords` | 2,052 |
| `in_geohash` | 2,052 |
| `located_in` | 942 |
| `wikidata_id` | 286 |
| `has_cuisine` | 169 |
| `has_brand` | 8 |
| **total** | **9,613** |

The full GB extract is ~270× the size of Isle of Man so a linear
extrapolation suggests ~2.5M triples, though density is lower outside
urban cores — expect the real number in the 2–5M range.

## Caveats

- **Licence is ODbL, not CC0.** Triples derived from this dataset are a
  derivative database. Downstream consumers must attribute OpenStreetMap
  contributors (`© OpenStreetMap contributors`) and share derivatives
  under the same licence. This is stricter than your other knowledge-band
  sources and should be surfaced in the compiled model's licence note.
- **Chain store collapse is intentional at the semantic layer.** The
  dedup means you see `Starbucks is_a cafe` exactly once. The geometry
  layer preserves every branch via `<name>#<osm_id>` subjects, but the
  cardinality of the chain is lost from the `is_a` triple — you know the
  relation exists, not how many times.
- **Tag noise.** OSM is volunteer-tagged. Mis-classified entities (a pub
  tagged `amenity=restaurant`, a shop tagged with the wrong `shop=`
  value) will produce spurious triples. The name / primary-tag filter
  catches gross issues but not semantic ones.
- **Name is the subject.** Two unrelated places sharing a name (e.g. two
  "Royal Hotel" pubs in different towns) collapse in the semantic layer
  to one `is_a hotel` triple but get separate `#<osm_id>` geometry
  entries. A downstream joiner should not assume `has_name` is
  functional — it can point at the same name from many instances.
- **Relations skipped.** Entities modelled as OSM relations (large
  multi-polygons like the boundary of a nature reserve) aren't emitted.
  The cost of adding them is a second pass with `osmium.area.AreaManager`
  and the complexity isn't worth it for v1.
- **Scoped to GB.** This extractor is hard-coded to the Geofabrik GB
  extract. To add another country, copy the folder to
  `knowledge/osm_<cc>/`, change `GEOFABRIK_URL`, `PBF_FILENAME`, and
  `META.name`, and register it in `registry.py`. A single multi-country
  dataset would be cleaner but is a design question for later.

## Example output

`datasets/extracted/knowledge/osm-gb/is_a.json`:
```json
{
  "source": "osm-gb",
  "relation": "is_a",
  "layer_band": "knowledge",
  "pair_count": 2052,
  "pairs": [
    ["The British Museum", "museum"],
    ["Pizza Express Soho", "restaurant"],
    ["Starbucks", "cafe"]
  ]
}
```

`datasets/extracted/knowledge/osm-gb/at_coords.json`:
```json
{
  "source": "osm-gb",
  "relation": "at_coords",
  "layer_band": "knowledge",
  "pair_count": 2052,
  "pairs": [
    ["The British Museum#w16217891", "51.51943,-0.12700"],
    ["Pizza Express Soho#n455952597", "54.14896,-4.47555"]
  ]
}
```

## Attribution

Any downstream use of these triples must display:

> © OpenStreetMap contributors — https://www.openstreetmap.org/copyright
