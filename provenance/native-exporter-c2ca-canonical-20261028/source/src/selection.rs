//! Parse the frozen public work JSON into existing Native key primitives.
//! Eligibility, profile completeness and measured frequencies belong to the
//! separate scientific validator. This module identifies only its outer schema
//! tag; it does not validate usage eligibility or completeness.
use std::{collections::BTreeSet, io::Read};

use eyre::{Result, ensure};
use rustred::{
    family::IntegralKey,
    persistence::application_cache::{ApplicationCacheBinding, ApplicationCacheKey},
};
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const MAX_LIGHT_BYTES: usize = 95_000_000;
pub const SELECTED_SCHEMA_SHA: &str =
    "c77a1d043a9925602b5cbc25d78c322a5089e45f1f59347c8ee485e52b02d232";
pub const PROFILE_SCHEMA_SHA: &str =
    "515a986b3364a8a1aa919e50b65e2f6d3dbe5bbc030440270b66df575aeeea46";

pub const COMPOSED_PROFILE_SCHEMA_SHA: &str =
    "3d8bc402451ebeab16a67b5119eaaaa19b0410d905dcffbf75c5bf95bcf945e4";

/// Identify only the authenticated outer profile tag for the export receipt.
/// The source admission tool remains responsible for complete usage validation.
pub fn profile_schema_sha256(archived: &[u8]) -> Result<&'static str> {
    let value: Value = serde_json::from_slice(&json_bytes(archived)?)?;
    match value.get("schema").and_then(Value::as_str) {
        Some("vakint.cache-record-usage-profile.v1") => Ok(PROFILE_SCHEMA_SHA),
        Some("vakint.cache-record-usage-profile.v2") => Ok(COMPOSED_PROFILE_SCHEMA_SHA),
        _ => eyre::bail!("unsupported usage-profile schema"),
    }
}

/// Serialization adapter for the existing four Native binding fields only.
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct BindingJson {
    pub artifact_digest: [u8; 32],
    pub family_fingerprint: String,
    pub physical_arity: usize,
    pub layer: String,
}

impl BindingJson {
    pub fn native(&self) -> Result<ApplicationCacheBinding> {
        ensure!(
            self.physical_arity == 15,
            "producer requires physical arity 15"
        );
        ensure!(!self.family_fingerprint.is_empty(), "empty family identity");
        ensure!(
            self.layer == "saved-application-route-apply-v1",
            "unsupported solver layer"
        );
        Ok(ApplicationCacheBinding {
            artifact_digest: self.artifact_digest,
            family_fingerprint: self.family_fingerprint.clone(),
            physical_arity: self.physical_arity,
            layer: self.layer.clone(),
        })
    }
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "lowercase", deny_unknown_fields)]
enum Work {
    Route {
        powers: Vec<i64>,
    },
    Apply {
        owner_sector: Vec<bool>,
        powers: Vec<i64>,
    },
}

