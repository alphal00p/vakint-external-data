# Datasets

A dataset is a RustRed p library too large for this repository, kept as one compressed,
checksummed archive outside it. This directory holds only its light description: one
directory per dataset revision, `datasets/<revision>/`, with

- `DATASET.json` (schema `vakint.external-data.dataset.v1`): the archive (name, bytes,
  sha256), its parts in order (each below 2 GiB; their concatenation is the archive), the
  content (files, bytes, the sha256 of the per-file checksum list, the sha256 of the root
  and area manifests it restores) and the restore command;
- `SHA256SUMS`: the sha256 of every part and of the whole archive (`sha256sum -c` format);
- `p_integral-manifest.json`: a byte copy of the `p_integral/manifest.json` the dataset
  restores, which lists every library file with its sha256 and size;
- `p-master-catalogue.json`: the p master catalogue the library ships
  (`p_integral/p-library-<a>-<b>/p-master-catalogue.json` in the dataset, byte-identical);
- `README.md`: revision, sizes, where the archive is, how to restore and use it.

Nothing here is read by Vakint or by `tools/data.py`, and nothing here is part of a
release archive or of a managed install. The `p_integral/` area of this repository is
unchanged by a dataset: it keeps listing the 1L-4L library `p-library-1-4`.

A dataset is an overlay of a checkout of this repository at the release it names: its
archive holds `<revision>/manifest.json` (this release's `manifest.json` with only the key
`p_integral` changed), `<revision>/p_integral/manifest.json` (the area manifest, listing
the dataset's library instead of `p-library-1-4`) and the library directory. Restored over
a checkout of that release, it makes the checkout a root for
`Vakint::load_external_data(<checkout>, n)` (Python: `vakint.load_external_data`), whose
p library is then the dataset's library: Vakint checks every listed file (sha256 and size)
when it loads it, says once on stderr that the listed library supersedes the built-in one,
and ignores the unlisted `p-library-1-4/` with one stderr line. A restored checkout is a
working tree for loading, not a source tree: `tools/p_integral_area.py validate` reports the
unlisted `p-library-1-4/` files there; run the repository's checks on a clean checkout.
