#!/usr/bin/env python3
"""Offline admission of a portable PR11dep0 proof bundle; Python standard library only.

This replays the final interval convolutions and publication rounding. Authenticated
source/transport/endpoint reviews retain their recorded scope; native recurrences,
HPL algorithms and Mathematica are not executed by this delivery verifier.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
from fractions import Fraction as F
from itertools import combinations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import time
import zlib

if not __debug__:
    raise RuntimeError("Scientific admission requires assertions enabled")
sys.set_int_max_str_digits(0)
HEX = re.compile(r"[0-9a-f]{64}\Z")
DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
SOURCE = "a9ec06c3a076f3460e84ec3492ae314b29f4cf470dddbe2a5442b502f7181184"
FAMILY = "693719b1bc3d2f1d4d32c9312df66ced667a542591a2ada6f6498844fc5d0de1"
UID = "L4_" + FAMILY + "_p0_p2_p1_p1_p1_p1_p1_p1_p1_p0"
POWERS = [0, 2, 1, 1, 1, 1, 1, 1, 1, 0]
SCIENTIFIC_REVIEW = "22f69516f6f2e0a8278b9a4913dfd85a74b0e82b5c7e8507d0b8655c13d8ef31"
IBP_REVIEW = "50a8e1b8ddfa550876016d329eae8e0fe952c345fdafadcb5e0825dc868181e2"
ADJOINT_ACCEPTANCE = "b523238139d137f911645bd179bd15cc7386bf89232abdac799421cbc85d3b38"
ORACLE_ACCEPTANCE = "af1521ef875f6e92f83597f9f445b69778c2391c997a82d7becff50b95a839a8"
# Production-v11 review hashes are added only after independent review seals.
# A mutually consistent chain/review pair supplied by a bundle is not a trust root.
TRUSTED_CHAIN_REVIEWS = {
    "20006e5f6ed2850280c346f40c942f69e713cd7752c9271494fc707d96e87f41",
}
# A validator review alone authenticates code, not a particular execution. These
# are the independently sealed complete physical A/B production receipts.
TRUSTED_CHAIN_RECEIPTS = {
    "c0eaeeb01cc4dec73828e8948b26ddcee744fcd9e71c6768ccdad71aa6a95dd4",
    "faeaf82baaf840eba8472c4e51b4dedbfa6da04eff63811280269caf0faf9d80",
}
# Independently reviewed exact scientific dataset and typed JSON-pointer policy.
TRUSTED_PROOF_READ_SET_SHA256 = "5c737067b24ef4c65a739ff5c9da558a63349a49e23b6799da824a27fe889aa8"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def unique(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError("Duplicate JSON key: " + key)
        out[key] = value
    return out


def json_read(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def rational(text):
    if not isinstance(text, str) or len(text) > 300000 or not DECIMAL.fullmatch(text):
        raise ValueError("Expected a finite scalar decimal")
    # Limit exponents before allocating a potentially adversarial integer.
    exponent = re.split("[eE]", text)
    if len(exponent) == 2 and abs(int(exponent[1])) > 100000:
        raise ValueError("Decimal exponent exceeds the scientific bundle limit")
    return F(text)


def interval(text):
    """Interpret Arb's outward decimal display, without evaluating source text."""
    if not isinstance(text, str) or len(text) > 300000:
        raise ValueError("Invalid decimal-ball text")
    if text.startswith("[") and text.endswith("]"):
        body = text[1:-1]
        if body.startswith("+/- "):
            center, radius = F(0), rational(body[4:])
        else:
            parts = body.split(" +/- ")
            if len(parts) != 2:
                raise ValueError("Invalid outward decimal-ball grammar")
            center, radius = map(rational, parts)
        if radius < 0:
            raise ValueError("A radius cannot be negative")
        return center - radius, center + radius
    center = rational(text)
    return center, center


def add(a, b):
    return a[0] + b[0], a[1] + b[1]


def sub(a, b):
    return a[0] - b[1], a[1] - b[0]


def mul(a, b):
    products = [x * y for x in a for y in b]
    return min(products), max(products)


def cmul(a, b):
    return sub(mul(a[0], b[0]), mul(a[1], b[1])), add(mul(a[0], b[1]), mul(a[1], b[0]))


def contains(outer, inner):
    return outer[0] <= inner[0] <= inner[1] <= outer[1]


