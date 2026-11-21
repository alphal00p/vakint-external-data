# Dataset vk5l-s12349d-r3: the 1L-5L p library

The RustRed p library `p-library-1-5` (scope 1-5 loops, schema `rustred.p-owner-library.v1`),
package revision `vk5l-s12349d-r3`, for release v0.4.0 of this repository.
Its identity (`library.json`, `p_integral/manifest.json`):

    p-library:scope=1-5:P_OWNER_LIBRARY_SEMANTICS=rustred-p-owner-library-2026-11-05,P_CLASS_KEY_VERSION=1,P_CENSUS_VERSION=2,P_PRESENTATION_VERSION=4,P_FAMILIES_VERSION=1,P_GAMMA_TAG_VERSION=1,P_GAMMA_TAG_MAX_M=8,P_GAMMA_TAG_WIDTH=16,P_INSERTION_KERNEL_VERSION=1,P_CARPET_KERNEL_VERSION=1,P_TRIANGLE_TEMPLATE_VERSION=1,P_DIAMOND_TEMPLATE_VERSION=1,P_SCHEME_TEMPLATE_VERSION=5,P_CUSTOM_OWNER_VERSION=2,P_LIBRARY_SCHEMA=rustred.p-owner-library.v1,P_FAMILIES_SCHEMA=rustred.p-families.v1,P_BASIS_LAYER_SCHEMA=rustred.p-basis-layer.v1,P_TOPOLOGY_VERSION=1,P_FAMILIES_5L_VERSION=1,P_PACKAGE_REVISION=vk5l-s12349d-r3

## Content

- 6,946 files, 10,118,887,925 bytes
  (10.12 GB); `library.json` sha256
  `10d00190142e0763acea5bec4a3320dcc6c638346d94ab16dceb6a2381d30dc1`.
- Area manifest `p_integral/manifest.json` (copy: `p_integral-manifest.json`): sha256
  `81b1b5f7ce884c31a12cb04ca0f4b39c98ce383d7a7fae46694936fb622ed3a2`, 1,671,690 bytes.
