//! Optional transport presentation for authenticated document references.
//! No application, Native state, cache, role or usage-profile APIs are used.
use std::{
    fs::{self, File, Metadata},
    io::Read,
    path::{Component, Path, PathBuf},
};

use eyre::{Result, ensure, eyre};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

#[derive(Debug)]
pub(crate) struct ProofRoot {
    path: PathBuf,
    identity: Metadata,
}

fn normal_absolute(path: &Path) -> Result<&str> {
    let text = path
        .to_str()
        .ok_or_else(|| eyre!("proof paths must be UTF-8"))?;
    ensure!(
        text.starts_with('/'),
        "proof paths must be canonical absolute POSIX paths"
    );
    ensure!(
        !text.contains('\\') && !text.chars().any(char::is_control),
        "invalid proof path character"
    );
    if text != "/" {
        ensure!(
            text[1..]
                .split('/')
                .all(|part| !part.is_empty() && part != "." && part != ".."),
            "proof paths forbid empty, dot or traversal components"
        );
    }
    Ok(text)
}

fn normal_relative(path: &Path) -> Result<&str> {
    let text = path
        .to_str()
        .ok_or_else(|| eyre!("transport reference must be UTF-8"))?;
    ensure!(
        !text.is_empty() && !path.is_absolute(),
        "transport reference must be a nonempty relative path"
    );
    ensure!(
        !text.contains('\\') && !text.chars().any(char::is_control),
        "invalid transport reference character"
    );
    ensure!(
        text.split('/')
            .all(|part| !part.is_empty() && part != "." && part != ".."),
        "transport reference is not normal ROOT-relative POSIX syntax"
    );
    Ok(text)
}

/// Check every existing path component, not only the final file/directory.
/// A symlink which resolves back inside ROOT is still an alias and is rejected.
fn regular_path(path: &Path, is_file: bool) -> Result<Metadata> {
    normal_absolute(path)?;
    let mut prefix = PathBuf::from("/");
    for component in path.components() {
        match component {
            Component::RootDir => {}
            Component::Normal(name) => {
                prefix.push(name);
                let metadata = fs::symlink_metadata(&prefix)?;
                ensure!(
                    !metadata.is_symlink(),
                    "proof path contains a symlink: {}",
                    prefix.display()
                );
                if prefix != path {
                    ensure!(
                        metadata.is_dir(),
                        "proof path parent is not a directory: {}",
                        prefix.display()
                    );
                }
            }
            _ => return Err(eyre!("invalid proof path component")),
        }
    }
    let metadata = fs::symlink_metadata(path)?;
    ensure!(
        !metadata.is_symlink()
            && if is_file {
                metadata.is_file()
            } else {
                metadata.is_dir()
            },
        "proof path has wrong regular-file/directory kind: {}",
        path.display()
    );
    ensure!(
        path.canonicalize()?.as_os_str() == path.as_os_str(),
        "proof path is an absolute alias rather than its canonical path"
    );
    Ok(metadata)
}

fn same_file(left: &Metadata, right: &Metadata) -> bool {
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        left.dev() == right.dev() && left.ino() == right.ino()
    }
    #[cfg(not(unix))]
    {
        // Runtime publication is Linux-only; keep non-Unix builds fallible.
        let _ = (left, right);
        false
    }
}

impl ProofRoot {
    pub(crate) fn parse(path: &Path) -> Result<Self> {
        let identity = regular_path(path, false)?;
        Ok(Self {
            path: path.to_owned(),
            identity,
        })
    }

    pub(crate) fn reference(
        &self,
        original: &Path,
        canonical: &Path,
        expected_sha: &str,
    ) -> Result<Value> {
        let root_now = regular_path(&self.path, false)?;
        ensure!(
            same_file(&self.identity, &root_now),
            "proof root was replaced"
        );
        normal_absolute(original)?;
        normal_absolute(canonical)?;
        ensure!(
            original.as_os_str() == canonical.as_os_str(),
            "referenced input uses an absolute path alias"
        );
        let metadata = regular_path(canonical, true)?;
        let relative = canonical
            .strip_prefix(&self.path)
            .map_err(|_| eyre!("referenced file lies outside proof root"))?;
        let transport = normal_relative(relative)?;
        // Reconstructing the transport path must identify the exact same file,
        // rather than a similarly spelled prefix, symlink or outside hardlink.
        let transported = self.path.join(relative);
        let transported_metadata = regular_path(&transported, true)?;
        ensure!(
            same_file(&metadata, &transported_metadata),
            "transport path identifies another file"
        );
        let mut input = File::open(&transported)?;
        ensure!(
            same_file(&metadata, &input.metadata()?),
            "referenced file changed before hashing"
        );
        let mut digest = Sha256::new();
        let mut block = [0; 65536];
        loop {
            let count = input.read(&mut block)?;
            if count == 0 {
                break;
            }
            digest.update(&block[..count]);
        }
        ensure!(
            format!("{:x}", digest.finalize()) == expected_sha,
            "referenced file SHA256 changed"
        );
        ensure!(
            same_file(&metadata, &regular_path(&transported, true)?),
            "referenced file changed during hashing"
        );
        ensure!(
            same_file(&self.identity, &regular_path(&self.path, false)?),
            "proof root changed during hashing"
        );
        Ok(json!({"path":transport,"sha256":expected_sha}))
    }
}

