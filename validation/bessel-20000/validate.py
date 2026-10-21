#!/usr/bin/env python3
"""Acceptance gates for completed, source-pinned 20k Bessel moment runs."""
import ast,hashlib,json,math
from decimal import Decimal,localcontext,ROUND_HALF_EVEN,ROUND_CEILING
from fractions import Fraction
from pathlib import Path
from flint import arb,ctx,fmpq
HERE=Path(__file__).resolve().parent
DIGITS=20000
if not __debug__:
    raise RuntimeError('Acceptance validation must run with Python assertions enabled')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def qarb(q):return arb(fmpq(q.numerator,q.denominator))
def finite(v):return v.is_finite()

def rounded_cell(v,digits):
    assert finite(v)
    assert not v.contains(0), 'zero requires an absolute-accuracy contract'
    with localcontext() as c:
        c.prec=digits;c.rounding=ROUND_HALF_EVEN
        out=+Decimal(v.mid().str(digits+70,radius=False))
        predecessor=out.next_minus(c);successor=out.next_plus(c)
    with localcontext() as c:
        c.prec=digits+20
        low=(out+predecessor)/2;high=(out+successor)/2
    # Cells are asymmetric at powers of ten. Use exact decimal neighbours,
    # with outward Arb conversion, rather than a symmetric half-ulp.
    assert v.lower()>arb(str(low)).upper() and v.upper()<arb(str(high)).lower(),('ambiguous rounding',digits,v.str(20),str(out)[:40])
    center=arb(str(out))
    return format(out,'f'),abs(v-center).upper()


def exact_map_series(text,order=6):
    zero=lambda:[Fraction(0) for _ in range(order)]
    def const(n):
        x=zero();x[0]=Fraction(n);return x
    def add(a,b):return [x+y for x,y in zip(a,b)]
    def mul(a,b):return [sum(a[k]*b[n-k] for k in range(n+1)) for n in range(order)]
    def inv(a):
        assert a[0]!=0
        x=zero();x[0]=1/a[0]
        for n in range(1,order):x[n]=-sum(a[k]*x[n-k] for k in range(1,n+1))/a[0]
        return x
    def power(a,n):
        if n<0:return power(inv(a),-n)
        x=const(1)
        while n:
            if n&1:x=mul(x,a)
            a=mul(a,a);n//=2
        return x
    def parse(node):
        if isinstance(node,ast.Constant) and isinstance(node.value,int):return const(node.value)
        if isinstance(node,ast.Name) and node.id=='e':
            x=zero();x[1]=Fraction(1);return x
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return [-x for x in parse(node.operand)]
        assert isinstance(node,ast.BinOp),ast.dump(node)
        a,b=parse(node.left),parse(node.right)
        if isinstance(node.op,ast.Add):return add(a,b)
        if isinstance(node.op,ast.Sub):return add(a,[-x for x in b])
        if isinstance(node.op,ast.Mult):return mul(a,b)
        if isinstance(node.op,ast.Div):return mul(a,inv(b))
        if isinstance(node.op,ast.Pow):
            assert all(x==0 for x in b[1:]) and b[0].denominator==1
            return power(a,int(b[0]))
        raise ValueError(ast.dump(node))
    tree=ast.parse(text.replace('pr4_dimension_shift::{}::epsilon','e').replace('^','**'),mode='eval')
    return parse(tree.body)


def independent_reconstruct(vals):
    assert len(vals)==4 and all(finite(x) for x in vals)
    srcpath=HERE/'source-receipts'/'exact-shift-and-valuations.json'
    assert sha(srcpath)=='660b9e0c6debdabd739fbb92ab9d9da700bdd6025f10b3b79082f48c2af7d531'
    src=json.loads(srcpath.read_bytes());order=6
    # Independent formal exponential and (1-eps)^(-4) coefficients.
    q=[arb(0),arb(0)]+[arb(4)*(-1)**n*arb(n).zeta()/n for n in range(2,order)]
    ee=[arb(1)]+[arb(0) for _ in range(order-1)]
    for n in range(1,order):ee[n]=sum(k*q[k]*ee[n-k] for k in range(1,n+1))/n
    t4=[sum(arb(math.comb(n-j+3,3))*ee[j] for j in range(n+1)) for n in range(order)]
    B1,J1,B3,J3=vals;out={}
    for i,name in enumerate(['PR4fin','PR4dfin']):
        g1=[qarb(x) for x in exact_map_series(src['D2_moment_coalesced_c1_coefficients'][i])]
        g3=[qarb(x) for x in exact_map_series(src['D2_moment_c3_coefficients'][i])]
        b=[qarb(x) for x in exact_map_series(src['shift_inverse_b'][i])]
        out[name]={
          'value':-16*(g1[0]*B1+g3[0]*B3)+sum(b[j]*t4[4-j] for j in range(5)),
          'epsilon1_value':-16*(g1[0]*J1+g1[1]*B1+g3[0]*J3+g3[1]*B3)+sum(b[j]*t4[5-j] for j in range(6))}
    return out

