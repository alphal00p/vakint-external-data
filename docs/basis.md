# The constant basis of the 1L–4L exact coefficients (basis v4)

Publication [`provenance/takeover-basis-v4-rewrite-v1`](../provenance/takeover-basis-v4-rewrite-v1) (31 October 2026) restates every exact 1L–4L master coefficient (739 rows of 115 masters; 713 distinct coefficients) as a polynomial with rational coefficients in the 68 generators below, times `3^(1/2)` for odd parity. No other constant occurs. The values are unchanged: every `numerical.json`, every numerical precision record and every constant value is byte-identical. The machine-readable list with every explicit definition is [`basis-v4.json`](../provenance/takeover-basis-v4-rewrite-v1/basis-v4.json); Vakint's `get_constant(symbol).definition()` (gammaloop PR #243) is the authoritative definition of each symbol.

Labels: EXACT (proved), COMPUTED+VALIDATED (two independent profiles agreeing beyond the validated digits plus an independent-method control; empirical, not an interval proof), numerical identity (integer relation found on part of the digits and confirmed on the rest; not a proof).

## Conventions

- Definitions are Symbolica atoms with the inert heads `vakint::Integral(f, vakint::Interval(x,a,b), ...)` (first interval outermost), `vakint::LoopIntegral(D, f, vakint::k(1), ...)` (Euclidean measure d^Dk/π^(D/2) per loop), `vakint::SeriesCoefficient(f, x, 0, n)` (the ordinary Taylor coefficient of x^n, not the n-th derivative) and `vakint::EuclideanDot`. All masses are 1. No definition refers to another named constant.
- `3^(1/2)` is an explicit algebraic factor, not a generator. It multiplies exactly the monomials with an odd number of Im-type factors (π, Cl2, Cl4, Im Li3(i/√3), Im Li4(i/√3), the three Im G, T111bar4).
- ω = e^(iπ/3). GPL letters −ω = e^(4iπ/3) and ω̄ = e^(−iπ/3); G(a1,…,an; 1) = ∫_(1>t1>…>tn>0) ∏ dt_i/(t_i − a_i).
- D=2 periods `vakint::<X>D2Eps<k>` (and `vakint::PR7D2` for k = 0): the ordinary Taylor coefficient [δ^k] of X̂(δ) = e^(4γδ) ∫ ∏_(l=1..4) d^(2−2δ)k_l/π^(1−δ) ∏_e (q_e² + 1)^(−a_e), positive Euclidean, unit mass, no coupling or symmetry factor; raw Minkowski jets are (−1)^(Σa) times these.
- MATAD bars follow Vakint `matad.rs`: T111bar(k) and BNbar(k) are [ε^k] of the master times Γ(1+ε)^(−L) and the MATAD prefactor, with **no** factor e^(Lγε); D5bar(k) and D6bar(k) are [ε^k] of (1−ε)(1−2ε) e^(3γε) times the master (d = 4 − 2ε, d^dk/π^(d/2) per loop).

## The 68 generators

### Multiple zeta values (4)

| # | constant | Vakint symbol | weight | definition | normalisation | digits |
|---:|---|---|---:|---|---|---|
| 1 | π | `𝜋` | 1 | `Integral(4/(1+t^2),Interval(t,0,1))` | plain real number; no loop measure involved | any (built-in) |
| 2 | ζ3 | `symbolica::zeta(3)` | 3 | `1/2*Integral(log(t)^2/(1-t),Interval(t,0,1))` | plain real number; no loop measure involved | any (built-in) |
| 3 | ζ5 | `symbolica::zeta(5)` | 5 | `1/24*Integral(log(t)^4/(1-t),Interval(t,0,1))` | plain real number; no loop measure involved | any (built-in) |
| 4 | ζ7 | `symbolica::zeta(7)` | 7 | `1/720*Integral(log(t)^6/(1-t),Interval(t,0,1))` | plain real number; no loop measure involved | any (built-in) |

### Level 2 (alternating sums) (5)

| # | constant | Vakint symbol | weight | definition | normalisation | digits |
|---:|---|---|---:|---|---|---|
| 5 | log2 | `symbolica::log(2)` | 1 | `Integral(1/(1+t),Interval(t,0,1))` | plain real number (alternating/level-2 sum); no loop measure involved | any (built-in) |
| 6 | Li4(1/2) | `symbolica::polylog(4,1/2)` | 4 | `1/6*Integral(-log(t)^3/(2-t),Interval(t,0,1))` | plain real number (alternating/level-2 sum); no loop measure involved | any (built-in) |
| 7 | Li5(1/2) | `symbolica::polylog(5,1/2)` | 5 | `1/24*Integral(log(t)^4/(2-t),Interval(t,0,1))` | plain real number (alternating/level-2 sum); no loop measure involved | any (built-in) |
| 8 | Li6(1/2) | `symbolica::polylog(6,1/2)` | 6 | `1/120*Integral(-log(t)^5/(2-t),Interval(t,0,1))` | plain real number (alternating/level-2 sum); no loop measure involved | any (built-in) |
| 9 | s6 | `vakint::s6weak` | 6 | `Integral(1/24*(1/(1+x(1))+x(2)/(1-x(1)*x(2)))*log(x(1))^4/(1+x(2)),Interval(x(1),0,1),Interval(x(2),0,1))` | plain real number (alternating/level-2 sum); no loop measure involved | 20000 (estimated) |

