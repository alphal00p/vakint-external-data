#!/usr/bin/env python3
"""Portable independent replay of the additive K0/K1 reference at center 1."""
import hashlib,json
from pathlib import Path
from flint import arb,ctx
if not __debug__:raise RuntimeError('Assertions must remain enabled')
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def wolfram(s):
    m,sep,e=s.partition('*^');return arb(m.split('`')[0]+('e'+e if sep else ''))
def main():
    c=json.loads((HERE/'coverage-correction.json').read_text())
    assert sha(HERE/'mathematica_anchor_one.wl')==c['supplemental_source_sha256']
    assert sha(HERE/'mathematica-anchor-one.json')==c['supplemental_values_sha256']
    data=json.loads((HERE/'mathematica-anchor-one.json').read_text())
    assert data['working_decimal_digits']==20400 and data['numerator']==data['denominator']==1
    assert len(data['values'])==2 and data['terms']==12000
    ctx.dps=20600;checks=[]
    for order,s in enumerate(data['values']):
        x=arb(1).bessel_k(order);y=wolfram(s);assert x.is_finite() and y.is_finite()
        rel=abs(x-y).upper()/abs(x).lower()
        assert rel.upper()<(arb(10)**-20300).lower()
        digits=int((-rel.log()/arb(10).log()).lower().floor().fmpz())
        checks.append({'order':order,'argument':'1','agreed_decimal_digits_lower_bound':digits})
    receipt={'accepted':True,'supplemental_required_anchor_count':1,'checks':checks,'coverage_correction_sha256':sha(HERE/'coverage-correction.json'),'validator_sha256':sha(Path(__file__))}
    (HERE/'validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS: missing center 1 independently checked at',min(x['agreed_decimal_digits_lower_bound'] for x in checks),'digits')
if __name__=='__main__':main()
