#!/usr/bin/env python3
"""Independent acceptance of the fresh 20,200-digit Bessel run.

Production, reference inputs and original accepted 20k files are never changed.
Every radius, finite partition and source binding is checked before publication.
"""
import hashlib,json,math
from fractions import Fraction
from pathlib import Path
from flint import arb,ctx,fmpq
from validate import independent_reconstruct,rounded_cell,upper_decimal,validate_cauchy

if not __debug__:
    raise RuntimeError('Acceptance validation requires assertions enabled')
HERE=Path(__file__).resolve().parent
D=20200

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def aa(q):
    q=Fraction(q);return arb(fmpq(q.numerator,q.denominator))
def finite_values(xs):
    assert len(xs)==4
    result=[arb(x) for x in xs]
    assert all(x.is_finite() for x in result)
    return result

def source_pins():
    expected={
      'production-source-manifest.json':{'produce.py','moments_taylor.py','reconstruct.py','source-receipts/exact-shift-and-valuations.json','source-receipts/root-exact-map-adoption.json','source-receipts/root-mathematica200-adoption.json'},
      'oracle-source-manifest.json':{'mathematica_seeds.wl','wolfram_one_thread.py','wolfram_one_thread.wl'}}
    for manifest,keys in expected.items():
        data=json.loads((HERE/manifest).read_text())
        assert set(data['source_sha256'])==keys
        for name,pin in data['source_sha256'].items():assert sha(HERE/name)==pin,(manifest,name)
    assert sha(HERE/'moments_taylor.py')=='f9f616dcee1c1e9323398da9b37257369d4f5e71880926c6cdc5a8be2022806f'

def settings(label):
    start=Fraction(1) if label=='a' else Fraction(3,4)
    guard={'a':180,'b':260}[label]
    rows=[{'profile':label,'kind':'small','index':-1,'digits':D,'guard':guard,'end':[start.numerator,start.denominator]}]
    lower=start;i=0;end=math.ceil((D+40)*math.log(10)/5)
    while lower<end:
        h=Fraction(1,4) if label=='b' and i==0 else Fraction(1,5)
        center=lower/(1-h);upper=center*(1+h)
        rows.append({'profile':label,'kind':'interval','index':i,'digits':D,'guard':guard,'lower':[lower.numerator,lower.denominator],'center':[center.numerator,center.denominator],'upper':[upper.numerator,upper.denominator],'h':[h.numerator,h.denominator]})
        lower=upper;i+=1
    return rows

