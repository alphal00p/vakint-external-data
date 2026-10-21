#!/usr/bin/env python3
"""Independent-library input validation; no production values are overwritten."""
import argparse,hashlib,json,math,re,time
from fractions import Fraction
from pathlib import Path
from flint import arb,ctx,fmpq
HERE=Path(__file__).resolve().parent
if not __debug__:
    raise RuntimeError('Acceptance validation must run with Python assertions enabled')

def from_wolfram(s):
    mantissa,sep,exponent=s.partition('*^')
    mantissa=mantissa.split('`')[0]
    return arb(mantissa+('e'+exponent if sep else ''))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');args=ap.parse_args()
    p=HERE/'mathematica-seeds-v2.json';raw=p.read_bytes();data=json.loads(raw)
    assert hashlib.sha256((HERE/'oracle-source-manifest-v2.json').read_bytes()).hexdigest()=='b6f212c7cdbf05251a469ee8b372f196f3f96d55d30e7e9c39d26093f4a67a19'
    oracle=json.loads((HERE/'oracle-source-manifest-v2.json').read_text())
    for name,pinned in oracle['source_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==pinned
    ctx.dps=data['working_decimal_digits']+100
    expected={Fraction(5,4),Fraction(15,8),Fraction(15,16)}
    for low in [Fraction(9,4),Fraction(5,4)]:
        while low<math.ceil(20040*math.log(10)/5):
            expected.add(low*Fraction(5,4));low*=Fraction(3,2)
    actual=[Fraction(row['numerator'],row['denominator']) for row in data['rows']]
    assert len(set(actual))==len(actual) and set(actual)<=expected
    assert set(data['constants'])=={'EulerGamma','pi','zeta2','zeta3','zeta4','zeta5'}
    checks=[]
    for row in data['rows']:
        assert len(row['values'])==2
        ctx.dps=data['working_decimal_digits']+150+math.ceil(2*(row['numerator']/row['denominator'])/math.log(10))
        z=arb(fmpq(row['numerator'],row['denominator']))
        for order,w in enumerate(row['values']):
            a=z.bessel_k(order);b=from_wolfram(w)
            delta=abs(a-b).upper()
            rel=delta/abs(a).lower()
            assert rel.upper()<(arb(10)**(-20080)).lower()
            digits=int((-rel.log()/arb(10).log()).lower().floor().fmpz())
            checks.append({'kind':'BesselK','order':order,'numerator':row['numerator'],'denominator':row['denominator'],'agreed_decimal_digits_lower_bound':int(digits)})
    ctx.dps=data['working_decimal_digits']+150
    funcs={'EulerGamma':lambda:arb.const_euler(),'pi':lambda:arb.pi(),**{f'zeta{n}':lambda n=n:arb(n).zeta() for n in range(2,6)}}
    for name,f in funcs.items():
        a=f();b=from_wolfram(data['constants'][name]);rel=abs(a-b).upper()/abs(a).lower()
        assert rel.upper()<(arb(10)**(-20080)).lower()
        digits=int((-rel.log()/arb(10).log()).lower().floor().fmpz())
        checks.append({'kind':'constant','name':name,'agreed_decimal_digits_lower_bound':int(digits)})
    complete=set(actual)==expected
    assert len(expected)==46
    if not args.partial:assert complete,len(data['rows'])
    receipt={'schema':'vakint.precision-periods.independent-Mathematica-input-validation.v1','complete':complete,'bessel_anchor_count':len(data['rows']),'minimum_agreed_decimal_digits':min(r['agreed_decimal_digits_lower_bound'] for r in checks),'working_decimal_digits':data['working_decimal_digits'],'checks':checks,'source_sha256':hashlib.sha256(raw).hexdigest(),'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Independent Mathematica and FLINT/Arb special-function inputs; complete moment proof also requires Cauchy/infinity bounds and shifted-partition checks.'}
    (HERE/'mathematica-validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('validated',len(checks),'checks',len(data['rows']),'anchors','minimum',receipt['minimum_agreed_decimal_digits'],'digits','complete',complete)
if __name__=='__main__':main()
