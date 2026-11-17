# l6: complete level-6 (sixth-root-of-unity) basis, tests of the MATAD bars and of the lifted 4L constants

Opus 5.5 execution agent, 2026-11-10/11.  Directory `basis-b/v5lpar/rstar/periods/l6/` ($L6).  Files: `GENERATORS.md` (proposed generator set),
`DICTIONARY.md` (opaque name -> traditional formula), `LIFTED-DEFINITIONS.md` (standard definitions of the non-reducing constants),
`RELATIONS.md` (the same relations in the G-word basis), `out/` (all JSON results), `tools/` (code), `PROGRESS.md` (log, PIDs).

## 0. Headlines

1. **Dimension count corrected.** With powers of i*pi the level-6 (MT(Z[w][1/6]), Deligne-Goncharov) graded dimensions are
   1, 3, 8, 21, 55, 144, 377, 987 (weights 0..7), real/imaginary 1/0, 2/1, 5/3, 12/9, 30/25, 76/68, 195/182, 504/483. The brief's
   1, 2, 5, 13, 34, 89 is the count WITHOUT the i*pi factor. New primitives (Re/Im): 2/1, 1/1, 3/2, 5/5, 13/11, 25/25, 62/58 (w1..7);
   a depth-r primitive of weight n is real-type iff n - r is even (parity theorem).
2. **Complete basis through weight 6, the Deligne-Goncharov bound is attained by MPLs at sixth roots** at every weight and parity
   (never more independent elements than the bound), certified independent (no relation with coefficients < 10^h):
   h = 2389/3983 (w2), 995/1327 (w3), 397/477 (w4), 155/174 (w5), 57.7/62.2 (w6) [Re/Im, 11950 digits].
3. **basis-v4 spans only part of it**: its classical monomials span 3/3, 7/8, 15/21, 32/55, 65/144, 124/377 of the weight 1..6 pieces
   (exact linear algebra on the decompositions; all v4 monomials independent).
4. **Every MATAD bar of weight <= 6 and every basis-v4 constant has an explicit verified formula** in a TRADITIONAL basis (zeta, ln 2, ln 3, pi,
   Li_n(x) at x = 1/2, -1/2, 1/3, -1/3, 2/3, 3/4, 8/9, -1/8, Cl_n(pi/3), Im Li_n(i/sqrt3), log-sines Ls_j^(k)(pi/3), Ls_j^(k)(2pi/3), and multiple
   polylogarithms Li_{a1..ar}(x1..xr) at sixth roots only where unavoidable). Each reproduces the stored 20000-digit value to its full claimed
   digits (agreement 20003.9-20008.7 d vs 19998-20000 claimed).
5. **Two lifted weight-7 constants become exact:**
   - **T111bar5** lies in the cube-root sub-algebra (letters {0, -w}); in traditional form a 15-term combination of ln3, pi, zeta(3), zeta(5),
     Cl2, Cl4, Im Li3/4(i/sqrt3) and Ls_5^(0), Ls_6^(0), Ls_7^(0) at 2pi/3 (height 10^4.48), found on 1500 d by flatter AND fplll, reproduces PREC's
     2F1 value (19998 d [R]) to 20003.4 d.  NEW (not in INDEP; INDEP had only excluded level 2).
   - **BNbar5**: INDEP's level-2 identity confirmed with an independent basis and evaluator: 14 terms, height 10^6.59, agrees 19712.3 d (claim 19706 [R]).
6. **D5bar3 (weight 7) is undecided**: it is not in the cube-root or level-2 algebras (D5bar(1,2) are not even in their product algebra); a decisive
   test needs the complete weight-7 real space (504 dims) at about 12000 STRICT digits (it has 5060 [2I], 9924 estimated). Section 2.3.
7. **Lifted 4L constants (Bessel moments, D=2 jets, PR14ep*) do not reduce**: none is in the complete level-6 space of weight <= 4 (all 46,
   h = 132 Bessel, 54-60 jets at >= 5000 d, 24-29 jets at 2350-2800 d) nor, where tested, of weight <= 5 (h = 47.5 Bessel); family (joint) tests:
   section 3.  **No 4L coefficient moves from S* to S** (T111bar5 and BNbar5 occur only in four eps^1 coefficients that also contain Bessel and
   D=2 constants).

