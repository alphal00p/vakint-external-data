# PR11dep0 numerical validation

The authoritative production builder passed **20,000 validated significant digits**, retaining **20,008 stored digits**. The complete compressed proof passed both producer and independent isolated Python-standard-library verifier runs (exit zero in 45.04 and 45.29 seconds). All scientific and portable acceptance gates are complete. Activation in Vakint is performed by the coordinated external-data staging and release.

The period begins `-2.90648628864311264181920643511348635967821765354622190230928344425351874580728…`. Its published total absolute error, including decimal rounding, is bounded by `3.3489120584697589184106699319561242E-20008`, strictly below `abs(center)*10^-20000`.

## Physical definition and method

This is the finite unit-mass FMFT coefficient of `vakint::PR11d`, canonical P17, family `693719b1bc3d2f1d4d32c9312df66ced667a542591a2ada6f6498844fc5d0de1`, ordered powers `[0,2,1,1,1,1,1,1,1,0]`. The independently proved generic target is `B30-B36-epsilon*B37-B38`.

The computation lifts the exact regulator-dependent connections to six epsilon jets before infinity normalization. It uses complete asymptotic source inventories, exact Gamma/primitive combinations, interval matching, a certified Frobenius start, bounded Taylor transport, and an authenticated zero-sector endpoint adjoint. All source, truncation and rounding radii survive the calculation. The finite-epsilon fitting method used for the old 200-digit result was replaced because its 20k scaling was impractical.

A separate all-massive graph/UV-forest argument proves the raw 42-state basis has no powers below epsilon^-4. A projective-parametric certificate proves the physical P17 target is holomorphic near epsilon=0. Every computed apparent pole and imaginary enclosure contains zero before the exact physical vanishing is used. Native and FMFT finite coefficients coincide because the target has no poles; the Minkowski sign is -1 and is applied once.

## Independent production profiles

| Profile | X8 halfsteps | Workers | Native ordinary time | Final relative-radius digits | Unique stored cell |
|---|---:|---:|---:|---:|---:|
| A | 12 | 8 | 4,878.96 s | 20,072 | 20,000 digits |
| B | 12 | 8 | 5,026.62 s | 20,368 | 20,008 digits |

A and B use different source precisions and upstream four-loop continuation partitions, with the same authenticated X8 equations and halfstep mesh. Each complete finite box independently meets the 20k error gate. Their full complex interval difference passes 20,072 relative decimal digits, both determine the same unique nearest 20,000-digit decimal, and the entire B finite complex box is contained in A. All six Laurent orders and both components were independently replayed by exact integer interval convolution and Fraction rounding checks.

Independent PR4/PR4d Bessel comparisons pass all twelve coefficients in each upstream four-loop profile at 20,000 digits. The source hierarchy also includes a separately bounded sunset/HPL comparison and independent native-flow versus HPL/API three-loop comparisons.

## Scope of independent evidence

The independent exact IBP replay proves all three X8 target identities and 21 of the 42 differential rows; the remaining 21 coupled rows retain their explicit authenticated external-Kira trust boundary. Full independent differential-equation validation is not claimed.

The original AMFlow development oracle uses an independent ordinary solver with shared exact equations, starting centers and endpoint formula. Its refinements agree by 125 observed complex digits, and the final period agrees with its real central value by 154 observed digits. This is a practical solver crosscheck, not a 20,000-digit AMFlow computation. Mathematica is never required by Vakint's build, required user tests or runtime.

## Frozen artifacts and delivery

The local accepted payload, validation and provenance are in `accepted20000/sealed-production-v1`. Important hashes:

- Payload: `b58a3494c327cf858ca12da7abad2cef2bcba7f1f308e496be5fa8916b264f94`
- Validation: `423d61d3334c8335edcddab4d5356522b355cd9a6961fde64e7a4d4267ecf3ca`
- Provenance manifest: `333888a1f764e9c9932de0bed909c284d536fc39c78d86d8218b834441c70843`
- Standalone verifier: `1cf290b886aeff1a80c34a39daf64f16fb647c89f5e22cc5610126f1bbf31ce7`
- Authoritative builder: `6b1700f5f7cb8093de47622b75951e43a5dc5c1b087e28474062fcb4cd9ce9d1`
- Scientific read-set: `5c737067b24ef4c65a739ff5c9da558a63349a49e23b6799da824a27fe889aa8`

The approved read-set contains 1,390 original scientific inputs, 2,990,004,489 decoded bytes, and 6,365 checked reference edges. Full historical catalogs remain authenticated bytes; only their explicitly selected current dependencies are mathematical inputs. One later-edited application source is materialized from a byte-identical frozen preimage, preserving its original logical path and old authenticated hash without modifying active development.

Proof objects are deterministic bounded single-member gzip streams outside runtime loop packs. The portable verifier uses only the Python standard library, authenticates the exact current read-set and separately admitted physical executions, replays both final interval convolutions, and checks the unique 20,008-digit cell and strict published error. No original developer filesystem fallback, network, native transport or Mathematica is used by that verifier.

Only PR11dep0 and its direct epsilon-zero aliases gain this finite source capability. Other Laurent coefficients retain their individual validated limits. The final proof-index SHA256 is `24d191de0c46d6352fa097980a5f8532a89b6b1c25dda3781202677ce465203a`. The actual standalone verifier accepted all 1,397 logical files and both exact interval convolutions in 45.04 seconds. The bundle contains 2,996,531,972 decoded bytes and 1,180,191,144 stored bytes, plus its 694,892-byte index. The independent final archive admission is `addd4165d398ec2afda48e139bdfd72a674cb157ad1defcb782708ab9d996a0d`. Final delivery metadata is `334cae19c5e1d3061011acb2d00c516cec5b6b41980424e4c1d0de21adf8d666`. Coordinated external publication and public API integration checks remain the release owner's responsibility.
