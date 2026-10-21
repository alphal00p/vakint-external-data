#!/usr/bin/env python3
"""Copy an explicit scientific proof allowlist without changing original bytes.

Packing establishes file integrity only. The independent numerical/scientific
verifier must admit the resulting bundle before any numerical capability changes.
"""
from __future__ import annotations
import argparse,ctypes,errno,gzip,hashlib,json,math,os,re,secrets,shutil,stat,tempfile,zlib
from pathlib import Path,PurePosixPath

INDEX_SCHEMA='vakint.pr11d.portable-proof-index.v1'
DEFAULT_ALLOWED_ROOTS=(
 '/shared/codex-1/vakint_rustred/workspace',
 '/shared/codex-2/vacuum_masters/MASTERS',
)
HASH=re.compile(r'[0-9a-f]{64}\Z')
RELATIVE_COMPONENT=re.compile(r'[A-Za-z0-9_.-]+\Z')
BLOCKED_COMPONENTS={'.ssh','.gnupg','.config','.git','.cache','venv','__pycache__','wolfram-license','mathematica-license','development-license','private'}
BLOCKED_BASENAMES={'mathpass','.env','.netrc','env.sh','credentials','credentials.json','secrets.json','tokens.json','id_rsa','id_ed25519','license.txt','license.dat'}

class ProofError(ValueError):pass
def require(ok,message):
    if not ok:raise ProofError(message)
def unique(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'Duplicate JSON key: '+str(key));result[key]=value
    return result
def finite_float(text):
    value=float(text);require(math.isfinite(value),'Nonfinite JSON number');return value
def parse_json(data):
    return json.loads(data,object_pairs_hook=unique,parse_float=finite_float,parse_constant=lambda x:(_ for _ in ()).throw(ProofError('Nonfinite JSON '+x)))
def load_json(path,expected_sha256=None):return parse_json(read_bytes_checked(path,expected_sha256,max_bytes=64<<20))
def checked_digest(value):
    require(type(value)is str and HASH.fullmatch(value)is not None,'Expected lowercase SHA256');return value
def canonical_absolute(value):
    text=os.fspath(value);require(type(text)is str and '\x00'not in text,'Invalid original path')
    require(text.startswith('/')and not text.startswith('//')and '\\'not in text,'Original path must be canonical absolute POSIX')
    require(all(p not in ('','.','..')for p in text.split('/')[1:]),'Noncanonical original path')
    require(str(PurePosixPath(text))==text,'Noncanonical original path');return Path(text)
def relative_path(value):
    require(type(value)is str and value and not value.startswith('/')and'\\'not in value and'\x00'not in value,'Expected portable relative path')
    pieces=value.split('/');require(all(p not in ('','.','..')and RELATIVE_COMPONENT.fullmatch(p)is not None for p in pieces),'Unsafe portable relative path')
    return PurePosixPath(value)
def _parent_fd(path,*,create=False):
    """Hold every traversed directory by descriptor; never follow symlinks."""
    path=canonical_absolute(path);current=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for component in path.parts[1:-1]:
            if create:
                try:os.mkdir(component,0o700,dir_fd=current)
                except FileExistsError:pass
            try:following=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=current)
            except OSError as error:raise ProofError('Unsafe or missing directory component: '+component)from error
            os.close(current);current=following
        return current,path.name
    except BaseException:os.close(current);raise
def _relative_parent_fd(root_fd,path,*,create=False):
    relative=relative_path(path);current=os.dup(root_fd)
    try:
        for component in relative.parts[:-1]:
            if create:
                try:os.mkdir(component,0o700,dir_fd=current)
                except FileExistsError:pass
            try:following=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=current)
            except OSError as error:raise ProofError('Unsafe or missing relative directory: '+component)from error
            os.close(current);current=following
        return current,relative.name
    except BaseException:os.close(current);raise
def _open_regular(path,*,flags=os.O_RDONLY,create=False,create_parents=False,root_fd=None):
    parent,leaf=_parent_fd(path,create=create_parents)if root_fd is None else _relative_parent_fd(root_fd,path,create=create_parents)
    try:
        try:fd=os.open(leaf,flags|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=parent)
        except OSError as error:raise ProofError('Unsafe or unavailable proof file: '+str(path))from error
    finally:os.close(parent)
    info=os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):os.close(fd);raise ProofError('Not a regular proof file: '+str(path))
    return fd
