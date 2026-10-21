#!/usr/bin/env python3
"""Parallel independent interval certificates for two shifted partitions."""
import argparse, concurrent.futures as cf, hashlib, json, math, os, time
from fractions import Fraction
from pathlib import Path
from flint import arb,ctx,fmpq
from moments_taylor import interval

HERE=Path(__file__).resolve().parent

def task(p):
    label,index,num,den,digits,guard=p
    ctx.threads=1
    ts=time.time()
    ctx.dps=digits+guard
    lower=Fraction(num,den);h=Fraction(1,5);center=lower/(1-h);upper=center*(1+h)
    vals,n,tail=interval(arb(fmpq(center.numerator,center.denominator)),arb(fmpq(1,5)),digits,guard)
    row={'profile':label,'index':index,'lower':[num,den],'upper':[upper.numerator,upper.denominator],'n':n,'seconds':time.time()-ts,'tail_bound':tail,'values':[v.str(digits+25) for v in vals],'accuracy_bits':[v.rel_accuracy_bits() for v in vals]}
    dest=HERE/'certificates'/f'{label}-{index:03d}.json'
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(row,indent=2)+'\n')
    return {k:v for k,v in row.items() if k!='values'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);ap.add_argument('--digits',type=int,default=20000);args=ap.parse_args()
    digits=args.digits;ctx.dps=digits+300
    starts={'a':(Fraction(3,2),HERE/'moments20000-a.json',180),'b':(Fraction(5,4),HERE/'moments20000-b.json',260)}
    endpoint=math.ceil((digits+40)*math.log(10)/5)
    tasks=[]
    for label,(lower,prefix,guard) in starts.items():
        data=json.loads(prefix.read_text())
        assert len(data['intervals']) in [1,2],(label,len(data['intervals']))
        if label=='a': lower=Fraction(3,2)**len(data['intervals'])
        i=1
        while lower<endpoint:
            dest=HERE/'certificates'/f'{label}-{i:03d}.json'
            if not dest.exists():tasks.append((label,i,lower.numerator,lower.denominator,digits,guard))
            lower*=Fraction(3,2);i+=1
    # Interleave independent profiles so one long profile cannot starve the other.
    tasks.sort(key=lambda p:(p[1],p[0]))
    print('tasks',len(tasks),'workers',args.workers,flush=True)
    t0=time.time()
    with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(task,tasks,chunksize=1):
            print('finished',row,'total_seconds',time.time()-t0,flush=True)
    for label,(lower,prefix,guard) in starts.items():
        ctx.dps=digits+300
        data=json.loads(prefix.read_text()); vals=[arb(v) for v in data['values']]
        if label=='a':lower=Fraction(3,2)**len(data['intervals'])
        i=1
        while lower<endpoint:
            row=json.loads((HERE/'certificates'/f'{label}-{i:03d}.json').read_text())
            vals=[v+arb(w) for v,w in zip(vals,row['values'])]
            data['intervals'].append({k:v for k,v in row.items() if k!='values'})
            lower*=Fraction(3,2);i+=1
        R=arb(fmpq(lower.numerator,lower.denominator))
        tail=3*(arb.pi()/2)**arb('2.5')*R**arb('1.5')*(-5*R).exp()/(5-arb('1.5')/R)
        vals=[v+arb(0,tail.upper()) for v in vals]
        data['infinite_tail_bound']=tail.str(20)
        data['values']=[v.str(digits+25) for v in vals]
        data['accuracy_bits']=[v.rel_accuracy_bits() for v in vals]
        data['interval_method']='Cauchy-bounded Arb Taylor, parallel exact rational partition'
        data['prefix_file']=str(prefix)
        data['source_sha256']=hashlib.sha256((HERE/'moments_taylor.py').read_bytes()).hexdigest()
        data['parallel_wall_seconds']=time.time()-t0
        (HERE/f'moments20000-{label}-complete.json').write_text(json.dumps(data,indent=2)+'\n')
        print('complete',label,data['accuracy_bits'],flush=True)

if __name__=='__main__':main()
