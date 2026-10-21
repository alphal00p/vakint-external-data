#!/usr/bin/env python3
"""Fresh high-guard Bessel production; never writes the accepted 20k run."""
import concurrent.futures as cf
from fractions import Fraction
import hashlib,json,math,os,time
from pathlib import Path
from flint import arb,ctx,fmpq
from moments_taylor import small_interval,interval

HERE=Path(__file__).resolve().parent
DIGITS=20200
ALGORITHM_SHA=hashlib.sha256((HERE/'moments_taylor.py').read_bytes()).hexdigest()

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def aa(q):return arb(fmpq(q.numerator,q.denominator))
def atomic(path,value):
    tmp=path.with_suffix('.'+str(os.getpid())+'.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)

def settings():
    end=math.ceil((DIGITS+40)*math.log(10)/5);out=[]
    for label,start,guard in [('a',Fraction(1),180),('b',Fraction(3,4),260)]:
        out.append({'profile':label,'kind':'small','index':-1,'digits':DIGITS,'guard':guard,'end':[start.numerator,start.denominator]})
        lower=start;i=0
        while lower<end:
            h=Fraction(1,4) if label=='b' and i==0 else Fraction(1,5)
            center=lower/(1-h);upper=center*(1+h)
            out.append({'profile':label,'kind':'interval','index':i,'digits':DIGITS,'guard':guard,'lower':[lower.numerator,lower.denominator],'center':[center.numerator,center.denominator],'upper':[upper.numerator,upper.denominator],'h':[h.numerator,h.denominator]})
            lower=upper;i+=1
    out.sort(key=lambda r:(r['index'],r['profile']))
    return out

def filename(s):return HERE/'certificates'/(s['profile']+('-small' if s['kind']=='small' else '-'+str(s['index']).zfill(3))+'.json')

def run(s):
    target=filename(s);target.parent.mkdir(exist_ok=True)
    if target.exists():
        data=json.loads(target.read_text())
        if data['settings']!=s or data['algorithm_sha256']!=ALGORITHM_SHA:raise ValueError('Incompatible certificate reuse')
        if len(data['values'])!=4:raise ValueError('Truncated certificate')
        return {**s,'reused':True}
    t=time.time();ctx.threads=1;ctx.dps=s['digits']+s['guard']
    if s['kind']=='small':
        vals,n=small_interval(aa(Fraction(*s['end'])),s['digits'],s['guard']);tail=None
    else:
        vals,n,tail=interval(aa(Fraction(*s['center'])),aa(Fraction(*s['h'])),s['digits'],s['guard'])
    data={'schema':'vakint.bessel-high-guard.certificate.v1','settings':s,'algorithm_sha256':ALGORITHM_SHA,'n':n,'tail_bound':tail,'values':[v.str(DIGITS+40,more=True) for v in vals],'relative_accuracy_bits':[v.rel_accuracy_bits() for v in vals],'seconds':time.time()-t}
    if any(not v.is_finite() for v in vals):raise ValueError('Nonfinite moment certificate')
    atomic(target,data)
    return {**s,'n':n,'seconds':data['seconds'],'relative_accuracy_bits':data['relative_accuracy_bits']}

def main():
    source=json.loads((HERE/'production-source-manifest.json').read_text())
    for name,pin in source['source_sha256'].items():
        if digest(HERE/name)!=pin:raise ValueError('Production source changed: '+name)
    tasks=settings();start=time.time();print('starting',len(tasks),'tasks with4workers',flush=True)
    with cf.ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(run,tasks,chunksize=1):print('finished',result,'wall',time.time()-start,flush=True)
    ctx.dps=DIGITS+400
    for label in ['a','b']:
        own=[s for s in tasks if s['profile']==label];values=[arb(0) for _ in range(4)]
        for s in own:
            data=json.loads(filename(s).read_text())
            if data['settings']!=s or data['algorithm_sha256']!=ALGORITHM_SHA:raise ValueError('Assembly metadata mismatch')
            vals=[arb(x) for x in data['values']]
            if len(vals)!=4 or any(not x.is_finite() for x in vals):raise ValueError('Incomplete assembly data')
            values=[a+b for a,b in zip(values,vals)]
        R=aa(Fraction(*own[-1]['upper']))
        tail=3*(arb.pi()/2)**arb('2.5')*R**arb('1.5')*(-5*R).exp()/(5-arb('1.5')/R)
        values=[v+arb(0,tail.upper()) for v in values]
        output={'schema':'vakint.bessel-high-guard.complete-profile.v1','complete':True,'profile':label,'digits':DIGITS,'guard':own[0]['guard'],'settings':own,'values':[v.str(DIGITS+40,more=True) for v in values],'accuracy_bits':[v.rel_accuracy_bits() for v in values],'infinite_tail_bound':tail.str(40,more=True),'wall_seconds':time.time()-start,'algorithm_sha256':ALGORITHM_SHA}
        atomic(HERE/f'profile-{label}.json',output);print('complete',label,output['accuracy_bits'],flush=True)
if __name__=='__main__':main()
