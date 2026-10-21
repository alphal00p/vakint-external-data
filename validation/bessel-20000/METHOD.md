# PR4 / PR4d primitive periods from Bessel moments

This development calculation evaluates independently defined supporting moments

\[
B_k=\int_0^\infty r^kK_0(r)^5\,dr,\qquad
J_k=3\int_0^\infty r^k\log(re^\gamma/2)K_0(r)^5\,dr,
\quad k=1,3.
\]

The exact dimension shift, routing and normalization are imported unchanged from
an authenticated producer receipt. No PSLQ relation or assumed master decimal
value enters the calculation. All production arithmetic is FLINT/Arb ball
arithmetic at 20,180 or 20,260 decimal working digits.

## Near zero: integrate logarithms analytically

For `r=a sqrt(t)`, write

\[
K_0(a\sqrt t)=A(t)-\tfrac12\log(t)I(t),\quad
I(t)=\sum_{n\ge0}\frac{(a^2t/4)^n}{(n!)^2},\quad
A(t)=\sum_{n\ge0}(H_n-L)\frac{(a^2t/4)^n}{(n!)^2},
\quad L=\log(a/2)+\gamma.
\]

Set `P_j=A^(5-j)I^j`. The contribution from `0..a` is a finite sum over `j=0..5`
of exact log-moment sums. Each coefficient `p_(j,n)` contributes

\[
\frac{a^{k+1}}2 {5\choose j}\frac{j!}{2^j}
\frac{p_{j,n}}{(n+(k+1)/2)^{j+1}}
\]

to `B_k`, and three times that expression multiplied by
`L-(j+1)/(2(n+(k+1)/2))` to `J_k`.

Only coefficients below `N` are computed. Crucially, the truncation bound covers
all omitted coefficients of the full product `P_j`, rather than merely the
omitted input-series coefficients. On `|t|=R>1`, put `x=a sqrt(R)`. Positivity of
the coefficient majorants and `H_n<=n` give

\[
|I(t)|\le I_0(x)=M_I,\quad
|A(t)|\le |L|I_0(x)+\tfrac{x}{2}I_1(x)=M_A.
\]

Cauchy's estimate therefore bounds the sum of absolute omitted `P_j`
coefficients by
`M_A^(5-j) M_I^j R^(-N)/(1-1/R)`. The integration denominators are bounded below
by their value at `n=N`. This produces a separate absolute remainder ball for
each moment and log moment.

## Finite intervals: scaled Taylor integration

Cover the remainder with rational intervals `r=a(1+h q)`, `-1<=q<=1`.
The production profiles use `h=1/5`, apart from the first independent validation
interval, which uses `h=1/4`.

The coefficients `c_n` of `K_0(a(1+h q))` start with
`c_0=K_0(a)` and `c_1=-a h K_1(a)`. Bessel's differential equation gives

\[
(n+2)(n+1)c_{n+2}=-h(n+1)(2n+1)c_{n+1}
-h^2(n^2-a^2)c_n+2a^2h^3c_{n-1}+a^2h^4c_{n-2},
\]

where negative-index terms are absent. Native polynomial multiplication forms
the fifth power and its logarithmic product. Integration over the symmetric
interval uses only the even Taylor coefficients, with weight `2/(n+1)`.

For the tail, use a complex circle `|h q|=rho=9/10`. It remains in `Re(r)>0`.
The standard integral representation of `K_0` implies
`|K_0(r)|<=K_0(Re(r))<=K_0(a(1-rho))`. Also

\[
|\log(r)+\gamma-\log2|
\le\max_{u\in\{a(1-\rho),a(1+\rho)\}}
|\log u+\gamma-\log2|+\pi/2.
\]

These bounds give a common circle majorant `M` for all four integrands.
The integrated remainder after order `N-1` is at most
`2 a h M (h/rho)^N/(1-h/rho)`. Every interval chooses `N` explicitly to make this
less than `10^(-20012)`. Arb separately propagates coefficient-rounding and seed
uncertainties. No high-order coefficient is assumed to be zero.

## Infinite tail

For positive `r`, `K_0(r)<sqrt(pi/(2r))exp(-r)`. For `r>=1`,
`|log(r exp(gamma)/2)|<=r`. Thus, for `R>=1`, all four omitted tails are bounded
by

\[
3(\pi/2)^{5/2}
\frac{R^{3/2}e^{-5R}}{5-3/(2R)}.
\]

The final rational endpoint exceeds `(20000+40) log(10)/5`.

## Independence and validation

The primary partition starts at `a=1` and has endpoints `(3/2)^n`.
The validation partition starts at `a=3/4`, first ends at `5/4`, and then has
endpoints `(5/4)(3/2)^n`. It uses 80 extra decimal guard digits. Each finite
interval is separately certified and the two assembled moment balls must
intersect and round to the same 20,000 significant digits.

All 46 distinct Taylor-anchor `K_0`, `K_1` pairs, plus EulerGamma, pi and
zeta(2)..zeta(5), are independently recomputed using Mathematica at 20,120
digits. The first 24 pairs use Mathematica's built-in BesselK. For the other
22 pairs an independent Mathematica implementation sums the entire
Frobenius series and its derivative, with `2r/log(10)+100` extra working
digits and a factorial-tail target beyond the requested accuracy. This
avoids a slow built-in algorithm at larger arguments. The original
built-in results and both versioned oracle sources are preserved.
Agreement is required beyond 20,080 digits. The Arb side of this comparison
also adds `2r/log(10)+150` guard digits, since its own BesselK cancellation
can otherwise return a wide enclosure even when the central values agree.
This is a development-only oracle and is not imported by Vakint.

The 200-digit moments are additionally compared against the immutable producer
receipt obtained with two Mathematica quadrature representations and two
working precisions. The current implementation reproduces these digits.

## Exact conversion to four-dimensional master coefficients

The producer receipt supplies rational functions `g_(i,1)(eps)`,
`g_(i,3)(eps)`, and `b_i(eps)`, for outputs PR4 and PR4d. The moment term is

\[
-16\frac{e^{\gamma\epsilon}}{\Gamma(1-\epsilon)}
[g_{i,1}(\epsilon)\kappa_1(\epsilon)
+g_{i,3}(\epsilon)\kappa_3(\epsilon)],
\]

where `kappa_k(0)=B_k`, `kappa'_k(0)=J_k`; the displayed prefactor has zero
linear epsilon coefficient. The lower term is `b_i(eps) T_1(eps)^4`, with

\[
T_1(\epsilon)^4=\epsilon^{-4}(1-\epsilon)^{-4}
\exp\left(4\sum_{n\ge2}\frac{(-1)^n\zeta(n)}n\epsilon^n\right).
\]

All rational functions are parsed with integer/rational Arb arithmetic; Python
binary floating point never enters this reconstruction. The finite and first
positive-epsilon coefficients follow by series extraction. Their 1,000-digit
pilot values reproduce the original finite and epsilon-one table values.

No new dimension-shift identity, master normalization, source-data precision, or
symbolic closed form is asserted by this method. The final release payload is
limited to the digits actually certified and cross-validated.