## 1. Basis (task 1, item (a))

- **Evaluator** (`tools/g6.py`, `g6par.py`): G(a_1..a_n;1) with letters in Z[w] (all sixth roots, 0, and any Z[w] element such as 2, -3, 1-2w for
  Li_n(1/2), Li_n(-1/3), Li_n(i/sqrt3)); Hoelder convolution p = 2 (Borwein-Bradley-Broadhurst-Lisonek) and exact fixed-point Z[w] arithmetic
  (every series converges like 2^-j because every nonzero Z[w] element has modulus >= 1). Cost: weight-6 word ~0.5 s at 3000 d, ~5 s at 10000 d.
- **Cross-checks of the evaluator:** GiNaC 1.8.10 ginsh G(): 120 random words, weights 1-6, all letters: >= 95.2 d at Digits=90
  (`out/xcheck-ginac-seed{1,2}.json`); PREC's rigorous Symbolica HPL words H(w; e^{i pi/3}), 183 words, weights 1-6: >= 20008.3 d at 20000 d
  (`out/xcheck-prec-hpl-20000.json`); classical polylogs vs PARI `polylog` and mpmath (agreement to the working precision; PARI values are what
  the full-digit checks of the traditional basis use); log-sine G-forms vs mpmath quadrature: 60 d (imaginary parts vanish to 10^-102).
- **Construction** (`tools/build_basis.py`): per weight and parity, lattice of all product monomials of lower-weight primitives plus candidate
  G-words of the parity-allowed depths; independent candidates chosen greedily (relations verified to 12000 d); adaptive enlargement until the
  bound is reached. Result `out/basis-w6.json` (94 primitives: w1 ln2, ln3, pi; w2-6 Re/Im 1/1, 3/2, 5/5, 13/11, 25/25).
  Values: 12000 d (`out/basis-w6-words-12000.jsonl`), re-evaluated at 20100 d for every full-digit check.
- **Sub-algebras** (`tools/build_hpl.py`): cube-root A3 (letters {0,-w}; dims 2^n, Re = Im = 2^(n-1), to w7 at 20100 d, certified h = 310 at
  w7), level 2 (Euler sums, Fibonacci dims, 21 at w7, to w7 at 19800 d, certified h = 937/1515), unramified level 6 ({0, wbar}: Fibonacci),
  vakint's HPL-at-w algebra (letters {0, w^2, wbar}: Re = Im = dim V_{n-1} through w5).
- **Sanity check, basis-v4 generators in the basis** (`out/basis-w6-v4check-*.json`): all of cl2, z3, ImLi3, cl4, ImLi4, Li4h, ReG4, z5, Li5h,
  ImG5a/b/c, s6, Li6h (and Re Li3(i/sqrt3), Re Li4(i/sqrt3), Im G(0,1,-w), Im G(0,1,1,-w)) found (3000/5000 d), re-found blind by fplll with
  identical vectors, and reproduce the 20000-d values (20004-20007 d, `out/basis-w6*-verify-20100.json`).
- Lattice codes: flatter (all searches), fplll 5.5.0 (blind re-finds), exclusion bounds from exact Gram-Schmidt (INDEP method). Symbolica's
  PSLQ was not used: flatter was fast enough everywhere (largest lattices N = 344 at 8000 d: 12.5 min); Symbolica enters through PREC's
  20000-d HPL values used as the independent evaluator check.

## 2. MATAD constants (task 2)

### 2.1 Relations (all: found by flatter, re-found blind by fplll, full-digit check; heights in the TRADITIONAL basis, G-basis in brackets)

| constant | weight/parity | terms | height | found on | full check (agree / claimed) |
|---|---|---:|---:|---:|---|
| D5bar1 | 5 Re | 18 [14] | 10^4.49 [10^5.56] | 5000 [3000] | 20008.7 / 19998 |
| D6bar1 | 5 Re | 35 [20] | 10^5.95 [10^6.74] | 5000 [3000] | 20008.4 / 19998 |
| D5bar2 | 6 Re | 112 [72] | 10^13.16 [10^13.73] | 5000 | 20008.0 / 19998 |
| D6bar2 | 6 Re | 119 [80] | 10^13.89 [10^13.91] | 5000 | 20008.0 / 19998 |
| T111bar4 | 6 Im | 12 [31] | 10^3.33 [10^9.27] | 5000 | 20003.9 / 19998 |
| T111bar5 | 7 Im (A3) | 15 [33] | 10^4.48 [10^7.12] | 1500 | 20003.4 / 19998 [R] |
| BNbar5 | 7 Re (level 2) | 14 [17] | 10^6.59 [10^6.5] | 1500 | 19712.3 / 19706 [R] |