def _read_open_fd(fd,expected_sha256=None,*,max_bytes=512<<20,expected_bytes=None):
    with os.fdopen(fd,'rb')as stream:
        info=os.fstat(stream.fileno());require(info.st_size<=max_bytes,'Proof-file byte limit exceeded')
        if expected_bytes is not None:require(info.st_size==expected_bytes,'Stored proof-file length mismatch')
        chunks=[];digest=hashlib.sha256();total=0
        for chunk in iter(lambda:stream.read(min(1<<20,max_bytes+1)),b''):
            total+=len(chunk);require(total<=max_bytes,'Proof file grew beyond byte limit');digest.update(chunk);chunks.append(chunk)
    if expected_bytes is not None:require(total==expected_bytes,'Stored proof-file length changed')
    if expected_sha256 is not None:require(digest.hexdigest()==checked_digest(expected_sha256),'Proof-file checksum mismatch')
    return b''.join(chunks)
def read_bytes_checked(path,expected_sha256=None,*,max_bytes=512<<20):
    """Return only the exact bounded bytes whose digest was authenticated."""
    require(type(max_bytes)is int and max_bytes>=0,'Invalid read bound');return _read_open_fd(_open_regular(path),expected_sha256,max_bytes=max_bytes)
def sha(path,*,max_bytes=512<<20):
    digest=hashlib.sha256();fd=_open_regular(path)
    with os.fdopen(fd,'rb')as stream:
        require(os.fstat(stream.fileno()).st_size<=max_bytes,'Proof-file byte limit exceeded');total=0
        for chunk in iter(lambda:stream.read(min(1<<20,max_bytes+1)),b''):
            total+=len(chunk);require(total<=max_bytes,'Proof file grew beyond byte limit');digest.update(chunk)
    return digest.hexdigest()
def reject_symlinks(path,*,allow_missing_leaf=False):
    path=canonical_absolute(path);current=Path('/')
    for index,part in enumerate(path.parts[1:]):
        current/=part
        try:info=current.lstat()
        except FileNotFoundError:
            require(allow_missing_leaf and index==len(path.parts)-2,'Missing file/directory: '+str(current));return
        require(not stat.S_ISLNK(info.st_mode),'Symlink rejected: '+str(current))
        if index<len(path.parts)-2:require(stat.S_ISDIR(info.st_mode),'Non-directory path component: '+str(current))
def source_policy(path,allowed_roots):
    path=canonical_absolute(path)
    require(any(path.is_relative_to(root)for root in allowed_roots),'Source outside explicit allowed roots: '+str(path))
    components=[x.lower()for x in path.parts]
    require(not any(x in BLOCKED_COMPONENTS for x in components),'Private/config/environment tree rejected: '+str(path))
    base=path.name.lower()
    public_attribution=path.name in {'LICENSE','LICENSE.md','COPYING','COPYING.LESSER'}
    require(public_attribution or(base not in BLOCKED_BASENAMES and 'mathpass'not in base and not re.search(r'(^|[-_.])(license|credentials?|secrets?|tokens?)([-_.]|$)',base)),'License/private configuration rejected: '+str(path))
    reject_symlinks(path);info=path.stat();require(stat.S_ISREG(info.st_mode),'Not a regular scientific proof file: '+str(path));return info
def roots(values):
    output=tuple(canonical_absolute(x)for x in values)
    require(output,'An explicit source-root allowlist is required')
    for path in output:reject_symlinks(path);require(path.is_dir(),'Allowed root is not a directory')
    return output