### Level 6 (sixth roots of unity) and the MATAD weight-5/6 constants (14)

| # | constant | Vakint symbol | weight | definition | normalisation | digits |
|---:|---|---|---:|---|---|---|
| 10 | log3 | `symbolica::log(3)` | 1 | `Integral(1/(1+t),Interval(t,0,2))` | plain real number; letters are sixth roots of unity, omega = e^{i pi/3}; Re/Im projections explicit | any (built-in) |
| 11 | Cl2 | `vakint::cl2` | 2 | `-Integral(log(2*sin(1/2*t)),Interval(t,0,1/3*𝜋))` | plain real number; letters are sixth roots of unity, omega = e^{i pi/3}; Re/Im projections explicit | any (built-in) |
| 12 | ImLi3(i/√3) | `vakint::PolylogImag(3,3^(1/2)*𝑖/3)` | 3 | `imaginary_part(1/2*3^(1/2)*𝑖/3*Integral((-log(t))^2*(1-3^(1/2)*𝑖/3*t)^(-1),Interval(t,0,1)))` | plain real number: imaginary part of Li_3(z) at z = i/sqrt3 (= Ti_3(1/sqrt3), the inverse tangent integral), Li_3(z) = z/2! * Integral_0^1 (-log t)^2/(1 - z t) dt (Vakint builtin family PolylogImag(n, z)); no loop measure | any (built-in) |
| 13 | Cl4 | `vakint::cl4` | 4 | `1/12*3^(1/2)*Integral(-log(t)^3/(1-t+t^2),Interval(t,0,1))` | plain real number; letters are sixth roots of unity, omega = e^{i pi/3}; Re/Im projections explicit | any (built-in) |
| 14 | ImLi4(i/√3) | `vakint::PolylogImag(4,3^(1/2)*𝑖/3)` | 4 | `imaginary_part(1/6*3^(1/2)*𝑖/3*Integral((-log(t))^3*(1-3^(1/2)*𝑖/3*t)^(-1),Interval(t,0,1)))` | plain real number: imaginary part of Li_4(z) at z = i/sqrt3 (= Ti_4(1/sqrt3), the inverse tangent integral), Li_4(z) = z/3! * Integral_0^1 (-log t)^3/(1 - z t) dt (Vakint builtin family PolylogImag(n, z)); no loop measure | any (built-in) |
| 15 | ReG(0,0,ω̄,−1) | `vakint::GPLReal(0,0,(1-3^(1/2)*𝑖)/2,-1,1)` | 4 | `real_part(Integral(1/((1+x(4))*(x(3)-1/2*(1-𝑖*3^(1/2)))*x(1)*x(2)),Interval(x(1),0,1),Interval(x(2),0,x(1)),Interval(x(3),0,x(2)),Interval(x(4),0,x(3))))` | plain real number; letters are sixth roots of unity, omega = e^{i pi/3}; Re/Im projections explicit | any (built-in) |
| 16 | D5bar1 | `vakint::D5bar1` | 5 | `SeriesCoefficient(𝑒^(3*γ*ep)*(1-2*ep)*(1-ep)*LoopIntegral(4-2*ep,1/((1+EuclideanDot(k(1),k(1)))*(1+EuclideanDot(k(2),k(2)))*(1+EuclideanDot(k(3),k(3)))*(EuclideanDot(k(2),k(2))-2*EuclideanDot(k(2),k(3))+EuclideanDot(k(3),k(3)))*(1+EuclideanDot(k(1),k(1))-2*EuclideanDot(k(1),k(2))+EuclideanDot(k(2),k(2)))*(1+EuclideanDot(k(1),k(1))-2*EuclideanDot(k(1),k(3))+EuclideanDot(k(3),k(3)))),k(1),k(2),k(3)),ep,0,1)` | MATAD bar of Vakint matad.rs, tetrahedron topology D5 (one massless line) / D6 (six unit-mass lines): Xbar(k) = ordinary Taylor coefficient [ep^k] (not a derivative) of (1-ep)(1-2ep) * exp(3 gamma ep) * LoopIntegral, Euclidean measure d^dk/pi^(d/2) per loop (3 loops, d = 4-2ep), unit masses, no sign, the propagators shown | any (built-in) |
| 17 | D6bar1 | `vakint::D6bar1` | 5 | `SeriesCoefficient(𝑒^(3*γ*ep)*(1-2*ep)*(1-ep)*LoopIntegral(4-2*ep,1/((1+EuclideanDot(k(1),k(1)))*(1+EuclideanDot(k(2),k(2)))*(1+EuclideanDot(k(3),k(3)))*(1+EuclideanDot(k(1),k(1))-2*EuclideanDot(k(1),k(2))+EuclideanDot(k(2),k(2)))*(1+EuclideanDot(k(1),k(1))-2*EuclideanDot(k(1),k(3))+EuclideanDot(k(3),k(3)))*(1+EuclideanDot(k(2),k(2))-2*EuclideanDot(k(2),k(3))+EuclideanDot(k(3),k(3)))),k(1),k(2),k(3)),ep,0,1)` | MATAD bar of Vakint matad.rs, tetrahedron topology D5 (one massless line) / D6 (six unit-mass lines): Xbar(k) = ordinary Taylor coefficient [ep^k] (not a derivative) of (1-ep)(1-2ep) * exp(3 gamma ep) * LoopIntegral, Euclidean measure d^dk/pi^(d/2) per loop (3 loops, d = 4-2ep), unit masses, no sign, the propagators shown | any (built-in) |
| 18 | ImG(0,1,1,1,−ω) | `vakint::GPLImag(0,1,1,1,(-1-3^(1/2)*𝑖)/2,1)` | 5 | `imaginary_part(Integral(1/((-1+x(2))*(-1+x(3))*(-1+x(4))*(x(5)-1/2*(-1-𝑖*3^(1/2)))*x(1)),Interval(x(1),0,1),Interval(x(2),0,x(1)),Interval(x(3),0,x(2)),Interval(x(4),0,x(3)),Interval(x(5),0,x(4))))` | plain real number; letters are sixth roots of unity, omega = e^{i pi/3}; Re/Im projections explicit | any (built-in) |
| 19 | ImG(0,0,0,1,ω̄) | `vakint::GPLImag(0,0,0,1,(1-3^(1/2)*𝑖)/2,1)` | 5 | `imaginary_part(Integral(1/((-1+x(4))*(x(5)-1/2*(1-𝑖*3^(1/2)))*x(1)*x(2)*x(3)),Interval(x(1),0,1),Interval(x(2),0,x(1)),Interval(x(3),0,x(2)),Interval(x(4),0,x(3)),Interval(x(5),0,x(4))))` | plain real number; letters are sixth roots of unity, omega = e^{i pi/3}; Re/Im projections explicit | any (built-in) |
| 20 | ImG(0,0,0,1,−ω) | `vakint::GPLImag(0,0,0,1,(-1-3^(1/2)*𝑖)/2,1)` | 5 | `imaginary_part(Integral(1/((-1+x(4))*(x(5)-1/2*(-1-𝑖*3^(1/2)))*x(1)*x(2)*x(3)),Interval(x(1),0,1),Interval(x(2),0,x(1)),Interval(x(3),0,x(2)),Interval(x(4),0,x(3)),Interval(x(5),0,x(4))))` | plain real number; letters are sixth roots of unity, omega = e^{i pi/3}; Re/Im projections explicit | any (built-in) |
| 21 | D5bar2 | `vakint::D5bar2` | 6 | `SeriesCoefficient(𝑒^(3*γ*ep)*(1-2*ep)*(1-ep)*LoopIntegral(4-2*ep,1/((1+EuclideanDot(k(1),k(1)))*(1+EuclideanDot(k(2),k(2)))*(1+EuclideanDot(k(3),k(3)))*(EuclideanDot(k(2),k(2))-2*EuclideanDot(k(2),k(3))+EuclideanDot(k(3),k(3)))*(1+EuclideanDot(k(1),k(1))-2*EuclideanDot(k(1),k(2))+EuclideanDot(k(2),k(2)))*(1+EuclideanDot(k(1),k(1))-2*EuclideanDot(k(1),k(3))+EuclideanDot(k(3),k(3)))),k(1),k(2),k(3)),ep,0,2)` | MATAD bar of Vakint matad.rs, tetrahedron topology D5 (one massless line) / D6 (six unit-mass lines): Xbar(k) = ordinary Taylor coefficient [ep^k] (not a derivative) of (1-ep)(1-2ep) * exp(3 gamma ep) * LoopIntegral, Euclidean measure d^dk/pi^(d/2) per loop (3 loops, d = 4-2ep), unit masses, no sign, the propagators shown | any (built-in) |
| 22 | D6bar2 | `vakint::D6bar2` | 6 | `SeriesCoefficient(𝑒^(3*γ*ep)*(1-2*ep)*(1-ep)*LoopIntegral(4-2*ep,1/((1+EuclideanDot(k(1),k(1)))*(1+EuclideanDot(k(2),k(2)))*(1+EuclideanDot(k(3),k(3)))*(1+EuclideanDot(k(1),k(1))-2*EuclideanDot(k(1),k(2))+EuclideanDot(k(2),k(2)))*(1+EuclideanDot(k(1),k(1))-2*EuclideanDot(k(1),k(3))+EuclideanDot(k(3),k(3)))*(1+EuclideanDot(k(2),k(2))-2*EuclideanDot(k(2),k(3))+EuclideanDot(k(3),k(3)))),k(1),k(2),k(3)),ep,0,2)` | MATAD bar of Vakint matad.rs, tetrahedron topology D5 (one massless line) / D6 (six unit-mass lines): Xbar(k) = ordinary Taylor coefficient [ep^k] (not a derivative) of (1-ep)(1-2ep) * exp(3 gamma ep) * LoopIntegral, Euclidean measure d^dk/pi^(d/2) per loop (3 loops, d = 4-2ep), unit masses, no sign, the propagators shown | any (built-in) |
| 23 | T111bar4 | `vakint::T111bar4` | 6 | `SeriesCoefficient(3^(1/2)*(-1+ep)*(1-2*ep)*LoopIntegral(4-2*ep,1/((1+EuclideanDot(k(1),k(1)))*(1+EuclideanDot(k(2),k(2)))*(1+EuclideanDot(k(1),k(1))+2*EuclideanDot(k(1),k(2))+EuclideanDot(k(2),k(2)))),k(1),k(2))/gamma(1+ep)^2-3/2*3^(1/2)/ep^2,ep,0,4)` | MATAD bar of Vakint matad.rs, T111 = two-loop equal-mass sunset: T111bar(k) = ordinary Taylor coefficient [ep^k] of sqrt3 (1-2ep)(ep-1) * Gamma(1+ep)^(-2) * LoopIntegral, Euclidean measure d^dk/pi^(d/2) per loop (2 loops, d = 4-2ep), unit masses, no sign; NO factor exp(2 gamma ep) (Gamma(1+ep)^(-2) takes its place); the subtracted 3 sqrt3/(2 ep^2) only removes the double pole and does not change [ep^k] for k >= 0 | any (built-in) |