def zero(box):
    return box[0] <= 0 <= box[1]


def magnitude_lower(box):
    assert not zero(box)
    return min(abs(box[0]), abs(box[1]))


def radius(box):
    return (box[1] - box[0]) / 2


# Exact integer convolution kernel; reviewed immutable source9dea862e.
def _integer_scalar(text):
    """Return integer n, exponent e with text exactly equal to n*10**e."""
    if not isinstance(text, str) or len(text) > 300000 or (not DECIMAL.fullmatch(text)):
        raise ValueError('Expected a finite scalar decimal')
    pieces = re.split('[eE]', text)
    explicit = int(pieces[1]) if len(pieces) == 2 else 0
    if abs(explicit) > 100000:
        raise ValueError('Decimal exponent exceeds the scientific bundle limit')
    mantissa = pieces[0]
    sign = -1 if mantissa.startswith('-') else 1
    mantissa = mantissa.lstrip('+-')
    whole, dot, fraction = mantissa.partition('.')
    digits = (whole + fraction).lstrip('0')
    if not digits:
        return (0, 0)
    shortened = digits.rstrip('0')
    return (sign * int(shortened), explicit - len(fraction) + len(digits) - len(shortened))

def _integer_rescale(n, exponent, common):
    assert exponent >= common
    return n * 10 ** (exponent - common) if n else 0

def _integer_interval(text):
    """Decode exactly the outward decimal-display grammar used by Arb."""
    if not isinstance(text, str) or len(text) > 300000:
        raise ValueError('Invalid decimal-ball text')
    if text.startswith('[') and text.endswith(']'):
        body = text[1:-1]
        if body.startswith('+/- '):
            center, radius = ((0, 0), _integer_scalar(body[4:]))
        else:
            pieces = body.split(' +/- ')
            if len(pieces) != 2:
                raise ValueError('Invalid outward decimal-ball grammar')
            center, radius = map(_integer_scalar, pieces)
        if radius[0] < 0:
            raise ValueError('A radius cannot be negative')
        exponent = min(center[1], radius[1])
        c, r = (_integer_rescale(*center, exponent), _integer_rescale(*radius, exponent))
        return ((c - r, c + r), exponent)
    n, exponent = _integer_scalar(text)
    return ((n, n), exponent)

def _integer_decode_complex(rows, count):
    assert isinstance(rows, list) and len(rows) == count
    assert all((isinstance(row, list) and len(row) == 2 for row in rows))
    parsed = [(_integer_interval(real), _integer_interval(imag)) for real, imag in rows]
    exponent = min((part[1] for row in parsed for part in row))
    powers = {delta: 10 ** delta for delta in {part[1] - exponent for row in parsed for part in row}}
    result = []
    for row in parsed:
        result.append(tuple(((box[0] * powers[e - exponent], box[1] * powers[e - exponent]) for box, e in row)))
    return (result, exponent)

def _integer_product(a, b):
    x, y, z, w = (a[0] * b[0], a[0] * b[1], a[1] * b[0], a[1] * b[1])
    return (min(x, y, z, w), max(x, y, z, w))

def _integer_convolve(raw_y_rows, v_rows, dimension=42, orders=6):
    """Return all shifted coefficients and their common decimal exponent."""
    assert type(dimension) is int and dimension > 0 and (type(orders) is int) and (orders > 0)
    y, ye = _integer_decode_complex(raw_y_rows, dimension * orders)
    v, ve = _integer_decode_complex(v_rows, dimension * orders)
    coefficients = []
    for p in range(orders):
        rl = rh = il = ih = 0
        for j in range(p + 1):
            for i in range(dimension):
                a, b = (v[dimension * j + i], y[dimension * (p - j) + i])
                ac, bd = (_integer_product(a[0], b[0]), _integer_product(a[1], b[1]))
                ad, bc = (_integer_product(a[0], b[1]), _integer_product(a[1], b[0]))
                rl += ac[0] - bd[1]
                rh += ac[1] - bd[0]
                il += ad[0] + bc[0]
                ih += ad[1] + bc[1]
        coefficients.append(((rl, rh), (il, ih)))
    return (coefficients, ye + ve)

def _integer_contains(outer, outer_exponent, inner, inner_exponent):
    exponent = min(outer_exponent, inner_exponent)
    ol, oh = (_integer_rescale(n, outer_exponent, exponent) for n in outer)
    il, ih = (_integer_rescale(n, inner_exponent, exponent) for n in inner)
    return ol <= il <= ih <= oh