def checked_source_overrides(source_overrides,logical_files,allowed_roots):
    """Explicit byte-identical materializations; never infer paths or hashes."""
    if source_overrides is None:return {}
    require(type(source_overrides)is dict and source_overrides,'Source materializations must be a nonempty logical-to-physical path map')
    output={}
    for logical,physical in source_overrides.items():
        require(type(logical)is str and type(physical)is str,'Source-materialization keys and values must be absolute path strings')
        original=str(canonical_absolute(logical));materialized=str(canonical_absolute(physical))
        require(original in logical_files,'Source materialization is not in the original manifest: '+original)
        require(original!=materialized,'Redundant source materialization rejected')
        source_policy(Path(original),allowed_roots);source_policy(Path(materialized),allowed_roots)
        output[original]=materialized
    return output
def inventory(provenance_manifest,expected_sha,allowed_roots,*,source_overrides=None,max_files=10000,max_single_bytes=512<<20,max_total_bytes=8<<30):
    path=canonical_absolute(provenance_manifest);source_policy(path,allowed_roots);checked_digest(expected_sha);require(sha(path)==expected_sha,'Provenance manifest checksum mismatch')
    document=load_json(path,expected_sha);files=document.get('files_sha256');require(type(files)is dict and files,'Provenance files_sha256 allowlist is required');require(len(files)<=max_files,'Proof file-count limit exceeded')
    overrides=checked_source_overrides(source_overrides,files,allowed_roots);result={};total=0
    for original,digest in files.items():
        original=canonical_absolute(original);checked_digest(digest);source_policy(original,allowed_roots);physical=Path(overrides.get(str(original),str(original)));info=source_policy(physical,allowed_roots);require(info.st_size<=max_single_bytes,'Single proof-file size limit exceeded');total+=info.st_size;require(total<=max_total_bytes,'Total proof-file size limit exceeded');require(sha(physical)==digest,'Proof file checksum mismatch: '+str(original));result[str(original)]={'sha256':digest,'bytes':info.st_size}
    require(sha(path)==expected_sha,'Provenance manifest changed during preflight')
    return result
def object_name(original,digest):
    suffix=''.join(Path(original).suffixes)
    if not re.fullmatch(r'(?:\.[A-Za-z0-9_-]{1,48}){0,4}',suffix):suffix=''
    return f'objects/{digest[:2]}/{digest}{suffix}.gz'
def descriptor(entry):
    require(type(entry)is dict,'Malformed proof descriptor')
    plain={'path','sha256','bytes'};compressed=plain|{'encoding','stored_sha256','stored_bytes'}
    require(set(entry)in(plain,compressed),'Unexpected proof descriptor fields');relative_path(entry['path']);checked_digest(entry['sha256']);require(type(entry['bytes'])is int and 0<=entry['bytes']<=512<<20,'Invalid uncompressed proof length')
    if set(entry)==compressed:
        require(entry['encoding']=='gzip','Unsupported proof encoding');checked_digest(entry['stored_sha256']);require(type(entry['stored_bytes'])is int and 0<entry['stored_bytes']<=512<<20,'Invalid stored proof length')
    return entry
def decode_entry(stored,entry):
    """Authenticate and decode exactly one bounded gzip member, never a tar."""
    descriptor(entry);compressed=entry.get('encoding')=='gzip';expected=entry['stored_bytes']if compressed else entry['bytes'];digest=entry['stored_sha256']if compressed else entry['sha256']
    require(len(stored)==expected and hashlib.sha256(stored).hexdigest()==digest,'Stored object integrity mismatch')
    if not compressed:return stored
    decoder=zlib.decompressobj(wbits=31);chunks=[];total=0
    for offset in range(0,len(stored),1<<20):
        pending=stored[offset:offset+(1<<20)]
        while pending:
            before=len(pending)
            try:raw=decoder.decompress(pending,entry['bytes']-total+1)
            except zlib.error as error:raise ProofError('Invalid gzip proof object')from error
            total+=len(raw);require(total<=entry['bytes']and total<=512<<20,'Decoded proof exceeds declared/raw limit');chunks.append(raw);pending=decoder.unconsumed_tail
            require(not decoder.unused_data,'Concatenated gzip members or trailing bytes rejected')
            require(not pending or len(pending)<before or raw,'Gzip decoder made no progress')
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,'Incomplete/trailing gzip frame');require(total==entry['bytes'],'Decoded proof length mismatch');raw=b''.join(chunks);require(hashlib.sha256(raw).hexdigest()==entry['sha256'],'Decoded proof checksum mismatch');return raw
class _HashingWriter:
    def __init__(self,stream,limit):self.stream=stream;self.limit=limit;self.count=0;self.digest=hashlib.sha256()
    def write(self,data):
        require(self.count+len(data)<=self.limit,'Stored proof exceeds byte limit');written=self.stream.write(data);require(written==len(data),'Incomplete proof-object write');self.digest.update(data);self.count+=len(data);return written
    def flush(self):self.stream.flush()
