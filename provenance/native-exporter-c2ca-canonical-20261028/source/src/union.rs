//! Invocation of the existing opaque Native union; no coefficient/context APIs.
use super::*;
use rustred_app::{
    NativePackSnapshot, SavedApplicationCacheBundleWriter, SavedApplicationCacheCopyStatistics,
};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
enum Kind {
    Bundle,
    Pack,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq, Serialize)]
#[serde(deny_unknown_fields)]
struct Census {
    generation: u64,
    runs: usize,
    chunk_references: usize,
    stored_record_references: usize,
    referenced_compressed_bytes: u64,
    manifest_bytes: usize,
}

/// Known seals remain mandatory; absent prior statistics must be explicit null.
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ExpectedCensus {
    generation: u64,
    #[serde(deserialize_with = "required_option")]
    runs: Option<usize>,
    #[serde(deserialize_with = "required_option")]
    chunk_references: Option<usize>,
    stored_record_references: usize,
    #[serde(deserialize_with = "required_option")]
    referenced_compressed_bytes: Option<u64>,
    manifest_bytes: usize,
}

fn required_option<'de, D, T>(deserializer: D) -> std::result::Result<Option<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: Deserialize<'de>,
{
    Option::<T>::deserialize(deserializer)
}

impl ExpectedCensus {
    fn matches(&self, actual: Census) -> bool {
        self.generation == actual.generation
            && self.stored_record_references == actual.stored_record_references
            && self.manifest_bytes == actual.manifest_bytes
            && self.runs.is_none_or(|expected| expected == actual.runs)
            && self
                .chunk_references
                .is_none_or(|expected| expected == actual.chunk_references)
            && self
                .referenced_compressed_bytes
                .is_none_or(|expected| expected == actual.referenced_compressed_bytes)
    }

    /// A grant/overflow lower bound only, never the actual source/output census.
    fn declared_minimum(&self) -> Census {
        Census {
            generation: self.generation,
            runs: self.runs.unwrap_or(0),
            chunk_references: self.chunk_references.unwrap_or(0),
            stored_record_references: self.stored_record_references,
            referenced_compressed_bytes: self.referenced_compressed_bytes.unwrap_or(0),
            manifest_bytes: self.manifest_bytes,
        }
    }
}

impl Census {
    fn read(reader: &SavedApplicationCachePack) -> Self {
        let statistics = reader.statistics();
        Self {
            generation: reader.generation(),
            runs: statistics.runs,
            chunk_references: statistics.chunks,
            stored_record_references: statistics.records,
            referenced_compressed_bytes: statistics.referenced_chunk_bytes,
            manifest_bytes: statistics.manifest_bytes,
        }
    }
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Source {
    id: String,
    kind: Kind,
    directory: PathBuf,
    cache_native_index_identity: Value,
    expected: ExpectedCensus,
}

impl Source {
    /// Project an existing collector identity's filename, never decode an index.
    /// The Native bundle reader separately verifies its exact sole binding.
    fn pack_directory(&self) -> Result<PathBuf> {
        let identity = &self.cache_native_index_identity;
        ensure!(
            identity["schema"] == "vakint.native-cache-index-identity.v1"
                && identity["sha256"].as_str().is_some_and(valid_sha),
            "invalid existing Native index identity"
        );
        let indexes = identity["indexes"]
            .as_object()
            .ok_or_else(|| eyre!("missing existing Native index inventory"))?;
        if self.kind == Kind::Pack {
            ensure!(
                identity["layout"] == "pack"
                    && indexes.len() == 1
                    && indexes.contains_key("cache.rrindex"),
                "pack identity must name exactly its existing cache.rrindex"
            );
            return Ok(self.directory.clone());
        }
        ensure!(
            identity["layout"] == "bundle"
                && indexes.len() == 2
                && indexes.contains_key("bundle.rrindex"),
            "union helper supports exactly one explicit 5L namespace per bundle"
        );
        let name = indexes
            .keys()
            .find(|name| *name != "bundle.rrindex")
            .unwrap();
        let parts = name.split('/').collect::<Vec<_>>();
        ensure!(
            parts.len() == 3
                && parts[0] == "bindings"
                && valid_sha(parts[1])
                && parts[2] == "cache.rrindex",
            "bundle child index must use the existing bindings/<hash>/cache.rrindex layout"
        );
        Ok(self.directory.join("bindings").join(parts[1]))
    }