### Bessel moments (D=2 banana) (10)

| # | constant | Vakint symbol | weight | definition | normalisation | digits |
|---:|---|---|---:|---|---|---|
| 24 | B1 | `vakint::K5Moment(1)` | – | `Integral(t*bessel_k(0,t)^5,Interval(t,0,∞))` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 20000 (bounded) |
| 25 | B3 | `vakint::K5Moment(3)` | – | `Integral(t^3*bessel_k(0,t)^5,Interval(t,0,∞))` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 20000 (bounded) |
| 26 | J1 | `vakint::K5LogMoment(1)` | – | `3*Integral(t*(γ-log(2)+log(t))*bessel_k(0,t)^5,Interval(t,0,∞))` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 20000 (bounded) |
| 27 | J3 | `vakint::K5LogMoment(3)` | – | `3*Integral(t^3*(γ-log(2)+log(t))*bessel_k(0,t)^5,Interval(t,0,∞))` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 20000 (bounded) |
| 28 | κ1[2] | `vakint::K5MomentTaylor(1,2)` | – | `SeriesCoefficient((1/2*𝑒^γ)^(3*ep)*Integral(t^(1+3*ep)*bessel_k(ep,t)^5,Interval(t,0,∞)),ep,0,2)` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 520 (estimated) |
| 29 | κ3[2] | `vakint::K5MomentTaylor(3,2)` | – | `SeriesCoefficient((1/2*𝑒^γ)^(3*ep)*Integral(t^(3+3*ep)*bessel_k(ep,t)^5,Interval(t,0,∞)),ep,0,2)` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 520 (estimated) |
| 30 | κ1[3] | `vakint::K5MomentTaylor(1,3)` | – | `SeriesCoefficient((1/2*𝑒^γ)^(3*ep)*Integral(t^(1+3*ep)*bessel_k(ep,t)^5,Interval(t,0,∞)),ep,0,3)` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 520 (estimated) |
| 31 | κ3[3] | `vakint::K5MomentTaylor(3,3)` | – | `SeriesCoefficient((1/2*𝑒^γ)^(3*ep)*Integral(t^(3+3*ep)*bessel_k(ep,t)^5,Interval(t,0,∞)),ep,0,3)` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 520 (estimated) |
| 32 | κ1[4] | `vakint::K5MomentTaylor(1,4)` | – | `SeriesCoefficient((1/2*𝑒^γ)^(3*ep)*Integral(t^(1+3*ep)*bessel_k(ep,t)^5,Interval(t,0,∞)),ep,0,4)` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 520 (estimated) |
| 33 | κ3[4] | `vakint::K5MomentTaylor(3,4)` | – | `SeriesCoefficient((1/2*𝑒^γ)^(3*ep)*Integral(t^(3+3*ep)*bessel_k(ep,t)^5,Interval(t,0,∞)),ep,0,4)` | one-dimensional integral over t in (0, oo) of modified Bessel functions K_nu(t); no loop measure; K5MomentTaylor is the ordinary Taylor coefficient (not a derivative) of the eps-deformed moment including the factor (e^gamma/2)^(3 eps) | 520 (estimated) |