def _copy_checked(source,destination,digest,*,max_bytes,stage_fd=None,encoding='gzip'):
    # The source context owns its fd before any size/destination check can fail.
    with os.fdopen(_open_regular(source),'rb')as incoming:
        before=os.fstat(incoming.fileno());require(before.st_size<=max_bytes,'Copy source exceeds byte limit');outfd=_open_regular(destination,flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL,create=True,create_parents=True,root_fd=stage_fd);actual=hashlib.sha256();total=0
        with os.fdopen(outfd,'wb')as outgoing:
            writer=_HashingWriter(outgoing,512<<20)
            target=gzip.GzipFile(filename='',mode='wb',compresslevel=9,mtime=0,fileobj=writer)if encoding=='gzip'else writer
            try:
                for chunk in iter(lambda:incoming.read(min(1<<20,max_bytes+1)),b''):
                    total+=len(chunk);require(total<=max_bytes,'Copy source grew beyond preflight byte limit');actual.update(chunk);target.write(chunk)
            finally:
                if encoding=='gzip':target.close()
            outgoing.flush();os.fsync(outgoing.fileno());after=os.fstat(incoming.fileno());os.fchmod(outgoing.fileno(),0o644)
    check=_open_regular(source)
    try:final=os.fstat(check)
    finally:os.close(check)
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)==(final.st_dev,final.st_ino,final.st_size,final.st_mtime_ns),'Source changed while copying: '+str(source));require(actual.hexdigest()==digest,'Copy checksum mismatch: '+str(source))
    result={'path':str(destination),'sha256':digest,'bytes':total}
    if encoding=='gzip':result.update({'encoding':'gzip','stored_sha256':writer.digest.hexdigest(),'stored_bytes':writer.count})
    return result
def _identity(info):return info.st_dev,info.st_ino
def _assert_parent(parent_fd,destination):
    current,_=_parent_fd(destination)
    try:require(_identity(os.fstat(current))==_identity(os.fstat(parent_fd)),'Destination parent identity changed')
    finally:os.close(current)
def _make_stage(destination):
    parent_fd,_=_parent_fd(destination);stage_fd=None;name=None;identity=None
    try:
        _assert_parent(parent_fd,destination)
        while True:
            candidate='.'+destination.name+'.tmp-'+secrets.token_hex(12)
            try:os.mkdir(candidate,0o700,dir_fd=parent_fd);name=candidate;break
            except FileExistsError:continue
        stage_fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent_fd);identity=_identity(os.fstat(stage_fd));_assert_parent(parent_fd,destination)
        return parent_fd,stage_fd,destination.parent/name,name,identity
    except BaseException:
        if stage_fd is not None:os.close(stage_fd)
        if name is not None:
            try:
                info=os.stat(name,dir_fd=parent_fd,follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode)and(identity is None or _identity(info)==identity):shutil.rmtree(name,dir_fd=parent_fd)
            except FileNotFoundError:pass
        os.close(parent_fd);raise
