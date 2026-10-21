#!/usr/bin/env python3
"""Reconstruct PR4/PR4d finite parts from authenticated rational D-shift."""
import argparse, ast, hashlib, json
from pathlib import Path
from flint import arb, arb_series,ctx

RECEIPT=Path(__file__).resolve().parent/'source-receipts'/'exact-shift-and-valuations.json'

def rational_series(text, e):
    tree=ast.parse(text.replace('pr4_dimension_shift::{}::epsilon','e').replace('^','**'),mode='eval')
    def f(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,int):return arb(n.value)
        if isinstance(n,ast.Name) and n.id=='e':return e
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -f(n.operand)
        if isinstance(n,ast.BinOp):
            a,b=f(n.left),f(n.right)
            if isinstance(n.op,ast.Add):return a+b
            if isinstance(n.op,ast.Sub):return a-b
            if isinstance(n.op,ast.Mult):return a*b
            if isinstance(n.op,ast.Div):return a/b
            if isinstance(n.op,ast.Pow):
                # All exponents of this authenticated rational map are integers.
                return a**int(str(b).split('.')[0])
        raise ValueError(ast.dump(n))
    out=f(tree.body)
    return out if isinstance(out,arb_series) else arb_series([out])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');args=ap.parse_args()
    data=json.loads(Path(args.input).read_text());digits=data['digits'];ctx.dps=digits+100;ctx.cap=6
    src=json.loads(RECEIPT.read_text());e=arb_series([0,1],prec=6)
    # exp(gamma*eps)Gamma(eps-1) = -exp(sum_{n>=2}(-1)^n*zeta(n)*eps^n/n)/(eps(1-eps)).
    # Its fourth power is eps^-4 times the following analytic series.
    expo=arb_series([0,0]+[arb(4)*(-1)**n*arb(n).zeta()/n for n in range(2,6)],prec=6)
    t4=(1-e)**-4*expo.exp()
    B1,J1,B3,J3=[arb(x) for x in data['values']]
    out={}
    for i,name in enumerate(['PR4fin','PR4dfin']):
        g1=rational_series(src['D2_moment_coalesced_c1_coefficients'][i],e)
        g3=rational_series(src['D2_moment_c3_coefficients'][i],e)
        b=rational_series(src['shift_inverse_b'][i],e)
        lower=(b*t4)[4]
        v=-16*(g1[0]*B1+g3[0]*B3)+lower
        # exp(gamma eps)/Gamma(1-eps) has zero linear coefficient.
        jet=-16*(g1[0]*J1+g1[1]*B1+g3[0]*J3+g3[1]*B3)+(b*t4)[5]
        out[name]={'value':v.str(digits+15),'epsilon1_value':jet.str(digits+15),'accuracy_bits':v.rel_accuracy_bits(),'lower_tadpole_part':lower.str(50),'g1_0':str(g1[0]),'g3_0':str(g3[0])}
    result={'schema':'vakint.precision-periods.bessel-reconstruction.v1','digits':digits,'moments':str(Path(args.input).resolve()),'map_sha256':hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),'periods':out}
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    for k,v in out.items():print(k,v['value'][:160],v['accuracy_bits'])
if __name__=='__main__':main()
