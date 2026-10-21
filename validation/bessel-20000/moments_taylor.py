#!/usr/bin/env python3
"""K0^5 moments and logarithmic jets using Arb Taylor integration.

Independent of Mathematica quadrature.  Positive-r axis only. Interval tails
are bounded by Cauchy on a circle contained in Re(z)>0, where the integral
representation gives |K0(z)| <= K0(Re(z)). All arithmetic is Arb ball arithmetic.
"""
import argparse, json, math, time
from pathlib import Path
from flint import arb, arb_series, ctx


def small_interval(a, digits, guard):
    # K0(a sqrt(t)) = A(t) - log(t) I0(a sqrt(t))/2.
    # Integrate all log monomials exactly; bound omitted entire-series tails
    # and use |x^5-y^5| <= 5 |x-y| max(|x|,|y|)^4.
    ctx.dps = digits + guard
    n = max(40, int((digits + guard) / max(1.0, math.log10(digits + 30))) + 50)
    # generous n; term factorial tails provide much faster convergence.
    while True:
        h = arb(0); u = arb(1); aa = arb(a)**2/4
        iv=[]; av=[]; L=arb(a).log()+arb.const_euler()-arb(2).log()
        for j in range(n):
            if j:
                u *= aa/(j*j); h += arb(1)/j
            iv.append(u); av.append(u*(h-L))
        if abs(u).upper() < arb(10)**(-(digits+guard+30)):
            break
        n *= 2
    ctx.cap=n
    I=arb_series(iv,prec=n); A=arb_series(av,prec=n)
    vals=[arb(0) for _ in range(4)]
    for j in range(6):
        p=(A**(5-j))*(I**j)
        fac=arb(math.comb(5,j)*math.factorial(j))/(2**j)
        for k,idx in [(1,0),(3,2)]:
            alpha=(k+1)//2
            b=arb(0); jet=arb(0)
            for l,c in enumerate(p.coeffs()):
                den=l+alpha
                z=c/(den**(j+1))
                b+=z
                jet+=z*(L-arb(j+1)/(2*den))
            scale=arb(a)**(k+1)*fac/2
            vals[idx]+=scale*b; vals[idx+1]+=3*scale*jet
    # Full P_j(t)=A(t)^(5-j)I(t)^j coefficients below n are exact.
    # Cauchy bounds cover every omitted PRODUCT coefficient, not just the
    # omitted input series. H_m <= m gives an entire-circle majorant for A.
    R=(arb(2*n)/(5*arb(a)))**2
    if R<2: raise ValueError("small interval Cauchy radius too small")
    x=arb(a)*R.sqrt()
    MI=x.bessel_i(0)
    MA=abs(L)*MI+x*x.bessel_i(1)/2
    common=R**(-n)/(1-1/R)
    for j in range(6):
        Ptail=MA**(5-j)*MI**j*common
        fac=arb(math.comb(5,j)*math.factorial(j))/(2**j)
        for k,idx in [(1,0),(3,2)]:
            alpha=(k+1)//2
            den=n+alpha
            scale=arb(a)**(k+1)*fac/2
            er=scale*Ptail/(den**(j+1))
            ej=3*er*(abs(L)+arb(j+1)/(2*den))
            vals[idx]+=arb(0,er.upper())
            vals[idx+1]+=arb(0,ej.upper())
    return vals, n