### D=2−2δ Taylor coefficients of four-loop vacuum integrals (30)

Each is [δ^k] of X̂(δ) as defined above for the integral X; the full `LoopIntegral` atom is the record's `symbolic_definition` in `4L/constants.json`.

| # | Vakint symbol | integral X | k | digits | status |
|---:|---|---|---:|---|---|
| 34 | `vakint::PR7D2` | D=2 value of the unit-mass six-line PR7 (triangle(3,2,1)) 4-loop vacuum integral, d^2k/pi per loop; family 693719b1bc3d, powers [0, 0, 1, 1, 0, 1, 1, 1, 1, 0] | 0 | 520 | ACCEPTED-500 |
| 35 | `vakint::PR7D2Eps1` | [delta^1] of hat PR7(D=2-2delta) | 1 | 520 | ACCEPTED-500 |
| 36 | `vakint::PR7D2Eps2` | proper six-line PR7 (triangle(3,2,1)); FMFT PR7; family 693719b1bc3d, powers [0, 0, 1, 1, 0, 1, 1, 1, 1, 0] | 2 | 520 | COMPUTED+VALIDATED |
| 37 | `vakint::PR7D2Eps3` | proper six-line PR7 (triangle(3,2,1)); FMFT PR7; family 693719b1bc3d, powers [0, 0, 1, 1, 0, 1, 1, 1, 1, 0] | 3 | 520 | COMPUTED+VALIDATED |
| 38 | `vakint::PR7D2Eps4` | proper six-line PR7 (triangle(3,2,1)); FMFT PR7; family 693719b1bc3d, powers [0, 0, 1, 1, 0, 1, 1, 1, 1, 0] | 4 | 600 | COMPUTED+VALIDATED |
| 39 | `vakint::PR9D2Eps1` | PR9 cat-eye (seven lines, K4 with one doubled edge); FMFT PR9 = RustRed P8; family 693719b1bc3d, powers [0, 0, 1, 1, 1, 1, 1, 1, 1, 0] | 1 | 520 | COMPUTED+VALIDATED |
| 40 | `vakint::PR9D2Eps2` | PR9 cat-eye (seven lines, K4 with one doubled edge); FMFT PR9 = RustRed P8; family 693719b1bc3d, powers [0, 0, 1, 1, 1, 1, 1, 1, 1, 0] | 2 | 520 | COMPUTED+VALIDATED |
| 41 | `vakint::PR9D2Eps3` | PR9 cat-eye (seven lines, K4 with one doubled edge); FMFT PR9 = RustRed P8; family 693719b1bc3d, powers [0, 0, 1, 1, 1, 1, 1, 1, 1, 0] | 3 | 520 | COMPUTED+VALIDATED |
| 42 | `vakint::PR9D2Eps4` | PR9 cat-eye (seven lines, K4 with one doubled edge); FMFT PR9 = RustRed P8; family 693719b1bc3d, powers [0, 0, 1, 1, 1, 1, 1, 1, 1, 0] | 4 | 600 | COMPUTED+VALIDATED |
| 43 | `vakint::PR9pD2Eps2` | PR9 with one dot on a doubled-edge line (NOT the central-dot PR9d); RustRed P10 graph; family 693719b1bc3d, powers [0, 0, 2, 1, 1, 1, 1, 1, 1, 0] | 2 | 520 | COMPUTED+VALIDATED |
| 44 | `vakint::PR9pD2Eps3` | PR9 with one dot on a doubled-edge line (NOT the central-dot PR9d); RustRed P10 graph; family 693719b1bc3d, powers [0, 0, 2, 1, 1, 1, 1, 1, 1, 0] | 3 | 520 | COMPUTED+VALIDATED |
| 45 | `vakint::PR9pD2Eps4` | PR9 with one dot on a doubled-edge line (NOT the central-dot PR9d); RustRed P10 graph; family 693719b1bc3d, powers [0, 0, 2, 1, 1, 1, 1, 1, 1, 0] | 4 | 600 | COMPUTED+VALIDATED |
| 46 | `vakint::PR10D2Eps1` | [delta^1] of hat PR10 | 1 | 520 | ACCEPTED-500 |
| 47 | `vakint::PR10D2Eps2` | PR10; FMFT PR10 = RustRed P13; family 693719b1bc3d, powers [0, 1, 0, 1, 1, 1, 1, 1, 1, 0] | 2 | 520 | ACCEPTED-500 |
| 48 | `vakint::PR10D2Eps3` | PR10; FMFT PR10 = RustRed P13; family 693719b1bc3d, powers [0, 1, 0, 1, 1, 1, 1, 1, 1, 0] | 3 | 520 | COMPUTED+VALIDATED |
| 49 | `vakint::PR10D2Eps4` | PR10; FMFT PR10 = RustRed P13; family 693719b1bc3d, powers [0, 1, 0, 1, 1, 1, 1, 1, 1, 0] | 4 | 560 | COMPUTED+VALIDATED |
| 50 | `vakint::PR15D2Eps1` | PR15; FMFT PR15 = RustRed P34; family bb95c283ed3c, powers [1, 1, 1, 1, 1, 1, 1, 1, 0, 0] | 1 | 520 | ACCEPTED-500 |
| 51 | `vakint::PR15D2Eps2` | PR15; FMFT PR15 = RustRed P34; family bb95c283ed3c, powers [1, 1, 1, 1, 1, 1, 1, 1, 0, 0] | 2 | 520 | ACCEPTED-500 |
| 52 | `vakint::PR15D2Eps3` | PR15; FMFT PR15 = RustRed P34; family bb95c283ed3c, powers [1, 1, 1, 1, 1, 1, 1, 1, 0, 0] | 3 | 520 | COMPUTED+VALIDATED |
| 53 | `vakint::PR11D2Eps2` | unit four-loop wheel (GLS I1011); FMFT PR11 = RustRed P14; family 693719b1bc3d, powers [0, 1, 1, 1, 1, 1, 1, 1, 1, 0] | 2 | 587 | COMPUTED+VALIDATED |
| 54 | `vakint::PR11D2Eps3` | unit four-loop wheel (GLS I1011); FMFT PR11 = RustRed P14; family 693719b1bc3d, powers [0, 1, 1, 1, 1, 1, 1, 1, 1, 0] | 3 | 586 | COMPUTED+VALIDATED |
| 55 | `vakint::PR11D2Eps4` | unit four-loop wheel (GLS I1011); FMFT PR11 = RustRed P14; family 693719b1bc3d, powers [0, 1, 1, 1, 1, 1, 1, 1, 1, 0] | 4 | 560 | COMPUTED+VALIDATED |
| 56 | `vakint::PR11dD2Eps1` | rim-dotted wheel (GLS I1011.1.2); FMFT PR11d = RustRed P17; family 693719b1bc3d, powers [0, 2, 1, 1, 1, 1, 1, 1, 1, 0] | 1 | 588 | COMPUTED+VALIDATED |
| 57 | `vakint::PR11dD2Eps3` | rim-dotted wheel (GLS I1011.1.2); FMFT PR11d = RustRed P17; family 693719b1bc3d, powers [0, 2, 1, 1, 1, 1, 1, 1, 1, 0] | 3 | 585 | COMPUTED+VALIDATED |
| 58 | `vakint::PR11dD2Eps4` | rim-dotted wheel (GLS I1011.1.2); FMFT PR11d = RustRed P17; family 693719b1bc3d, powers [0, 2, 1, 1, 1, 1, 1, 1, 1, 0] | 4 | 560 | COMPUTED+VALIDATED |
| 59 | `vakint::PR12D2Eps2` | prism PR12 (GLS I1022, Laporta V12); FMFT PR12 = RustRed P70; family eb225daea1dd, powers [1, 1, 1, 1, 1, 1, 1, 1, 1, 0] | 2 | 520 | COMPUTED+VALIDATED |
| 60 | `vakint::PR12D2Eps3` | prism PR12 (GLS I1022, Laporta V12); FMFT PR12 = RustRed P70; family eb225daea1dd, powers [1, 1, 1, 1, 1, 1, 1, 1, 1, 0] | 3 | 520 | COMPUTED+VALIDATED |
| 61 | `vakint::PR0D2Eps1` | non-planar K3,3 PR0 (GLS I511); FMFT PR0 = RustRed P18; family 693719b1bc3d, powers [1, 1, 1, 1, 1, 1, 1, 1, 1, 0] | 1 | 520 | COMPUTED+VALIDATED |
| 62 | `vakint::PR0D2Eps2` | non-planar K3,3 PR0 (GLS I511); FMFT PR0 = RustRed P18; family 693719b1bc3d, powers [1, 1, 1, 1, 1, 1, 1, 1, 1, 0] | 2 | 520 | COMPUTED+VALIDATED |
| 63 | `vakint::PR5D2Eps4` | PR5 graph (triangle of three unit-mass double edges = DREAM T8); FMFT PR5; family 693719b1bc3d, powers [0, 0, 1, 0, 1, 1, 1, 1, 1, 0] | 4 | 520 | COMPUTED+VALIDATED |