impl Work {
    fn native(self, arity: usize) -> Result<ApplicationCacheKey> {
        let key = match self {
            Self::Route { powers } => ApplicationCacheKey::route(&IntegralKey::try_new(powers)?),
            Self::Apply {
                owner_sector,
                powers,
            } => ApplicationCacheKey::apply(owner_sector, &IntegralKey::try_new(powers)?),
        };
        key.validate(arity)?;
        Ok(key)
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Document {
    schema: String,
    semantic_binding: BindingJson,
    usage_profile_sha256: String,
    eligible_case_ids: Vec<String>,
    keys: Vec<Work>,
    selection: Value,
}

pub fn valid_sha(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}

/// Hash archived bytes outside this parser. Gzip is the existing standard
/// compression wrapper around JSON, not a new cache/profile codec.
pub fn json_bytes(archived: &[u8]) -> Result<Vec<u8>> {
    if !archived.starts_with(&[0x1f, 0x8b]) {
        return Ok(archived.to_vec());
    }
    let mut decoder = flate2::bufread::GzDecoder::new(archived);
    let mut plain = Vec::new();
    decoder.read_to_end(&mut plain)?;
    ensure!(
        decoder.into_inner().is_empty(),
        "extra gzip members/trailing JSON archive data"
    );
    Ok(plain)
}

pub fn parse_selection(
    archived: &[u8],
    usage_sha: &str,
    binding: &ApplicationCacheBinding,
) -> Result<Vec<ApplicationCacheKey>> {
    ensure!(valid_sha(usage_sha), "invalid usage-profile SHA256");
    let document: Document = serde_json::from_slice(&json_bytes(archived)?)?;
    ensure!(
        document.schema == "vakint.cache-record-selection.v1",
        "unsupported selection schema"
    );
    ensure!(
        document.semantic_binding.native()? == *binding,
        "selection binding differs"
    );
    ensure!(
        document.usage_profile_sha256 == usage_sha,
        "selection usage-profile SHA256 differs"
    );
    ensure!(
        !document.eligible_case_ids.is_empty(),
        "empty eligible case list"
    );
    let mut cases = BTreeSet::new();
    for case in document.eligible_case_ids {
        ensure!(
            !case.is_empty() && cases.insert(case),
            "empty/duplicate eligible case identity"
        );
    }
    ensure!(
        document.selection.is_object(),
        "selection policy must be an object"
    );
    ensure!(
        document.selection["method"]
            .as_str()
            .is_some_and(|s| !s.is_empty()),
        "selection method missing"
    );
    ensure!(
        document.selection["max_compressed_bytes"].as_u64() == Some(MAX_LIGHT_BYTES as u64),
        "selection must request 95000000 decimal bytes"
    );
    ensure!(!document.keys.is_empty(), "empty selected key list");
    let mut keys = BTreeSet::new();
    for work in document.keys {
        ensure!(
            keys.insert(work.native(binding.physical_arity)?),
            "duplicate selected Native key"
        );
    }
    Ok(keys.into_iter().collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn fixture() -> (Value, ApplicationCacheBinding) {
        let binding = BindingJson {
            artifact_digest: [17; 32],
            family_fingerprint: "synthetic-not-science".into(),
            physical_arity: 15,
            layer: "saved-application-route-apply-v1".into(),
        };
        let value = json!({"schema":"vakint.cache-record-selection.v1","semantic_binding":binding,
            "usage_profile_sha256":"a".repeat(64),"eligible_case_ids":["synthetic-tuning"],
            "keys":[{"kind":"route","powers":[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]}],
            "selection":{"method":"synthetic-parser-test","max_compressed_bytes":95000000}});
        (value, binding.native().unwrap())
    }
    fn accepted(value: &Value, binding: &ApplicationCacheBinding) -> bool {
        parse_selection(
            &serde_json::to_vec(value).unwrap(),
            &"a".repeat(64),
            binding,
        )
        .is_ok()
    }
    #[test]
    fn public_work_maps_to_exact_existing_native_keys() {
        let (mut doc, binding) = fixture();
        doc["keys"].as_array_mut().unwrap().push(json!({"kind":"apply","owner_sector":[true,true,true,true,true,true,true,true,true,true,true,true,true,true,false],"powers":[1,1,1,1,1,1,1,1,1,1,1,1,1,1,-2]}));
        let keys = parse_selection(
            &serde_json::to_vec(&doc).unwrap(),
            &"a".repeat(64),
            &binding,
        )
        .unwrap();
        assert_eq!(keys.len(), 2);
        assert_eq!(keys[1].owner().last(), Some(&false));
        assert_eq!(keys[1].powers().last(), Some(&-2));
    }
    #[test]
    fn duplicates_empty_lists_and_unknown_top_fields_fail() {
        let (base, binding) = fixture();
        for (field, value) in [
            ("keys", json!([])),
            ("eligible_case_ids", json!([])),
            ("eligible_case_ids", json!(["same", "same"])),
        ] {
            let mut doc = base.clone();
            doc[field] = value;
            assert!(!accepted(&doc, &binding));
        }
        let mut doc = base.clone();
        doc["keys"]
            .as_array_mut()
            .unwrap()
            .push(base["keys"][0].clone());
        assert!(!accepted(&doc, &binding));
        let mut doc = base;
        doc["trusted"] = json!(true);
        assert!(!accepted(&doc, &binding));
    }
    #[test]
    fn arity_owner_unknown_stage_and_route_owner_fail() {
        let (base, binding) = fixture();
        for work in [
            json!({"kind":"route","powers":[1]}),
            json!({"kind":"guarded_root","powers":[1]}),
            json!({"kind":"route","powers":[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],"owner_sector":null}),
            json!({"kind":"apply","powers":[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],"owner_sector":[true,true,true,true,true,true,true,true,true,true,true,true,true,true,false]}),
        ] {
            let mut doc = base.clone();
            doc["keys"] = json!([work]);
            assert!(!accepted(&doc, &binding));
        }
    }
    #[test]
    fn wrong_schema_binding_usage_hash_and_budget_fail() {
        let (base, binding) = fixture();
        for (pointer, value) in [
            ("/schema", json!("unknown")),
            ("/semantic_binding/artifact_digest/0", json!(18)),
            ("/usage_profile_sha256", json!("b".repeat(64))),
            ("/selection/max_compressed_bytes", json!(95000001)),
            ("/selection/method", json!("")),
        ] {
            let mut doc = base.clone();
            *doc.pointer_mut(pointer).unwrap() = value;
            assert!(!accepted(&doc, &binding));
        }
        assert!(!valid_sha(&"A".repeat(64)));
    }
    #[test]
    fn standard_gzip_json_uses_same_parser_and_rejects_extra_members() {
        use std::io::Write;
        let (doc, binding) = fixture();
        let raw = serde_json::to_vec(&doc).unwrap();
        let mut encoder = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
        encoder.write_all(&raw).unwrap();
        let gzip = encoder.finish().unwrap();
        assert!(parse_selection(&gzip, &"a".repeat(64), &binding).is_ok());
        let mut twice = gzip.clone();
        twice.extend_from_slice(&gzip);
        assert!(parse_selection(&twice, &"a".repeat(64), &binding).is_err());
        let mut trailing = gzip;
        trailing.push(0);
        assert!(parse_selection(&trailing, &"a".repeat(64), &binding).is_err());
    }
    #[test]
    fn binding_adapter_rejects_non_native_fields_and_bad_shapes() {
        assert!(serde_json::from_value::<BindingJson>(json!({"binding":{}})).is_err());
        let (mut doc, _) = fixture();
        doc["semantic_binding"]["artifact_digest"] = json!([0, 1]);
        assert!(serde_json::from_value::<BindingJson>(doc["semantic_binding"].clone()).is_err());
    }
    #[test]
    fn actual_profile_tag_preserves_v1_and_records_v2_schema_identity() {
        for (schema, expected) in [
            ("vakint.cache-record-usage-profile.v1", PROFILE_SCHEMA_SHA),
            (
                "vakint.cache-record-usage-profile.v2",
                COMPOSED_PROFILE_SCHEMA_SHA,
            ),
        ] {
            let raw = serde_json::to_vec(&json!({"schema": schema})).unwrap();
            assert_eq!(profile_schema_sha256(&raw).unwrap(), expected);
        }
        for raw in [b"{}".as_slice(), br#"{"schema":"unknown"}"#, b"not JSON"] {
            assert!(profile_schema_sha256(raw).is_err());
        }
    }
}
