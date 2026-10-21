#!/usr/bin/env python3
"""Export independent finite K5 primitive balls from accepted moment proofs.

This does not recover moments by inverting master formulas. Both original
Arb integration partitions are used directly, and sealed source files are read
without modification. No quadrature or expensive special-function computation
is needed to reproduce this data-format adaptation.
"""
import hashlib,json,sys
from pathlib import Path
from flint import arb,ctx
HERE=Path(__file__).resolve().parent
from rounding_support import rounded_cell,upper_decimal
if not __debug__:raise RuntimeError('Publication validation requires assertions enabled')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def export():
    ctx.dps=20400;ctx.threads=1
    manifest=json.loads((HERE/'source-manifest.json').read_text())
    if sha(HERE/manifest['reused_rounding_support']['copy'])!=manifest['reused_rounding_support']['copy_sha256']:
        raise ValueError('Accepted outward-rounding helper checksum mismatch')
    for name,pin in manifest['input_sha256'].items():
        if sha(HERE/'inputs'/name)!=pin:raise ValueError('Moment input checksum mismatch: '+name)
    receipt=json.loads((HERE/'inputs/high-guard-validation.json').read_text())
    if not receipt['accepted'] or receipt['validated_significant_digits']!=20200 or sha(HERE/'inputs/high-guard-validation.json')!=manifest['accepted_high_guard_receipt_sha256']:
        raise ValueError('Accepted20200digit moment certificate is required')
    definitions=json.loads((HERE/'inputs/independent-period-definitions.json').read_text())
    if definitions['logarithmic_moment_factor']!=3 or definitions['logarithmic_factor']!='log(t)+EulerGamma-log(2)' or definitions['native_atoms']!={'B1':'vakint::K5Moment(1)','B3':'vakint::K5Moment(3)','J1':'vakint::K5LogMoment(1)','J3':'vakint::K5LogMoment(3)'}:
        raise ValueError('Upstream moment convention differs from the accepted producer')
    profiles=[json.loads((HERE/'inputs'/('high-guard-profile-'+label+'.json')).read_text()) for label in ['a','b']]
    for label,p in zip(['a','b'],profiles):
        if not p['complete'] or p['digits']!=20200 or p['profile']!=label or len(p['values'])!=4:
            raise ValueError('Complete accepted raw moment partitions are required')
        expected=receipt['artifact_sha256']['profile-'+label+'.json']
        if sha(HERE/'inputs'/('high-guard-profile-'+label+'.json'))!=expected:raise ValueError('Raw moment profile is not authenticated by acceptance')
    moments={m['moment']:m for m in receipt['moments']};records=[];checks=[]
    for index,(label,symbol,k,logarithmic) in enumerate([
      ('B1','vakint::K5Moment(1)',1,False),('J1','vakint::K5LogMoment(1)',1,True),
      ('B3','vakint::K5Moment(3)',3,False),('J3','vakint::K5LogMoment(3)',3,True)]):
        x,y=[arb(p['values'][index]) for p in profiles]
        if not x.is_finite() or not y.is_finite() or not x.overlaps(y):raise ValueError('Independent accepted moment balls disagree')
        sx,ex=rounded_cell(x,20008);sy,ey=rounded_cell(y,20008)
        if sx!=sy:raise ValueError('Moment20008digit rounding is not unique across partitions')
        error=upper_decimal(max(ex,ey))
        accepted=arb(moments[label]['numerical_value'])+arb(0,arb(moments[label]['absolute_error_bound']).upper())
        if not accepted.overlaps(x) or not accepted.overlaps(y):raise ValueError('Accepted moment record contradicts raw certified partitions')
        if not arb(error).upper()<min(abs(x).lower(),abs(y).lower())*(arb(10)**-20000).lower():
            raise ValueError('Stored finite primitive does not support20000significant digits')
        definition=(f"3*Integral[t^{k}*BesselK(0,t)^5*(log(t)+EulerGamma-log(2)),{{t,0,infinity}}]" if logarithmic else f"Integral[t^{k}*BesselK(0,t)^5,{{t,0,infinity}}]")
        records.append({'symbol':symbol,'value':sx,'significant_digits':20000,'stored_significant_digits':20008,
          'absolute_error':error,'error_quality':'Bounded','definition':definition,
          'definition_metadata':{'integration_variable':'t','integration_interval':'positive real axis(0,infinity)','modified_Bessel_order':0,'Bessel_power':5,'power':k,
            'logarithmic':logarithmic,'logarithmic_moment_factor':3 if logarithmic else None,'logarithmic_factor':'log(t)+EulerGamma-log(2)' if logarithmic else None},
          'provenance':{'source_kind':'independently integrated primitive moment; no master inversion','accepted_moment_label':label,
            'accepted_high_guard_digits':20200,'accepted_high_guard_receipt_sha256':manifest['accepted_high_guard_receipt_sha256'],
            'upstream_revision':manifest['upstream_revision'],'upstream_definition_sha256':manifest['input_sha256']['independent-period-definitions.json'],
            'raw_profile_sha256':[manifest['input_sha256']['high-guard-profile-'+a+'.json'] for a in ['a','b']],
            'publication_validation':'validation.json'}})
        checks.append({'symbol':symbol,'accepted_moment':label,'both_partitions_overlap':True,'stored_rounding_unique':True,
          'validated_significant_digits':20000,'available_precision':'FixedPrecision(20000)','absolute_error':error})
    return {'schema':'vakint.external-data.finite-constants.v1','constants':records},checks

def main():
    payload,checks=export()
    encoded=json.dumps(payload,indent=2)+'\n'
    output=HERE/'constants.json'
    if output.exists() and output.read_text()!=encoded:raise ValueError('Preserve previous primitive payloads; a changed export requires a versioned output')
    output.write_text(encoded)
    validation={'schema':'vakint.K5-independent-primitive-export.v1','accepted':True,'scope':'Direct finite primitive data format adaptation from already accepted interval integration, not new moment computation',
      'no_master_alias_inversion':True,'source_manifest_sha256':sha(HERE/'source-manifest.json'),'payload_sha256':sha(output),
      'checks':checks,'producer_sha256':sha(Path(__file__)),'primitive_cap_digits':20000,'whole_PR11d_accuracy_claimed':False}
    (HERE/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print('ACCEPTED four independent finiteK5primitives at20000digits; payloadSHA',sha(output))
if __name__=='__main__':main()
