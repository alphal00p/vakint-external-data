//! Private Native-only producer. No reduction, downloads or usage-profile analysis.
mod index_identity;
mod proof_reference;
mod resource_guard_admission;
mod selection;
mod union;

use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use eyre::{Result, bail, ensure, eyre};
use rustred::persistence::application_cache::{ApplicationCacheBinding, ApplicationCacheKey};
use rustred_app::{
    AppError, AppErrorKind, PreparedSavedApplication, SavedApplicationCacheBundle,
    SavedApplicationCacheFile, SavedApplicationCacheFileLimits, SavedApplicationCachePack,
    SavedApplicationCachePackLimits, SavedApplicationOptions, load_saved_application,
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

use proof_reference::ProofRoot;
use selection::{BindingJson, MAX_LIGHT_BYTES, json_bytes, parse_selection, valid_sha};

const WORKSPACE: &str = "/shared/codex-1/vakint_rustred/workspace";
const USAGE: &str = "native-selected-cache-producer build-info\n\
native-selected-cache-producer export-selected COMMON --selected-keys PATH --selected-keys-sha256 SHA --usage-profile PATH --usage-profile-sha256 SHA\n\
native-selected-cache-producer validate-source-only COMMON --legacy-cache PATH --legacy-cache-sha256 SHA --expected-records 25088\n\
native-selected-cache-producer union-bases --request PATH --request-sha256 SHA --collector-artifacts PATH --collector-artifacts-sha256 SHA --output-dir NEW [--proof-root CANONICAL_ROOT]\n\
COMMON: --application PATH --application-sha256 SHA --binding PATH --binding-sha256 SHA --native-cache DIR --source-inventory PATH --source-inventory-sha256 SHA --collector-artifacts PATH --collector-artifacts-sha256 SHA --output-dir NEW [--proof-root CANONICAL_ROOT]\n\
Output contains cache.rrcache.gz plus raw-validation.json for export-selected, only raw-validation.json for validate-source-only, or cache/ plus snapshots/ and raw-validation.json for union-bases. All outputs publish together into a NEW directory; failures retain unpublished staging. Eligibility and usage semantics require the separate scientific validator. No automatic retry.";

fn phase_start(name: &'static str) -> Instant {
    eprintln!("producer_phase={name} event=start");
    Instant::now()
}

fn phase_end(name: &'static str, started: Instant, status: &'static str) -> f64 {
    let elapsed = started.elapsed().as_secs_f64();
    eprintln!("producer_phase={name} event=end status={status} elapsed_seconds={elapsed}");
    elapsed
}

fn record_counter_due(processed: usize, final_count: bool) -> bool {
    final_count || (processed > 0 && processed.is_multiple_of(1024))
}

fn record_counter_line(
    name: &'static str,
    processed: usize,
    final_count: bool,
    elapsed: Duration,
) -> String {
    format!(
        "producer_phase={name} event=record_count processed_records={processed} final={final_count} elapsed_seconds={:.6}",
        elapsed.as_secs_f64()
    )
}

fn record_counter(name: &'static str, processed: usize, final_count: bool, started: Instant) {
    if record_counter_due(processed, final_count) {
        eprintln!(
            "{}",
            record_counter_line(name, processed, final_count, started.elapsed())
        );
    }
}

fn file_statistics(phase: &'static str, file: &SavedApplicationCacheFile) {
    // A diagnostic census must never introduce a new acceptance/error gate.
    match file.statistics() {
        Ok(stats) => {
            eprintln!("producer_phase={phase} event=existing_file_statistics statistics={stats:?}")
        }
        Err(error) => eprintln!(
            "producer_phase={phase} event=existing_file_statistics_unavailable error={error}"
        ),
    }
}

fn append_completed_phases(
    raw: &mut Value,
    phase_seconds: &BTreeMap<&'static str, f64>,
) -> Result<()> {
    if !phase_seconds.is_empty() {
        raw["phase_seconds"] = serde_json::to_value(phase_seconds)?;
    }
    Ok(())
}

fn sha(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn sha_file(path: &Path) -> Result<String> {
    let mut input = File::open(path)?;
    let mut digest = Sha256::new();
    let mut block = [0; 65536];
    loop {
        let count = input.read(&mut block)?;
        if count == 0 {
            break;
        }
        digest.update(&block[..count]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn cohort() -> Result<Value> {
    let mut compiled: Value = serde_json::from_str(include_str!(concat!(
        env!("OUT_DIR"),
        "/compiled-cohort.json"
    )))?;
    compiled["measurement_executable_sha256"] = sha_file(&std::env::current_exe()?)?.into();
    Ok(compiled)
}

struct Args {
    mode: String,
    values: BTreeMap<String, String>,
}

impl Args {
    fn parse() -> Result<Self> {
        Self::from_iter(std::env::args().skip(1))
    }
    fn from_iter(arguments: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut args = arguments.into_iter();
        let mode = args.next().ok_or_else(|| eyre!(USAGE))?;
        ensure!(
            matches!(
                mode.as_str(),
                "export-selected" | "validate-source-only" | "union-bases"
            ),
            "{USAGE}"
        );
        let mut values = BTreeMap::new();
        while let Some(key) = args.next() {
            ensure!(key.starts_with("--"), "expected named argument: {key}");
            let value = args
                .next()
                .ok_or_else(|| eyre!("missing value for {key}"))?;
            ensure!(
                values.insert(key.clone(), value).is_none(),
                "duplicate argument {key}"
            );
        }
        let mut allowed = BTreeSet::from([
            "--collector-artifacts",
            "--collector-artifacts-sha256",
            "--output-dir",
        ]);
        if mode == "union-bases" {
            allowed.extend(["--request", "--request-sha256"]);
        } else {
            allowed.extend([
                "--application",
                "--application-sha256",
                "--binding",
                "--binding-sha256",
                "--native-cache",
                "--source-inventory",
                "--source-inventory-sha256",
            ]);
        }
        if mode == "export-selected" {
            allowed.extend([
                "--selected-keys",
                "--selected-keys-sha256",
                "--usage-profile",
                "--usage-profile-sha256",
            ]);
        } else if mode == "validate-source-only" {
            allowed.extend([
                "--legacy-cache",
                "--legacy-cache-sha256",
                "--expected-records",
            ]);
        }
        let required = allowed.clone();
        allowed.insert("--proof-root");
        ensure!(
            required.iter().all(|key| values.contains_key(*key))
                && values.keys().all(|key| allowed.contains(key.as_str())),
            "missing, unknown or wrong-mode arguments"
        );
        Ok(Self { mode, values })
    }
    fn text(&self, key: &str) -> &str {
        &self.values[key]
    }
    fn path(&self, key: &str) -> PathBuf {
        PathBuf::from(self.text(key))
    }
}

struct Document {
    original_path: PathBuf,
    path: PathBuf,
    bytes: Vec<u8>,
    sha256: String,
}

impl Document {
    fn read(path: &Path, expected: &str) -> Result<Self> {
        ensure!(
            valid_sha(expected),
            "invalid lowercase SHA256 for {}",
            path.display()
        );
        ensure!(
            fs::symlink_metadata(path)?.is_file(),
            "input must be a regular file, not a symlink: {}",
            path.display()
        );
        let original_path = path.to_owned();
        let path = path.canonicalize()?;
        let bytes = fs::read(&path)?;
        let sha256 = sha(&bytes);
        ensure!(
            sha256 == expected,
            "input SHA256 mismatch: {}",
            path.display()
        );
        Ok(Self {
            original_path,
            path,
            bytes,
            sha256,
        })
    }
    fn from_args(args: &Args, key: &str) -> Result<Self> {
        Self::read(&args.path(key), args.text(&format!("{key}-sha256")))
    }
    fn reference(&self, proof_root: Option<&ProofRoot>) -> Result<Value> {
        match proof_root {
            Some(root) => root.reference(&self.original_path, &self.path, &self.sha256),
            None => Ok(json!({"path":self.path,"sha256":self.sha256})),
        }
    }
    fn unchanged(&self) -> Result<()> {
        ensure!(
            fs::symlink_metadata(&self.path)?.is_file() && sha_file(&self.path)? == self.sha256,
            "input changed: {}",
            self.path.display()
        );
        Ok(())
    }

    fn unchanged_reference(&self, root: Option<&ProofRoot>, expected: &Value) -> Result<()> {
        let current = self.reference(root)?;
        ensure!(
            &current == expected,
            "authenticated artifact transport reference changed"
        );
        Ok(())
    }
}

/// Output staging is a sibling of a fresh destination. Atomic no-replace rename
/// publishes the cache and its validation together. A failed attempt is retained.
struct Output {
    staging: PathBuf,
    destination: PathBuf,
}

impl Output {
    fn new(path: &Path, protected: &[&Path]) -> Result<Self> {
        let name = path
            .file_name()
            .ok_or_else(|| eyre!("output needs a final directory name"))?;
        let parent = path
            .parent()
            .ok_or_else(|| eyre!("output needs an existing parent"))?
            .canonicalize()?;
        ensure!(
            parent.starts_with(Path::new(WORKSPACE).canonicalize()?),
            "output must remain beneath workspace"
        );
        let destination = parent.join(name);
        match fs::symlink_metadata(&destination) {
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            _ => bail!(
                "output already exists or cannot be inspected: {}",
                destination.display()
            ),
        }
        for source in protected {
            let source = source.canonicalize()?;
            ensure!(
                !destination.starts_with(&source) && !source.starts_with(&destination),
                "output overlaps input: {}",
                source.display()
            );
        }
        let nonce = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos();
        let staging = parent.join(format!(
            ".native-selected-cache-{}-{nonce}.staging",
            std::process::id()
        ));
        fs::create_dir(&staging)?;
        eprintln!(
            "Preserving this attempt's staging directory: {}",
            staging.display()
        );
        Ok(Self {
            staging,
            destination,
        })
    }
    fn write(&self, name: &str, bytes: &[u8]) -> Result<()> {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(self.staging.join(name))?;
        file.write_all(bytes)?;
        file.sync_all()?;
        Ok(())
    }
    fn publish(self) -> Result<()> {
        File::open(&self.staging)?.sync_all()?;
        #[cfg(target_os = "linux")]
        {
            use std::{ffi::CString, os::unix::ffi::OsStrExt};
            let source = CString::new(self.staging.as_os_str().as_bytes())?;
            let target = CString::new(self.destination.as_os_str().as_bytes())?;
            // Both paths are owned NUL-terminated strings. RENAME_NOREPLACE is
            // essential: std::fs::rename can replace an existing empty directory.
            let code = unsafe {
                libc::renameat2(
                    libc::AT_FDCWD,
                    source.as_ptr(),
                    libc::AT_FDCWD,
                    target.as_ptr(),
                    libc::RENAME_NOREPLACE,
                )
            };
            ensure!(
                code == 0,
                "atomic no-replace publication failed: {}",
                std::io::Error::last_os_error()
            );
        }
        #[cfg(not(target_os = "linux"))]
        bail!("atomic directory publication requires Linux renameat2 NOREPLACE");
        File::open(self.destination.parent().expect("canonical output parent"))?.sync_all()?;
        Ok(())
    }
}

fn open_pack(path: &Path, binding: &ApplicationCacheBinding) -> Result<SavedApplicationCachePack> {
    let limits = SavedApplicationCachePackLimits::default();
    if path.join("bundle.rrindex").exists() {
        Ok(SavedApplicationCacheBundle::open_generated(
            path,
            std::slice::from_ref(binding),
            limits,
        )?
        .open_reader(binding)?)
    } else {
        Ok(SavedApplicationCachePack::open_generated(
            path, binding, limits,
        )?)
    }
}

fn native_failure(error: impl std::fmt::Display) -> AppError {
    AppError::new(AppErrorKind::Input, error.to_string())
}

/// Compare a second source read to a separately reimported file. Record Eq
/// includes the exact key, coefficient map and raw ordered duplicate guards.
fn compare(
    prepared: &PreparedSavedApplication<15>,
    source: &mut SavedApplicationCachePack,
    binding: &ApplicationCacheBinding,
    file: &mut SavedApplicationCacheFile,
    selected: Option<&[ApplicationCacheKey]>,
    phase_seconds: &mut BTreeMap<&'static str, f64>,
) -> Result<usize> {
    let phase = if selected.is_some() {
        "compare_selected_native_visitor"
    } else {
        "compare_full_native_visitor"
    };
    let started = phase_start(phase);
    let file_keys = file.keys().cloned().collect::<BTreeSet<_>>();
    if let Some(keys) = selected {
        ensure!(
            keys.iter().cloned().collect::<BTreeSet<_>>() == file_keys,
            "reimported output key set differs from selection"
        );
    }
    let mut seen = BTreeSet::new();
    let context = prepared.family().coefficient_context();
    let visit = |record: rustred::persistence::application_cache::ApplicationCacheRecord| -> Result<(), AppError> {
        prepared.validate_completed_cache_record(binding, &record)?;
        let other = file.lookup(&record.key, context)?.ok_or_else(|| native_failure("source key missing from reimported file"))?;
        prepared.validate_completed_cache_record(binding, &other)?;
        if record != other { return Err(native_failure(format!("exact record/ordered guard mismatch: {:?}", record.key))); }
        if !seen.insert(record.key) { return Err(native_failure("duplicate emitted source key")); }
        record_counter(phase, seen.len(), false, started);
        Ok(())
    };
    let result = if let Some(keys) = selected {
        source.visit_selected_completed_records(keys, context, visit)
    } else {
        source.visit_completed_records(context, visit)
    };
    record_counter(phase, seen.len(), true, started);
    let result = (|| {
        let count = result?;
        ensure!(
            count == file_keys.len() && seen == file_keys,
            "extra/missing source or reimported keys"
        );
        Ok(count)
    })();
    eprintln!(
        "producer_phase={phase} event=existing_pack_statistics statistics={:?}",
        source.statistics()
    );
    file_statistics(phase, file);
    eprintln!(
        "producer_phase={phase} event=existing_owner_statistics statistics={:?}",
        prepared.owner_preparation_statistics()
    );
    let elapsed = phase_end(phase, started, if result.is_ok() { "ok" } else { "error" });
    if result.is_ok() {
        phase_seconds.insert(phase, elapsed);
    }
    result
}

/// The existing file decoder has already checked single-member framing. Hash
/// the complete uncompressed frame without defining or parsing another codec.
fn decoded_sha(path: &Path, expected: u64) -> Result<String> {
    let bytes = fs::read(path)?;
    let mut decoder = flate2::bufread::GzDecoder::new(bytes.as_slice());
    let mut digest = Sha256::new();
    let mut count = 0u64;
    let mut block = [0; 65536];
    loop {
        let n = decoder.read(&mut block)?;
        if n == 0 {
            break;
        }
        count = count
            .checked_add(n as u64)
            .ok_or_else(|| eyre!("decoded length overflow"))?;
        ensure!(
            count <= expected,
            "decoded output exceeds authenticated length"
        );
        digest.update(&block[..n]);
    }
    ensure!(
        count == expected && decoder.into_inner().is_empty(),
        "decoded length/trailing member mismatch"
    );
    Ok(format!("{:x}", digest.finalize()))
}

fn require_runtime_admission(receipt: Option<Value>) -> Result<Value> {
    receipt.ok_or_else(|| {
        eyre!("this private five-loop helper requires the complete reviewed VAKINT_RESOURCE_GUARD_* admission tuple before reading data")
    })
}

fn execute(args: Args) -> Result<()> {
    // This exact shared owner module authenticates the Rust worker and existing
    // task supervisor/guard. Its policy is not reimplemented here. Admission is
    // mandatory for this private runtime and precedes every data/Native read.
    let mut phase_seconds = BTreeMap::new();
    let started = phase_start("mandatory_admission");
    let admission = require_runtime_admission(resource_guard_admission::admit_from_task_env()?)?;
    phase_seconds.insert(
        "mandatory_admission",
        phase_end("mandatory_admission", started, "ok"),
    );
    if args.mode == "union-bases" {
        return union::execute(&args, admission, phase_seconds);
    }
    let started = phase_start("input_documents_and_indexes");
    let proof_root = args
        .values
        .get("--proof-root")
        .map(|value| ProofRoot::parse(Path::new(value)))
        .transpose()?;
    let application = Document::from_args(&args, "--application")?;
    let binding_doc = Document::from_args(&args, "--binding")?;
    let binding_json: BindingJson = serde_json::from_slice(&json_bytes(&binding_doc.bytes)?)?;
    let binding = binding_json.native()?;
    let inventory = Document::from_args(&args, "--source-inventory")?;
    let artifacts = Document::from_args(&args, "--collector-artifacts")?;
    let artifact_reference = artifacts.reference(proof_root.as_ref())?;
    // These are authenticated references, not a second scientific validator.
    let inventory_value: Value = serde_json::from_slice(&json_bytes(&inventory.bytes)?)?;
    let _: Value = serde_json::from_slice(&json_bytes(&artifacts.bytes)?)?;
    let native_path = args.path("--native-cache").canonicalize()?;
    let source_identity = index_identity::native_index_identity(&native_path)?;
    ensure!(
        inventory_value.get("cache_native_index_identity") == Some(&source_identity),
        "authenticated inventory does not identify this exact Native snapshot"
    );
    let extra = if args.mode == "export-selected" {
        vec![
            Document::from_args(&args, "--selected-keys")?,
            Document::from_args(&args, "--usage-profile")?,
        ]
    } else {
        vec![Document::from_args(&args, "--legacy-cache")?]
    };
    let selected = if args.mode == "export-selected" {
        Some(parse_selection(
            &extra[0].bytes,
            &extra[1].sha256,
            &binding,
        )?)
    } else {
        None
    };
    // Record the actual outer schema without promoting this metadata helper
    // into a second usage/eligibility validator. Reject unknown tags before export.
    let usage_profile_schema_sha = if selected.is_some() {
        Some(selection::profile_schema_sha256(&extra[1].bytes)?)
    } else {
        None
    };
    let expected_records = if selected.is_none() {
        let value: usize = args.text("--expected-records").parse()?;
        ensure!(value > 0, "expected records must be positive");
        Some(value)
    } else {
        None
    };
    // Protect the complete external-data checkout as well as its IBP directory.
    // This only recognizes an ancestor path for output exclusion; it does not
    // introduce another dataset loader or certify its manifest.
    let data_root = application
        .path
        .ancestors()
        .skip(1)
        .filter(|ancestor| ancestor.join("manifest.json").is_file())
        .last()
        .map(Path::to_owned);
    let mut protected = vec![
        native_path.as_path(),
        application.path.parent().expect("application parent"),
        inventory.path.as_path(),
        artifacts.path.as_path(),
        binding_doc.path.as_path(),
    ];
    if let Some(root) = &data_root {
        protected.push(root);
    }
    protected.extend(extra.iter().map(|doc| doc.path.as_path()));
    let output = Output::new(&args.path("--output-dir"), &protected)?;
    phase_seconds.insert(
        "input_documents_and_indexes",
        phase_end("input_documents_and_indexes", started, "ok"),
    );
    let started = phase_start("load_saved_application");
    let prepared =
        load_saved_application::<15>(&application.path, SavedApplicationOptions::default())?;
    ensure!(
        prepared.cache_binding(binding.artifact_digest) == binding,
        "prepared owner binding differs"
    );
    eprintln!(
        "producer_phase=load_saved_application event=existing_preparation_statistics statistics={:?}",
        prepared.preparation_statistics()
    );
    eprintln!(
        "producer_phase=load_saved_application event=existing_owner_statistics statistics={:?}",
        prepared.owner_preparation_statistics()
    );
    phase_seconds.insert(
        "load_saved_application",
        phase_end("load_saved_application", started, "ok"),
    );
    let started = phase_start("open_native_pack");
    let mut pack = open_pack(&native_path, &binding)?;
    let generation = pack.generation();
    let source_raw_refs = pack.statistics().records;
    eprintln!(
        "producer_phase=open_native_pack event=existing_pack_statistics statistics={:?}",
        pack.statistics()
    );
    phase_seconds.insert(
        "open_native_pack",
        phase_end("open_native_pack", started, "ok"),
    );
    let file_limits = SavedApplicationCacheFileLimits {
        max_compressed_bytes: MAX_LIGHT_BYTES,
        ..Default::default()
    };
    let started = phase_start("compiled_artifact_identity");
    let compiled = cohort()?;
    phase_seconds.insert(
        "compiled_artifact_identity",
        phase_end("compiled_artifact_identity", started, "ok"),
    );
    let mut raw = json!({
        "semantic_binding":binding_json,"compiled_cohort":compiled,
        "resource_guard_admission":admission,
        "collector_artifacts":artifact_reference,
        "executable_sha256":compiled["measurement_executable_sha256"],
        "source_inventory_sha256":inventory.sha256,
        "source_cache_native_index_identity":source_identity,
        "source_native_generation":generation,"source_native_stored_record_references":source_raw_refs,
        "application_sha256":application.sha256,"codec_state_format":6,
        "missing_keys":0,"partial_records":0,
        "exact_record_and_ordered_guard_equality":true,
        "declared_terminal_validation":true,
        "functional_IBP_comparison":false,"new_reduction_or_capture":false,
        "source_unchanged_scope":{"native_indexes":"pre/post exact collector index identity", "source_records":"every selected key read and validated again; source-only mode scans all referenced chunks and newest unique records", "unselected_heavy_payloads_rehashed":false,"input_documents":"actual archived bytes SHA256 before and after"}
    });
    if let Some(keys) = selected.as_deref() {
        let started = phase_start("encode_selected_completed_cache");
        let (bytes, identity) =
            prepared.encode_selected_completed_cache(&binding, &mut pack, keys, file_limits)?;
        ensure!(
            !bytes.is_empty() && bytes.len() <= MAX_LIGHT_BYTES,
            "LIGHT output byte bound failed"
        );
        phase_seconds.insert(
            "encode_selected_completed_cache",
            phase_end("encode_selected_completed_cache", started, "ok"),
        );
        let started = phase_start("write_selected_cache");
        output.write("cache.rrcache.gz", &bytes)?;
        phase_seconds.insert(
            "write_selected_cache",
            phase_end("write_selected_cache", started, "ok"),
        );
        let cache_path = output.staging.join("cache.rrcache.gz");
        let started = phase_start("reimport_selected_cache");
        let mut imported = SavedApplicationCacheFile::open_generated(
            &cache_path,
            &binding,
            &identity,
            file_limits,
        )?;
        file_statistics("reimport_selected_cache", &imported);
        phase_seconds.insert(
            "reimport_selected_cache",
            phase_end("reimport_selected_cache", started, "ok"),
        );
        let records = compare(
            &prepared,
            &mut pack,
            &binding,
            &mut imported,
            Some(keys),
            &mut phase_seconds,
        )?;
        ensure!(records == keys.len(), "selected count mismatch");
        let started = phase_start("selected_cache_output_identity");
        let digest = sha_file(&cache_path)?;
        ensure!(digest == sha(&bytes), "written output SHA differs");
        raw["schema"] = "vakint.strict-light-cache-native-validation.v1".into();
        raw["selected_keys_sha256"] = extra[0].sha256.clone().into();
        raw["usage_profile_sha256"] = extra[1].sha256.clone().into();
        raw["selected_keys_schema_sha256"] = selection::SELECTED_SCHEMA_SHA.into();
        raw["usage_profile_schema_sha256"] = usage_profile_schema_sha
            .ok_or_else(|| eyre!("selected export lacks its actual profile schema"))?
            .into();
        raw["cache_sha256"] = digest.into();
        raw["cache_identity"] = serde_json::to_value(identity)?;
        raw["decoded_sha256"] = decoded_sha(&cache_path, identity.decoded_bytes)?.into();
        raw["selected_records"] = records.into();
        raw["reimported_records"] = records.into();
        raw["complete_records"] = records.into();
        raw["usage_semantics_validated_by_this_tool"] = false.into();
        phase_seconds.insert(
            "selected_cache_output_identity",
            phase_end("selected_cache_output_identity", started, "ok"),
        );
    } else {
        let legacy = &extra[0];
        let started = phase_start("open_legacy_cache_file");
        let mut imported = SavedApplicationCacheFile::open(&legacy.path, &binding, file_limits)?;
        file_statistics("open_legacy_cache_file", &imported);
        phase_seconds.insert(
            "open_legacy_cache_file",
            phase_end("open_legacy_cache_file", started, "ok"),
        );
        let expected = expected_records.expect("source-only expected count");
        ensure!(
            source_raw_refs == expected && imported.keys().len() == expected,
            "source raw-reference/file count differs from expected"
        );
        let records = compare(
            &prepared,
            &mut pack,
            &binding,
            &mut imported,
            None,
            &mut phase_seconds,
        )?;
        ensure!(
            records == expected,
            "source unique key count differs from expected"
        );
        raw["schema"] = "vakint.strict-cache-source-parity-native-validation.v1".into();
        raw["legacy_cache_sha256"] = legacy.sha256.clone().into();
        raw["native_unique_records"] = records.into();
        raw["legacy_validated_records"] = records.into();
        raw["light_export_performed"] = false.into();
        raw["usage_selection_claim"] = false.into();
    }
    let started = phase_start("final_inputs_indexes_artifact_reference");
    for document in [&application, &binding_doc, &inventory, &artifacts]
        .into_iter()
        .chain(extra.iter())
    {
        document.unchanged()?;
    }
    ensure!(
        index_identity::native_index_identity(&native_path)? == source_identity
            && pack.generation() == generation,
        "source index identity changed"
    );
    // Byte equality alone cannot detect a replaced ROOT or parent directory.
    // Reapply the strict presentation check after all Native work as well.
    artifacts.unchanged_reference(proof_root.as_ref(), &artifact_reference)?;
    phase_seconds.insert(
        "final_inputs_indexes_artifact_reference",
        phase_end("final_inputs_indexes_artifact_reference", started, "ok"),
    );
    raw["source_unchanged"] = true.into();
    raw["success"] = true.into();
    // Only completed, nonoverlapping phases are present. Publication happens
    // after this report is written and therefore remains stderr-only.
    append_completed_phases(&mut raw, &phase_seconds)?;
    let started = phase_start("output_publication");
    output.write("raw-validation.json", &serde_json::to_vec_pretty(&raw)?)?;
    output.publish()?;
    phase_end("output_publication", started, "ok");
    Ok(())
}

fn main() -> Result<()> {
    let arguments = std::env::args().skip(1).collect::<Vec<_>>();
    if arguments == ["build-info"] || arguments == ["--build-info"] {
        println!("{}", serde_json::to_string_pretty(&cohort()?)?);
        return Ok(());
    }
    if arguments == ["--help"] {
        println!("{USAGE}");
        return Ok(());
    }
    execute(Args::parse()?)
}

#[cfg(test)]
mod reference_parser_tests {
    use super::*;
    use proof_reference::test_support::Scratch;

    #[test]
    fn record_diagnostics_are_bounded_to_each_1024_records_and_final_count() {
        let periodic = (0..=25088)
            .filter(|count| record_counter_due(*count, false))
            .collect::<Vec<_>>();
        assert_eq!(
            periodic,
            (1..=24).map(|index| index * 1024).collect::<Vec<_>>()
        );
        assert!(record_counter_due(25088, true));
        assert!(record_counter_due(0, true));
        assert!(!record_counter_due(0, false));
    }

    #[test]
    fn record_diagnostic_line_is_only_phase_count_and_elapsed_metadata() {
        assert_eq!(
            record_counter_line(
                "compare_full_native_visitor",
                1024,
                false,
                Duration::from_millis(1250)
            ),
            "producer_phase=compare_full_native_visitor event=record_count processed_records=1024 final=false elapsed_seconds=1.250000"
        );
        assert_eq!(
            record_counter_line("compare_selected_native_visitor", 7, true, Duration::ZERO),
            "producer_phase=compare_selected_native_visitor event=record_count processed_records=7 final=true elapsed_seconds=0.000000"
        );
    }

    #[test]
    fn optional_timing_map_preserves_absence_and_only_records_completed_named_phases() {
        let mut raw = json!({"success":true});
        append_completed_phases(&mut raw, &BTreeMap::new()).unwrap();
        assert_eq!(raw, json!({"success":true}));
        let completed = BTreeMap::from([
            ("mandatory_admission", 0.25),
            ("load_saved_application", 12.5),
        ]);
        append_completed_phases(&mut raw, &completed).unwrap();
        assert_eq!(
            raw["phase_seconds"],
            json!({"mandatory_admission":0.25,"load_saved_application":12.5})
        );
        for unperformed in [
            "open_legacy_cache_file",
            "encode_selected_completed_cache",
            "output_publication",
            "selection",
            "ranking",
            "total",
        ] {
            assert!(raw["phase_seconds"].get(unperformed).is_none());
        }
    }

    #[test]
    fn private_five_loop_runtime_cannot_bypass_absent_shared_admission() {
        assert!(require_runtime_admission(None).is_err());
    }

    fn arguments(mode: &str) -> Vec<String> {
        let mut args = vec![mode.to_owned()];
        for flag in [
            "--application",
            "--application-sha256",
            "--binding",
            "--binding-sha256",
            "--native-cache",
            "--source-inventory",
            "--source-inventory-sha256",
            "--collector-artifacts",
            "--collector-artifacts-sha256",
            "--output-dir",
        ] {
            args.extend([flag.to_owned(), "synthetic-unused-parser-value".to_owned()]);
        }
        let extras = if mode == "export-selected" {
            vec![
                "--selected-keys",
                "--selected-keys-sha256",
                "--usage-profile",
                "--usage-profile-sha256",
            ]
        } else {
            vec![
                "--legacy-cache",
                "--legacy-cache-sha256",
                "--expected-records",
            ]
        };
        for flag in extras {
            args.extend([flag.to_owned(), "synthetic-unused-parser-value".to_owned()]);
        }
        args
    }

    #[test]
    fn optional_proof_root_preserves_existing_required_arguments_in_both_modes() {
        for mode in ["export-selected", "validate-source-only"] {
            let legacy = Args::from_iter(arguments(mode)).unwrap();
            assert!(!legacy.values.contains_key("--proof-root"));
            let mut values = arguments(mode);
            values.extend([
                "--proof-root".to_owned(),
                "/canonical/path/validated-at-reference-time".to_owned(),
            ]);
            let rooted = Args::from_iter(values).unwrap();
            assert_eq!(
                rooted.text("--proof-root"),
                "/canonical/path/validated-at-reference-time"
            );
            for (flag, value) in legacy.values {
                assert_eq!(rooted.values[&flag], value);
            }
        }
    }

    #[test]
    fn proof_root_parser_rejects_missing_duplicate_and_unknown_arguments() {
        let mut missing = arguments("export-selected");
        missing.push("--proof-root".to_owned());
        assert!(Args::from_iter(missing).is_err());
        let mut duplicate = arguments("export-selected");
        duplicate.extend(["--proof-root", "/root", "--proof-root", "/other"].map(str::to_owned));
        assert!(Args::from_iter(duplicate).is_err());
        let mut unknown = arguments("validate-source-only");
        unknown.extend(["--unknown-proof-alias", "/root"].map(str::to_owned));
        assert!(Args::from_iter(unknown).is_err());
        let mut incomplete = arguments("validate-source-only");
        incomplete.drain(1..3);
        incomplete.extend(["--proof-root", "/root"].map(str::to_owned));
        assert!(Args::from_iter(incomplete).is_err());
    }

    #[test]
    fn document_without_root_preserves_historical_absolute_reference_bytes() {
        let scratch = Scratch::new();
        let (file, sha) = scratch.file("collector-artifacts.json");
        let document = Document::read(&file, &sha).unwrap();
        let historical = json!({"path":file,"sha256":sha});
        assert_eq!(
            serde_json::to_vec(&document.reference(None).unwrap()).unwrap(),
            serde_json::to_vec(&historical).unwrap()
        );
    }

    #[test]
    fn document_rooted_reference_preserves_actual_sha_and_rechecks_contents() {
        let scratch = Scratch::new();
        let (file, sha) = scratch.file("provenance/native-exporter-v2/collector-artifacts.json");
        let document = Document::read(&file, &sha).unwrap();
        let root = ProofRoot::parse(&scratch.0).unwrap();
        assert_eq!(
            document.reference(Some(&root)).unwrap(),
            json!({"path":"provenance/native-exporter-v2/collector-artifacts.json","sha256":sha})
        );
        fs::write(&file, b"changed after authenticated read").unwrap();
        assert!(document.reference(Some(&root)).is_err());
    }

    #[test]
    fn document_does_not_normalize_an_alias_into_an_acceptable_rooted_reference() {
        let scratch = Scratch::new();
        let (file, sha) = scratch.file("collector-artifacts.json");
        let alias = scratch.0.join("./collector-artifacts.json");
        let document = Document::read(&alias, &sha).unwrap();
        assert_eq!(document.path, file);
        assert!(document.reference(None).is_ok());
        assert!(
            document
                .reference(Some(&ProofRoot::parse(&scratch.0).unwrap()))
                .is_err()
        );
    }

    #[test]
    fn root_replacement_with_equal_bytes_fails_reference_postflight() {
        let scratch = Scratch::new();
        let (file, sha) = scratch.file("provenance/native-exporter-v2/collector-artifacts.json");
        let bytes = fs::read(&file).unwrap();
        let document = Document::read(&file, &sha).unwrap();
        let root = ProofRoot::parse(&scratch.0).unwrap();
        let reference = document.reference(Some(&root)).unwrap();
        let moved = scratch.0.with_extension("moved-root");
        fs::rename(&scratch.0, &moved).unwrap();
        fs::create_dir_all(file.parent().unwrap()).unwrap();
        fs::write(&file, bytes).unwrap();
        document.unchanged().unwrap();
        assert!(
            document
                .unchanged_reference(Some(&root), &reference)
                .is_err()
        );
        fs::remove_dir_all(moved).unwrap();
    }
}
