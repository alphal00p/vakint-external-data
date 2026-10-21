#!/usr/bin/env python3
"""Seal the period only after two complete source-bound numerical refinements pass."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math
from flint import arb,acb,ctx
if not __debug__:raise RuntimeError('Assertions required for scientific acceptance')
ROOT=Path(__file__).resolve().parent.parent
# The active checkout acquired four later API call-site arguments after this
# scientific source was authenticated. Preserve its logical identity and use
# only the byte-identical recovered preimage; never revert active development.
SOURCE_PREIMAGE_ORIGINAL=Path('/shared/codex-1/vakint_rustred/gammaloop_vakint_rustred/crates/vakint/src/lib.rs')
SOURCE_PREIMAGE_FILE=ROOT/'accepted20000/frozen-source-preimages/vakint-lib.rs'
SOURCE_PREIMAGE_SHA256='257df086de7f3135faafd3bc7bbd288d66a6d62eb5ee646ae6b50c06ea7531e1'
def SHA(path):
 path=Path(path)
 if path.resolve()==SOURCE_PREIMAGE_ORIGINAL:
  data=SOURCE_PREIMAGE_FILE.read_bytes()
  assert hashlib.sha256(data).hexdigest()==SOURCE_PREIMAGE_SHA256,'Changed recovered scientific source preimage'
 else:data=path.read_bytes()
 return hashlib.sha256(data).hexdigest()
HELPER=ROOT/'p853/validate.py'
assert SHA(HELPER)=='eaf83ed92f7f48a6ef198dc2dbcf29fe0b4be05dc46065115477526f837a2fa8'
spec=importlib.util.spec_from_file_location('pr11d_seal_decimal_helper',HELPER);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
assert Path(helper.__file__).resolve()==HELPER.resolve()
POLICY_PATH=ROOT/'accepted20000/verify_bundle.py'
APPROVED_PORTABLE_VERIFIER_SHA256='1cf290b886aeff1a80c34a39daf64f16fb647c89f5e22cc5610126f1bbf31ce7'
assert SHA(POLICY_PATH)==APPROVED_PORTABLE_VERIFIER_SHA256,'Portable verifier changes require independent review before scientific sealing'
policy_spec=importlib.util.spec_from_file_location('pr11d_seal_trust_policy',POLICY_PATH);policy=importlib.util.module_from_spec(policy_spec);policy_spec.loader.exec_module(policy)
assert Path(policy.__file__).resolve()==POLICY_PATH.resolve()
def unique(items):
 result={}
 for key,value in items:
  if key in result:raise ValueError('Duplicate JSON key: '+key)
  result[key]=value
 return result
def load(path):
 assert Path(path).resolve()!=SOURCE_PREIMAGE_ORIGINAL,'The recovered Rust source is a hash-only input, never JSON evidence'
 return json.loads(Path(path).read_text(),object_pairs_hook=unique)
def pin_map(pins):
 for path,pin in pins.items():assert SHA(path)==pin,('Changed scientific source',path)
def projection(path):
 data=load(path);assert data['schema']=='vakint.pr11d.bounded-finite-endpoint-projection.v1'
 assert data['normalization']=='native_raw' and data['error_quality']=='rigorous-bound'
 assert data['master_alias']=='PR11dep0' and data['epsilon_power']==0
 assert [r['epsilon_power'] for r in data['coefficients']]==list(range(-5,1))
 for row in data['coefficients']:
  real,imag=arb(row['real_ball']),arb(row['imaginary_ball']);assert real.is_finite() and imag.is_finite() and imag.contains(0)
  if row['epsilon_power']<0:assert real.contains(0),'A computed pole enclosure contradicts the exact finiteness proof'
 chain=load(data['chain_acceptance_path']);assert SHA(data['chain_acceptance_path'])==data['chain_acceptance_sha256']
 assert data['chain_acceptance_sha256'] in policy.TRUSTED_CHAIN_RECEIPTS,'This completed physical production chain is not independently blessed'
 assert chain['independent_validator_review_sha256'] in policy.TRUSTED_CHAIN_REVIEWS,'This chain validator is not independently blessed'
 assert chain['status']=='passed_for_frozen_completed_physical_chain' and chain['schema']=='vakint.pr11d.physical-X8-chain-acceptance.v1'
 for key in ['initial_physical_provenance_verified','all_step_source_hashes_and_centers_verified','all_local_tails_certified','all_interval_gauge_and_serialization_checks_passed']:assert chain[key] is True
 pin_map(chain['source_pins']);pin_map(chain['artifact_sha256'])
 assert SHA(chain['independent_validator_review_path'])==chain['independent_validator_review_sha256']
 review=load(chain['independent_validator_review_path']);assert review['status']=='passed_for_frozen_physical_X8_chain_validator' and review['validator_sha256']==chain['validator_sha256']
 assert SHA(data['boundary_path'])==data['boundary_sha256'] and SHA(data['transport_receipt_path'])==data['transport_receipt_sha256']
 assert chain['artifact_sha256'][data['boundary_path']]==data['boundary_sha256'] and chain['artifact_sha256'][data['transport_receipt_path']]==data['transport_receipt_sha256']
 transport=load(data['transport_receipt_path']);assert transport['complete'] is True and transport['all_final_component_radii_meet_target'] is True
 assert chain['final_boundary_sha256']==transport['final_boundary_sha256']==data['boundary_sha256']
 assert SHA(data['adjoint_path'])==data['adjoint_sha256'] and SHA(data['adjoint_acceptance_path'])==data['adjoint_acceptance_sha256']=='b523238139d137f911645bd179bd15cc7386bf89232abdac799421cbc85d3b38'
 adj=load(data['adjoint_acceptance_path']);pin_map(adj['source_pins']);pin_map(adj['artifact_sha256'])
 assert adj['artifact_sha256'][data['adjoint_path']]==data['adjoint_sha256']
 # Replay the final exact coefficient convolution; a label/hash-only projection
 # acceptance would not establish that its boxes came from these raw jets.
 saved_precision=ctx.prec
 try:
  digits=data['working_decimal_precision'];assert type(digits)==int and digits>=64 and data['serialization_decimal_digits']==digits+8
  ctx.dps=digits;assert ctx.prec==data['working_bits']
  raw=load(data['boundary_path']);adjoint=load(data['adjoint_path']);Y=[acb(arb(x),arb(y)) for x,y in raw['values']];V=[acb(arb(x),arb(y)) for x,y in adjoint['complex_balls']]
  assert raw['basis']=='original_raw_epsilon_jets' and raw['dimension']==42 and raw['epsilon_min_power']==-4 and raw['epsilon_max_power']==1
  assert raw['normalization']=='native_raw' and raw['error_quality']=='rigorous-bound' and raw['eta_center']==['0','1/16']
  assert raw['source_equation_sha256']==chain['source_equation_sha256']==data['source_equation_sha256']
  assert adjoint['dimension']==252 and adjoint['epsilon_range']==[0,5] and adjoint['tail_bound_added'] is True and adjoint['eta_center']==['0','1/16']
  assert len(Y)==len(V)==252 and all(z.is_finite() for z in Y+V)
  for power in range(6):
   value=sum((V[42*j+i]*Y[42*(power-j)+i] for j in range(power+1) for i in range(42)),acb(0));row=data['coefficients'][power]
   assert value.real.str(digits+8,more=True)==row['real_ball'] and value.imag.str(digits+8,more=True)==row['imaginary_ball'],'Final coefficient boxes differ from the source-bound outward convolution'
 finally:
  ctx.prec=saved_precision
 finite=data['coefficients'][-1];return data,chain,arb(finite['real_ball']),arb(finite['imaginary_ball'])
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--proof-read-set',type=Path,required=True);parser.add_argument('--first',type=Path,required=True);parser.add_argument('--second',type=Path,required=True);parser.add_argument('--first-chain-review-sha256',required=True);parser.add_argument('--second-chain-review-sha256',required=True);parser.add_argument('--output-directory',type=Path,required=True);args=parser.parse_args()
 ctx.dps=21280
 assert SHA(args.proof_read_set)==policy.TRUSTED_PROOF_READ_SET_SHA256,'Scientific read-set requires independent acceptance'
 read_set=load(args.proof_read_set);assert read_set['status']=='complete_current_scientific_proof_read_set'
 pin_map(read_set['files_sha256'])
 assert args.output_directory.resolve().is_relative_to((ROOT/'accepted20000').resolve()),'Acceptance output must remain in the owned workspace'
 assert not args.output_directory.exists() and not args.output_directory.is_symlink(),'A fresh immutable acceptance directory is required'
 a,ca,A,IA=projection(args.first);b,cb,B,IB=projection(args.second)
 assert ca['independent_validator_review_sha256']==args.first_chain_review_sha256 and cb['independent_validator_review_sha256']==args.second_chain_review_sha256
 assert args.first.resolve()!=args.second.resolve() and ca['initial_physical_boundary_sha256']!=cb['initial_physical_boundary_sha256'],'Two distinct source/continuation refinements required'
 assert a['source_equation_sha256']==b['source_equation_sha256'] and A.overlaps(B) and IA.overlaps(IB)
 assert B<0 and not B.contains(0)
 scale=abs(B).lower();difference=abs(A-B).upper();assert difference<scale*arb(10)**-20000,'Independent refinement agreement is insufficient'
 for real,imag in [(A,IA),(B,IB)]:assert max(real.rad(),imag.rad())<scale*arb(10)**-20000,'A refinement does not independently meet the20k total-error gate'
 center,error=helper.rounded_cell(B,20008);assert error>0 and error<abs(arb(center)).lower()*arb(10)**-20000
 error_text=helper.upper_decimal(error);assert arb(error_text).lower()>=error and arb(error_text).upper()<abs(arb(center)).lower()*arb(10)**-20000
 scientific_path=ROOT/'helper/physical-poles-review/review.json';assert SHA(scientific_path)=='22f69516f6f2e0a8278b9a4913dfd85a74b0e82b5c7e8507d0b8655c13d8ef31'
 scientific=load(scientific_path);assert scientific['accepted'] is True
 for kind in ['raw_pole','finiteness']:assert SHA(scientific[kind+'_certificate_path'])==scientific[kind+'_certificate_sha256']
 finiteness=load(scientific['finiteness_certificate_path']);assert finiteness['all_negative_Laurent_coefficients_exactly_zero'] and finiteness['FMFT_equals_native_finite_coefficient'] and finiteness['Minkowski_overall_sign']==-1
 oracle_path=ROOT/'amflow-oracle/acceptance.json';assert SHA(oracle_path)=='af1521ef875f6e92f83597f9f445b69778c2391c997a82d7becff50b95a839a8'
 oracle=load(oracle_path);assert oracle['status']=='PASS_practical_100_digit_independent_ordinary_solver_crosscheck' and oracle['reference_is_postsolve_only'] is True
 oracle_difference=abs(B-arb(oracle['finite_real_central_value'])).upper()/scale;assert oracle_difference<arb(10)**-100
 oracle_agreement=int((-oracle_difference.log()/arb(10).log()).lower().floor().fmpz())
 ibp_path=ROOT/'kira-identity-audit/REPLAY_RECEIPT.json';assert SHA(ibp_path)=='50a8e1b8ddfa550876016d329eae8e0fe952c345fdafadcb5e0825dc868181e2'
 ibp=load(ibp_path);assert ibp['target_relations_total']==3 and ibp['target_relations_independently_proved']==[0,1,2] and ibp['complete_independent_DE_validation'] is False
 assert len(ibp['de_rows_independently_proved'])==21 and len(ibp['de_rows_still_trusting_external_Kira'])==21
 assert a['source_equation_sha256']==ibp['source_system_sha256'] and ibp['source_family_sha256']==finiteness['family_sha256']
 manifest_paths=[Path(__file__),ROOT/'accepted20000/verify_bundle.py',HELPER,args.first,args.second,Path(a['chain_acceptance_path']),Path(b['chain_acceptance_path']),scientific_path,Path(scientific['raw_pole_certificate_path']),Path(scientific['finiteness_certificate_path']),Path(finiteness['original_X8_source_path']),Path(finiteness['canonical_reference_input_path']),oracle_path,ROOT/'amflow-oracle/files.json',ibp_path]
 for key in ['implementation_sha256','transitive_source_sha256']:
  pin_map(scientific[key]);manifest_paths.extend(map(Path,scientific[key]))
 for name,pin in ibp['files_sha256'].items():
  file=(ibp_path.parent/name).resolve();assert read_set['files_sha256'].get(str(file))==pin and SHA(file)==pin;manifest_paths.append(file)
 oracle_manifest_path=ROOT/'amflow-oracle/files.json';assert SHA(oracle_manifest_path)=='df4209b0def8a90d491bc718eca235c70068dede96fa0892c62107e06be5b999'
 oracle_manifest=load(oracle_manifest_path);assert oracle_manifest['acceptance_sha256']==SHA(oracle_path) and oracle_manifest['private_license_configuration_excluded'] is True
 for row in oracle_manifest['files']:
  file=(oracle_path.parent/row['path']).resolve();assert file.is_relative_to(oracle_path.parent.resolve()) and SHA(file)==row['sha256'];assert file.stat().st_size==row['bytes'];manifest_paths.append(file)
 for chain in [ca,cb]:
  manifest_paths.extend(map(Path,chain['source_pins']));manifest_paths.extend(map(Path,chain['artifact_sha256']));manifest_paths.append(Path(chain['independent_validator_review_path']))
 for data,chain in [(a,ca),(b,cb)]:
  manifest_paths.extend(Path(data[k]) for k in ['boundary_path','transport_receipt_path','adjoint_path','adjoint_acceptance_path'])
  for proof in [load(data['adjoint_acceptance_path']),load(chain['independent_validator_review_path'])]:
   for key in ['source_pins','artifact_sha256','implementation_sha256','transitive_source_sha256','implementation_and_source_dependency_sha256']:
    pins=proof.get(key,{})
    if pins:pin_map(pins);manifest_paths.extend(map(Path,pins))
 manifest_paths.extend(map(Path,read_set['files_sha256']))
 provenance={str(p.resolve()):SHA(p) for p in manifest_paths}
 manifest={'schema':'vakint.pr11d.validated-provenance-manifest.v1','scope':'Frozen scientific source, witnesses, source admissions, two complete bounded continuation profiles, endpoint and independent numerical controls. Development license configuration is excluded.','files_sha256':provenance,'source_equation_sha256':a['source_equation_sha256'],'complete_independent_DE_validation':False,'independent_exact_IBP_scope':{'targets_proved':3,'DE_rows_proved':ibp['de_rows_independently_proved'],'DE_rows_trusting_external_Kira':ibp['de_rows_still_trusting_external_Kira']},'publication_cap':20000,'portable_verifier_sha256':SHA(POLICY_PATH),'scientific_proof_read_set_sha256':policy.TRUSTED_PROOF_READ_SET_SHA256,'closure_policy':'This rooted inventory is expanded through authenticated typed JSON references into the portable proof-index; publication requires the complete allowlisted closure and standalone verifier replay.'}
 manifest_text=json.dumps(manifest,indent=2)+'\n';manifest_sha=hashlib.sha256(manifest_text.encode()).hexdigest()
 period={'symbol':'PR11dep0','master_basis':'vakint::PR11d','value':center,'stored_significant_digits':20008,'validated_significant_digits':20000,'absolute_error_upper_bound':error_text,'arithmetic_ball':b['coefficients'][-1]['real_ball'],'physical_imaginary_ball':b['coefficients'][-1]['imaginary_ball'],'error_quality':'rigorous-bound','normalization':'FMFT','unit_mass_squared':'1','master_id':finiteness['master_id'],'family_sha256':finiteness['family_sha256'],'ordered_powers':finiteness['powers'],'epsilon_power':0,'Minkowski_overall_sign':-1,'normalization_equality_proof_sha256':SHA(scientific['finiteness_certificate_path'])}
 payload={'schema':'vakint.pr11d.validated-periods.v1','constants':{'PR11dep0':period},'provenance_manifest_sha256':manifest_sha,'scope':'Finite primitive period only. Other numerical master coefficients retain their individual accepted limits.'}
 payload_text=json.dumps(payload,indent=2)+'\n';payload_sha=hashlib.sha256(payload_text.encode()).hexdigest()
 validation={'schema':'vakint.pr11d.validated-period-acceptance.v1','status':'accepted_20000_validated_significant_digits','coefficient_data_sha256':payload_sha,'provenance_manifest_sha256':manifest_sha,'validator_sha256':SHA(Path(__file__)),'portable_verifier_sha256':SHA(POLICY_PATH),'scientific_proof_read_set_sha256':policy.TRUSTED_PROOF_READ_SET_SHA256,'source_period':'PR11dep0','validated_significant_digits':20000,'stored_significant_digits':20008,'stored_center':center,'stored_center_absolute_error_upper_bound':error_text,'unambiguous_nearest_decimal_cell_verified':True,'strict_published_relative_error_gate_passed':True,'two_refinement_projection_sha256':[SHA(args.first),SHA(args.second)],'refinement_scaled_difference_upper':helper.upper_decimal(difference/scale),'both_refinement_total_error_gates_passed':True,'refinement_scope':'Distinct source precision and upstream four-loop continuation partitions; common X8 halfstep mesh, authenticated exact equations and boundary identities. Both complete coefficient boxes have separate rigorous arithmetic/truncation/source bounds.','AMFlow_practical_agreement_digits':oracle_agreement,'AMFlow_scope':oracle['independence_scope'],'AMFlow_20000_digit_comparison_claimed':False,'all_computed_apparent_pole_boxes_contain_zero':True,'exact_negative_poles_from_finiteness_proof':True,'finite_FMFT_native_normalization_equal':True,'scientific_pole_review_sha256':SHA(scientific_path),'independent_IBP_witness_receipt_sha256':SHA(ibp_path),'complete_independent_DE_validation':False,'remaining_external_exact_equation_trust':ibp['remaining_scope'],'publication_only_after_this_acceptance':True}
 args.output_directory.mkdir(parents=True,exist_ok=False,mode=0o700)
 texts={'periods.json':payload_text,'provenance-manifest.json':manifest_text,'validation.json':json.dumps(validation,indent=2)+'\n'}
 for name,text in texts.items():
  with (args.output_directory/(name+'.tmp')).open('x') as stream:stream.write(text)
 for name in ['periods.json','provenance-manifest.json','validation.json']:(args.output_directory/(name+'.tmp')).replace(args.output_directory/name)
 print('ACCEPTED PR11dep0:20000 validated digits,20008 stored; oracleagreement',oracle_agreement)
if __name__=='__main__':main()