Formulas: `DICTIONARY.md`.  Excess over the fit: >= 14900 digits everywhere (bar: 40).  D5bar1/2, D6bar1/2, T111bar4 are by construction
level-6 (vakint's matad.rs expansions in HPLs at w); the content is the explicit reduction to traditional constants. D5bar1/D6bar1 need new
weight-5 generators beyond basis-v4 (exact: not in the v4 span).  T111bar(0..5) and D3bar/D4bar/DMbar(0..2), D5bar(0), BNbar(1) lie in the cube-root
algebra; DNbar(0..2) in cube-root x level 2; D5bar(1,2), D6bar(0..2) need genuinely mixed sixth-root MPLs (not in that product algebra, h = 54 at w5,
25 at w6, 2500 d).

### 2.2 Exclusion bounds (no relation with max|coef| < 10^h)
- D5bar3 vs the complete level-6 space of weight <= 4 / <= 5 (5052 d): h = 54.3 / 17.7 (not meaningful for a weight-7 number; recorded only).
- T111bar5, BNbar5 vs W<=4: h = 132 (superseded by the relations).

### 2.3 Weight 7: what a decisive D5bar3 test needs
Heights grow ~10^8 per weight (D5bar1 10^5.6, D5bar2 10^13.7, k 14 -> 72), so D5bar3 is expected at height >= 10^20 with ~250 terms. Against the
complete weight-7 real space (504 elements, plus a weight-7 basis that does not yet exist: 62 new real primitives) detection needs
D ~ N (log10 H + 2) ~ 505 x 22 ~ 11000 digits, i.e. **about 12000 strict digits of D5bar3 and of the basis**; current claims 5060 [2I] (strict) /
9924 (release, estimated) are not enough. A cheaper ansatz (vakint's HPL-at-w algebra, Re dim at w7 ~ 377 if the pattern dim = dim V_{n-1}
holds) would need ~8500 digits. The cube-root x level-2 product algebra was started for D5bar3 and stopped: D5bar(1,2) are already outside it.

## 3. 4L S* coefficients and lifted constants (task 3)

**Family (joint) tests** (`out/basis-w6-lifted-family-*-w5.json`): all lifted monomials of a family that occur in the 92 S* forms
(c, c pi^2, c zeta3, c pi^4, sqrt3 c) together with the complete level-6 space W<=5 (232 elements). No relation in any family, so no rational
combination of them (in particular none of the 92 lifted parts X of the S* coefficients) lies in the level-6 space of weight <= 5 below height 10^h:

| family | members | N | digits | h |
|---|---:|---:|---:|---:|
| Bessel | 22 | 254 | 11975 | 42.89 |
| D2hi | 22 | 254 | 5350 | 16.9 |
| D2lo | 7 | 239 | 2342 | 5.74 |
| W7 | 6 | 238 | 5052 | 17.21 |

(Bessel = K5Moment, K5LogMoment, K5MomentTaylor; D2hi = PR7/PR9/PR9p/PR10/PR11/PR11d jets (>= 5350 d); D2lo = PR0/PR12/PR15 jets (2342-2798 d,
h only 5.7: weak); W7 = T111bar5, BNbar5, D5bar3, PR14ep2/3, PR5D2Eps4 at D5bar3's strict 5052 d.)  These bounds extend INDEP's C4 (Bessel vs
classical weight <= 5, h 129) to the complete level-6 space; they are weaker per element because the ansatz is ~2x larger and the basis has 12000 d.

Single constants vs the complete level-6 space W<=4 (88 elements: weights 0-4, Re and sqrt3-normalised Im): no relation for any of the 46
lifted constants; h = 132.1 (Bessel moments and jets, T111bar5, BNbar5; 11975 d), 54.3 (D5bar3, PR14ep2/3, PR5D2Eps4; 5052 d strict), 57.7-59.8
(PR7/PR9/PR9p/PR10/PR11/PR11d jets; 5350-5535 d), 23.9-29.0 (PR0/PR12/PR15 jets; 2342-2798 d).  vs W<=5 (232 elements, 11975 d): h = 47.4-47.5 for
the eleven tested (BNbar5, K5LogMoment(1,3), K5MomentTaylor(1|3, 2..4), K5Moment(1)); the remaining singles were superseded by the family tests.
**Which reduce:** T111bar5 (A3) and BNbar5 (level 2), both exact now. **Which stay new:** all Bessel moments and jets, all D=2 periods and jets,
PR14ep2/3, PR5D2Eps4 (within the tested spans), D5bar3 (undecided, 2.3).  **S* -> S:** none (T111bar5/BNbar5 occur only in P14|1, P49|1, P69|1,
P70|1, which also contain K5* and PR*D2* constants); after the change those four coefficients carry two fewer lifted constants.

## 4. Proposed generator set and dictionary (task 4 + user request)

`GENERATORS.md`: for every weight 2-6 and parity, generators chosen by exact exchange (Steinitz) in the preference order zeta/ln/pi <
classical Li_n / Cl_n / Im Li_n(i/sqrt3) < log-sine < depth-2 MPL < deeper MPL (standard notation Li_{a1..ar}(x1..xr), x_i sixth roots).
Counts (classical depth 1 incl. zeta/ln/pi | log-sine | depth >= 2):

| weight | Re | Im |
|---|---|---|
| 2 | 1 / 0 / 0 (Li2(-1/2)) | 1 / 0 / 0 (Cl2(pi/3)) |
| 3 | 3 / 0 / 0 (zeta3, Li3(-1/2), Li3(1/3)) | 1 / 0 / 1 (Im Li3(i/sqrt3), Im Li_{2,1}(w,-1)) |
| 4 | 5 / 0 / 0 (Li4 at 1/2, -1/2, 1/3, -1/3, 2/3) | 2 / 0 / 3 |
| 5 | 8 / 0 / 5 | 1 / 2 / 8 |
| 6 | 8 / 1 / 16 | 2 / 2 / 21 |

Depth >= 2 is unavoidable from weight 4 Im on (the parity theorem forces depth-3 objects there); classical polylogs at the S-unit arguments
cover all real primitives through weight 4 and 8 of 13 / 25 at weights 5 / 6. In the cube-root algebra (T111 family) the generalised log-sines
at 2pi/3 are the natural generators (Davydychev-Kalmykov), and T111bar4/T111bar5 need only Ls_j^(0)(2pi/3) beyond depth-1 constants.

(c) Lattice quality: the traditional basis is certified independent (h = 999/1666, 416/555, 165/199, 63.5/71.4, 22.1/24.0 at 5000 d, w2..6;
per digit the same as the G-basis) and re-finds every target with heights equal or better except: ReG4 (10^0 -> 10^3.64, it was itself a G-basis
element), s6 (10^3.54 -> 10^4.74), and D5bar2/D6bar2 (similar height, 112/119 instead of 72/80 terms). Evaluation: zeta, Li_n(x) (PARI
`polylog`, mpmath `polylog`), Cl_n (mpmath `clsin`), Ls (mpmath `quad` of the definition; exact G-form in `tools/trad.py`), MPLs (Symbolica GPL
evaluator as already used by vakint for GPLReal/GPLImag, GiNaC `G`, `tools/g6.py`) - all at arbitrary precision; every full-digit check used
PARI/g6 values at 20100 d.

**What it changes in the tables:** the level-6 sector can be stated without opaque names: D5bar1/2, D6bar1/2, T111bar4 (S already) get
explicit traditional formulas; T111bar5 and BNbar5 become S-type constants (exact formulas, evaluable at any precision) - but no coefficient
changes status S* -> S (section 3). D5bar3, the Bessel moments and the D=2 jets keep their (now explicit, `LIFTED-DEFINITIONS.md`) integral
definitions.

## 5. Caveats
- All relations are numerical identities passing the bar (>= 40 digits beyond the fit, blind re-find by fplll), not proofs.
- Basis completeness rests on the Deligne-Goncharov upper bound (theorem) plus numerically certified independence (h above).
- fplll blind re-find of every traditional formula (23 at w<=6, T111bar5, BNbar5): identical vectors (out/trad-dict-*-fplll.json).