def upper_decimal(v,digits=30):
    upper=v.upper()
    assert finite(upper) and upper>=0
    ratio=upper.fmpq()
    with localcontext() as c:
        c.prec=digits;c.rounding=ROUND_CEILING
        value=Decimal(int(ratio.numerator))/Decimal(int(ratio.denominator))
        text=str(value)
        if arb(text).lower()<upper:
            value=value.next_plus(c);text=str(value)
    assert arb(text).lower()>=upper
    return text


def validate_cauchy(row,digits,lower=None,h_fraction=Fraction(1,5)):
    assert isinstance(row['n'],int) and not isinstance(row['n'],bool) and row['n']>=20 and row['n']%2==0
    if lower is None:
        lower=Fraction(*row['lower']);upper=Fraction(*row['upper'])
        assert upper==lower*(1+h_fraction)/(1-h_fraction)
    a=qarb(lower/(1-h_fraction));h=qarb(h_fraction);rho=arb(fmpq(9,10))
    k=(a*(1-rho)).bessel_k(0);maxr=a*(1+rho);minr=a*(1-rho)
    lb=max(abs(minr.log()+arb.const_euler()-arb(2).log()).upper(),abs(maxr.log()+arb.const_euler()-arb(2).log()).upper())+arb.pi()/2
    M=max(arb(1),maxr**3)*k**5*max(arb(1),3*lb)
    bound=2*a*h*M*(h/rho)**row['n']/(1-h/rho)
    assert bound.upper()<arb(10)**(-(digits+12))
    published=arb(row['tail_bound'])
    assert finite(published) and published.lower()>0
    assert published.overlaps(bound),(row.get('profile','prefix'),row.get('index','prefix'),'tail disagreement')
    return bound

def validate_frobenius(prefix,label):
    a=arb(1) if label=='a' else arb(fmpq(3,4))
    assert isinstance(prefix['small'],dict)
    n=prefix['small']['n']
    assert isinstance(n,int) and not isinstance(n,bool) and n==({'a':4741,'b':4759}[label])
    L=a.log()+arb.const_euler()-arb(2).log()
    R=(arb(2*n)/(5*a))**2
    assert R.lower()>1
    x=a*R.sqrt();MI=x.bessel_i(0);MA=abs(L)*MI+x*x.bessel_i(1)/2
    common=R**(-n)/(1-1/R)
    errors=[arb(0) for _ in range(4)]
    for j in range(6):
        Ptail=MA**(5-j)*MI**j*common
        fac=arb(math.comb(5,j)*math.factorial(j))/(2**j)
        for k,idx in [(1,0),(3,2)]:
            den=n+(k+1)//2;scale=a**(k+1)*fac/2
            er=scale*Ptail/(den**(j+1));ej=3*er*(abs(L)+arb(j+1)/(2*den))
            errors[idx]+=er;errors[idx+1]+=ej
    assert all(finite(e) and e.lower()>0 and e.upper()<(arb(10)**(-(DIGITS+12))).lower() for e in errors)
    return errors


