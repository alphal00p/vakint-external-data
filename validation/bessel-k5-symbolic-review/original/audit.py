#!/usr/bin/env python3
"""Independent, read-only audit of PR4-family K5 moment formula bindings.

No imported producer algebra, master alias lookup, quadrature, or CAS is used.
The exact check uses sparse Q-polynomials and a separate Q epsilon-series parser.
"""
import ast
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction as Q
import hashlib
import json
import math
from pathlib import Path
import subprocess

from flint import arb, ctx, fmpq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BESSEL = HERE.parent
REPO = ROOT / 'vakint-external-data'
COMMIT = '277e8768b37bb97141c45444f5fb94fa18177dc7'
PRODUCER = Path('/shared/codex-2/vacuum_masters/MASTERS/pslq/artifacts/PR4-direct10-acceptance-publication-source-v1')
NAMES = ('B1', 'J1', 'B3', 'J3', 'pi', 'zeta3', 'zeta5')
ZERO = (0,) * len(NAMES)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Poly(dict):
    """Sparse multivariate polynomials over Q; variables are formal, independent."""
    def __init__(self, value=0):
        super().__init__(value if isinstance(value, dict) else ({ZERO: Q(value)} if value else {}))

    @classmethod
    def var(cls, name):
        key = list(ZERO)
        key[NAMES.index(name)] = 1
        return cls({tuple(key): Q(1)})

    def __add__(self, other):
        out = Poly(self)
        for key, val in Poly(other).items():
            out[key] = out.get(key, Q(0)) + val
            if not out[key]:
                del out[key]
        return out

    __radd__ = __add__

    def __neg__(self):
        return Poly({key: -val for key, val in self.items()})

    def __sub__(self, other):
        return self + -Poly(other)

    def __rsub__(self, other):
        return Poly(other) + -self

    def __mul__(self, other):
        out = Poly()
        for a, x in self.items():
            for b, y in Poly(other).items():
                key = tuple(ai + bi for ai, bi in zip(a, b))
                out = out + Poly({key: x * y})
        return out

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = Poly(other)
        require(set(other) == {ZERO} and other[ZERO], 'Only nonzero rational denominators admitted')
        return Poly({key: val / other[ZERO] for key, val in self.items()})

    def __pow__(self, power):
        if power < 0:
            return (Poly(1) / self) ** -power
        out = Poly(1)
        for _ in range(power):
            out = out * self
        return out

    def report(self):
        return {('*'.join(n + (f'^{p}' if p != 1 else '') for n, p in zip(NAMES, key) if p) or '1'): str(val)
                for key, val in sorted(self.items())}

    def evaluate(self, values):
        out = arb(0)
        for key, val in self.items():
            term = arb(fmpq(val.numerator, val.denominator))
            for name, power in zip(NAMES, key):
                if power:
                    term *= values[name] ** power
            out += term
        return out