### Weight 7 and D=4−2ε constants (5)

| # | Vakint symbol | definition | normalisation | digits | status |
|---:|---|---|---|---|---|
| 64 | `vakint::T111bar5` | T111bar(5) in the MATAD convention of vakint matad.rs: sum_k T111bar(k) eps^k = sqrt3 (1-2eps)(1-eps) Sunset2(eps)/G(eps)^2 - 3 sqrt3/(2 eps^2), G = exp(EulerGamma eps) Gamma(1+eps), Sunset2 = -miT111, miT111 = exp(2 EulerGamma eps) * integral d^dk d^dl/pi^d [(k^2+1)(l^2+1)((k+l)^2+1)]^-1 (Euclidean, d = 4-2eps); weight-7 coefficient at eps^5 | MATAD bar of Vakint matad.rs, T111 = two-loop equal-mass sunset: T111bar(k) = ordinary Taylor coefficient [ep^k] of sqrt3 (1-2ep)(ep-1) * Gamma(1+ep)^(-2) * LoopIntegral, Euclidean measure d^dk/pi^(d/2) per loop (2 loops, d = 4-2ep), unit masses, no sign; NO factor exp(2 gamma ep) (Gamma(1+ep)^(-2) takes its place); the subtracted 3 sqrt3/(2 ep^2) only removes the double pole and does not change [ep^k] for k >= 0 | 650 | COMPUTED+VALIDATED |
| 65 | `vakint::BNbar5` | BNbar(5) in the MATAD convention of vakint matad.rs: miBN = exp(3 EulerGamma eps) Gamma(1+eps)^3 (4/eps^3 - 44/(3 eps^2) + sum_(k>=1) BNbar(k) eps^k)/((1-3eps)(2-3eps)(1-2eps)(1-eps)), miBN = exp(3 EulerGamma eps) * integral of the three-loop equal-mass banana (four unit-mass lines k1, k2, k3, k1+k2+k3; Euclidean, d^dk/pi^(d/2) per loop); weight-7 coefficient at eps^5 | MATAD bar of Vakint matad.rs, BN = three-loop equal-mass banana (4 unit-mass lines): BNbar(k) = ordinary Taylor coefficient [ep^k] of (1-ep)(1-2ep)(1-3ep)(2-3ep) * Gamma(1+ep)^(-3) * LoopIntegral, Euclidean measure d^dk/pi^(d/2) per loop (3 loops, d = 4-2ep), unit masses, no sign; NO factor exp(3 gamma ep) (Gamma(1+ep)^(-3) takes its place) | 581 | COMPUTED+VALIDATED |
| 66 | `vakint::D5bar3` | D5bar(3) in the MATAD convention of vakint matad.rs: miD5 = (D5bar(0) + eps D5bar(1) + eps^2 D5bar(2) + eps^3 D5bar(3) + ... + 2 zeta3/eps)/((1-2eps)(1-eps)), miD5 = exp(3 EulerGamma eps) * integral of the three-loop tetrahedron with five unit-mass lines and one massless line (Euclidean, d^dk/pi^(d/2) per loop, d = 4-2eps); weight-7 coefficient at eps^3 | MATAD bar of Vakint matad.rs, tetrahedron topology D5 (one massless line) / D6 (six unit-mass lines): Xbar(k) = ordinary Taylor coefficient [ep^k] (not a derivative) of (1-ep)(1-2ep) * exp(3 gamma ep) * LoopIntegral, Euclidean measure d^dk/pi^(d/2) per loop (3 loops, d = 4-2ep), unit masses, no sign, the propagators shown | 600 | COMPUTED+VALIDATED |
| 67 | `vakint::PR14ep2` | [eps^2] of the FMFT/MATAD D=4-2eps master FMFT PR14 = RustRed P31: M = (-1)^(sum a) exp(4 EulerGamma eps) * integral prod_(l=1..4) d^(4-2eps)k_l/pi^(2-eps) prod_e (q_e^2+1)^(-a_e) (Euclidean, unit mass; PR14 (ring of three one-loop bubbles + one line, GLS I1016); family bb95c283ed3c, powers [1, 0, 1, 1, 1, 1, 1, 1, 0, 0], sum a = 7); same normalisation as the published 4L coefficients of this master (P31 rows eps^-4..1) | public FMFT master normalisation: Minkowski masters M = (-1)^(sum a) exp(4 gamma ep) LoopIntegral(4-2ep, ...), Euclidean measure d^dk/pi^(d/2) per loop, unit masses; the constant is the ordinary Taylor coefficient [ep^k] | 600 | COMPUTED+VALIDATED |
| 68 | `vakint::PR14ep3` | [eps^3] of the FMFT/MATAD D=4-2eps master FMFT PR14 = RustRed P31: M = (-1)^(sum a) exp(4 EulerGamma eps) * integral prod_(l=1..4) d^(4-2eps)k_l/pi^(2-eps) prod_e (q_e^2+1)^(-a_e) (Euclidean, unit mass; PR14 (ring of three one-loop bubbles + one line, GLS I1016); family bb95c283ed3c, powers [1, 0, 1, 1, 1, 1, 1, 1, 0, 0], sum a = 7); same normalisation as the published 4L coefficients of this master (P31 rows eps^-4..1) | public FMFT master normalisation: Minkowski masters M = (-1)^(sum a) exp(4 gamma ep) LoopIntegral(4-2ep, ...), Euclidean measure d^dk/pi^(d/2) per loop, unit masses; the constant is the ordinary Taylor coefficient [ep^k] | 600 | COMPUTED+VALIDATED |

