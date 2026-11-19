# Dataset {{TO FILL FROM revision: rev.name}}: the 1L-5L p library

The RustRed p library `p-library-1-5` (scope 1-5 loops, schema `rustred.p-owner-library.v1`),
package revision `{{TO FILL FROM revision: rev.revision}}`, for release v0.4.0 of this repository.
Its identity (`library.json`, `p_integral/manifest.json`):

    {{TO FILL FROM revision: rev.identity}}

## Content

- {{TO FILL FROM revision: rev.library_files}} files, {{TO FILL FROM revision: rev.library_bytes}} bytes
  ({{TO FILL FROM revision: rev.library_bytes|gb}}); `library.json` sha256
  `{{TO FILL FROM revision: rev.library_json_sha256}}`.
- Area manifest `p_integral/manifest.json` (copy: `p_integral-manifest.json`): sha256
  `{{TO FILL FROM revision: rev.area_manifest_sha256}}`, {{TO FILL FROM revision: rev.area_manifest_bytes}} bytes.
- Root manifest `manifest.json` (v0.4.0, only the key `p_integral` differs from this
  repository's): sha256 `{{TO FILL FROM revision: rev.root_manifest_sha256}}`.
- Owner payloads (`owners/`): {{TO FILL FROM revision: rev.dir.files:owners/}} files,
  {{TO FILL FROM revision: rev.dir.bytes:owners/}} bytes; relation roots (`relations/`):
  {{TO FILL FROM revision: rev.dir.files:relations/}} files, {{TO FILL FROM revision: rev.dir.bytes:relations/}} bytes.
- Master catalogue (`p-master-catalogue.json`, copy here): data version
  `{{TO FILL FROM revision: catalogue.data_version}}`, sha256 `{{TO FILL FROM revision: catalogue.sha256}}`,
  {{TO FILL FROM revision: catalogue.masters}} masters and {{TO FILL FROM revision: catalogue.placeholders}}
  placeholders; {{TO FILL FROM revision: catalogue.terminals}} terminal rows, {{TO FILL FROM revision: catalogue.terminals_mapped}}
  on catalogue masters and {{TO FILL FROM revision: catalogue.terminals_placeholder}} on a placeholder.
  Master basis data `masters/MANIFEST.json` sha256 `{{TO FILL FROM revision: masters.manifest_sha256}}`
  (catalogue version `{{TO FILL FROM revision: masters.catalogue_version}}`).
- Library counts: {{TO FILL FROM revision: rev.counts.tops}} tops, {{TO FILL FROM revision: rev.counts.presentations}}
  presentations, {{TO FILL FROM revision: rev.counts.classes}} classes, {{TO FILL FROM revision: rev.counts.terminals}} terminals,
  {{TO FILL FROM revision: rev.counts.sectors}} sectors ({{TO FILL FROM revision: rev.counts.zero_sectors}} zero).

Largest files:

{{TO FILL FROM revision: rev.largest}}

## Archive

`{{TO FILL FROM DATASET.json: ds.archive.name}}`: {{TO FILL FROM DATASET.json: ds.archive.bytes}} bytes
({{TO FILL FROM DATASET.json: ds.archive.bytes|gb}}), sha256 `{{TO FILL FROM DATASET.json: ds.archive.sha256}}`,
codec {{TO FILL FROM DATASET.json: ds.codec}} level {{TO FILL FROM DATASET.json: ds.level}}, in
{{TO FILL FROM DATASET.json: ds.parts}} parts of at most {{TO FILL FROM DATASET.json: ds.part_bytes}} bytes
(the archive is their concatenation in order). `DATASET.json` sha256
`{{TO FILL FROM DATASET.json: ds.dataset_json_sha256}}`, `SHA256SUMS` sha256 `{{TO FILL FROM SHA256SUMS: ds.sha256sums_sha256}}`.

| part | bytes | sha256 |
|---|---|---|
{{TO FILL FROM DATASET.json: ds.parts_table}}

The archive is kept on the host where it was built, in `{{TO FILL FROM dataset dir: ds.location}}`;
it is not in this repository and not part of a release archive.

## Restore and use

In the dataset directory, then in a checkout of this repository at v0.4.0:

    sha256sum -c SHA256SUMS
    cat {{TO FILL FROM DATASET.json: ds.archive.name}}.part-* | {{TO FILL FROM DATASET.json: ds.decompress}} | tar -x --strip-components=1 -C <checkout>

then, in `<checkout>`, check every restored library file against the area manifest:

    python3 -c 'import hashlib,json,os;h=lambda p:hashlib.sha256(open(p,"rb").read()).hexdigest();k=json.load(open("manifest.json"))["p_integral"];assert h(k["manifest"])==k["manifest_sha256"],"area manifest";L=json.load(open(k["manifest"]))["libraries"][0];d=os.path.join("p_integral",L["directory"]);bad=[f for f,v in L["files"].items() if h(os.path.join(d,f))!=v["sha256"]];print(L["identity"].rsplit("=",1)[1],len(L["files"]),"files,",len(bad),"bad")'

which prints `{{TO FILL FROM revision: rev.revision}} {{TO FILL FROM revision: rev.library_files|raw}} files, 0 bad`
(it reads each file whole: the largest needs about {{TO FILL FROM revision: rev.largest_bytes|gb}} of memory). Use:
`Vakint::load_external_data(<checkout>, n)` (Python: `vakint.load_external_data`); see `datasets/README.md`.