def atomic_install(stage,destination,*,parent_fd=None,stage_identity=None):
    # Linux renameat2 gives the required atomic no-replacement contract. A
    # check-then-os.rename fallback could replace a concurrently created empty
    # directory; refusing an unsupported host is safer than weakening it.
    libc=ctypes.CDLL(None,use_errno=True);rename=getattr(libc,'renameat2',None)
    require(rename is not None,'Atomic no-replace installation requires renameat2')
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];rename.restype=ctypes.c_int
    require(stage.parent==destination.parent,'Atomic install requires one parent directory');owned=parent_fd is None;parent,leaf=_parent_fd(destination)if owned else(parent_fd,destination.name)
    try:
        _assert_parent(parent,destination);before=os.stat(stage.name,dir_fd=parent,follow_symlinks=False);require(stat.S_ISDIR(before.st_mode),'Staging tree was replaced')
        if stage_identity is not None:require(_identity(before)==stage_identity,'Verified staging directory identity changed')
        result=rename(parent,os.fsencode(stage.name),parent,os.fsencode(leaf),1)
        if result:
            code=ctypes.get_errno()
            if code in (errno.EEXIST,errno.ENOTEMPTY):raise ProofError('Refusing concurrent destination replacement')
            raise OSError(code,os.strerror(code),str(destination))
        after=os.stat(leaf,dir_fd=parent,follow_symlinks=False);require(_identity(before)==_identity(after),'Installed tree identity changed');_assert_parent(parent,destination)
    finally:
        if owned:os.close(parent)

class BundleResolver:
    """Strict original-path resolver for the agreed self-contained verifier."""
    def __init__(self,bundle_directory,index='proof-index.json',*,expected_index_sha256=None):
        self.root=canonical_absolute(bundle_directory);self._root_fd,_=_parent_fd(self.root/'_proof_root_anchor');self._closed=False
        relative=relative_path(index);self._index_relative=str(relative)
        self.index=parse_json(_read_open_fd(_open_regular(str(relative),root_fd=self._root_fd),expected_index_sha256,max_bytes=64<<20));require(self.index.get('schema')==INDEX_SCHEMA,'Unsupported proof-index schema')
        self.files=self.index.get('files');require(type(self.files)is dict and 0<len(self.files)<=10000,'Missing or excessive proof-index file allowlist');self._paths={};self._descriptors={}
        for original,entry in self.files.items():
            canonical_absolute(original);self._add_descriptor(entry)
            self._paths[original]=self.root/relative_path(entry['path'])
        artifacts=self.index.get('artifacts');require(type(artifacts)is dict and set(artifacts)=={'payload','validation','provenance_manifest','proof_read_set'},'Expected exactly four scientific top artifacts')
        for entry in artifacts.values():require(type(entry)is dict and set(entry)=={'path','sha256','bytes'},'Top artifacts must be plaintext');self._add_descriptor(entry)
        implementations=self.index.get('implementations');require(type(implementations)is dict and set(implementations)=={'verify_bundle','assemble','pack_proof'},'Exactly verifier/assembler/packer implementation pins are required')
        for entry in implementations.values():require(type(entry)is dict and set(entry)=={'path','sha256','bytes'},'Implementation entrypoints must be plaintext');self._add_descriptor(entry)
        for entry in list(artifacts.values())+list(implementations.values()):require(any(entry==value for value in self.files.values()),'Top descriptor is not in the explicit original-file allowlist')
        relative_refs=self.index.get('relative_references',{});require(type(relative_refs)is dict,'Malformed relative-reference map')
        for owner,references in relative_refs.items():
            require(owner in self.files and type(references)is dict,'Undeclared relative-reference owner')
            for reference,entry in references.items():
                require(type(reference)is str and reference and not reference.startswith('/')and'\x00'not in reference and'\\'not in reference,'Malformed original relative reference');require(type(entry)is dict and set(entry)=={'original_path','sha256'},'Malformed relative-reference descriptor');original=str(canonical_absolute(entry['original_path']));require(original in self.files and self.files[original]['sha256']==checked_digest(entry['sha256']),'Relative reference escapes authenticated allowlist')
        self.verify_all()
    def close(self):
        if not getattr(self,'_closed',True):os.close(self._root_fd);self._closed=True
    def __enter__(self):return self
    def __exit__(self,*unused):self.close()
    def __del__(self):self.close()
    def _add_descriptor(self,entry):
        descriptor(entry);relative=str(relative_path(entry['path']))
        if relative in self._descriptors:require(self._descriptors[relative]==entry,'Conflicting portable object path')
        self._descriptors[relative]=entry
    def _entry_bytes(self,entry):
        compressed=entry.get('encoding')=='gzip';length=entry['stored_bytes']if compressed else entry['bytes'];digest=entry['stored_sha256']if compressed else entry['sha256'];stored=_read_open_fd(_open_regular(entry['path'],root_fd=self._root_fd),digest,max_bytes=512<<20,expected_bytes=length);return decode_entry(stored,entry)
    def resolve(self,original_absolute_path):
        """A path reference only. Security-sensitive callers use read_bytes/json."""
        original=str(canonical_absolute(original_absolute_path));require(original in self._paths,'Undeclared original proof path: '+original);self._entry_bytes(self.files[original]);return self._paths[original]
    def read_bytes(self,original_absolute_path):
        original=str(canonical_absolute(original_absolute_path));require(original in self._paths,'Undeclared original proof path: '+original);return self._entry_bytes(self.files[original])
    def read_json(self,original_absolute_path):return parse_json(self.read_bytes(original_absolute_path))
    def artifact_bytes(self,name):
        require(name in self.index['artifacts'],'Unknown top artifact');return self._entry_bytes(self.index['artifacts'][name])
    def artifact(self,name):
        require(name in self.index['artifacts'],'Unknown top artifact');entry=self.index['artifacts'][name];require('encoding'not in entry,'Top artifact must remain plain');self._entry_bytes(entry);return self.root/relative_path(entry['path'])
    def verify_all(self):
        require(sum(e['bytes']for e in self.files.values())<=8<<30,'Logical uncompressed proof total exceeds bound');require(sum(e.get('stored_bytes',e['bytes'])for e in self._descriptors.values())<=8<<30,'Stored proof total exceeds bound')
        for entry in self._descriptors.values():self._entry_bytes(entry)
        manifest=parse_json(self.artifact_bytes('provenance_manifest'));original=manifest.get('files_sha256');require(type(original)is dict and original,'Scientific provenance file allowlist is missing')
        for path,digest in original.items():require(path in self.files and self.files[path]['sha256']==digest,'Original provenance/file-index mismatch: '+path)
        # A bundle contains no implicit secondary evidence. Entrypoints and top
        # artifacts are declared above; only the index itself is self-exempt.
        require(self._index_relative not in self._descriptors,'Proof index cannot masquerade as a declared source object');declared=set(self._descriptors)|{self._index_relative}
        for directory,subdirs,filenames,directory_fd in os.fwalk('.',dir_fd=self._root_fd,follow_symlinks=False):
            for name in subdirs:require(stat.S_ISDIR(os.stat(name,dir_fd=directory_fd,follow_symlinks=False).st_mode),'Symlink/special bundle directory rejected')
            for name in filenames:
                require(stat.S_ISREG(os.stat(name,dir_fd=directory_fd,follow_symlinks=False).st_mode),'Symlink/special bundle file rejected');relative=(PurePosixPath(directory)/name).as_posix();require(relative in declared,'Undeclared extra bundle file: '+relative)
        return True