def interval(center, h, digits, guard):
    ctx.dps=digits+guard
    a=arb(center); hh=arb(h)
    rho=arb('0.9')
    # For |q|=rho/h, Re r>=a(1-rho).
    kval=(a*(1-rho)).bessel_k(0)
    maxr=a*(1+rho)
    minr=a*(1-rho)
    logbound=max(abs(minr.log()+arb.const_euler()-arb(2).log()).upper(),abs(maxr.log()+arb.const_euler()-arb(2).log()).upper())+arb.pi()/2
    M=max(arb(1),maxr**3)*kval**5*max(arb(1),3*logbound)
    target=arb(10)**(-(digits+12))
    ratio=hh/rho
    n=max(20,int(float((target/(2*a*hh*M)*(1-ratio)).log()/ratio.log()))+5)
    if n%2: n+=1
    while (2*a*hh*M*ratio**n/(1-ratio)).upper() > target.lower(): n+=2
    tail=2*a*hh*M*ratio**n/(1-ratio)
    # Increase source precision for unstable high-degree recurrence; verify actual
    # final balls rather than claiming this guard is sufficient a priori.
    c=[a.bessel_k(0), -a*hh*a.bessel_k(1)]
    a2=a*a; h2=hh*hh
    for j in range(n-2):
        v=-hh*((j+1)*(2*j+1))*c[j+1] - h2*(arb(j*j)-a2)*c[j]
        if j>=1: v+=2*a2*h2*hh*c[j-1]
        if j>=2: v+=a2*h2*h2*c[j-2]
        c.append(v/((j+1)*(j+2)))
    ctx.cap=n
    y=arb_series(c,prec=n)
    fifth=y**5
    q=arb_series([1,hh],prec=n)
    L=arb_series([a.log()+arb.const_euler()-arb(2).log()],prec=n)+q.log()
    logged=fifth*L*3
    vals=[]
    for k in [1,3]:
        for p in [fifth*q**k, logged*q**k]:
            s=arb(0)
            for j in range(0,n,2): s += p[j]*arb(2)/(j+1)
            s*=a**(k+1)*hh
            s+=arb(0,tail.upper())
            vals.append(s)
    return vals,n,tail.upper().str(12)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--digits',type=int,default=200);ap.add_argument('--guard',type=int,default=100);ap.add_argument('--ratio',default='0.2');ap.add_argument('--start',default='1');ap.add_argument('--output',required=True);ap.add_argument('--limit',type=int)
    args=ap.parse_args(); t0=time.time(); ctx.dps=args.digits+args.guard
    a=arb(args.start); h=arb(args.ratio); endpoint=arb(math.ceil((args.digits+40)*math.log(10)/5))
    data={'method':'Arb Taylor K0^5 Cauchy bounds','digits':args.digits,'guard':args.guard,'intervals':[]}
    ts=time.time(); vals,n=small_interval(a,args.digits,args.guard)
    print('small',n,time.time()-ts,[v.rel_accuracy_bits() for v in vals],flush=True)
    data['small']={'n':n,'seconds':time.time()-ts}
    lower=a
    count=0
    while lower<endpoint:
        center=lower/(1-h); upper=center*(1+h)
        ts=time.time(); vv,n,tail=interval(center,h,args.digits,args.guard)
        vals=[x+y for x,y in zip(vals,vv)];count+=1
        row={'lower':lower.str(12),'upper':upper.str(12),'n':n,'seconds':time.time()-ts,'tail_bound':tail,'accuracy_bits':[v.rel_accuracy_bits() for v in vals]}
        data['intervals'].append(row)
        data['values']=[v.str(args.digits+20) for v in vals]; data['elapsed_seconds']=time.time()-t0
        Path(args.output).write_text(json.dumps(data,indent=2)+'\n')
        print(count,row,flush=True)
        lower=upper
        if args.limit and count>=args.limit:break
    # For R>=1, K0(r)<=sqrt(pi/(2r))*exp(-r). The logarithmic
    # factor 3|log(r exp(gamma)/2)|<=3r gives this common upper bound.
    if lower>=endpoint:
        tail=3*(arb.pi()/2)**arb('2.5')*lower**arb('1.5')*(-5*lower).exp()/(5-arb('1.5')/lower)
        vals=[v+arb(0,tail.upper()) for v in vals]
        data['infinite_tail_bound']=str(tail)
        data['values']=[v.str(args.digits+20) for v in vals]
    data['elapsed_seconds']=time.time()-t0;Path(args.output).write_text(json.dumps(data,indent=2)+'\n')

if __name__=='__main__':main()