def parse_formula(text):
    replacements = {
        'vakint::K5Moment(1)': 'B1', 'vakint::K5LogMoment(1)': 'J1',
        'vakint::K5Moment(3)': 'B3', 'vakint::K5LogMoment(3)': 'J3',
        'symbolica::zeta(3)': 'zeta3', 'symbolica::zeta(5)': 'zeta5', '𝜋': 'pi',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    def visit(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, int):
            return Poly(n.value)
        if isinstance(n, ast.Name) and n.id in NAMES:
            return Poly.var(n.id)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -visit(n.operand)
        require(isinstance(n, ast.BinOp), f'Unsupported expression node {ast.dump(n)}')
        a, b = visit(n.left), visit(n.right)
        if isinstance(n.op, ast.Add): return a + b
        if isinstance(n.op, ast.Sub): return a - b
        if isinstance(n.op, ast.Mult): return a * b
        if isinstance(n.op, ast.Div): return a / b
        if isinstance(n.op, ast.Pow):
            require(set(b) == {ZERO} and b[ZERO].denominator == 1, 'Exponent must be an integer')
            return a ** int(b[ZERO])
        raise ValueError(ast.dump(n))
    return visit(ast.parse(text.replace('^', '**'), mode='eval').body)


def rational_jet(text, order=6):
    """Independent formal series implementation; Q arithmetic only."""
    def c(value): return [Q(value)] + [Q(0)] * (order - 1)
    def mul(a, b): return [sum((a[j] * b[n-j] for j in range(n+1)), Q(0)) for n in range(order)]
    def inv(a):
        require(a[0] != 0, 'Laurent pole unexpectedly present in rational dimension shift')
        b = c(1 / a[0])
        for n in range(1, order): b[n] = -sum(a[j] * b[n-j] for j in range(1, n+1)) / a[0]
        return b
    def power(a, n):
        if n < 0: return power(inv(a), -n)
        b = c(1)
        for _ in range(n): b = mul(a, b)
        return b
    def visit(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, int): return c(n.value)
        if isinstance(n, ast.Name) and n.id == 'e': return [Q(0), Q(1)] + [Q(0)] * (order-2)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return [-x for x in visit(n.operand)]
        require(isinstance(n, ast.BinOp), f'Invalid dimension-shift syntax {ast.dump(n)}')
        a, b = visit(n.left), visit(n.right)
        if isinstance(n.op, ast.Add): return [x+y for x, y in zip(a, b)]
        if isinstance(n.op, ast.Sub): return [x-y for x, y in zip(a, b)]
        if isinstance(n.op, ast.Mult): return mul(a, b)
        if isinstance(n.op, ast.Div): return mul(a, inv(b))
        if isinstance(n.op, ast.Pow):
            require(not any(b[1:]) and b[0].denominator == 1, 'Noninteger power in rational shift')
            return power(a, int(b[0]))
        raise ValueError(ast.dump(n))
    return visit(ast.parse(text.replace('pr4_dimension_shift::{}::epsilon', 'e').replace('^', '**'), mode='eval').body)


def rounding_cell(value, digits):
    require(value.is_finite() and not value.contains(0), 'Finite nonzero ball required')
    with localcontext() as dec:
        dec.prec = digits
        dec.rounding = ROUND_HALF_EVEN
        central = +Decimal(value.mid().str(digits+70, radius=False))
        before, after = central.next_minus(dec), central.next_plus(dec)
    with localcontext() as dec:
        dec.prec = digits + 30
        low, high = (central + before)/2, (central + after)/2
    require(value.lower() > arb(str(low)).upper() and value.upper() < arb(str(high)).lower(), 'Nonunique rounded result')
    return format(central, 'f')


def main():
    inputs = {}
    def file(path, pin=None):
        raw = path.read_bytes()
        actual = digest(raw)
        if pin: require(actual == pin, f'Hash mismatch: {path}')
        inputs[str(path)] = actual
        return json.loads(raw)
    def blob(path):
        raw = subprocess.check_output(['git', '-C', str(REPO), 'show', f'{COMMIT}:{path}'])
        inputs[f'git:{COMMIT}:{path}'] = digest(raw)
        return json.loads(raw)

    upstream = blob('provenance/producer-update.json')
    publication = file(PRODUCER/'publication-output-v1/publication.json', upstream['provenance']['actual_PR4_publication']['sha256'])
    plan = file(PRODUCER/'plan.json', publication['source_plan']['sha256'])
    definitions = file(PRODUCER/'independent-period-definitions.json', plan['period_definitions']['sha256'])
    require(definitions['logarithmic_moment_factor'] == 3, 'Wrong log moment factor')
    require(definitions['definitions'] == {
        'K5LogMoment': '3*Integral[t^k*BesselK(0,t)^5*(log(t)+EulerGamma-log(2)),{t,0,infinity}], k=1,3',
        'K5Moment': 'Integral[t^k*BesselK(0,t)^5,{t,0,infinity}], k=1,3'}, 'Moment convention drift')
    require(definitions['native_atoms'] == {'B1':'vakint::K5Moment(1)', 'B3':'vakint::K5Moment(3)', 'J1':'vakint::K5LogMoment(1)', 'J3':'vakint::K5LogMoment(3)'}, 'Ambiguous native atoms')
    shift = file(BESSEL/'high-guard/source-receipts/exact-shift-and-valuations.json', '660b9e0c6debdabd739fbb92ab9d9da700bdd6025f10b3b79082f48c2af7d531')
    accepted = file(BESSEL/'high-guard/validation.json', '1f641d1ddca038481e44cb4ce2d7bcc5d765faac4c5a765ea3a8dfc456d6bca4')
    constants = file(BESSEL/'high-guard/constants20200.json', 'bc9afa66faaaf01afef7ee4e90c2cc1a13691aa4cc8d674e3f39ce688c9afa31')
    require(accepted['accepted'] is True and accepted['validated_significant_digits'] == 20200, 'Unaccepted moment source')
    require(constants['validation_sha256'] == inputs[str(BESSEL/'high-guard/validation.json')], 'Constant validation binding mismatch')

    # Exact exponent coefficients for exp[4 sum_{n>=2} (-1)^n zeta(n) e^n/n].
    pi, z3, z5 = (Poly.var(n) for n in ('pi', 'zeta3', 'zeta5'))
    q = [Poly(), Poly(), pi**2/3, -4*z3/3, pi**4/90, -4*z5/5]
    exp = [Poly(1)] + [Poly() for _ in range(5)]
    for n in range(1, 6): exp[n] = sum((k*q[k]*exp[n-k] for k in range(1, n+1)), Poly()) / n
    t4 = [sum((math.comb(n-j+3, 3)*exp[j] for j in range(n+1)), Poly()) for n in range(6)]
    expected, dimension_coefficients = {}, {}
    B1, J1, B3, J3 = (Poly.var(n) for n in NAMES[:4])
    for i, master in enumerate(('PR4', 'PR4d')):
        g1 = rational_jet(shift['D2_moment_coalesced_c1_coefficients'][i])
        g3 = rational_jet(shift['D2_moment_c3_coefficients'][i])
        b = rational_jet(shift['shift_inverse_b'][i])
        expected[master] = {
            0: -16*(g1[0]*B1 + g3[0]*B3) + sum((b[j]*t4[4-j] for j in range(5)), Poly()),
            1: -16*(g1[0]*J1 + g1[1]*B1 + g3[0]*J3 + g3[1]*B3) + sum((b[j]*t4[5-j] for j in range(6)), Poly()),
        }
        dimension_coefficients[master] = {'g1':list(map(str, g1[:2])), 'g3':list(map(str, g3[:2])), 'b_through_5':list(map(str, b))}
    # Exact single-dot relation D(e)=(3-4e)/5 U(e), not numerical fitting.
    pr4_minus1 = parse_formula('-10/3*symbolica::zeta(3)+35/9*𝜋^2+58345/864')
    expected['PR4singleDot'] = {0:Q(3,5)*expected['PR4'][0]-Q(4,5)*pr4_minus1,
                              1:Q(3,5)*expected['PR4'][1]-Q(4,5)*expected['PR4'][0]}
    groups = {'PR4':('P6','P24','P41','P59'), 'PR4d':('P11','P29','P46','P68'), 'PR4singleDot':('P9','P28','P44','P66')}
    exact_checks = []
    formulas = {}
    for group, masters in groups.items():
        for master in masters:
            formulas[master] = dict(blob(f'4L/masters/{master}/symbolic.json'))
            for order in (0,1):
                parsed = parse_formula(formulas[master][order])
                require(parsed == expected[group][order], f'Exact formula mismatch: {master}, e^{order}')
                exact_checks.append({'master':master, 'epsilon_power':order, 'basis':group, 'exact_difference':{}})

    # Evaluate exact upstream formulas with both certified moment balls.
    ctx.dps = 20350
    fixed = {'pi':arb.pi(), 'zeta3':arb(3).zeta(), 'zeta5':arb(5).zeta()}
    numeric_checks = []
    by_symbol = {r['symbol']:r for r in constants['constants']}
    for label in ('a','b'):
        profile = file(BESSEL/f'high-guard/profile-{label}.json', accepted['artifact_sha256'][f'profile-{label}.json'])
        require(profile['complete'] is True and len(profile['values']) == 4, 'Malformed moment profile')
        values = dict(zip(NAMES[:4], map(arb, profile['values']))) | fixed
        for master, names in [('P6',('PR4fin','PR4ep1')), ('P11',('PR4dfin','PR4dep1'))]:
            for order, short in enumerate(names):
                value = parse_formula(formulas[master][order]).evaluate(values)
                ref = by_symbol[f'vakint::{short}']
                require(rounding_cell(value, 20208) == ref['numerical_value'], f'Numerical payload mismatch: {master}, e^{order}, profile {label}')
                source_ball = arb(ref['numerical_value']) + arb(0, ref['validation']['absolute_error_bound'])
                require(value.overlaps(source_ball), 'Accepted error radius is inconsistent')
                numeric_checks.append({'master':master,'epsilon_power':order,'profile':label,'stored_digits_identical':20208,'accepted_precision':20200,'value_prefix':ref['numerical_value'][:82], 'relative_accuracy_bits':value.rel_accuracy_bits()})

    report = {
        'schema':'vakint.independent-upstream-moment-binding-audit.v1', 'accepted':True,
        'upstream_commit':COMMIT, 'logarithmic_moment_factor':3,
        'mapping':definitions['native_atoms'],
        'normalization':definitions['normalization_of_master_coefficients'],
        'proof':{
            'dimension_shift':'-16 exp(gamma e)/Gamma(1-e) [g1(e) kappa1(e)+g3(e) kappa3(e)] + b(e) T1(e)^4',
            'kappa_jet':'kappa_k(0)=B_k; kappa_k_prime(0)=J_k=3 integral r^k(log(r)+gamma-log(2)) K0(r)^5 dr',
            'prefactor_linear_coefficient':0,
            'T1_fourth':'e^-4 (1-e)^-4 exp[4 sum_{n>=2} (-1)^n zeta(n)e^n/n]',
            'exact_method':'Independent sparse rational polynomial and formal rational epsilon-series arithmetic; no imported producer implementation, numerical fitting, or PR4 alias lookup',
            'dimension_shift_rational_jets':dimension_coefficients,
            'representative_polynomials':{master:{str(order):poly.report() for order,poly in orders.items()} for master,orders in expected.items()},
        },
        'exact_formula_checks':exact_checks, 'numerical_checks':numeric_checks,
        'limits':['This audit accepts symbol-to-certified-moment bindings and finite/epsilon-one formula parity. It does not assert arbitrary-precision runtime capability for finite stored moment payloads.', 'Published moment-source certification is consumed with pinned hashes; expensive quadrature is not repeated.'],
        'input_sha256':inputs, 'audit_script_sha256':digest(Path(__file__).read_bytes()),
    }
    output = HERE/'audit.json'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'accepted':True,'exact_formula_checks':len(exact_checks),'numerical_checks':len(numeric_checks),'report':str(output),'sha256':digest(output.read_bytes())}))


if __name__ == '__main__':
    main()