def pack(*,provenance_manifest,provenance_manifest_sha256,payload,payload_sha256,validation,validation_sha256,proof_read_set,proof_read_set_sha256,verifier,verifier_sha256,assemble,assemble_sha256,destination,allowed_roots,relative_references=None,source_overrides=None,max_files=10000,max_single_bytes=512<<20,max_total_bytes=8<<30):
    allowed_roots=roots(allowed_roots);files=inventory(provenance_manifest,provenance_manifest_sha256,allowed_roots,source_overrides=source_overrides,max_files=max_files,max_single_bytes=max_single_bytes,max_total_bytes=max_total_bytes);overrides=checked_source_overrides(source_overrides,files,allowed_roots)
    specials={
      'payload':(canonical_absolute(payload),checked_digest(payload_sha256),'periods.json'),
      'validation':(canonical_absolute(validation),checked_digest(validation_sha256),'validation.json'),
      'provenance_manifest':(canonical_absolute(provenance_manifest),checked_digest(provenance_manifest_sha256),'provenance-manifest.json'),
      'proof_read_set':(canonical_absolute(proof_read_set),checked_digest(proof_read_set_sha256),'proof-read-set.json'),
      'verify_bundle':(canonical_absolute(verifier),checked_digest(verifier_sha256),'verify_bundle.py'),
      'assemble':(canonical_absolute(assemble),checked_digest(assemble_sha256),'assemble.py'),
      'pack_proof':(Path(__file__).resolve(),sha(__file__),'pack_proof.py'),
    }
    require(len({str(x[0])for x in specials.values()})==len(specials),'Top artifacts/implementations must be distinct original files')
    require(not(set(overrides)&{str(x[0])for x in specials.values()}),'Top artifacts and implementations cannot be source-materialized')
    for path,digest,_ in specials.values():
        info=source_policy(path,allowed_roots);require(sha(path)==digest,'Top artifact/implementation checksum mismatch')
        if str(path)in files:require(files[str(path)]['sha256']==digest,'Conflicting top artifact digest')
        files[str(path)]={'sha256':digest,'bytes':info.st_size}
    require(len(files)<=max_files and all(e['bytes']<=max_single_bytes for e in files.values())and sum(e['bytes']for e in files.values())<=max_total_bytes,'Final proof inventory exceeds bounds')
    dest=canonical_absolute(destination);reject_symlinks(dest.parent);require(dest.parent.is_dir(),'Destination parent must already exist');require(not dest.exists()and not dest.is_symlink(),'Refusing to replace a proof bundle')
    # The parent and stage are held from creation, not first sampled after
    # verification. Replacing a parent with another regular directory cannot
    # substitute an unverified tree at installation.
    parent_fd,stage_fd,stage,stage_name,stage_identity=_make_stage(dest);paths={str(path):name for path,digest,name in specials.values()};index_files={};copied={};installed=False
    try:
        for original,entry in sorted(files.items()):
            _assert_parent(parent_fd,dest);require(_identity(os.stat(stage_name,dir_fd=parent_fd,follow_symlinks=False))==stage_identity,'Staging directory changed during copy')
            relative=paths.get(original,object_name(original,entry['sha256']));relative_path(relative)
            if relative not in copied:
                source_policy(original,allowed_roots);physical=Path(overrides.get(original,original));source_policy(physical,allowed_roots);copied[relative]=_copy_checked(physical,relative,entry['sha256'],max_bytes=min(max_single_bytes,entry['bytes']),stage_fd=stage_fd,encoding='identity'if original in paths else'gzip')
            else:require(copied[relative]['sha256']==entry['sha256']and copied[relative]['bytes']==entry['bytes'],'Content-addressed object collision')
            index_files[original]=dict(copied[relative])
        top=lambda name:index_files[str(specials[name][0])]
        index={'schema':INDEX_SCHEMA,'files':index_files,'artifacts':{name:top(name)for name in ['payload','validation','provenance_manifest','proof_read_set']},'implementations':{name:top(name)for name in ['verify_bundle','assemble','pack_proof']},'relative_references':relative_references or{},'storage':{'proof_objects':'single-member gzip','gzip_mtime':0,'gzip_filename':'','gzip_compresslevel':9},'scope':'Byte-preserving allowlisted scientific proof package. Numerical/scientific acceptance requires the pinned standalone verifier; packing itself promotes no precision capability.'}
        require(sum(e.get('stored_bytes',e['bytes'])for e in copied.values())<=max_total_bytes,'Stored proof total exceeds bound');index_bytes=(json.dumps(index,indent=2,sort_keys=True)+'\n').encode();index_fd=_open_regular('proof-index.json',flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL,create=True,root_fd=stage_fd)
        with os.fdopen(index_fd,'wb')as stream:stream.write(index_bytes);stream.flush();os.fsync(stream.fileno())
        _assert_parent(parent_fd,dest)
        with BundleResolver(stage,expected_index_sha256=hashlib.sha256(index_bytes).hexdigest())as resolver:resolver.verify_all()
        for original,entry in files.items():
            source_policy(original,allowed_roots);physical=Path(overrides.get(original,original));source_policy(physical,allowed_roots);require(sha(physical)==entry['sha256'],'Authenticated packing source changed before atomic installation')
        atomic_install(stage,dest,parent_fd=parent_fd,stage_identity=stage_identity);installed=True
        return {'status':'packed_integrity_only;independent_numerical_verification_required','destination':str(dest),'index_sha256':hashlib.sha256(index_bytes).hexdigest(),'original_files':len(files),'unique_objects':len(copied),'total_original_bytes':sum(e['bytes']for e in files.values()),'total_stored_bytes':sum(e.get('stored_bytes',e['bytes'])for e in copied.values()),'source_materializations':{original:{'physical_path':physical,**files[original]}for original,physical in overrides.items()},'source_files_modified':False,'native_or_Mathematica_executed':False,'numerical_capability_promoted':False}
    except BaseException:
        if not installed:
            try:
                if _identity(os.stat(stage_name,dir_fd=parent_fd,follow_symlinks=False))==stage_identity:shutil.rmtree(stage_name,dir_fd=parent_fd)
            except FileNotFoundError:pass
        raise
    finally:os.close(stage_fd);os.close(parent_fd)

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    for name in ['inventory','pack']:
        p=sub.add_parser(name);p.add_argument('--provenance-manifest',type=Path,required=True);p.add_argument('--provenance-manifest-sha256',required=True);p.add_argument('--allowed-root',action='append');p.add_argument('--max-files',type=int,default=10000);p.add_argument('--max-single-bytes',type=int,default=512<<20);p.add_argument('--max-total-bytes',type=int,default=8<<30);p.add_argument('--source-overrides',type=Path);p.add_argument('--source-overrides-sha256')
        if name=='inventory':p.add_argument('--output',type=Path,required=True)
        else:
            for role in ['payload','validation','proof-read-set','verifier','assemble']:p.add_argument('--'+role,type=Path,required=True);p.add_argument('--'+role+'-sha256',required=True)
            p.add_argument('--destination',type=Path,required=True);p.add_argument('--relative-references',type=Path);p.add_argument('--relative-references-sha256')
    a=parser.parse_args();limits={k:getattr(a,k)for k in ['max_files','max_single_bytes','max_total_bytes']};allowed=a.allowed_root or DEFAULT_ALLOWED_ROOTS
    source_overrides=None
    if a.source_overrides is not None:
        require(a.source_overrides_sha256 is not None,'Source-materialization input requires its explicit SHA256');source_policy(a.source_overrides,roots(allowed));source_overrides=load_json(a.source_overrides,a.source_overrides_sha256);require(type(source_overrides)is dict,'Source-materialization path map required')
    else:require(a.source_overrides_sha256 is None,'Source-materialization checksum has no input')
    if a.command=='inventory':
        files=inventory(a.provenance_manifest,a.provenance_manifest_sha256,roots(allowed),source_overrides=source_overrides,**limits);require(not a.output.exists(),'Refusing to replace an inventory');a.output.write_text(json.dumps({'schema':'vakint.pr11d.portable-proof-inventory.v1','files':files,'total_bytes':sum(x['bytes']for x in files.values()),'numerical_acceptance_claimed':False},indent=2,sort_keys=True)+'\n');print('INVENTORY',len(files),sha(a.output))
    else:
        relative_refs=None
        if a.relative_references is not None:
            require(a.relative_references_sha256 is not None,'Relative-reference input requires its explicit SHA256');source_policy(a.relative_references,roots(allowed));data=load_json(a.relative_references,a.relative_references_sha256);relative_refs=data.get('relative_references',data);require(type(relative_refs)is dict,'Relative-reference mapping required')
        else:require(a.relative_references_sha256 is None,'Relative-reference checksum has no input')
        print(json.dumps(pack(provenance_manifest=a.provenance_manifest,provenance_manifest_sha256=a.provenance_manifest_sha256,payload=a.payload,payload_sha256=a.payload_sha256,validation=a.validation,validation_sha256=a.validation_sha256,proof_read_set=a.proof_read_set,proof_read_set_sha256=a.proof_read_set_sha256,verifier=a.verifier,verifier_sha256=a.verifier_sha256,assemble=a.assemble,assemble_sha256=a.assemble_sha256,destination=a.destination,allowed_roots=allowed,relative_references=relative_refs,source_overrides=source_overrides,**limits),indent=2))
if __name__=='__main__':main()
