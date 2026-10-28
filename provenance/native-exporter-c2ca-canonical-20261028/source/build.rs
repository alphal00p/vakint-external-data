//! Actual private-helper/Native build identities. No caller-supplied revision stamps.
use std::{collections::BTreeMap, env, fs, path::Path, process::Command};

use serde_json::json;
use sha2::{Digest, Sha256};

const NATIVE: &str =
    "/shared/codex-1/vakint_rustred/workspace/5l-push/native-cache-monitor-integration";
const REVISION: &str = "c2ca815cc906bdeaf7cb8c63b637e81a80fba917";
const KERNEL: &str = "9cd57678d8817ec33c05cacba4925162f1c86b0b";

fn command(program: &str, args: &[&str]) -> String {
    let output = Command::new(program)
        .args(args)
        .output()
        .expect("run build identity command");
    assert!(
        output.status.success(),
        "build identity command failed: {program}"
    );
    String::from_utf8(output.stdout)
        .expect("UTF-8 identity")
        .trim()
        .to_owned()
}

fn git(path: &str, args: &[&str]) -> String {
    let mut all = vec!["-C", path];
    all.extend(args);
    command("git", &all)
}

fn sha(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn main() {
    assert_eq!(
        git(NATIVE, &["rev-parse", "HEAD"]),
        REVISION,
        "wrong Native source"
    );
    assert!(
        git(NATIVE, &["status", "--porcelain", "--untracked-files=all"]).is_empty(),
        "Native source is dirty"
    );
    let kernel_path = format!("{NATIVE}/vendor/symbolica");
    assert_eq!(git(&kernel_path, &["rev-parse", "HEAD"]), KERNEL);
    assert!(
        git(
            &kernel_path,
            &["status", "--porcelain", "--untracked-files=all"]
        )
        .is_empty(),
        "kernel source is dirty"
    );
    let state = fs::read_to_string(Path::new(&kernel_path).join("src/state.rs")).unwrap();
    assert!(
        state.contains("const EXPORT_FORMAT_VERSION: u16 = 6;"),
        "wrong State format"
    );

    let native_identity = json!({
        "schema":"native.git-source-tree-identity.v1",
        "source_repository":"https://github.com/alphal00p/rustred",
        "revision":REVISION,"tree":git(NATIVE,&["rev-parse","HEAD^{tree}"]),
        "kernel_revision":KERNEL,"kernel_tree":git(&kernel_path,&["rev-parse","HEAD^{tree}"]),
        "clean":true,"codec_state_format":6
    });
    let native_sha = sha(&serde_json::to_vec(&native_identity).unwrap());
    let helper_root = env::var("CARGO_MANIFEST_DIR").unwrap();
    assert_eq!(
        sha(
            &fs::read(Path::new(&helper_root).join("src/resource_guard_admission.rs"))
                .expect("reviewed shared admission source")
        ),
        "bb3223d27584b42069d3813ebdcaefa6598a0935ca4531714a50248b334870cb",
        "shared task-admission source differs from the reviewed owner module"
    );
    let mut source_files = BTreeMap::new();
    // Cargo creates the resolved lock before compiling this build script.
    for name in [
        "Cargo.toml",
        "Cargo.lock",
        "build.rs",
        "src/main.rs",
        "src/selection.rs",
        "src/union.rs",
        "src/index_identity.rs",
        "src/proof_reference.rs",
        "src/resource_guard_admission.rs",
    ] {
        let path = Path::new(&helper_root).join(name);
        source_files.insert(
            name,
            sha(&fs::read(&path).expect("frozen helper source/lock")),
        );
        println!("cargo:rerun-if-changed={}", path.display());
    }
    let source_identity = json!({
        "schema":"native.private-layered-helper-source-identity.v1",
        "role":"native-selected-cache-producer","source_repository":"https://github.com/alphal00p/rustred",
        "source_layer":"private standalone v4-census successor on public Nativec2ca with actualv1/v2profile schema metadata, source parity and unchanged ordered opaque union; exact reviewed task-admission module; no linked Vakint Main",
        "files":source_files,"native_identity":native_identity
    });
    let helper_sha = sha(&serde_json::to_vec(&source_identity).unwrap());
    let rustc = command(&env::var("RUSTC").unwrap(), &["-Vv"]);
    let profile = env::var("PROFILE").unwrap();
    let stamps = BTreeMap::from([
        ("VAKINT_CACHE_BUILD_RUSTC", rustc.clone()),
        ("VAKINT_CACHE_BUILD_PROFILE", profile.clone()),
        ("VAKINT_CACHE_BUILD_GIT_REVISION", REVISION.to_owned()),
        ("VAKINT_CACHE_BUILD_RUSTRED_REVISION", REVISION.to_owned()),
        ("VAKINT_CACHE_BUILD_SYMBOLICA_REVISION", KERNEL.to_owned()),
        (
            "VAKINT_CACHE_BUILD_MAIN_SOURCE_SNAPSHOT_SHA256",
            helper_sha.clone(),
        ),
        (
            "VAKINT_CACHE_BUILD_NATIVE_SOURCE_SNAPSHOT_SHA256",
            native_sha.clone(),
        ),
    ]);
    // Multiline rustc -Vv is stored in JSON; rustc-env values use one line.
    for (key, value) in &stamps {
        println!("cargo:rustc-env={key}={}", value.replace('\n', " | "));
    }
    let identity = json!({
        "role":"native-selected-cache-producer","source_repository":"https://github.com/alphal00p/rustred",
        "source_layer":"private standalone v4-census helper with ordered opaque union and exact reviewed task-admission module; not linked Vakint Main",
        "main_revision":REVISION,"main_source_snapshot_sha256":helper_sha,
        "native_revision":REVISION,"native_source_snapshot_sha256":native_sha,
        "kernel_revision":KERNEL,"collector_source_sha256":source_files["src/main.rs"],
        "profile":profile,"rustc":rustc,"stamps":stamps,"source_identity":source_identity
    });
    fs::write(
        Path::new(&env::var("OUT_DIR").unwrap()).join("compiled-cohort.json"),
        serde_json::to_vec_pretty(&identity).unwrap(),
    )
    .unwrap();
    for repository in [NATIVE, &kernel_path] {
        for item in ["HEAD", "index"] {
            let path = git(repository, &["rev-parse", "--git-path", item]);
            let path = Path::new(&path);
            let path = if path.is_absolute() {
                path.to_owned()
            } else {
                Path::new(repository).join(path)
            };
            println!("cargo:rerun-if-changed={}", path.display());
        }
    }
    // Catch an unstaged dependency edit as well as a changed Git HEAD. The
    // build coordinator separately freezes/checks the complete source cohort.
    for path in [
        format!("{NATIVE}/crates"),
        format!("{NATIVE}/Cargo.toml"),
        format!("{NATIVE}/Cargo.lock"),
        format!("{kernel_path}/src"),
        format!("{kernel_path}/lib"),
    ] {
        println!("cargo:rerun-if-changed={path}");
    }
    println!("cargo:rerun-if-env-changed=RUSTC");
}