- Root manifest `manifest.json` (v0.4.0, only the key `p_integral` differs from this
  repository's): sha256 `281cb35e9fdc7f86ce8d1cf15185c13af81d1d0ea9a3a09ea43ec9a9b1e65867`.
- Owner payloads (`owners/`): 279 files,
  4,849,226,374 bytes; relation roots (`relations/`):
  9 files, 3,884,742,188 bytes.
- Master catalogue (`p-master-catalogue.json`, copy here): data version
  `ggppss-5L-v4-rc4a`, sha256 `fa3b6d3f3bd7598500a128abe87ce72c639583c9992ed8e5bd1d9afabc9a6ae6`,
  281 masters and 8
  placeholders, and the map of the package's 231 residual terminals onto
  GGPPSS or Forcer masters and Γ factors (8 of them onto a
  placeholder).
  Master basis data `masters/MANIFEST.json` sha256 `5980a4a0719ff4b65d25b15239827be7ebf10072157b2de8a7f0eef880d3185b`
  (catalogue version `ggppss-5L-v3.7`).
- Library counts: 80 tops, 6,650
  presentations, 3,797 classes, 231 residual
  terminals (and the unit),
  13,254,053 sectors (12,197,983 zero).

Largest files:

- `relations/T266-ea3ee0b1379450ef/seg-orbitcut-r3p4.jsonl`: 3,884,640,930 bytes
- `owners/L4T09-b0a8dd0dd96d5d09.rrbin`: 1,128,637,337 bytes
- `routes.rrbin`: 1,127,082,548 bytes
- `owners/L5T10-514f2291cea530d5.rrbin`: 660,060,980 bytes
- `owners/L5T12-89a756192b4670af.rrbin`: 486,533,529 bytes
- `owners/L5T14-5ab247e9cf3bf219.rrbin`: 469,933,622 bytes
- `owners/L5T09-b75121bb0882a0ae.rrbin`: 417,192,275 bytes
- `owners/L4T09-5ae35383b5b20b2c.rrbin`: 359,166,764 bytes
- `owners/L4T08-aacd9485f2ea2cc7.rrbin`: 149,383,977 bytes
- `census.rrbin`: 141,250,345 bytes

## Archive

`vk5l-s12349d-r3.tar.gz`: 5,332,711,180 bytes
(5.33 GB), sha256 `1c46b32c7965e318631bcede9c06333adb161e3dc55fb7ad4982332345f0e059`,
codec gzip level 6, in
3 parts of at most 1,900,000,000 bytes
(the archive is their concatenation in order). `DATASET.json` sha256
`dc129895b8d56809399d8bdac47e75d1b0b9248e9e9618e0d38ae65af853855d`, `SHA256SUMS` sha256 `5ff5e435057a876aae9185975bb5950ebe5cad0cc0140aef203260a3817146be`.

| part | bytes | sha256 |
|---|---|---|
| `vk5l-s12349d-r3.tar.gz.part-000` | 1,900,000,000 | `8d3a869b71a4bf19dba8bcbd13fb0dde752d263999d4427c0ed0e1389c2b13a8` |
| `vk5l-s12349d-r3.tar.gz.part-001` | 1,900,000,000 | `09818989aa21264268338a73f7574a18e7861cb8bb38576b8a878dcf89cd5142` |
| `vk5l-s12349d-r3.tar.gz.part-002` | 1,532,711,180 | `1e2f7ae6312a9d925bbeb9ed57d4f2952db938b392dd9bb3ad1d357ab3fb4250` |

The archive is kept by the maintainers: obtain it on request.
{{TO FILL FROM the user's decision on release assets: pin.dataset_release_assets}} It is not in this repository and not in a
loop-pack archive.

## Restore and use

First check with your own `sha256sum` that `DATASET.json` has the sha256 given above (it records the sha256 of every part,
of the archive and of the shipped tools `dataset_restore.sh`, `dataset_verify.sh`, `dataset_index.py`; the tools check
against it, which finds damage, not tampering). The archive is an overlay of a checkout of this repository at
v0.4.0; a bare revision directory is not a root for `load_external_data` (it has no
loop packs). Recommended, in the dataset directory (the tools and a `README.txt` sit beside the parts):

    git clone --depth 1 --branch v0.4.0 https://github.com/alphal00p/vakint-external-data <checkout>
    bash dataset_restore.sh . <checkout> --overlay

It checks every part, the whole archive and `SHA256SUMS.files` before anything is written, refuses a checkout of another
release or one already overlaid, unpacks (the files keep the modes of your umask), checks every restored file and prints the
root manifest sha256: it must be `281cb35e9fdc7f86ce8d1cf15185c13af81d1d0ea9a3a09ea43ec9a9b1e65867`. Without the tools, in the dataset
directory (`SHA256SUMS` lists every part; the archive's own sha256 is in `DATASET.json`):

    sha256sum -c SHA256SUMS && cat vk5l-s12349d-r3.tar.gz.part-* | gzip -dc | tar -x --strip-components=1 -C <checkout>

then, in `<checkout>`, check every restored library file against the area manifest:

    python3 -c 'import hashlib,json,os;h=lambda p:hashlib.sha256(open(p,"rb").read()).hexdigest();k=json.load(open("manifest.json"))["p_integral"];assert h(k["manifest"])==k["manifest_sha256"],"area manifest";L=json.load(open(k["manifest"]))["libraries"][0];d=os.path.join("p_integral",L["directory"]);bad=[f for f,v in L["files"].items() if h(os.path.join(d,f))!=v["sha256"]];print(L["identity"].rsplit("=",1)[1],len(L["files"]),"files,",len(bad),"bad")'

which prints `vk5l-s12349d-r3 6946 files, 0 bad`
(it reads each file whole: the largest needs about 3.88 GB of memory). Use:
`Vakint::load_external_data(<checkout>, n)` (Python: `engine.load_external_data(path, max_loop_count=n)`); see
`datasets/README.md`.
The 1-5 library needs its master catalogue also for three- and four-loop integrals, which `p-library-1-4` served alone; Vakint loads it with the library and, from gammaloop `p_integral` {{TO FILL FROM pins (the gammaloop p_integral commit of the release): pin.vakint}} on, uses it at every loop count; a program that uses RustRed directly must load `p-master-catalogue.json` itself.
A program that loads the library through RustRed and hands it to Vakint gives Vakint no catalogue with it: from that commit on, Vakint consults the catalogue it has at five loops, as before, and at every loop count wherever a value carries a residual terminal (the catalogue set by the program or by `VAKINT_P_MASTER_CATALOGUE`, else its built-in `ggppss-5L-v3.2`, which lacks five-loop rows of this release). Retain mode then returns three- and four-loop results as combinations of `PMaster` symbols, the same kind as its five-loop results.
Nothing binds a catalogue to its library; the 17 one- to four-loop rows of the built-in catalogue and of this package are identical, pinned by a test (Vakint's `one_to_four_loop_integrals_through_the_1_5_package_equal_the_1_4_library`).