def frobenius_bound(row,a,guard):
    n=row['n'];assert type(n) is int and n>=40
    expected=max(40,int((D+guard)/max(1.0,math.log10(D+30)))+50)
    # Production may double this number if the omitted input term is too large.
    assert n>=expected and n%expected==0 and (n//expected)&((n//expected)-1)==0
    a=aa(a);L=a.log()+arb.const_euler()-arb(2).log()
    R=(arb(2*n)/(5*a))**2;assert R.lower()>1
    x=a*R.sqrt();MI=x.bessel_i(0);MA=abs(L)*MI+x*x.bessel_i(1)/2
    common=R**(-n)/(1-1/R);errors=[arb(0) for _ in range(4)]
    for j in range(6):
        ptail=MA**(5-j)*MI**j*common
        fac=arb(math.comb(5,j)*math.factorial(j))/(2**j)
        for k,idx in [(1,0),(3,2)]:
            den=n+(k+1)//2;er=a**(k+1)*fac*ptail/(2*den**(j+1))
            errors[idx]+=er;errors[idx+1]+=3*er*(abs(L)+arb(j+1)/(2*den))
    assert all(e.is_finite() and e.lower()>0 and e.upper()<(arb(10)**(-(D+12))).lower() for e in errors)
    return [upper_decimal(e) for e in errors]

def complete_profile(label):
    path=HERE/f'profile-{label}.json';data=json.loads(path.read_text());rows=settings(label)
    assert data['complete'] is True and data['profile']==label and data['digits']==D
    assert data['guard']==rows[0]['guard'] and data['settings']==rows
    assert data['algorithm_sha256']==sha(HERE/'moments_taylor.py')
    values=[arb(0) for _ in range(4)];paths=[path];bounds=[]
    for s in rows:
        suffix='small' if s['kind']=='small' else str(s['index']).zfill(3)
        p=HERE/'certificates'/f'{label}-{suffix}.json';row=json.loads(p.read_text());paths.append(p)
        assert row['schema']=='vakint.bessel-high-guard.certificate.v1'
        assert row['settings']==s and row['algorithm_sha256']==data['algorithm_sha256']
        parts=finite_values(row['values'])
        if s['kind']=='small':
            assert row['tail_bound'] is None
            bounds.append({'kind':'full-product-Frobenius','bounds':frobenius_bound(row,Fraction(*s['end']),s['guard'])})
        else:
            h=Fraction(*s['h']);lower=Fraction(*s['lower']);center=Fraction(*s['center']);upper=Fraction(*s['upper'])
            assert center==lower/(1-h) and upper==center*(1+h)
            bound=validate_cauchy(row,D,lower,h)
            bounds.append({'kind':'finite-interval-Cauchy','index':s['index'],'bound':upper_decimal(bound)})
        values=[x+y for x,y in zip(values,parts)]
    R=aa(Fraction(*rows[-1]['upper']))
    tail=3*(arb.pi()/2)**aa(Fraction(5,2))*R**aa(Fraction(3,2))*(-5*R).exp()/(5-aa(Fraction(3,2))/R)
    published_tail=arb(data['infinite_tail_bound'])
    assert published_tail.is_finite() and published_tail.lower()>0 and published_tail.overlaps(tail)
    assert tail.upper()<(arb(10)**(-(D+12))).lower()
    values=[x+arb(0,tail.upper()) for x in values]
    published=finite_values(data['values'])
    for x,y in zip(values,published):
        assert x.overlaps(y) and x.rel_accuracy_bits()>=math.floor(D*math.log2(10))
        rounded_cell(x,D+8)
    return values,paths,{'profile':label,'small_and_cauchy_bounds':bounds,'infinity_bound':upper_decimal(tail)}

def wolfram(s):
    m,sep,e=s.partition('*^');m=m.split('`')[0]
    return arb(m+('e'+e if sep else ''))

def oracle_validation():
    data=json.loads((HERE/'mathematica-seeds.json').read_text())
    assert data['working_decimal_digits']==20400
    expected={Fraction(*s['center']) for label in ['a','b'] for s in settings(label) if s['kind']=='interval'}
    extra=json.loads((HERE/'mathematica-anchor-one.json').read_text())
    assert extra['working_decimal_digits']==20400 and extra['numerator']==extra['denominator']==1
    data['rows'].append(extra)
    actual=[Fraction(r['numerator'],r['denominator']) for r in data['rows']]
    # The frozen initial oracle list had a spare 15/16 point in place of the
    # first shifted interval's true center 1. Preserve it and add the missing
    # center, checking the intended set directly from exact production geometry.
    assert len(expected)==46
    assert len(actual)==47 and len(set(actual))==47 and set(actual)==expected|{Fraction(15,16)}
    assert set(data['constants'])=={'EulerGamma','pi','zeta2','zeta3','zeta4','zeta5'}
    checks=[]
    def compare(a,b,identity):
        assert a.is_finite() and b.is_finite() and not a.contains(0)
        rel=abs(a-b).upper()/abs(a).lower()
        assert rel.upper()<(arb(10)**-20300).lower(),identity
        digits=int((-rel.log()/arb(10).log()).lower().floor().fmpz())
        checks.append({'identity':identity,'agreed_decimal_digits_lower_bound':digits})
    for row in data['rows']:
        assert len(row['values'])==2
        z=Fraction(row['numerator'],row['denominator'])
        ctx.dps=20400+150+math.ceil(2*float(z)/math.log(10))
        for order,w in enumerate(row['values']):compare(aa(z).bessel_k(order),wolfram(w),f'K{order}({z})')
    ctx.dps=20400+150
    funcs={'EulerGamma':lambda:arb.const_euler(),'pi':lambda:arb.pi(),**{f'zeta{n}':lambda n=n:arb(n).zeta() for n in range(2,6)}}
    for name,f in funcs.items():compare(f(),wolfram(data['constants'][name]),name)
    assert len(checks)==100
    receipt={'complete':True,'bessel_anchor_count':47,'required_production_anchor_count':46,'checks':checks,'minimum_agreed_decimal_digits':min(x['agreed_decimal_digits_lower_bound'] for x in checks),'source_sha256':sha(HERE/'mathematica-seeds.json'),'supplemental_anchor_sha256':sha(HERE/'mathematica-anchor-one.json'),'validator_sha256':sha(Path(__file__))}
    (HERE/'oracle-validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def main():
    source_pins();ctx.threads=1
    oracle=oracle_validation();print('independent input agreement',oracle['minimum_agreed_decimal_digits'],flush=True)
    ctx.dps=D+400
    av,ap,ab=complete_profile('a');bv,bp,bb=complete_profile('b');checks=[]
    for name,x,y in zip(['B1','J1','B3','J3'],av,bv):
        assert x.overlaps(y)
        sx,ex=rounded_cell(x,D+8);sy,ey=rounded_cell(y,D+8);assert sx==sy,name
        error=upper_decimal(max(ex,ey));assert arb(error).upper()<min(abs(x).lower(),abs(y).lower())*(arb(10)**-D).lower()
        checks.append({'moment':name,'numerical_value':sx,'absolute_error_bound':error,'validated_significant_digits':D,'stored_significant_digits':D+8})
    ia=independent_reconstruct(av);ib=independent_reconstruct(bv);records=[]
    for name,basis in [('PR4fin','PR4'),('PR4dfin','PR4d')]:
        for power,key,symbol in [(0,'value',name),(1,'epsilon1_value','PR4ep1' if basis=='PR4' else 'PR4dep1')]:
            x=ia[name][key];y=ib[name][key];assert x.overlaps(y)
            sx,ex=rounded_cell(x,D+8);sy,ey=rounded_cell(y,D+8);assert sx==sy,symbol
            error=upper_decimal(max(ex,ey));assert arb(error).upper()<min(abs(x).lower(),abs(y).lower())*(arb(10)**-D).lower()
            records.append({'symbol':'vakint::'+symbol,'numerical_value':sx,'significant_digits':D,'stored_significant_digits':D+8,'normalization':'FMFTandMATAD','master_basis':'vakint::'+basis,'epsilon_power':power,'validation':{'methods':['Arb Cauchy-bounded Taylor and analytic log-moment integration','independent rational interval partition at 80 extra guard digits','independent 20400-digit Mathematica inputs','independent exact-Fraction dimensional-shift reconstruction'],'absolute_error_bound':error,'source_map_sha256':sha(HERE/'source-receipts/exact-shift-and-valuations.json'),'primary_accuracy_bits':x.rel_accuracy_bits(),'validation_accuracy_bits':y.rel_accuracy_bits(),'acceptance_receipt':'validation.json'}})
    paths=set(ap+bp+[HERE/n for n in ['accept.py','validate.py','produce.py','moments_taylor.py','reconstruct.py','production-source-manifest.json','oracle-source-manifest.json','mathematica-seeds.json','mathematica_seeds.wl','mathematica-anchor-one.json','mathematica_anchor_one.wl','oracle-validation.json','wolfram_one_thread.py','wolfram_one_thread.wl']]);paths.update((HERE/'source-receipts').glob('*.json'))
    receipt={'schema':'vakint.precision-periods.bessel-validation.v2','accepted':True,'validated_significant_digits':D,'stored_significant_digits':D+8,'moments':checks,'mathematical_bound_checks':[ab,bb],'independent_input_agreement_decimal_digits':oracle['minimum_agreed_decimal_digits'],'full_gap_free_partitions':True,'complete_infinity_tails':True,'source_pins_unchanged':True,'unique_rounding_cells':True,'independent_exact_fraction_reconstruction':True,'artifact_sha256':{str(p.relative_to(HERE)):sha(p) for p in sorted(paths)}}
    (HERE/'validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (HERE/'constants20200.json').write_text(json.dumps({'schema':'vakint.precision-periods.constants.v1','constants':records,'validation_sha256':sha(HERE/'validation.json')},indent=2)+'\n')
    print('ACCEPTED four moments and four master coefficients at',D,'validated digits',flush=True)

if __name__=='__main__':main()