`vakint::PR12D2Eps3` is COMPUTED+VALIDATED: two-profile validation at 520 digits plus the closure-implied independent-method control of at least 421 digits, accepted by the user (decision D13, 30 October 2026).

### s6 without the four-loop pack

`vakint::s6weak` (s6 = Σ_(m≥k≥1) (−1)^(m+k)/(m⁵k)) is a `4L/constants.json` record, and Vakint loads constants only from the loaded loop packs. The three-loop rows P13, P21 and P28 at ε⁴ therefore write s6 through its definition in the Vakint built-in GPL family, s6 = π⁶/945 + `vakint::GPLReal(0,0,0,0,-1,1,1)` (ζ(6) + Li_{5,1}(−1,−1), Li_{5,1}(−1,−1) = G(0,0,0,0,−1,1; 1)), so that a `max_loop_count = 3` load evaluates them. The generator is still s6; the identity is exact and agrees with the published s6weak value to 1048 digits (PARI) and 299 digits (native Vakint).

## Constants that are not generators

| constant | expressed through | status |
|---|---|---|
| `vakint::PR5D2Eps3` | J8 jet-3 formula in log 2, pi, zeta3, zeta5, Li4/5/6(1/2), s6 (relation PR5D2EPS3_J8) | ACCEPTED-260, confirmed to 520.29 digits; re-checked to 560.8 digits |
| `vakint::PR10D2` | D2J0_PR10 (Cl4, K5Moment(1), PR7D2) | ACCEPTED |
| `vakint::PR15D2` | D2J0_PR15 (zeta3, K5Moment(1), PR7D2) | ACCEPTED |
| `vakint::PR11dep0` | closed formula of PR11d[0] (= 4L P17 eps^0 row): D2 jets, K5 moments, classical | COMPUTED+VALIDATED (closure, 544 digits vs 20k) |
| `vakint::PR4fin, PR4dfin, PR4ep1, PR4dep1` | published K5-moment rows of P6/P11 | EXACT |
| `vakint::S2, T1ep, T1ep2` | MATAD definitions in Cl2 / HI words | PROVEN / ACCEPTED |
| `vakint::BNbar4` | BNBAR4_LEVEL2: 1536 (12 Li6(1/2) + 5 s6) - MZV/level-2 products | COMPUTED+VALIDATED numerical identity (19899.7 digits) |
| `342 HPL words H(w; e^{i pi/3}), 15 Vakint GPLs (9 not kept), Li2/Li4(e^{+-i pi/3}), Li3(+-i/sqrt3)` | HSS tables / proven identities -> generators (Li3(+-i/sqrt3) numerically, LI3_I_SQRT3_V1) | EXACT except LI3 (COMPUTED) |
| `vakint::PR11dD2Eps2` | R1 (48 terms, height 10^6.28): PR11dD2Eps2 = 2/3 PR11D2Eps2 + 1/2 PR11dD2Eps1 - 4/9 PR10D2Eps1 - 2/9 PR10D2Eps2 + ... (receipt relation R1_PR11dD2Eps2) | COMPUTED+VALIDATED numerical relation (547 digits; adopted by user decision, 30 Oct 2026); GLS (c30): identical where comparable |
| `vakint::GPLImag(0,1,(-1-3^(1/2)*𝑖)/2,1)` | X3_TI3 swap to Im Li3(i/sqrt3) | COMPUTED+VALIDATED (4100 digits) |
| `vakint::GPLImag(0,1,1,(-1-3^(1/2)*𝑖)/2,1)` | X4_TI4 swap to Im Li4(i/sqrt3) | COMPUTED+VALIDATED (4100 digits) |

