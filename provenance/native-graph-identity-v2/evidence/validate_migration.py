"""Read-only authentication and semantic checks for scalar-model DOT migration."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import re
import time
import vakint_hepkit_standalone as h

ROOT=Path('/shared/codex-1/vakint_rustred')
OUT=ROOT/'workspace/5l-push/graph-fingerprint'
records=json.loads((OUT/'preimage-comparison.json').read_text())
ATTR=re.compile(r'(\w+)=("(?:\\.|[^"\\])*"|[^,\]]+)')

def attrs(line):
    return {k:json.loads(v) if v.startswith('"') else v.strip() for k,v in ATTR.findall(line)}

MOMENTA={'FeynKit::Momentum':'gammalooprs::Q','FeynKit::LoopMomentum':'gammalooprs::K','FeynKit::ExternalMomentum':'gammalooprs::P'}
PATTERNS=[(h.E(old+'(migration_args___)'),h.E(new+'(migration_args___)')) for old,new in MOMENTA.items()]
EXPRESSION_MAP={}
def migrate_ast(expression):
    for old,new in PATTERNS:
        expression=expression.replace(old,new)
    return expression

def migrate_expression(source):
    if not any(head+'(' in source for head in MOMENTA):
        return source
    if source in EXPRESSION_MAP:
        return EXPRESSION_MAP[source]['new_expression']
    original=h.E(source)
    migrated=migrate_ast(original)
    inverse=migrated
    for old,new in reversed(PATTERNS):
        inverse=inverse.replace(new,old)
    assert inverse==original
    result=migrated.to_canonical_string()
    assert h.E(result)==migrated
    EXPRESSION_MAP[source]={'old_expression':source,'new_expression':result,'original_sha256':hashlib.sha256(source.encode()).hexdigest(),'migrated_sha256':hashlib.sha256(result.encode()).hexdigest(),'inverse_rename_exact':True,'source_atom_bytes':original.get_byte_size(),'migrated_atom_bytes':migrated.get_byte_size()}
    return result

def migrate_dot(text,old_binding,new_binding):
    # Modify only JSON-string expression attributes, plus the authenticated model identity.
    replacements=[]
    for match in ATTR.finditer(text):
        key,value=match.groups()
        if key not in ('numerator','numerator_prefactor','projector') or not value.startswith('"'):
            continue
        source=json.loads(value)
        migrated=migrate_expression(source)
        if migrated!=source:
            replacements.append((match.start(2),match.end(2),json.dumps(migrated,ensure_ascii=False)))
    updated=text
    for start,end,replacement in reversed(replacements):
        updated=updated[:start]+replacement+updated[end:]
    assert updated.count(old_binding)==1
    return updated.replace(old_binding,new_binding)

def equal_expression(left,right):
    # Exact normalized AST identity after a bijective coordinate-head rename;
    # no expansion, random substitutions or floating-point evaluation.
    assert migrate_ast(h.E(left))==migrate_ast(h.E(right)),(left,right)

reports=[]
started=time.monotonic()
for record in records:
    label=record['label'];number=int(label.split('-')[-1][0])
    base=ROOT/('gammaloop_vakint_rustred/crates/vakint/data' if label.startswith('vendored') else 'vakint-external-data')/f'{number}L'
    manifest=json.loads((base/'manifest.json').read_text())
    original_model=base/'model.json';original_bytes=original_model.read_bytes()
    assert hashlib.sha256(original_bytes).hexdigest()==record['source_sha256']
    assert hashlib.sha256(original_bytes).hexdigest()==manifest['files']['model.json']['sha256']
    old=json.loads((OUT/f'{label}-old.json').read_text());new=json.loads((OUT/f'{label}-new.json').read_text())
    assert len(record['changes'])==6
    for change in record['changes']:
        path=change['path']
        if path in ('/particles/0/charge','/particles/0/y_charge'):
            assert Fraction(str(change['old']))==Fraction(change['new'])==0
        elif path=='/particles/0/y_charge_right':
            assert change['kind']=='added' and change['new'] is None
            assert old['particles'][0]['spin']==1
        elif path in ('/propagators/0/denominator','/couplings/0/expression','/couplings/1/expression'):
            equal_expression(change['old'],change['new'])
        else:raise AssertionError(change)
    model=h.Model.from_json(original_bytes.decode())
    graphs=[]
    for master in manifest['masters']:
        graph_path=master['files']['graph.dot']['path'];path=base/graph_path;raw=path.read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        assert digest==master['files']['graph.dot']['sha256']==manifest['files'][graph_path]['sha256']
        text=raw.decode();source=attrs(next(line for line in text.splitlines() if line.lstrip().startswith('graph [')))
        assert source['model_fingerprint']==record['old_blake3']
        old_binding=f'model_fingerprint="{record["old_blake3"]}"'
        new_binding=f'model_fingerprint="{record["new_blake3"]}"'
        assert text.count(old_binding)==1
        updated=migrate_dot(text,old_binding,new_binding)
        diagram=h.FeynmanDiagram.from_dot(model,updated)
        native=json.loads(diagram.to_json())
        for key in ('loop_momentum_basis','half_edge_order','cuts','topology_threshold_candidates'):
            assert native[key]==json.loads(source[key]),(label,master['master_id'],key)
        assert native['name']==source['feynkit_name']
        assert native['symmetry_factor']==int(source['symmetry_factor'])
        for key in ('overall_factor','numerator','numerator_prefactor','projector'):
            equal_expression(source[key],native[key])
        edges=[];vertices=[]
        for line in text.splitlines():
            match=re.match(r'\s*v(\d+) -> v(\d+) \[',line)
            if match:
                data=attrs(line);idx=int(data['id']);ends,edge=native['edges'][idx]
                assert ends=={'source':int(match[1]),'target':int(match[2])}
                for field,attribute in [('particle','particle_id'),('source_slot','source_slot'),('target_slot','target_slot'),('propagator_power','power')]:
                    assert edge[field]==int(data.get(attribute,1)),(label,graph_path,idx,field)
                assert edge['directed']==(data['directed']=='true')
                equal_expression(data['numerator'],edge['numerator'])
                if 'lmb_id' in data:
                    assert native['loop_momentum_basis']['loop_edges'][int(data['lmb_id'])]==idx
                edges.append(idx)
                continue
            match=re.match(r'\s*v(\d+) \[',line)
            if match:
                data=attrs(line);idx=int(match[1]);vertex=native['vertices'][idx]
                assert vertex['name']==data['feynkit_name']
                assert vertex['interaction']==(int(data['interaction_id']) if 'interaction_id' in data else None)
                equal_expression(data['numerator'],vertex['numerator']);vertices.append(idx)
        assert len(edges)==len(native['edges']) and len(vertices)==len(native['vertices'])
        restored=h.FeynmanDiagram.from_dot(model,diagram.to_dot())
        assert restored.to_json()==diagram.to_json()
        graphs.append({'master_id':master['master_id'],'path':graph_path,'source_sha256':digest,'migrated_sha256':hashlib.sha256(updated.encode()).hexdigest(),'edges':len(edges),'vertices':len(vertices)})
    reports.append({'label':label,'model_source_sha256':record['source_sha256'],'old_fingerprint':record['old_blake3'],'new_fingerprint':record['new_blake3'],'graphs':graphs,'count':len(graphs)})
    print(label,len(graphs),flush=True)
(OUT/'semantic-migration-validation.json').write_text(json.dumps({'status':'passed','seconds':time.monotonic()-started,'graph_count':sum(r['count'] for r in reports),'momentum_symbol_renaming':MOMENTA,'reports':reports},indent=2)+'\n')

(OUT/'native-expression-mapping.json').write_text(json.dumps({'schema':'feynkit-native-graph-momentum-notation-v1','owner_old':'8ab99b3e0198f5986d68db9bfb1f5b8a17ed2278','owner_new':'e846b584ef31f9e35dc7df0b2bb1d096cb66d6eb','symbolica_revision':'9c8623ecb800baca621afbe9dffa930a3a4bfbe7','renaming':MOMENTA,'allowed_dot_attributes':['numerator','numerator_prefactor','projector'],'expressions':list(EXPRESSION_MAP.values())},indent=2,ensure_ascii=False)+'\n')