def complete_profile(label):
    p=HERE/f'moments20000-{label}-complete.json';data=json.loads(p.read_bytes())
    assert data['digits']==DIGITS and data['guard']==({'a':180,'b':260}[label])
    assert data['source_sha256']==sha(HERE/'moments_taylor.py')
    assert 'infinite_tail_bound' in data and 'parallel_wall_seconds' in data
    prefixpath=HERE/f'moments20000-{label}.json';prefix=json.loads(prefixpath.read_bytes())
    assert prefix['digits']==DIGITS and prefix['guard']==data['guard']
    assert len(prefix['intervals'])==({'a':2,'b':1}[label])
    validate_frobenius(prefix,label)
    lower=Fraction(1) if label=='a' else Fraction(3,4)
    for row in prefix['intervals']:
        assert finite(arb(row['lower'])) and finite(arb(row['upper']))
        assert arb(row['lower']).contains(qarb(lower))
        upper=lower*(Fraction(3,2) if label=='a' else Fraction(5,3))
        assert arb(row['upper']).contains(qarb(upper))
        validate_cauchy(row,DIGITS,lower,Fraction(1,5) if label=='a' else Fraction(1,4))
        lower=upper
    assert len(prefix['values'])==4 and all(finite(arb(v)) for v in prefix['values'])
    assert len(data['values'])==4 and all(finite(arb(v)) for v in data['values'])
    vals=[arb(v) for v in prefix['values']]
    paths=[prefixpath]
    expected_rows=list(prefix['intervals'])
    i=1
    endpoint=math.ceil((DIGITS+40)*math.log(10)/5)
    while lower<endpoint:
        q=HERE/'certificates'/f'{label}-{i:03d}.json';row=json.loads(q.read_bytes())
        assert row['profile']==label and row['index']==i
        assert Fraction(*row['lower'])==lower
        assert Fraction(*row['upper'])==lower*Fraction(3,2)
        validate_cauchy(row,DIGITS)
        assert len(row['values'])==4
        parts=[arb(v) for v in row['values']]
        assert all(finite(v) for v in parts)
        vals=[v+w for v,w in zip(vals,parts)]
        expected_rows.append({k:v for k,v in row.items() if k!='values'})
        paths.append(q);lower*=Fraction(3,2);i+=1
    R=qarb(lower)
    tail=3*(arb.pi()/2)**arb('2.5')*R**arb('1.5')*(-5*R).exp()/(5-arb('1.5')/R)
    published_tail=arb(data['infinite_tail_bound'])
    assert finite(published_tail) and published_tail.lower()>0 and published_tail.overlaps(tail)
    assert data['intervals']==expected_rows
    vals=[v+arb(0,tail.upper()) for v in vals]
    for v,w in zip(vals,data['values']):
        published=arb(w)
        assert v.overlaps(published)
        assert published.contains(v) or v.contains(published) or abs(v-published).contains(0)
        assert v.rel_accuracy_bits()>=math.floor(DIGITS*math.log2(10))
        rounded_cell(v,DIGITS+8)
    assert len(data['intervals'])==len(prefix['intervals'])+i-1
    return data,vals,paths