`4L/constants.json` keeps the records of `vakint::PR10D2`, `vakint::PR15D2`, `vakint::PR5D2Eps3` and `vakint::PR11dD2Eps2` unchanged; no published row uses them. The PR11dD2Eps2 record carries `provenance.validation.basis_v4`: it is not a basis generator because R1 expresses it.

### R1 and GLS 1609.05071 (c30)

R1 is a 48-term integer relation of height 10^6.28 among the D=2 jets PR11dD2Eps2, PR11D2Eps2, PR11dD2Eps1, PR10D2Eps1/2, PR7D2/Eps1/Eps2, PR9D2Eps1/2, PR9pD2Eps2, the Bessel moments and classical products. It was found with at most 75% of the digits (372 of 496) by eight engines, holds on the held-out digits (residual 10^−490.1) and to 547 digits with all stored digits; it is a numerical identity, not a proof. Normalised to PR11dD2Eps2, its coefficients of PR11D2Eps2 (2/3), PR11dD2Eps1 (1/2), PR10D2Eps1 (−4/9) and PR10D2Eps2 (−2/9) are identical to those of Gerlach, Laporta and Schneider, arXiv:1609.05071, relation (c30). The other coefficients are not comparable, because (c30) also contains the side-dot cat-eye jet c27 and the three-loop D5-topology jets c1, c7, which have no closed form in these generators; no coefficient differs. With the printed c1, c7, c27, (c30) reproduces PR11dD2Eps2 and R1 to 48.91 digits, the print limit.

