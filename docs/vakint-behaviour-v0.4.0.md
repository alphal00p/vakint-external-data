# Vakint behaviour with release v0.4.0

Release v0.4.0 needs Vakint from gammaloop `p_integral` {{TO FILL FROM pins: pin.vakint}} or later (README, "v0.4.0").
That build differs from earlier gammaloop `p_integral` builds in the following ways. None of them is a change of the
data in this repository; the numbers are gammaloop pull requests.

1. Dot-power opening (#261): vakint now opens powers of dot products in one pass by default. Results have the same value
   as before, but dummy index labels can differ from earlier versions (in 563 of 3,000 random test numerators), so the
   claim that dummies keep their old order does not hold in general. Set `VAKINT_DOT_CONVERSION=fast` to get the
   previous output byte for byte.
2. Vocabulary and master-metadata caches (#249): the change was applied in part, because about two thirds of it were
   already on gammaloop's `p_integral` branch. MATAD bar symbols are not created in advance: doing so would shift symbol
   ids, which changes the labelling of retained masters in one three-loop test and the order of
   `Vakint::constant_symbols()`. Two duplicated test-fixture fields were dropped, and one test symbol was added to the
   display-form list.
3. UV child boundary routing (#253): the two tests that assert a reduced epsilon depth for pole-only callers
   (`epsilon_depth_matches_pole_and_finite_prescriptions`, `epsilon_depth_ignores_empty_muv_identity`) are not included.
4. Pole-only epsilon depth (#253): the reduced epsilon depth for pole-only callers is not included, because it gave a
   wrong PolePart integrand value. Only the UV child boundary routing fix of that pull request is in; the title of the
   merged commit ("Fix UV child boundary routing and pole-only epsilon depth") still names both. As a consequence, the
   new massive-vacuum counterterm route of #252 (`massive_vacuum_counterterm`) refuses at four loops until a corrected
   depth change lands.