#[cfg(test)]
pub(crate) mod test_support {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    pub(crate) struct Scratch(pub PathBuf);
    impl Scratch {
        pub(crate) fn new() -> Self {
            let nonce = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = Path::new(env!("CARGO_MANIFEST_DIR")).join(format!(
                "proof-root-synthetic-{}-{nonce}",
                std::process::id()
            ));
            fs::create_dir(&path).unwrap();
            Self(path.canonicalize().unwrap())
        }
        pub(crate) fn file(&self, name: &str) -> (PathBuf, String) {
            let path = self.0.join(name);
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(&path, b"synthetic document; no Native or scientific data\n").unwrap();
            let sha = format!("{:x}", Sha256::digest(fs::read(&path).unwrap()));
            (path, sha)
        }
    }
    impl Drop for Scratch {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).unwrap();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{test_support::Scratch, *};

    #[test]
    fn canonical_contained_file_emits_exact_relative_transport_and_same_sha() {
        let scratch = Scratch::new();
        let (path, sha) = scratch.file("provenance/native-exporter-v2/collector-artifacts.json");
        let root = ProofRoot::parse(&scratch.0).unwrap();
        assert_eq!(
            root.reference(&path, &path, &sha).unwrap(),
            json!({"path":"provenance/native-exporter-v2/collector-artifacts.json","sha256":sha})
        );
    }

    #[test]
    fn root_requires_existing_normal_absolute_regular_directory() {
        let scratch = Scratch::new();
        let (file, _) = scratch.file("file.json");
        for bad in [
            PathBuf::from("relative-root"),
            scratch.0.join("missing"),
            file,
            PathBuf::from(format!("{}/.", scratch.0.display())),
            PathBuf::from(format!("{}//", scratch.0.display())),
            scratch.0.join("../").join(scratch.0.file_name().unwrap()),
        ] {
            assert!(
                ProofRoot::parse(&bad).is_err(),
                "accepted invalid root: {}",
                bad.display()
            );
        }
    }

    #[test]
    fn file_reference_rejects_traversal_absolute_aliases_and_relative_inputs() {
        let scratch = Scratch::new();
        let (file, sha) = scratch.file("file.json");
        let root = ProofRoot::parse(&scratch.0).unwrap();
        for alias in [
            PathBuf::from("file.json"),
            scratch.0.join("./file.json"),
            PathBuf::from(format!("{}//file.json", scratch.0.display())),
            scratch.0.join("sub/../file.json"),
        ] {
            assert!(root.reference(&alias, &file, &sha).is_err());
        }
        assert!(normal_relative(Path::new("/absolute.json")).is_err());
        assert!(normal_relative(Path::new("../escape.json")).is_err());
        assert!(normal_relative(Path::new("a\\escape.json")).is_err());
    }

    #[test]
    fn same_bytes_outside_root_and_prefix_collision_are_not_containment() {
        let scratch = Scratch::new();
        let root_dir = scratch.0.join("root");
        fs::create_dir(&root_dir).unwrap();
        let (outside, sha) = scratch.file("root-other/file.json");
        let root = ProofRoot::parse(&root_dir).unwrap();
        assert!(root.reference(&outside, &outside, &sha).is_err());
        let (outside, sha) = scratch.file("outside.json");
        assert!(root.reference(&outside, &outside, &sha).is_err());
    }

    #[cfg(unix)]
    #[test]
    fn root_leaf_parent_and_inside_pointing_symlinks_are_rejected() {
        use std::os::unix::fs::symlink;
        let scratch = Scratch::new();
        let (file, sha) = scratch.file("real/file.json");
        symlink(scratch.0.join("real"), scratch.0.join("alias-dir")).unwrap();
        symlink(&file, scratch.0.join("alias-file.json")).unwrap();
        assert!(ProofRoot::parse(&scratch.0.join("alias-dir")).is_err());
        assert!(ProofRoot::parse(&scratch.0.join("alias-dir/inner")).is_err());
        let root = ProofRoot::parse(&scratch.0).unwrap();
        for alias in [
            scratch.0.join("alias-file.json"),
            scratch.0.join("alias-dir/file.json"),
        ] {
            assert!(root.reference(&alias, &file, &sha).is_err());
            assert!(root.reference(&alias, &alias, &sha).is_err());
        }
    }

    #[test]
    fn changed_document_or_replaced_root_cannot_emit_a_reference() {
        let scratch = Scratch::new();
        let root_dir = scratch.0.join("root");
        fs::create_dir(&root_dir).unwrap();
        let (file, sha) = scratch.file("root/file.json");
        let root = ProofRoot::parse(&root_dir).unwrap();
        fs::write(&file, b"changed bytes").unwrap();
        assert!(root.reference(&file, &file, &sha).is_err());
        fs::rename(&root_dir, scratch.0.join("old-root")).unwrap();
        fs::create_dir(&root_dir).unwrap();
        let (new_file, new_sha) = scratch.file("root/file.json");
        assert!(root.reference(&new_file, &new_file, &new_sha).is_err());
    }
}