### Fixed combinations replaced by standard constants

- Im G(0,1,−ω; 1) only occurred as √3(π³ + 27 log3 Cl2 + 81 Im G)/81 = √3 (17π³ + 9π log²3 − 432 Im Li3(i/√3))/270; it is replaced by Im Li3(i/√3) = `vakint::PolylogImag(3,3^(1/2)*𝑖/3)` (numerical identity X3, residual 10^−4102.8 at 4100 digits; GLS H3 = √3 X3/6).
- Im G(0,1,1,−ω; 1) is replaced by Im Li4(i/√3) = `vakint::PolylogImag(4,3^(1/2)*𝑖/3)` through 360 X4 = 584 Cl4 − 3π log³3 + 40π² Cl2 − 17π³ log3 − 864 Im Li4(i/√3) (numerical identity X4, 10^−4100.4 at 4100 digits).
- Kept because no single Vakint-supported standard constant matches: Re G(0,0,ω̄,−1; 1) (would be Re Li4((3+i√3)/6)), Im G(0,1,1,1,−ω; 1) (log-sine Ls5(2π/3)) and the pair Im G(0,0,0,1,ω̄; 1), Im G(0,0,0,1,−ω; 1).
- Li4(1/2), Li5(1/2) and the pair Li6(1/2), s6 are already the standard constants.

## Independence

"No rational dependency" means that integer-relation searches (lattice reduction with flatter, fplll and PARI qflll, PARI lindep, BKZ/exact SVP where the dimension allows, mpmath PSLQ and Mathematica FindIntegerNullVector on selected blocks) find no stable relation: discovery on at most 75% of the available digits (about 500 for the hard constants, 5000 for classical blocks), confirmation on the rest. The searches cover the generators and the products that occur in the coefficients.

- Generators: no stable relation in any of the 27 main blocks. Excluded heights: all 68 together 10^3.44 (500 digits); the 45 non-classical 10^6.99; the 30 D2 periods 10^11.03; the 23 classical generators 10^155.1 (5000 digits); classical products per weight at 5000 digits: weight 5 10^54.1, 6 10^25.58, 7 10^11.1.
- Products: no stable relation in any of the 487 main blocks of occurring product monomials.
- Positive controls: 16/16 product-level controls rediscovered (R1 before and after the swaps, the BNbar(4) identity at 5000 and 500 digits, the accepted J8 relation, R12/R13, planted relations); 8/10 generator-level controls (X3, X4, PR10D2, PR15D2, J8, BNbar(4)); the two missed ones have heights 10^5.44 and 10^5.59, beyond what their n = 75/83 blocks resolve, and are found in smaller blocks.
- This testing was done on the 69-generator basis v3 (which found exactly one stable relation, R1) and repeated for basis v4 with every main block finished; redundant extra engines were stopped on 31 October 2026.
- **Possible jet-3 and jet-4 analogues of R1** (PR11dD2Eps3/4 against PR11D2Eps3/4, lower jets, K5MomentTaylor(k,3/4) and weight-6/7 classical products) **are not excluded at the available precision** (about 500 digits): the blocks that could contain them exclude only heights below about 10^5.2.

## Size of the coefficients

| | coefficients | terms as previously published | basis v4 |
|---|---:|---:|---:|
| 1L | 6 | 17 | 17 |
| 2L | 13 | 342 | 109 |
| 3L | 252 | 7845 | 2277 |
| 4L | 425 | 8029 | 3080 |
| new 4L directions | 17 | 4738 | 1162 |
| total (713) | 713 | 20971 | 6645 |

The 739 rows include 26 repeated aliases (27506 → 8358 terms). The largest rows are the four-loop P14/P49/P69 at ε¹ (153 terms each).