def main():
    ctx.dps=DIGITS+350;ctx.threads=1
    assert sha(HERE/'source-manifest.json')=='548fa94c50050c71a62c4ed95fe73f2f9d520e4a118b8106d10eac6d93809037'
    manifest=json.loads((HERE/'source-manifest.json').read_bytes())
    for name,h in manifest['source_sha256'].items():
        p=Path(name) if name.startswith('/') else HERE/name
        assert sha(p)==h,('source changed',name)
    a,av,ap=complete_profile('a');b,bv,bp=complete_profile('b')
    checks=[]
    for name,x,y in zip(['B1','J1','B3','J3'],av,bv):
        assert x.overlaps(y),name
        sx,ex=rounded_cell(x,DIGITS+8);sy,ey=rounded_cell(y,DIGITS+8)
        assert sx==sy,('shifted partition mismatch',name)
        checks.append({'moment':name,'validated_significant_digits':DIGITS,'stored_significant_digits':DIGITS+8,'absolute_error_bound':upper_decimal(max(ex,ey)),'primary_accuracy_bits':x.rel_accuracy_bits(),'validation_accuracy_bits':y.rel_accuracy_bits()})
    # Reconstructed master values are generated before this validator is run.
    pa=json.loads((HERE/'periods20000-a.json').read_bytes());pb=json.loads((HERE/'periods20000-b.json').read_bytes())
    ia=independent_reconstruct(av);ib=independent_reconstruct(bv)
    for label,published in [('a',pa),('b',pb)]:
        assert published['digits']==DIGITS
        assert Path(published['moments']).resolve()==(HERE/f'moments20000-{label}-complete.json').resolve()
        assert published['map_sha256']=='660b9e0c6debdabd739fbb92ab9d9da700bdd6025f10b3b79082f48c2af7d531'
        assert set(published['periods'])=={'PR4fin','PR4dfin'}
    records=[]
    for name,basis in [('PR4fin','PR4'),('PR4dfin','PR4d')]:
        for power,key,symbol in [(0,'value',name),(1,'epsilon1_value','PR4ep1' if basis=='PR4' else 'PR4dep1')]:
            x=ia[name][key];y=ib[name][key];assert x.overlaps(y),symbol
            for value,published in [(x,pa),(y,pb)]:
                z=arb(published['periods'][name][key]);assert finite(z) and value.overlaps(z),symbol
            sx,ex=rounded_cell(x,DIGITS+8);sy,ey=rounded_cell(y,DIGITS+8);assert sx==sy,symbol
            assert arb(upper_decimal(max(ex,ey))).upper()<min(abs(x).lower(),abs(y).lower())*arb(10)**(-DIGITS)
            records.append({'symbol':'vakint::'+symbol,'numerical_value':sx,'significant_digits':DIGITS,'stored_significant_digits':DIGITS+8,'normalization':'FMFTandMATAD','master_basis':'vakint::'+basis,'epsilon_power':power,'validation':{'methods':['Arb Cauchy-bounded Taylor and analytic log-moment integration','independent rational interval partition at 80 extra guard digits','independent Mathematica Bessel/elementary input validation'],'absolute_error_bound':upper_decimal(max(ex,ey)),'source_map_sha256':pa['map_sha256'],'primary_accuracy_bits':x.rel_accuracy_bits(),'validation_accuracy_bits':y.rel_accuracy_bits(),'acceptance_receipt':'validation.json'}})
    mv=json.loads((HERE/'mathematica-validation.json').read_bytes())
    assert mv['complete'] and mv['bessel_anchor_count']==46 and mv['minimum_agreed_decimal_digits']>=20080
    assert mv['source_sha256']==sha(HERE/'mathematica-seeds-v2.json')
    assert mv['validator_sha256']==sha(HERE/'validate_mathematica.py')
    assert len(mv['checks'])==98
    assert mv['minimum_agreed_decimal_digits']==min(x['agreed_decimal_digits_lower_bound'] for x in mv['checks'])
    paths=set(ap+bp+[HERE/'moments20000-a-complete.json',HERE/'moments20000-b-complete.json',HERE/'periods20000-a.json',HERE/'periods20000-b.json',HERE/'mathematica-seeds-v2.json',HERE/'oracle-source-manifest-v2.json',HERE/'mathematica_series_seeds.wl',HERE/'mathematica-builtin-seeds.json',HERE/'mathematica-validation.json',HERE/'source-manifest.json',Path(__file__),HERE/'METHOD.md'])
    paths.update(HERE/name for name in ['moments_taylor.py','parallel_moments.py','reconstruct.py','validate_mathematica.py','wolfram_one_thread.py','wolfram_one_thread.wl','mathematica_seeds.wl'])
    paths.update((HERE/'source-receipts').glob('*.json'))
    receipt={'schema':'vakint.precision-periods.bessel-validation.v1','accepted':True,'validated_significant_digits':DIGITS,'stored_significant_digits':DIGITS+8,'moments':checks,'primitive_periods':['vakint::PR4fin','vakint::PR4dfin'],'additional_jet_coefficients':['vakint::PR4ep1','vakint::PR4dep1'],'independent_input_agreement_decimal_digits':mv['minimum_agreed_decimal_digits'],'full_gap_free_partitions':True,'complete_infinity_tails':True,'source_pins_unchanged':True,'unique_rounding_cells':True,'artifact_sha256':{str(p.relative_to(HERE)):sha(p) for p in sorted(paths)}}
    (HERE/'validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (HERE/'constants20000.json').write_text(json.dumps({'schema':'vakint.precision-periods.constants.v1','constants':records,'validation_sha256':sha(HERE/'validation.json')},indent=2)+'\n')
    print('ACCEPTED',len(checks),'moments',len(records),'master coefficients at',DIGITS,'validated significant digits')
if __name__=='__main__':main()
