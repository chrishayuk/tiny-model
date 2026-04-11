# domain/standards

Hand-curated tables of IANA-registered network and web protocol metadata:
HTTP status codes, HTTP methods, DNS record types, TCP/UDP well-known ports,
MIME types, and TLS versions. Zero external dependencies — everything lives
in the extractor source file and is trivially editable.

Why a hand-curated dataset at all? Because these mappings are small, stable,
authoritative, and the alternative (scraping RFCs or the IANA registry CSVs)
is more maintenance for the same data. Add rows to the tables in
`src/knowledge_extractor/domain/standards/model.py` when you need more coverage.

- **Upstream**: IANA registries (https://www.iana.org/), RFC 7231, RFC 2616, RFC 1035, etc.
- **Licence**: public domain (facts), extractor code MIT
- **Layer band**: `knowledge`
- **Scale**: 127 pairs across 7 relations

## Relations produced

| relation | subject | object | count | example |
|---|---|---|---:|---|
| `http_status` | 3-digit code | reason phrase | 41 | `404` → `not found` |
| `http_method` | method name | description | 9 | `get` → `retrieve a resource` |
| `dns_record` | record type | description | 16 | `mx` → `mail exchange` |
| `tcp_port` | port number | service | 20 | `443` → `https` |
| `udp_port` | port number | service | 10 | `53` → `dns` |
| `mime_type` | type/subtype | common extension | 25 | `application/json` → `json` |
| `tls_version` | version label | status | 6 | `tls 1.3` → `current` |

## Provenance

All pairs carry `provenance = "iana"`. This is deliberately low-detail —
if you need per-pair citation, add a second mapping from key to RFC number
in the module and emit it as a separate relation like `rfc_reference`.

## Dependencies

None. Runs in ~50ms. This is the extractor the `examples/run_demo.py`
script uses as a smoke test.

## Caveats

- **Coverage is intentionally small.** 20 TCP ports, not 5000. The tables
  cover the everyday web stack a model is likely to encounter in code and
  prose. For exhaustive coverage, fetch the IANA CSVs directly — they're
  public and well-structured.
- **Subject types are mixed.** `http_status` subjects are stringified
  numbers (`"200"`), `dns_record` subjects are lowercase abbreviations
  (`"mx"`), `mime_type` subjects contain slashes (`"application/json"`).
  The permissive normaliser preserves all of these. Downstream compilation
  should treat the subject as an opaque token, not a structured value.
- **TLS version status is a judgment call.** "deprecated" vs "supported"
  vs "current" is accurate as of 2026-04 but will drift. Update the table
  when TLS 1.4 becomes a thing (don't hold your breath).
- **Hand curation is a feature, not a bug.** You can add domain-specific
  standards (websocket close codes, MQTT return codes, gRPC status codes)
  by editing one dict. No parser to maintain.

## Extending

To add a new table:

1. Define it as a `dict[str, str]` at the top of
   `src/knowledge_extractor/domain/standards/model.py`:
   ```python
   WEBSOCKET_CLOSE_CODES = {
       "1000": "normal closure",
       "1001": "going away",
       # ...
   }
   ```
2. Append it to the `TABLES` list in the same file:
   ```python
   TABLES = [
       ...,
       ("websocket_close", WEBSOCKET_CLOSE_CODES),
   ]
   ```
3. Re-run: `python3 -m knowledge_extractor.cli run domain/standards`

That's it. The pipeline handles normalisation, dedup, manifest, and output.

## Example output

`datasets/extracted/domain/standards/http_status.json`:
```json
{
  "source": "standards",
  "relation": "http_status",
  "layer_band": "knowledge",
  "pair_count": 41,
  "pairs": [
    ["100", "continue"],
    ["200", "ok"],
    ["404", "not found"],
    ["500", "internal server error"]
  ]
}
```

See [`examples/sample_output/domain/standards/`](../../examples/sample_output/domain/standards/)
for the full trimmed snapshot.