class Bundle:
    def __init__(self, directory, index="proof-index.json"):
        self.root = Path(directory).resolve(strict=True)
        self.index = self.parse(self.authenticated_bytes(index))
        assert self.index["schema"] == "vakint.pr11d.portable-proof-index.v1"
        self.files = self.index["files"]
        self.verified_storage = set()
        assert isinstance(self.files, dict) and 1 <= len(self.files) <= 10000
        descriptors = list(self.files.values()) + list(self.index["artifacts"].values()) + list(self.index["implementations"].values())
        assert all("encoding" not in item for item in list(self.index["artifacts"].values()) + list(self.index["implementations"].values())), "Top-level artifacts and verifier implementations remain readable identity files"
        sizes, stored_paths = {}, {}
        for item in descriptors:
            assert type(item["bytes"]) is int and 0 <= item["bytes"] <= 512 << 20
            key = (item["path"], item["sha256"])
            assert key not in sizes or sizes[key] == item["bytes"]
            sizes[key] = item["bytes"]
            assert item["path"] not in stored_paths or stored_paths[item["path"]] == item, "One stored path has conflicting descriptor metadata"
            stored_paths[item["path"]] = item
        assert sum(sizes.values()) <= 8 << 30, "The portable proof exceeds its total decoded-size limit"
        for original, item in self.files.items():
            assert Path(original).is_absolute() and HEX.fullmatch(item["sha256"])
        for item in descriptors:
            self.content_bytes(item, keep=False)
        policy, policy_sha = self.artifact("proof_read_set")
        assert policy_sha == TRUSTED_PROOF_READ_SET_SHA256, "The scientific read-set is not independently blessed"
        self.proof_read_set_sha256 = policy_sha
        assert policy["schema"] == "vakint.pr11d.scientific-proof-read-set.v1"
        assert policy["status"] == "complete_current_scientific_proof_read_set"
        self.proof_files = policy["files_sha256"]
        self.implementation_paths = policy["implementation_paths"]
        assert set(self.implementation_paths.values()) == {"verify_bundle", "assemble"}
        assert policy["required_file_count"] == len(self.proof_files) == len(policy["nodes"])
        for original, digest in self.proof_files.items():
            assert self.files[original]["sha256"] == digest == policy["nodes"][original]["sha256"]
        self.check_read_set_edges(policy)

    @staticmethod
    def parse(data):
        return json.loads(data, object_pairs_hook=unique)

    def authenticated_bytes(self, relative, expected=None, keep=True, expected_bytes=None):
        """Open every component without symlinks and parse only hashed bytes."""
        assert isinstance(relative, str)
        path = PurePosixPath(relative)
        assert str(path) == relative and not path.is_absolute() and path.parts
        assert all(x not in ("", ".", "..") for x in path.parts)
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open(self.root, directory_flags)
        try:
            for component in path.parts[:-1]:
                following = os.open(component, directory_flags, dir_fd=fd)
                os.close(fd)
                fd = following
            following = os.open(path.parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = following
            info = os.fstat(fd)
            assert stat.S_ISREG(info.st_mode) and info.st_size <= 512 << 20
            digest, blocks, count = hashlib.sha256(), [], 0
            while True:
                block = os.read(fd, 1 << 20)
                if not block:
                    break
                count += len(block)
                assert count <= 512 << 20, "A proof file grew beyond its size limit"
                digest.update(block)
                if keep:
                    blocks.append(block)
            assert expected is None or digest.hexdigest() == expected, ("Changed portable proof bytes", relative)
            assert expected_bytes is None or count == expected_bytes, "Stored proof length differs from its authenticated descriptor"
            return b"".join(blocks) if keep else None
        finally:
            os.close(fd)

    def content_bytes(self, item, keep=True):
        assert HEX.fullmatch(item["sha256"])
        assert type(item["bytes"]) is int and 0 <= item["bytes"] <= 512 << 20
        encoding = item.get("encoding")
        allowed = {"path", "sha256", "bytes"} if encoding is None else {"path", "sha256", "bytes", "encoding", "stored_sha256", "stored_bytes"}
        assert set(item) == allowed, "Unknown or missing portable storage descriptor fields"
        key = tuple(sorted(item.items()))
        if not keep and key in getattr(self, "verified_storage", set()):
            return None
        if encoding is None:
            assert "stored_sha256" not in item and "stored_bytes" not in item
            data = self.authenticated_bytes(item["path"], item["sha256"], keep=keep, expected_bytes=item["bytes"])
            if hasattr(self, "verified_storage"):
                self.verified_storage.add(key)
            return data
        assert encoding == "gzip" and HEX.fullmatch(item["stored_sha256"])
        assert type(item["stored_bytes"]) is int and 0 <= item["stored_bytes"] <= 512 << 20
        stored = self.authenticated_bytes(item["path"], item["stored_sha256"], expected_bytes=item["stored_bytes"])
        assert stored[:10] == b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff", "Proof gzip requires no optional headers, zero mtime, level-nine marker and portable OS byte"
        decoder, digest, chunks, count = zlib.decompressobj(31), hashlib.sha256(), [], 0
        for offset in range(0, len(stored), 65536):
            pending = stored[offset:offset + 65536]
            while pending:
                part = decoder.decompress(pending, item["bytes"] - count + 1)
                count += len(part)
                assert count <= item["bytes"] and count <= 512 << 20, "Decoded proof exceeds its declared limit"
                digest.update(part)
                if keep:
                    chunks.append(part)
                pending = decoder.unconsumed_tail
                assert not decoder.unused_data, "Concatenated gzip members or trailing bytes are forbidden"
        assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail, "Incomplete or concatenated gzip proof"
        assert count == item["bytes"] and digest.hexdigest() == item["sha256"], "Decoded proof does not match its original authenticated bytes"
        if hasattr(self, "verified_storage"):
            self.verified_storage.add(key)
        return b"".join(chunks) if keep else None

    def local(self, relative):
        assert isinstance(relative, str)
        path = PurePosixPath(relative)
        assert not path.is_absolute() and path.parts and all(x not in ("", ".", "..") for x in path.parts)
        target = self.root
        for component in path.parts:
            target = target / component
            assert not target.is_symlink(), "Symlinks are not portable scientific proof files"
        assert target.is_file() and target.resolve().is_relative_to(self.root)
        return target

    def original(self, original, expected=None, allow_implementation=False):
        item = self.files[original]  # No fallback to the original developer filesystem.
        digest = item["sha256"]
        if expected is not None:
            assert digest == expected
        if self.proof_files.get(original) != digest:
            assert allow_implementation and original in self.implementation_paths, "Undeclared required scientific read"
            role = self.implementation_paths[original]
            assert role in ("verify_bundle", "assemble")
            assert self.index["implementations"][role]["sha256"] == digest
        return self.local(item["path"])

    def read(self, original, expected=None):
        self.original(original, expected)
        item = self.files[original]
        return self.parse(self.content_bytes(item))

    def by_hash(self, digest):
        paths = [p for p, h in self.proof_files.items() if h == digest]
        assert paths, "Required reviewed evidence is absent from the scientific read-set"
        return self.read(paths[0], digest)

    def pin_map(self, pins, allow_implementation=False):
        assert isinstance(pins, dict)
        for path, digest in pins.items():
            assert HEX.fullmatch(digest)
            self.original(path, digest, allow_implementation=allow_implementation)

    @staticmethod
    def pointer(record, pointer):
        assert isinstance(pointer, str) and (pointer == "" or pointer.startswith("/"))
        if pointer == "":
            return record
        for encoded in pointer[1:].split("/"):
            assert re.search(r"~(?![01])", encoded) is None, "Invalid JSON-pointer escape"
            key = encoded.replace("~1", "/").replace("~0", "~")
            if isinstance(record, list):
                assert re.fullmatch(r"0|[1-9][0-9]*", key), "JSON-pointer array indices must be canonical nonnegative integers"
                record = record[int(key)]
            else:
                record = record[key]
        return record

    def check_read_set_edges(self, policy):
        """Replay only reviewed current edges; retained history is not a graph walk."""
        import posixpath
        for owner, node in policy["nodes"].items():
            references = node["required_references"]
            assert isinstance(references, list) and isinstance(node["roles"], list)
            assert isinstance(node["embedded_provenance_policy"], str)
            assert node["portable_operation"] in ("semantic_json_read", "authenticated_catalog_identity_data", "hash_only_current_admission_input")
            pointers = node["consumed_json_pointers"]
            assert isinstance(pointers, list) and isinstance(node["informational_reference_scopes"], list)
            if not references and not pointers:
                continue
            record = self.read(owner, node["sha256"])
            for pointer in pointers:
                self.pointer(record, pointer)
            for scope in node["informational_reference_scopes"]:
                self.pointer(record, scope["json_pointer"])
                assert scope["reason"] and scope["classification"]
            for edge in references:
                assert edge["owner"] == owner
                digest = self.pointer(record, edge["digest_json_pointer"])
                assert digest == edge["sha256"] == self.proof_files[edge["target"]]
                if edge["target_from_map_key"]:
                    reference = edge["digest_json_pointer"].rsplit("/", 1)[1].replace("~1", "/").replace("~0", "~")
                elif edge["path_json_pointer"] is not None:
                    reference = self.pointer(record, edge["path_json_pointer"])
                else:
                    # An explicitly named hash-only role, e.g. AMFlow result.
                    continue
                assert isinstance(reference, str)
                if PurePosixPath(reference).is_absolute():
                    target = reference
                else:
                    base = edge["relative_reference_base"]
                    assert PurePosixPath(base).is_absolute()
                    target = posixpath.normpath(str(PurePosixPath(base) / reference))
                assert target == edge["target"], "A required edge's pointer/path/hash binding differs"

    def artifact(self, name):
        item = self.index["artifacts"][name]
        assert HEX.fullmatch(item["sha256"])
        assert "encoding" not in item, "Top-level scientific artifacts remain readable identity files"
        return self.parse(self.content_bytes(item)), item["sha256"]


def rank(rows):
    rows = [list(map(F, row)) for row in rows]
    r = 0
    for column in range(4):
        pivot = next((i for i in range(r, len(rows)) if rows[i][column]), None)
        if pivot is None:
            continue
        rows[r], rows[pivot] = rows[pivot], rows[r]
        value = rows[r][column]
        rows[r] = [x / value for x in rows[r]]
        for i in range(r + 1, len(rows)):
            value = rows[i][column]
            rows[i] = [a - value * b for a, b in zip(rows[i], rows[r])]
        r += 1
    return r


def determinant(rows):
    rows = [list(map(F, row)) for row in rows]
    value = F(1)
    for c in range(4):
        pivot = next((i for i in range(c, 4) if rows[i][c]), None)
        if pivot is None:
            return F(0)
        if pivot != c:
            rows[pivot], rows[c] = rows[c], rows[pivot]
            value = -value
        x = rows[c][c]
        value *= x
        for i in range(c + 1, 4):
            factor = rows[i][c] / x
            for j in range(c, 4):
                rows[i][j] -= factor * rows[c][j]
    return value


def physical_proof(bundle):
    review = bundle.by_hash(SCIENTIFIC_REVIEW)
    assert review["accepted"] is True
    certificate = bundle.read(review["finiteness_certificate_path"], review["finiteness_certificate_sha256"])
    raw = bundle.read(review["raw_pole_certificate_path"], review["raw_pole_certificate_sha256"])
    assert certificate["master_id"] == UID and certificate["family_sha256"] == FAMILY and certificate["powers"] == POWERS
    assert certificate["all_negative_Laurent_coefficients_exactly_zero"] is True
    assert certificate["FMFT_equals_native_finite_coefficient"] is True and certificate["Minkowski_overall_sign"] == -1
    assert certificate["original_X8_source_sha256"] == SOURCE
    source = bundle.read(certificate["original_X8_source_path"], SOURCE)
    reference = bundle.read(certificate["canonical_reference_input_path"], certificate["canonical_reference_input_sha256"])
    assert reference["master_id"] == UID and reference["powers"] == POWERS and reference["family_sha256"] == FAMILY
    vectors = [list(map(F, row)) for row in certificate["ordered_active_vectors"]]
    powers = certificate["ordered_active_powers"]
    assert len(vectors) == len(powers) == 8 and powers == [2, 1, 1, 1, 1, 1, 1, 1]
    # Bind each certified momentum vector back to its actual quadratic form.
    family = source["family"]
    assert family["sha256"] == FAMILY
    for slot, vector in zip(certificate["active_slot_indices"], vectors):
        prop = family["denominators"][slot]
        assert F(prop["constant"]) == -1
        for coordinate, coefficient in zip(family["coordinates"], prop["coefficients"]):
            assert coordinate["kind"] == "loop_loop"
            i, j = coordinate["left"], coordinate["right"]
            assert F(coefficient) == vector[i] * vector[j] * (1 if i == j else 2)
    bases = [(subset, determinant([vectors[i] for i in subset]) ** 2) for subset in combinations(range(8), 4)]
    bases = [(subset, coefficient) for subset, coefficient in bases if coefficient]
    assert len(bases) == 45
    assert [{"active_indices": list(s), "coefficient": str(c)} for s, c in bases] == certificate["positive_U_bases"]
    assert len(certificate["UV_face_checks"]) == 254
    for mask in range(1, 255):
        selected = [i for i in range(8) if mask >> i & 1]
        valuation = 4 - rank([vectors[i] for i in range(8) if not mask >> i & 1])
        assert valuation == min(sum(i in selected for i in subset) for subset, _ in bases)
        margin = sum(powers[i] for i in selected) - 2 * valuation
        assert F(margin) - F(valuation, 8) > 0
        row = certificate["UV_face_checks"][mask - 1]
        assert row["active_subset_mask"] == mask and row["U_face_valuation"] == valuation and row["D4_face_margin"] == margin
    assert sum(powers) - 2 * 4 - F(4, 8) > 0
    target = [x for x in source["target_reductions"] if x["powers"] == POWERS]
    assert len(target) == 1
    expected = {tuple(source["basis"][30]): "1", tuple(source["basis"][36]): "-1", tuple(source["basis"][37]): "-1*masters_4l::{}::epsilon", tuple(source["basis"][38]): "-1"}
    assert {tuple(x["powers"]): x["coefficient"] for x in target[0]["terms"]} == expected
    assert raw and review["scientific_conclusions"]["raw_basis_Laurent_support_lower_bound"] == -4
    return certificate


def projection(bundle, digest):
    data = bundle.by_hash(digest)
    assert data["schema"] == "vakint.pr11d.bounded-finite-endpoint-projection.v1"
    assert data["source_equation_sha256"] == SOURCE and data["master_alias"] == "PR11dep0" and data["epsilon_power"] == 0
    assert data["normalization"] == "native_raw" and data["error_quality"] == "rigorous-bound"
    chain = bundle.read(data["chain_acceptance_path"], data["chain_acceptance_sha256"])
    assert data["chain_acceptance_sha256"] in TRUSTED_CHAIN_RECEIPTS, "This particular completed physical chain is not independently blessed"
    assert chain["schema"] == "vakint.pr11d.physical-X8-chain-acceptance.v1" and chain["status"] == "passed_for_frozen_completed_physical_chain"
    for field in ["initial_physical_provenance_verified", "all_step_source_hashes_and_centers_verified", "all_local_tails_certified", "all_interval_gauge_and_serialization_checks_passed"]:
        assert chain[field] is True
    bundle.pin_map(chain["source_pins"])
    bundle.pin_map(chain["artifact_sha256"])
    assert chain["independent_validator_review_sha256"] in TRUSTED_CHAIN_REVIEWS, "The chain review is not independently blessed by this verifier"
    review = bundle.read(chain["independent_validator_review_path"], chain["independent_validator_review_sha256"])
    assert review["status"] == "passed_for_frozen_physical_X8_chain_validator" and review["validator_sha256"] == chain["validator_sha256"]
    boundary = bundle.read(data["boundary_path"], data["boundary_sha256"])
    transport = bundle.read(data["transport_receipt_path"], data["transport_receipt_sha256"])
    assert chain["artifact_sha256"][data["boundary_path"]] == data["boundary_sha256"]
    assert chain["artifact_sha256"][data["transport_receipt_path"]] == data["transport_receipt_sha256"]
    assert chain["final_boundary_sha256"] == data["boundary_sha256"] == transport["final_boundary_sha256"]
    assert transport["complete"] is True and transport["all_final_component_radii_meet_target"] is True
    assert boundary["basis"] == "original_raw_epsilon_jets" and boundary["dimension"] == 42 and boundary["epsilon_min_power"] == -4 and boundary["epsilon_max_power"] == 1
    assert boundary["normalization"] == "native_raw" and boundary["error_quality"] == "rigorous-bound" and boundary["eta_center"] == ["0", "1/16"]
    adjoint = bundle.read(data["adjoint_path"], data["adjoint_sha256"])
    acceptance = bundle.read(data["adjoint_acceptance_path"], ADJOINT_ACCEPTANCE)
    assert data["adjoint_acceptance_sha256"] == ADJOINT_ACCEPTANCE and acceptance["status"] == "passed_for_frozen_completed_endpoint_production"
    assert acceptance["artifact_sha256"][data["adjoint_path"]] == data["adjoint_sha256"], "The actual adjoint is not the accepted endpoint output"
    bundle.pin_map(acceptance["source_pins"])
    bundle.pin_map(acceptance["artifact_sha256"])
    assert adjoint["dimension"] == 252 and adjoint["epsilon_range"] == [0, 5] and adjoint["tail_bound_added"] is True and adjoint["eta_center"] == ["0", "1/16"]
    coefficients, decimal_exponent = _integer_convolve(boundary["values"], adjoint["complex_balls"], dimension=42, orders=6)
    assert [r["epsilon_power"] for r in data["coefficients"]] == list(range(-5, 1))
    for p, row in enumerate(data["coefficients"]):
        saved_real, real_exponent = _integer_interval(row["real_ball"])
        saved_imag, imag_exponent = _integer_interval(row["imaginary_ball"])
        assert _integer_contains(saved_real, real_exponent, coefficients[p][0], decimal_exponent) and _integer_contains(saved_imag, imag_exponent, coefficients[p][1], decimal_exponent), ("Saved final box fails independent exact decimal convolution", p - 5)
        assert saved_imag[0] <= 0 <= saved_imag[1] and (p == 5 or saved_real[0] <= 0 <= saved_real[1])
    finite = data["coefficients"][-1]
    return data, chain, interval(finite["real_ball"]), interval(finite["imaginary_ball"])


def decimal_cell(text, digits, box):
    value = Decimal(text)
    assert value.is_finite() and value and len(value.as_tuple().digits) == digits
    center = rational(text)
    exponent = value.adjusted()
    unit, decade = F(10) ** (exponent - digits + 1), F(10) ** exponent
    toward = unit / 10 if abs(center) == decade else unit
    previous = center - (unit if center < 0 else toward)
    following = center + (toward if center < 0 else unit)
    assert (previous + center) / 2 < box[0] <= box[1] < (following + center) / 2
    return center, max(abs(box[0] - center), abs(box[1] - center))


def verify(directory, index="proof-index.json"):
    started = time.monotonic()
    bundle = Bundle(directory, index)
    assert bundle.index["implementations"]["verify_bundle"]["sha256"] == sha(Path(__file__)), "The executed verifier differs from the portable implementation pin"
    payload, payload_sha = bundle.artifact("payload")
    validation, _ = bundle.artifact("validation")
    manifest, manifest_sha = bundle.artifact("provenance_manifest")
    assert payload["schema"] == "vakint.pr11d.validated-periods.v1" and set(payload["constants"]) == {"PR11dep0"}
    assert validation["schema"] == "vakint.pr11d.validated-period-acceptance.v1" and validation["status"] == "accepted_20000_validated_significant_digits"
    assert validation["coefficient_data_sha256"] == payload_sha
    assert validation["provenance_manifest_sha256"] == payload["provenance_manifest_sha256"] == manifest_sha
    assert manifest["schema"] == "vakint.pr11d.validated-provenance-manifest.v1" and manifest["publication_cap"] == 20000
    assert validation["scientific_proof_read_set_sha256"] == manifest["scientific_proof_read_set_sha256"] == bundle.proof_read_set_sha256
    assert validation["portable_verifier_sha256"] == manifest["portable_verifier_sha256"] == bundle.index["implementations"]["verify_bundle"]["sha256"]
    assert validation["validator_sha256"] == bundle.index["implementations"]["assemble"]["sha256"]
    bundle.pin_map(manifest["files_sha256"], allow_implementation=True)
    row = payload["constants"]["PR11dep0"]
    for field, wanted in [("symbol", "PR11dep0"), ("master_basis", "vakint::PR11d"), ("master_id", UID), ("family_sha256", FAMILY), ("ordered_powers", POWERS), ("epsilon_power", 0), ("normalization", "FMFT"), ("unit_mass_squared", "1"), ("error_quality", "rigorous-bound"), ("Minkowski_overall_sign", -1), ("validated_significant_digits", 20000), ("stored_significant_digits", 20008)]:
        assert row[field] == wanted, field
    assert validation["validated_significant_digits"] == 20000 and validation["stored_significant_digits"] == 20008
    assert validation["stored_center"] == row["value"] and validation["stored_center_absolute_error_upper_bound"] == row["absolute_error_upper_bound"]
    certificate = physical_proof(bundle)
    assert row["normalization_equality_proof_sha256"] == bundle.files[bundle.by_hash(SCIENTIFIC_REVIEW)["finiteness_certificate_path"]]["sha256"]
    assert validation["scientific_pole_review_sha256"] == SCIENTIFIC_REVIEW
    digests = validation["two_refinement_projection_sha256"]
    assert isinstance(digests, list) and len(digests) == 2 and digests[0] != digests[1]
    a, ca, A, IA = projection(bundle, digests[0])
    b, cb, B, IB = projection(bundle, digests[1])
    assert ca["initial_physical_boundary_sha256"] != cb["initial_physical_boundary_sha256"]
    assert A[0] <= B[1] and B[0] <= A[1] and zero(IA) and zero(IB) and B[1] < 0
    scale = magnitude_lower(B)
    difference = max(abs(A[0] - B[1]), abs(A[1] - B[0]))
    assert difference < scale * F(10) ** -20000
    for real, imag in [(A, IA), (B, IB)]:
        assert max(radius(real), radius(imag)) < scale * F(10) ** -20000
    assert row["arithmetic_ball"] == b["coefficients"][-1]["real_ball"] and row["physical_imaginary_ball"] == b["coefficients"][-1]["imaginary_ball"]
    center, error = decimal_cell(row["value"], 20008, B)
    published_error = rational(row["absolute_error_upper_bound"])
    assert 0 < error <= published_error < abs(center) * F(10) ** -20000
    ibp = bundle.by_hash(IBP_REVIEW)
    assert validation["independent_IBP_witness_receipt_sha256"] == IBP_REVIEW
    assert ibp["source_system_sha256"] == SOURCE and ibp["source_family_sha256"] == FAMILY
    assert ibp["target_relations_total"] == 3 and ibp["target_relations_independently_proved"] == [0, 1, 2]
    assert ibp["complete_independent_DE_validation"] is False and len(ibp["de_rows_independently_proved"]) == len(ibp["de_rows_still_trusting_external_Kira"]) == 21
    assert set(ibp["de_rows_independently_proved"]) | set(ibp["de_rows_still_trusting_external_Kira"]) == set(range(42))
    assert validation["complete_independent_DE_validation"] is False and manifest["complete_independent_DE_validation"] is False
    assert validation["remaining_external_exact_equation_trust"] == ibp["remaining_scope"]
    oracle = bundle.by_hash(ORACLE_ACCEPTANCE)
    for resource in oracle["resources"]:
        bundle.by_hash(resource["process_sha256"])
        bundle.by_hash(resource["result_sha256"])
    assert oracle["status"] == "PASS_practical_100_digit_independent_ordinary_solver_crosscheck" and oracle["reference_is_postsolve_only"] is True
    point = rational(oracle["finite_real_central_value"])
    assert max(abs(B[0] - point), abs(B[1] - point)) < scale * F(10) ** -100
    assert validation["AMFlow_20000_digit_comparison_claimed"] is False and validation["AMFlow_scope"] == oracle["independence_scope"]
    assert validation["exact_negative_poles_from_finiteness_proof"] is True and validation["finite_FMFT_native_normalization_equal"] is True
    return {"schema": "vakint.pr11d.portable-bundle-verification.v1", "accepted": True, "symbol": "PR11dep0", "validated_significant_digits": 20000, "stored_significant_digits": 20008, "payload_sha256": payload_sha, "provenance_manifest_sha256": manifest_sha, "checked_portable_files": len(bundle.files), "two_refinement_interval_convolutions_replayed": True, "complete_independent_DE_validation": False, "AMFlow_20000_digit_comparison_claimed": False, "native_or_Mathematica_execution": False, "seconds": time.monotonic() - started}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--index", default="proof-index.json")
    args = parser.parse_args()
    print(json.dumps(verify(args.directory, args.index), indent=2))


if __name__ == "__main__":
    main()
