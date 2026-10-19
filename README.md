# Vakint external data

Versioned native RustRed reductions, master-integral Laurent coefficients and
graphs, and prepared reduction caches for [Vakint](https://github.com/alphal00p/vakint).
The data originates in Vakint's former `artifacts` directory; original payloads
and their migration checksums are retained.

Each release has separate `1L` through `5L` compressed packs. Loading a maximum
loop count installs all packs up to that count. `data-latest` points to the
current immutable release through its `manifest.json`; exact versions remain
available independently.

```python
engine.load_official_external_data(4)
engine.load_official_external_data(4, version="v0.1.0", local_artifacts_path="/path/to/data")
```

A checkout of this repository can be passed directly as `local_artifacts_path`
and is validated without network access. Source manifests leave archive hashes
unset; release manifests contain them. All loop-manifest paths are relative to
their loop directory.

1L–4L contain 115 computed masters in total. The 905 declared 5L campaign
terminals have graphs and exact identities, but **no computed coefficients**.
Their nominal epsilon ranges are provenance, not available numerical data.
Prepared 1L–4L caches complete a declared finite workload; this does not certify
arbitrary-index IBP coverage. See `coverage.json` and `cache.json` in each pack.

Run `python3 tools/data.py validate` to verify payloads, coefficient availability,
cache completion receipts and migration hashes. Release and authorship
instructions are in [AUTHORING.typ](AUTHORING.typ).