    fn child_index_name(&self) -> Result<String> {
        let pack = self.pack_directory()?;
        Ok(pack
            .join("cache.rrindex")
            .strip_prefix(&self.directory)?
            .to_str()
            .ok_or_else(|| eyre!("index filename must be UTF-8"))?
            .to_owned())
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Limits {
    max_disk_bytes: u64,
    max_manifest_bytes: usize,
    max_directory_owned_bytes: usize,
}

impl Limits {
    fn native(self) -> Result<SavedApplicationCachePackLimits> {
        ensure!(
            self.max_disk_bytes > 0
                && self.max_manifest_bytes > 0
                && self.max_directory_owned_bytes > 0,
            "explicit union byte grants must be positive"
        );
        Ok(SavedApplicationCachePackLimits {
            diagnostics_enabled: false,
            max_disk_bytes: self.max_disk_bytes,
            max_manifest_bytes: self.max_manifest_bytes,
            max_directory_owned_bytes: self.max_directory_owned_bytes,
            ..Default::default()
        })
    }
}

#[derive(Default, Debug, PartialEq, Eq, Serialize)]
struct Totals {
    runs: usize,
    chunk_references: usize,
    stored_record_references: usize,
    referenced_compressed_bytes: u64,
}

impl Totals {
    fn add(&mut self, census: Census) -> Result<()> {
        self.runs = self
            .runs
            .checked_add(census.runs)
            .ok_or_else(|| eyre!("run sum overflow"))?;
        self.chunk_references = self
            .chunk_references
            .checked_add(census.chunk_references)
            .ok_or_else(|| eyre!("chunk-reference sum overflow"))?;
        self.stored_record_references = self
            .stored_record_references
            .checked_add(census.stored_record_references)
            .ok_or_else(|| eyre!("record-reference sum overflow"))?;
        self.referenced_compressed_bytes = self
            .referenced_compressed_bytes
            .checked_add(census.referenced_compressed_bytes)
            .ok_or_else(|| eyre!("referenced-byte sum overflow"))?;
        Ok(())
    }

    fn matches(&self, census: Census) -> bool {
        self.runs == census.runs
            && self.chunk_references == census.chunk_references
            && self.stored_record_references == census.stored_record_references
            && self.referenced_compressed_bytes == census.referenced_compressed_bytes
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    schema: String,
    semantic_binding: BindingJson,
    sources_newest_first: Vec<Source>,
    limits: Limits,
}

impl Request {
    fn parse(bytes: &[u8]) -> Result<Self> {
        let request: Self = serde_json::from_slice(&json_bytes(bytes)?)?;
        ensure!(
            request.schema == "vakint.native-opaque-union-request.v1",
            "unknown union invocation request"
        );
        request.semantic_binding.native()?;
        request.limits.native()?;
        ensure!(
            !request.sources_newest_first.is_empty(),
            "union needs at least one source"
        );
        let mut ids = BTreeSet::new();
        let mut identities = BTreeSet::new();
        for source in &request.sources_newest_first {
            ensure!(
                !source.id.is_empty()
                    && source
                        .id
                        .bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_'),
                "invalid source ID"
            );
            ensure!(ids.insert(&source.id), "duplicate source ID");
            source.pack_directory()?;
            ensure!(
                identities.insert(
                    source.cache_native_index_identity["sha256"]
                        .as_str()
                        .unwrap()
                ),
                "duplicate Native snapshot alias"
            );
        }
        let totals = request.declared_minimum_totals()?;
        ensure!(
            totals.referenced_compressed_bytes <= request.limits.max_disk_bytes,
            "disk grant must admit referenced bytes including shadowed duplicates, separately from physical copied bytes"
        );
        Ok(request)
    }

    fn declared_minimum_totals(&self) -> Result<Totals> {
        let mut totals = Totals::default();
        for source in &self.sources_newest_first {
            totals.add(source.expected.declared_minimum())?;
        }
        Ok(totals)
    }
}

/// Reuse the existing strict canonical-root/file witness for each source index.
struct Witness {
    root: ProofRoot,
    references: Vec<(PathBuf, Value)>,
}

impl Witness {
    fn read(source: &Source) -> Result<Self> {
        let root = ProofRoot::parse(&source.directory)?;
        ensure!(
            index_identity::native_index_identity(&source.directory)?
                == source.cache_native_index_identity,
            "source index identity changed: {}",
            source.id
        );
        let mut references = Vec::new();
        for (name, row) in source.cache_native_index_identity["indexes"]
            .as_object()
            .unwrap()
        {
            let path = source.directory.join(name);
            let expected = row["sha256"]
                .as_str()
                .ok_or_else(|| eyre!("missing index SHA256"))?;
            references.push((path.clone(), root.reference(&path, &path, expected)?));
        }
        Ok(Self { root, references })
    }

    fn unchanged(&self, source: &Source) -> Result<()> {
        ensure!(
            index_identity::native_index_identity(&source.directory)?
                == source.cache_native_index_identity,
            "source index identity changed: {}",
            source.id
        );
        for (path, expected) in &self.references {
            ensure!(
                self.root
                    .reference(path, path, expected["sha256"].as_str().unwrap())?
                    == *expected,
                "source root/index reference changed: {}",
                source.id
            );
        }
        Ok(())
    }
}

fn disjoint_sources(request: &Request) -> Result<()> {
    for (position, source) in request.sources_newest_first.iter().enumerate() {
        // This rejects all symlink/dot/relative aliases before Native opens.
        ProofRoot::parse(&source.directory)?;
        for previous in &request.sources_newest_first[..position] {
            ensure!(
                !source.directory.starts_with(&previous.directory)
                    && !previous.directory.starts_with(&source.directory),
                "duplicate or overlapping Native source directories"
            );
        }
    }
    Ok(())
}

fn snapshot_identity(snapshot: &NativePackSnapshot, file: &str) -> Result<Value> {
    let metadata = fs::symlink_metadata(&snapshot.manifest_path)?;
    ensure!(
        metadata.is_file() && metadata.len() == snapshot.manifest_bytes,
        "captured snapshot length changed"
    );
    Ok(json!({"manifest":file,"generation":snapshot.generation,
        "manifest_bytes":snapshot.manifest_bytes,"manifest_blake3":snapshot.manifest_digest,
        "manifest_sha256":sha_file(&snapshot.manifest_path)?,"refresh_allowed":false}))
}

fn validate_copy(
    totals: &Totals,
    destination: Census,
    copied: SavedApplicationCacheCopyStatistics,
    sources: usize,
    charged_bytes: u64,
) -> Result<()> {
    ensure!(
        destination.generation == 1
            && totals.matches(destination)
            && copied.copied_bases == sources
            && copied.namespaces == 1
            && copied.preserved_record_references == totals.stored_record_references
            && copied.copied_chunks <= totals.chunk_references
            && copied.compressed_bytes <= totals.referenced_compressed_bytes,
        "Native union reference/physical-copy census differs"
    );
    ensure!(
        Some(charged_bytes) == copied.compressed_bytes.checked_add(copied.index_bytes),
        "Native charged disk/copy statistics differ"
    );
    Ok(())
}

pub(super) fn execute(
    args: &Args,
    admission: Value,
    mut phase_seconds: BTreeMap<&'static str, f64>,
) -> Result<()> {
    let started = phase_start("union_request_preflight");
    let document = Document::from_args(args, "--request")?;
    let artifacts = Document::from_args(args, "--collector-artifacts")?;
    let proof_root = args
        .values
        .get("--proof-root")
        .map(|value| ProofRoot::parse(Path::new(value)))
        .transpose()?;
    let artifact_reference = artifacts.reference(proof_root.as_ref())?;
    let compiled = cohort()?;
    let declared_artifact: Value = serde_json::from_slice(&artifacts.bytes)?;
    ensure!(
        declared_artifact["compiled_cohort"] == compiled
            && declared_artifact["binary"]["sha256"] == compiled["measurement_executable_sha256"]
            && declared_artifact["stamps"] == compiled["stamps"],
        "union producer artifact must bind this actual compiled cohort and executable"
    );
    let request = Request::parse(&document.bytes)?;
    disjoint_sources(&request)?;
    let binding = request.semantic_binding.native()?;
    let limits = request.limits.native()?;
    let witnesses = request
        .sources_newest_first
        .iter()
        .map(Witness::read)
        .collect::<Result<Vec<_>>>()?;
    let mut protected = vec![document.path.as_path(), artifacts.path.as_path()];
    protected.extend(
        request
            .sources_newest_first
            .iter()
            .map(|source| source.directory.as_path()),
    );
    let output = Output::new(&args.path("--output-dir"), &protected)?;
    let snapshots = output.staging.join("snapshots");
    fs::create_dir(&snapshots)?;
    phase_seconds.insert(
        "union_request_preflight",
        phase_end("union_request_preflight", started, "ok"),
    );

    let started = phase_start("open_and_freeze_sources");
    let mut readers = Vec::new();
    let mut captured = Vec::new();
    let mut source_snapshots = Vec::new();
    let mut source_censuses = Vec::new();
    let mut totals = Totals::default();
    for (position, source) in request.sources_newest_first.iter().enumerate() {
        let reader = match source.kind {
            Kind::Pack => {
                SavedApplicationCachePack::open_generated(&source.directory, &binding, limits)?
            }
            Kind::Bundle => SavedApplicationCacheBundle::open_generated(
                &source.directory,
                std::slice::from_ref(&binding),
                limits,
            )?
            .open_reader(&binding)?,
        };
        let census = Census::read(&reader);
        ensure!(
            source.expected.matches(census),
            "source census differs: {}",
            source.id
        );
        let name = format!("snapshots/source-{position}.rrindex");
        let snapshot = reader.freeze_snapshot(&output.staging.join(&name))?;
        let identity = snapshot_identity(&snapshot, &name)?;
        let expected = &source.cache_native_index_identity["indexes"][source.child_index_name()?];
        ensure!(
            identity["manifest_sha256"] == expected["sha256"]
                && identity["manifest_bytes"] == expected["bytes"],
            "captured Native snapshot differs from declared index"
        );
        // Retain only the real frozen reader, not a duplicate decoded index.
        drop(reader);
        let reader = SavedApplicationCachePack::open_snapshot(
            &source.pack_directory()?,
            &binding,
            &snapshot,
            limits,
        )?;
        ensure!(
            Census::read(&reader) == census,
            "frozen source census differs"
        );
        source_snapshots.push(identity);
        totals.add(census)?;
        source_censuses.push(census);
        captured.push(snapshot);
        readers.push(reader);
    }
    phase_seconds.insert(
        "open_and_freeze_sources",
        phase_end("open_and_freeze_sources", started, "ok"),
    );

    let started = phase_start("copy_base_union");
    let bases = readers.iter().collect::<Vec<_>>();
    let cache = output.staging.join("cache");
    let (writer, copied) = SavedApplicationCacheBundleWriter::copy_base_union_to_new(
        &cache,
        std::slice::from_ref(&binding),
        &bases,
        limits,
    )?;
    let charged_bytes = writer.charged_disk_bytes()?;
    drop(writer);
    phase_seconds.insert(
        "copy_base_union",
        phase_end("copy_base_union", started, "ok"),
    );

    let started = phase_start("validate_union_metadata");
    let bundle = SavedApplicationCacheBundle::open_generated(
        &cache,
        std::slice::from_ref(&binding),
        limits,
    )?;
    ensure!(
        bundle.metadata()?.is_none(),
        "union must not copy preparation-job metadata"
    );
    let reader = bundle.open_reader(&binding)?;
    let destination = Census::read(&reader);
    validate_copy(&totals, destination, copied, readers.len(), charged_bytes)?;
    let identity = index_identity::native_index_identity(&cache)?;
    phase_seconds.insert(
        "validate_union_metadata",
        phase_end("validate_union_metadata", started, "ok"),
    );

    let started = phase_start("union_postflight");
    for (position, source) in request.sources_newest_first.iter().enumerate() {
        witnesses[position].unchanged(source)?;
        ensure!(
            snapshot_identity(
                &captured[position],
                &format!("snapshots/source-{position}.rrindex")
            )? == source_snapshots[position]
                && Census::read(&readers[position]) == source_censuses[position]
                && source.expected.matches(source_censuses[position]),
            "frozen source snapshot/census changed"
        );
    }
    document.unchanged()?;
    artifacts.unchanged()?;
    artifacts.unchanged_reference(proof_root.as_ref(), &artifact_reference)?;
    phase_seconds.insert(
        "union_postflight",
        phase_end("union_postflight", started, "ok"),
    );
    let mut raw = json!({"schema":"vakint.native-opaque-union-validation.v1","success":true,
        "request_sha256":document.sha256,"semantic_binding":request.semantic_binding,
        "sources_newest_first":request.sources_newest_first,"captured_snapshots":source_snapshots,
        "source_censuses":source_censuses,
        "source_indexes_unchanged":true,"frozen_readers_used":true,"cache_native_index_identity":identity,
        "output_census":destination,"source_reference_totals":totals,
        "copy_statistics":{"namespaces":copied.namespaces,"copied_bases":copied.copied_bases,
            "unique_physical_chunks":copied.copied_chunks,"physical_compressed_bytes":copied.compressed_bytes,
            "index_bytes":copied.index_bytes,"preserved_record_references":copied.preserved_record_references,
            "transfer_buffer_bytes":copied.transfer_buffer_bytes,"charged_disk_bytes":charged_bytes},
        "distinct_keys":Value::Null,"limits":request.limits,"compiled_cohort":compiled,
        "executable_sha256":compiled["measurement_executable_sha256"],"collector_artifacts":artifact_reference,
        "resource_guard_admission":admission,"compiled_codec_state_format":6,
        "coefficient_context_created":false,"state_or_coefficient_imports":0,"IBP_applications":0,
        "scope":"Opaque preservation of trusted-generated committed sources; no new record mathematics, complete-workload/physical certification, source exposure or distinct-key census. Native verifies chosen unique compressed files; compatible duplicate source files need not be reread."});
    append_completed_phases(&mut raw, &phase_seconds)?;
    output.write("raw-validation.json", &serde_json::to_vec_pretty(&raw)?)?;
    output.publish()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::proof_reference::test_support::Scratch;

    fn source(position: usize) -> Value {
        json!({"id":format!("source-{position}"),"kind":"pack",
            "directory":format!("{WORKSPACE}/synthetic-{position}"),
            "cache_native_index_identity":{"schema":"vakint.native-cache-index-identity.v1",
                "layout":"pack","sha256":format!("{position:064x}"),
                "indexes":{"cache.rrindex":{"bytes":9,"sha256":"a".repeat(64)}}},
            "expected":{"generation":3,"runs":1,"chunk_references":2,
                "stored_record_references":4,"referenced_compressed_bytes":100,"manifest_bytes":9}})
    }

    fn request(count: usize) -> Value {
        json!({"schema":"vakint.native-opaque-union-request.v1",
            "semantic_binding":{"artifact_digest":vec![7u8;32],"family_fingerprint":"SYNTHETIC-NOT-A-REAL-FAMILY",
                "physical_arity":15,"layer":"saved-application-route-apply-v1"},
            "sources_newest_first":(0..count).map(source).collect::<Vec<_>>(),
            "limits":{"max_disk_bytes":10000,"max_manifest_bytes":10000,"max_directory_owned_bytes":10000}})
    }

    fn parsed(value: &Value) -> Result<Request> {
        Request::parse(&serde_json::to_vec(value)?)
    }

    #[test]
    fn source_count_and_order_are_not_hardcoded() {
        for count in [1, 2, 3, 7] {
            let mut value = request(count);
            value["sources_newest_first"]
                .as_array_mut()
                .unwrap()
                .reverse();
            let result = parsed(&value).unwrap();
            assert_eq!(result.sources_newest_first.len(), count);
            assert_eq!(
                result.sources_newest_first[0].id,
                format!("source-{}", count - 1)
            );
            assert_eq!(
                result
                    .declared_minimum_totals()
                    .unwrap()
                    .stored_record_references,
                count * 4
            );
        }
    }

    #[test]
    fn empty_duplicate_wrong_kind_unknown_fields_and_bindings_refuse() {
        assert!(parsed(&request(0)).is_err());
        for field in ["id", "cache_native_index_identity"] {
            let mut value = request(2);
            value["sources_newest_first"][1][field] =
                value["sources_newest_first"][0][field].clone();
            assert!(parsed(&value).is_err());
        }
        let mut value = request(1);
        value["sources_newest_first"][0]["kind"] = "file".into();
        assert!(parsed(&value).is_err());
        let mut value = request(1);
        value["sources_newest_first"][0]["surprise"] = true.into();
        assert!(parsed(&value).is_err());
        let mut value = request(1);
        value["semantic_binding"]["physical_arity"] = 4.into();
        assert!(parsed(&value).is_err());
    }

    #[test]
    fn namespace_projection_is_exact_existing_layout_only() {
        let mut value = request(1);
        let row = &mut value["sources_newest_first"][0];
        row["kind"] = "bundle".into();
        row["cache_native_index_identity"]["layout"] = "bundle".into();
        let good = format!("bindings/{}/cache.rrindex", "b".repeat(64));
        row["cache_native_index_identity"]["indexes"] =
            json!({"bundle.rrindex":{},(good.clone()):{}});
        assert!(parsed(&value).is_ok());
        for name in [
            "../cache.rrindex".to_owned(),
            "bindings/not-a-hash/cache.rrindex".to_owned(),
            format!("bindings/{}/../cache.rrindex", "b".repeat(64)),
        ] {
            let mut bad = value.clone();
            bad["sources_newest_first"][0]["cache_native_index_identity"]["indexes"] =
                json!({"bundle.rrindex":{},(name):{}});
            assert!(parsed(&bad).is_err());
        }
        value["sources_newest_first"][0]["cache_native_index_identity"]["indexes"]["extra.rrindex"] =
            json!({});
        assert!(parsed(&value).is_err());
    }

    #[test]
    fn positive_grants_and_checked_reference_sums_are_required() {
        for field in [
            "max_disk_bytes",
            "max_manifest_bytes",
            "max_directory_owned_bytes",
        ] {
            let mut value = request(1);
            value["limits"][field] = 0.into();
            assert!(parsed(&value).is_err());
        }
        let mut value = request(2);
        value["limits"]["max_disk_bytes"] = 100.into();
        assert!(parsed(&value).is_err());
        let mut value = request(2);
        value["sources_newest_first"][0]["expected"]["stored_record_references"] =
            json!(usize::MAX);
        assert!(parsed(&value).is_err());
    }

    #[test]
    fn unknown_expectations_require_explicit_null_and_mandatory_seals() {
        let mut value = request(1);
        for name in ["runs", "chunk_references", "referenced_compressed_bytes"] {
            value["sources_newest_first"][0]["expected"][name] = Value::Null;
        }
        assert!(parsed(&value).is_ok());
        for name in [
            "runs",
            "chunk_references",
            "referenced_compressed_bytes",
            "generation",
            "stored_record_references",
            "manifest_bytes",
        ] {
            let mut missing = value.clone();
            missing["sources_newest_first"][0]["expected"]
                .as_object_mut()
                .unwrap()
                .remove(name);
            assert!(parsed(&missing).is_err(), "missing {name}");
        }
        for name in ["generation", "stored_record_references", "manifest_bytes"] {
            let mut unknown = value.clone();
            unknown["sources_newest_first"][0]["expected"][name] = Value::Null;
            assert!(parsed(&unknown).is_err(), "unknown mandatory {name}");
        }
    }

    #[test]
    fn partial_expectations_check_every_provided_value() {
        let actual = Census {
            generation: 3,
            runs: 7,
            chunk_references: 9,
            stored_record_references: 4,
            referenced_compressed_bytes: 800,
            manifest_bytes: 9,
        };
        let mut value = request(1);
        for name in ["runs", "chunk_references", "referenced_compressed_bytes"] {
            value["sources_newest_first"][0]["expected"][name] = Value::Null;
        }
        assert!(
            parsed(&value).unwrap().sources_newest_first[0]
                .expected
                .matches(actual)
        );
        for (name, right) in [
            ("generation", 3),
            ("runs", 7),
            ("chunk_references", 9),
            ("stored_record_references", 4),
            ("referenced_compressed_bytes", 800),
            ("manifest_bytes", 9),
        ] {
            let mut known = value.clone();
            known["sources_newest_first"][0]["expected"][name] = right.into();
            assert!(
                parsed(&known).unwrap().sources_newest_first[0]
                    .expected
                    .matches(actual),
                "{name}"
            );
            known["sources_newest_first"][0]["expected"][name] = (right + 1).into();
            assert!(
                !parsed(&known).unwrap().sources_newest_first[0]
                    .expected
                    .matches(actual),
                "{name}"
            );
        }
    }

    #[test]
    fn actual_metadata_alone_controls_output_sums_and_checked_overflow() {
        let mut value = request(3);
        for row in value["sources_newest_first"].as_array_mut().unwrap() {
            for name in ["runs", "chunk_references", "referenced_compressed_bytes"] {
                row["expected"][name] = Value::Null;
            }
        }
        let request = parsed(&value).unwrap();
        let minimum = request.declared_minimum_totals().unwrap();
        assert_eq!(minimum.runs, 0);
        assert_eq!(minimum.referenced_compressed_bytes, 0);
        let source = Census {
            generation: 3,
            runs: 7,
            chunk_references: 9,
            stored_record_references: 4,
            referenced_compressed_bytes: 800,
            manifest_bytes: 9,
        };
        let mut actual = Totals::default();
        for row in &request.sources_newest_first {
            assert!(row.expected.matches(source));
            actual.add(source).unwrap();
        }
        let output = Census {
            generation: 1,
            runs: 21,
            chunk_references: 27,
            stored_record_references: 12,
            referenced_compressed_bytes: 2400,
            manifest_bytes: 25,
        };
        assert!(actual.matches(output));
        assert!(!minimum.matches(output));
        let mut overflow = Totals::default();
        overflow
            .add(Census {
                referenced_compressed_bytes: u64::MAX,
                ..source
            })
            .unwrap();
        assert!(overflow.add(source).is_err());
        let mut overflow = Totals::default();
        overflow
            .add(Census {
                runs: usize::MAX,
                ..source
            })
            .unwrap();
        assert!(overflow.add(source).is_err());
    }

    #[test]
    fn sources_and_sidecars_cannot_alias_or_nest() {
        let scratch = Scratch::new();
        let parent = scratch.0.join("source");
        fs::create_dir(&parent).unwrap();
        let child = parent.join("child");
        fs::create_dir(&child).unwrap();
        let mut value = request(2);
        value["sources_newest_first"][0]["directory"] = json!(parent);
        value["sources_newest_first"][1]["directory"] = json!(child);
        let result = parsed(&value).unwrap();
        assert!(disjoint_sources(&result).is_err());
        assert!(Output::new(&parent.join("new-output"), &[parent.as_path()]).is_err());
        #[cfg(unix)]
        {
            let link = scratch.0.join("link");
            std::os::unix::fs::symlink(&parent, &link).unwrap();
            value["sources_newest_first"][0]["directory"] = json!(link);
            assert!(disjoint_sources(&parsed(&value).unwrap()).is_err());
        }
    }

    #[test]
    fn synthetic_index_drift_and_root_replacement_are_detected_without_native_open() {
        let scratch = Scratch::new();
        let directory = scratch.0.join("synthetic");
        fs::create_dir(&directory).unwrap();
        let path = directory.join("cache.rrindex");
        fs::write(&path, b"SYNTHETIC-NOT-NATIVE").unwrap();
        let mut value = request(1);
        value["sources_newest_first"][0]["directory"] = json!(directory);
        value["sources_newest_first"][0]["cache_native_index_identity"] =
            index_identity::native_index_identity(&directory).unwrap();
        let result = parsed(&value).unwrap();
        let source = &result.sources_newest_first[0];
        let witness = Witness::read(source).unwrap();
        fs::write(&path, b"DIFFERENT-SYNTHETIC").unwrap();
        assert!(witness.unchanged(source).is_err());
        fs::write(&path, b"SYNTHETIC-NOT-NATIVE").unwrap();
        let witness = Witness::read(source).unwrap();
        fs::rename(&directory, scratch.0.join("preserved-old-directory")).unwrap();
        fs::create_dir(&directory).unwrap();
        fs::write(&path, b"SYNTHETIC-NOT-NATIVE").unwrap();
        assert!(witness.unchanged(source).is_err());
    }

    #[test]
    fn copied_physical_bytes_are_not_confused_with_stored_references() {
        let expected = parsed(&request(3))
            .unwrap()
            .declared_minimum_totals()
            .unwrap();
        let destination = Census {
            generation: 1,
            runs: 3,
            chunk_references: 6,
            stored_record_references: 12,
            referenced_compressed_bytes: 300,
            manifest_bytes: 77,
        };
        let copied = SavedApplicationCacheCopyStatistics {
            namespaces: 1,
            copied_bases: 3,
            copied_chunks: 2,
            preserved_record_references: 12,
            compressed_bytes: 100,
            index_bytes: 90,
            transfer_buffer_bytes: 65536,
        };
        assert!(validate_copy(&expected, destination, copied, 3, 190).is_ok());
        assert!(validate_copy(&expected, destination, copied, 2, 190).is_err());
        assert!(validate_copy(&expected, destination, copied, 3, 191).is_err());
        let mut bad = copied;
        bad.preserved_record_references = 2;
        assert!(validate_copy(&expected, destination, bad, 3, 190).is_err());
    }

    #[test]
    fn snapshot_reporting_distinguishes_native_blake3_from_source_sha256() {
        let scratch = Scratch::new();
        let (path, sha) = scratch.file("synthetic-sidecar.rrindex");
        let snapshot = NativePackSnapshot {
            manifest_path: path.clone(),
            generation: 9,
            manifest_bytes: fs::metadata(&path).unwrap().len(),
            manifest_digest: [5; 32],
        };
        let identity = snapshot_identity(&snapshot, "snapshots/source-0.rrindex").unwrap();
        assert_eq!(identity["manifest_sha256"], sha);
        assert_eq!(identity["manifest_blake3"], json!(vec![5u8; 32]));
        fs::write(&path, b"changed length").unwrap();
        assert!(snapshot_identity(&snapshot, "snapshots/source-0.rrindex").is_err());
    }

    #[test]
    fn union_cli_needs_no_application_and_forbids_wrong_mode_arguments() {
        let values = [
            "union-bases",
            "--request",
            "/synthetic/request",
            "--request-sha256",
            "sha",
            "--collector-artifacts",
            "/synthetic/artifact",
            "--collector-artifacts-sha256",
            "sha",
            "--output-dir",
            "/synthetic/output",
        ];
        assert!(Args::from_iter(values.into_iter().map(str::to_owned)).is_ok());
        let mut wrong = values.into_iter().map(str::to_owned).collect::<Vec<_>>();
        wrong.extend(["--application".to_owned(), "/not-allowed".to_owned()]);
        assert!(Args::from_iter(wrong).is_err());
        assert!(require_runtime_admission(None).is_err());
    }
}
