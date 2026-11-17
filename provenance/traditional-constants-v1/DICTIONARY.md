# Dictionary: vakint opaque names -> traditional level-6 constants (tools/render_trad.py)

Notation as in GENERATORS.md (w = e^{i pi/3}; Li_{a..}(x..) = sum_{k1>..>kr>=1} prod x_i^{k_i}/k_i^{a_i}; [Re -Li..] means -Re Li..; Ls_j^(k)(t) = -int_0^t phi^k ln^{j-1-k}|2 sin(phi/2)| dphi). Every formula was found by lattice reduction on 5000 (w<=6) / 1500 (w7) digits, re-found blind by fplll with identical vectors (all entries), and reproduces the stored value to its FULL claimed digits (generators re-evaluated at 20100 d: PARI polylog for Li_n(x), g6 G-functions for the rest). vakint conventions: G5c = 200 ImG5b + 81 ImG5c; GPLReal/GPLImag(a..;1) = Re/Im G(a..;1); s6 = vakint::s6 (= Li_{5,1}(-1,-1) + zeta(6), PARI convention).

## basis-v4 generators and MATAD bars (weights 2-6)

- **cl2** = + [Cl2(pi/3)=Im Li2(w)]
  (2 terms, height 10^0.0; full check: agree 20004.3 d vs claimed 20000)

- **z3** = + [zeta(3)]
  (2 terms, height 10^0.0; full check: agree 20004.8 d vs claimed 20000)

- **ReLi3** = - 1/48 [ln3]^3 + 1/48 [ln3] [pi]^2 - 13/48 [zeta(3)] + 1/4 [Li3(1/3)]
  (5 terms, height 10^1.68; full check: agree 20006.3 d vs claimed 20000)

- **ImLi3** = + [Im Li3(i/sqrt3)]
  (2 terms, height 10^0.0; full check: agree 20005.9 d vs claimed 20000)

- **ImG3** = + 1/30 [ln3]^2 [pi] - 1/3 [ln3] [Cl2(pi/3)=Im Li2(w)] + 41/810 [pi]^3 - 8/5 [Im Li3(i/sqrt3)]
  (5 terms, height 10^2.64; full check: agree 20005.9 d vs claimed 20000)

- **ReLi4** = + 1/16 [Li4(-1/3)]
  (2 terms, height 10^1.2; full check: agree 20004.6 d vs claimed 20000)

- **Li4h** = + [Li4(1/2)]
  (2 terms, height 10^0.0; full check: agree 20005.2 d vs claimed 20000)

- **ReG4** = - 1/27 [ln2]^4 + 1/27 [ln2]^2 [pi]^2 - 7/9 [ln2] [zeta(3)] + 1/96 [ln3]^4 - 1/48 [ln3]^2 [pi]^2 + 119/12960 [pi]^4 - 8/9 [Li4(1/2)] + 1/2 [Li4(1/3)] - 1/4 [Li4(-1/3)]
  (10 terms, height 10^3.64; full check: agree 20006.5 d vs claimed 20000)

- **cl4** = + [Cl4(pi/3)=Im Li4(w)]
  (2 terms, height 10^0.0; full check: agree 20005.8 d vs claimed 20000)

- **ImLi4** = + [Im Li4(i/sqrt3)]
  (2 terms, height 10^0.0; full check: agree 20006.1 d vs claimed 20000)

- **ImG4** = - 41/1620 [ln3] [pi]^3 - 2/5 [ln3] [Im Li3(i/sqrt3)] + 1/9 [pi]^2 [Cl2(pi/3)=Im Li2(w)] - 13/108 [pi] [zeta(3)] + 73/45 [Cl4(pi/3)=Im Li4(w)] - 12/5 [Im Li4(i/sqrt3)]
  (7 terms, height 10^3.11; full check: agree 20005.7 d vs claimed 20000)

- **z5** = + [zeta(5)]
  (2 terms, height 10^0.0; full check: agree 20004.5 d vs claimed 20000)

- **Li5h** = + [Li5(1/2)]
  (2 terms, height 10^0.0; full check: agree 20005.7 d vs claimed 20000)

- **D5bar1** = - 4/3 [ln2]^4 [ln3] + 4/3 [ln2]^2 [ln3] [pi]^2 - 14 [ln2]^2 [zeta(3)] - 1/15 [ln3]^5 + 2/9 [ln3]^3 [pi]^2 + 4/15 [ln3]^2 [pi] [Cl2(pi/3)=Im Li2(w)] + 29/45 [ln3] [pi]^4 - 32 [ln3] [Li4(1/2)] + 68/135 [pi]^3 [Cl2(pi/3)=Im Li2(w)] + 7/54 [pi]^2 [zeta(3)] + 16/3 [pi] [Cl4(pi/3)=Im Li4(w)] - 28 [Li2(-1/2)] [zeta(3)] - 64/5 [Cl2(pi/3)=Im Li2(w)] [Im Li3(i/sqrt3)] - 2798/81 [zeta(5)] + 16 [Li5(1/3)] - 8 [Li5(-1/3)] - 32 [Re -Li_{3,1,1}(-1,1,w)]
  (18 terms, height 10^4.49; full check: agree 20008.7 d vs claimed 19998)

- **D6bar1** = + 34/15 [ln2]^5 - 92/21 [ln2]^4 [ln3] + 48/7 [ln2]^3 [ln3]^2 - 22/63 [ln2]^3 [pi]^2 - 24/7 [ln2]^2 [ln3]^3 - 16/21 [ln2]^2 [ln3] [pi]^2 + 26 [ln2]^2 [zeta(3)] + 4/7 [ln2] [ln3]^4 + 119/90 [ln2] [pi]^4 - 20 [ln2] [Cl2(pi/3)=Im Li2(w)]^2 - 61/420 [ln3]^5 + 53/126 [ln3]^3 [pi]^2 + 1/5 [ln3]^2 [pi] [Cl2(pi/3)=Im Li2(w)] - 13/2 [ln3]^2 [zeta(3)] - 149/945 [ln3] [pi]^4 - 4 [ln3] [Cl2(pi/3)=Im Li2(w)]^2 + 416/7 [ln3] [Li4(1/2)] + 52/45 [pi]^3 [Cl2(pi/3)=Im Li2(w)] - 307/378 [pi]^2 [zeta(3)] - 208/21 [pi] [Cl4(pi/3)=Im Li4(w)] + 52 [Li2(-1/2)] [zeta(3)] - 48/5 [Cl2(pi/3)=Im Li2(w)] [Im Li3(i/sqrt3)] - 24 [Cl2(pi/3)=Im Li2(w)] [Im Li2,1(w,-1)] - 28529/1134 [zeta(5)] + 544/7 [Li5(1/2)] - 144/7 [Li5(-1/2)] + 356/7 [Li5(1/3)] - 202/7 [Li5(-1/3)] - 288/7 [Li5(2/3)] - 72/7 [Li5(3/4)] + 8/7 [Li5(8/9)] - 36 [Re -Li_{1,3,1}(-w,1,1)] + 416/7 [Re -Li_{3,1,1}(-1,1,w)] + 24 [Re -Li_{2,1,2}(-1,w,-w^2)]
  (35 terms, height 10^5.95; full check: agree 20008.4 d vs claimed 19998)

- **ImG5a** = - 23/4320 [ln3]^4 [pi] + 1/18 [ln3]^3 [Cl2(pi/3)=Im Li2(w)] + 19/3240 [ln3]^2 [pi]^3 + 2/5 [ln3]^2 [Im Li3(i/sqrt3)] - 73/90 [ln3] [Cl4(pi/3)=Im Li4(w)] + 6/5 [ln3] [Im Li4(i/sqrt3)] - 1531/116640 [pi]^5 + 2/15 [pi]^2 [Im Li3(i/sqrt3)] - 1/18 [pi] [Li4(1/3)] + 1/36 [pi] [Li4(-1/3)] - 2/3 [Cl2(pi/3)=Im Li2(w)] [zeta(3)] - 1/6 [Ls5^(0)(2pi/3)]
  (13 terms, height 10^4.19; full check: agree 20006.6 d vs claimed 20000)

- **ImG5b** = + 223/29160 [pi]^5 + 1/3 [Cl2(pi/3)=Im Li2(w)] [zeta(3)] + 1/9 [Ls5^(0)(pi/3)]
  (4 terms, height 10^3.51; full check: agree 20007.0 d vs claimed 20000)

- **ImG5c** = + 1/252 [ln3]^4 [pi] - 10/189 [ln3]^3 [Cl2(pi/3)=Im Li2(w)] - 8/21 [ln3]^2 [Im Li3(i/sqrt3)] + 4/9 [ln3] [Cl4(pi/3)=Im Li4(w)] - 32/21 [ln3] [Im Li4(i/sqrt3)] + 71/11340 [pi]^5 - 8/27 [Cl2(pi/3)=Im Li2(w)] [zeta(3)] - 64/21 [Im Li5(i/sqrt3)] - 116/567 [Ls5^(0)(pi/3)] + 10/63 [Ls5^(0)(2pi/3)]
  (11 terms, height 10^4.54; full check: agree 20007.1 d vs claimed 20000)

- **s6** = + 1/208 [ln2]^6 - 1/208 [ln2]^4 [pi]^2 + 1/156 [ln2]^2 [pi]^4 + 89/58968 [pi]^6 + 3/8 [zeta(3)]^2 + 126/13 [Li6(1/2)] + 162/13 [Li6(-1/2)] - 1/39 [Li6(-1/8)]
  (9 terms, height 10^4.74; full check: agree 20006.5 d vs claimed 20000)

- **Li6h** = + [Li6(1/2)]
  (2 terms, height 10^0.0; full check: agree 20005.7 d vs claimed 20000)

- **D5bar2** = + 3018131/876798 [ln2]^6 - 24179/6245 [ln2]^5 [ln3] + 111330/8743 [ln2]^4 [ln3]^2 - 79195/876798 [ln2]^4 [pi]^2 - 11296/1249 [ln2]^4 [Li2(-1/2)] - 63036/8743 [ln2]^3 [ln3]^3 - 45119/8743 [ln2]^3 [ln3] [pi]^2 - 9464/1249 [ln2]^3 [zeta(3)] + 29418/8743 [ln2]^2 [ln3]^4 - 30453/8743 [ln2]^2 [ln3]^2 [pi]^2 + 109200/1249 [ln2]^2 [ln3] [zeta(3)] + 136395377/42086304 [ln2]^2 [pi]^4 + 11296/1249 [ln2]^2 [pi]^2 [Li2(-1/2)] - 48513/2498 [ln2]^2 [Cl2(pi/3)=Im Li2(w)]^2 - 1152/1249 [ln2]^2 [Li4(1/2)] + 100800/1249 [ln2]^2 [Li4(1/3)] - 50400/1249 [ln2]^2 [Li4(-1/3)] - 59623/174860 [ln2] [ln3]^5 + 2603/7494 [ln2] [ln3]^3 [pi]^2 + 6687/4996 [ln2] [ln3]^2 [pi] [Cl2(pi/3)=Im Li2(w)] + 18096/1249 [ln2] [ln3]^2 [zeta(3)] - 990331/539568 [ln2] [ln3] [pi]^4 - 35451/1249 [ln2] [ln3] [Cl2(pi/3)=Im Li2(w)]^2 + 244704/1249 [ln2] [ln3] [Li4(1/2)] - 12636/1249 [ln2] [ln3] [Li4(1/3)] + 6318/1249 [ln2] [ln3] [Li4(-1/3)] + 58693/67446 [ln2] [pi]^3 [Cl2(pi/3)=Im Li2(w)] - 106886/11241 [ln2] [pi]^2 [zeta(3)] - 109934/1249 [ln2] [pi] [Cl4(pi/3)=Im Li4(w)] - 27384/1249 [ln2] [Li2(-1/2)] [zeta(3)] - 80244/1249 [ln2] [Cl2(pi/3)=Im Li2(w)] [Im Li3(i/sqrt3)] - 50400/1249 [ln2] [Cl2(pi/3)=Im Li2(w)] [Im Li2,1(w,-1)] - 40554305/134892 [ln2] [zeta(5)] + 398400/1249 [ln2] [Li5(1/2)] - 43200/1249 [ln2] [Li5(-1/2)] + 36528/1249 [ln2] [Li5(1/3)] - 25464/1249 [ln2] [Li5(-1/3)] - 86400/1249 [ln2] [Li5(2/3)] - 21600/1249 [ln2] [Li5(3/4)] + 2400/1249 [ln2] [Li5(8/9)] + 135216/1249 [ln2] [Re -Li_{1,3,1}(-w,1,1)] + 93504/1249 [ln2] [Re -Li_{3,1,1}(-1,1,w)] + 50400/1249 [ln2] [Re -Li_{2,1,2}(-1,w,-w^2)] - 18575111/7553952 [ln3]^6 + 43426171/10071936 [ln3]^4 [pi]^2 - 6743563/1049160 [ln3]^3 [pi] [Cl2(pi/3)=Im Li2(w)] - 21868465/269784 [ln3]^3 [zeta(3)] - 1304767/5035968 [ln3]^2 [pi]^4 - 913793/17486 [ln3]^2 [pi] [Im Li3(i/sqrt3)] - 11915/1249 [ln3]^2 [Cl2(pi/3)=Im Li2(w)]^2 - 50544/8743 [ln3]^2 [Li4(1/2)] - 2595521/14988 [ln3]^2 [Li4(1/3)] + 2595521/29976 [ln3]^2 [Li4(-1/3)] + 220061/168615 [ln3] [pi]^3 [Cl2(pi/3)=Im Li2(w)] + 3028205/1258992 [ln3] [pi]^2 [zeta(3)] + 7848383/52458 [ln3] [pi] [Cl4(pi/3)=Im Li4(w)] - 1834082/8743 [ln3] [pi] [Im Li4(i/sqrt3)] - 119424/6245 [ln3] [Cl2(pi/3)=Im Li2(w)] [Im Li3(i/sqrt3)] - 15120/1249 [ln3] [Cl2(pi/3)=Im Li2(w)] [Im Li2,1(w,-1)] - 1228819099/2517984 [ln3] [zeta(5)] - 113724/8743 [ln3] [Li5(1/2)] + 37908/8743 [ln3] [Li5(-1/2)] - 8687122/26229 [ln3] [Li5(1/3)] + 4362515/26229 [ln3] [Li5(-1/3)] + 75816/8743 [ln3] [Li5(2/3)] + 18954/8743 [ln3] [Li5(3/4)] - 2106/8743 [ln3] [Li5(8/9)] - 73215/1249 [ln3] [Re -Li_{1,3,1}(-w,1,1)] - 50544/8743 [ln3] [Re -Li_{3,1,1}(-1,1,w)] + 889880609221/159086229120 [pi]^6 + 1033063/539568 [pi]^4 [Li2(-1/2)] - 181516/56205 [pi]^3 [Im Li3(i/sqrt3)] + 21995/22482 [pi]^3 [Im Li2,1(w,-1)] - 546103/89928 [pi]^2 [Cl2(pi/3)=Im Li2(w)]^2 - 126752/11241 [pi]^2 [Li4(1/2)] + 8093/29976 [pi]^2 [Li4(1/3)] - 8093/59952 [pi]^2 [Li4(-1/3)] - 19681/9992 [pi] [Cl2(pi/3)=Im Li2(w)] [zeta(3)] - 3668164/8743 [pi] [Im Li5(i/sqrt3)] - 21377957/944244 [pi] [Ls5^(0)(pi/3)] + 50092909/629496 [pi] [Ls5^(0)(2pi/3)] - 12636/1249 [pi] [Im Li4,1(w,-1)] + 35487/1249 [Li2(-1/2)] [Cl2(pi/3)=Im Li2(w)]^2 - 271104/1249 [Li2(-1/2)] [Li4(1/2)] + 8296421/18735 [Cl2(pi/3)=Im Li2(w)] [Cl4(pi/3)=Im Li4(w)] + 823648/6245 [Cl2(pi/3)=Im Li2(w)] [Im Li4(i/sqrt3)] - 92142/1249 [Cl2(pi/3)=Im Li2(w)] [Im -Li_{1,2,1}(-1,1,w^2)] + 399753/1249 [Cl2(pi/3)=Im Li2(w)] [Im -Li_{1,2,1}(-1,w^2,1)] + 15447119/29976 [zeta(3)]^2 + 168 [zeta(3)] [Li3(-1/2)] + 46286/1249 [zeta(3)] [Li3(1/3)] - 5568/1249 [Im Li3(i/sqrt3)]^2 - 15120/1249 [Im Li2,1(w,-1)]^2 + 102787664/48711 [Li6(1/2)] + 39559056/16237 [Li6(-1/2)] - 2343635/7494 [Li6(1/3)] + 2343635/14988 [Li6(-1/3)] - 6593176/1315197 [Li6(-1/8)] - 2595521/29976 [Ls6^(1)(2pi/3)] - 707415/1249 [Re Li5,1(-1,w)] + 302400/1249 [Re Li_{1,3,1,1}(-w^2,-w,1,1)] + 73215/1249 [Re Li_{3,1,1,1}(-w,1,-w,w^2)] + 37908/1249 [Re Li_{1,2,2,1}(-1,1,w^2,1)] + 27450/1249 [Re Li_{2,1,1,2}(-w^2,-w,w^2,1)] - 141948/1249 [Re Li_{1,1,1,3}(-w^2,-w,w^2,1)] - 70416/1249 [Re Li_{1,1,3,1}(-w,-w^2,w,-w^2)] - 37908/1249 [Re Li_{1,1,3,1}(-w,1,-w^2,w)] + 77256/1249 [Re Li_{2,1,1,2}(-w^2,1,-w,w^2)] + 75600/1249 [Re Li_{1,2,2,1}(-1,1,w^2,-w)] + 30240/1249 [Re Li_{1,2,2,1}(-w^2,-w,w^2,-w)] - 48 [Re Li_{1,2,2,1}(-w^2,1,-1,-1)]
  (112 terms, height 10^13.16; full check: agree 20008.0 d vs claimed 19998)

- **D6bar2** = + 22813673/8767980 [ln2]^6 + 416459/131145 [ln2]^5 [ln3] - 44666/8743 [ln2]^4 [ln3]^2 - 15819815/6137586 [ln2]^4 [pi]^2 + 8816/1249 [ln2]^4 [Li2(-1/2)] + 24804/8743 [ln2]^3 [ln3]^3 + 12653/26229 [ln2]^3 [ln3] [pi]^2 + 127294/3747 [ln2]^3 [zeta(3)] + 3139/17486 [ln2]^2 [ln3]^4 - 13878/8743 [ln2]^2 [ln3]^2 [pi]^2 - 12090/1249 [ln2]^2 [ln3] [zeta(3)] - 545676917/210431520 [ln2]^2 [pi]^4 - 8816/1249 [ln2]^2 [pi]^2 [Li2(-1/2)] + 47449/2498 [ln2]^2 [Cl2(pi/3)=Im Li2(w)]^2 + 90912/1249 [ln2]^2 [Li4(1/2)] + 48792/1249 [ln2]^2 [Li4(1/3)] - 24396/1249 [ln2]^2 [Li4(-1/3)] - 338237/262290 [ln2] [ln3]^5 + 149836/78687 [ln2] [ln3]^3 [pi]^2 - 65951/24980 [ln2] [ln3]^2 [pi] [Cl2(pi/3)=Im Li2(w)] + 47773/2498 [ln2] [ln3]^2 [zeta(3)] - 1092101/6294960 [ln2] [ln3] [pi]^4 + 87657/1249 [ln2] [ln3] [Cl2(pi/3)=Im Li2(w)]^2 - 356512/8743 [ln2] [ln3] [Li4(1/2)] - 115668/1249 [ln2] [ln3] [Li4(1/3)] + 57834/1249 [ln2] [ln3] [Li4(-1/3)] - 1735703/337230 [ln2] [pi]^3 [Cl2(pi/3)=Im Li2(w)] + 20706757/944244 [ln2] [pi]^2 [zeta(3)] + 452842/8743 [ln2] [pi] [Cl4(pi/3)=Im Li4(w)] - 24696/1249 [ln2] [Li2(-1/2)] [zeta(3)] + 791412/6245 [ln2] [Cl2(pi/3)=Im Li2(w)] [Im Li3(i/sqrt3)] + 35556/1249 [ln2] [Cl2(pi/3)=Im Li2(w)] [Im Li2,1(w,-1)] - 832346995/2832732 [ln2] [zeta(5)] - 578544/8743 [ln2] [Li5(1/2)] + 123408/8743 [ln2] [Li5(-1/2)] - 1353748/8743 [ln2] [Li5(1/3)] + 697442/8743 [ln2] [Li5(-1/3)] + 246816/8743 [ln2] [Li5(2/3)] + 61704/8743 [ln2] [Li5(3/4)] - 6856/8743 [ln2] [Li5(8/9)] + 120564/1249 [ln2] [Re -Li_{1,3,1}(-w,1,1)] - 554080/8743 [ln2] [Re -Li_{3,1,1}(-1,1,w)] - 20568/1249 [ln2] [Re -Li_{2,1,2}(-1,w,-w^2)] + 21838009/50359680 [ln3]^6 - 52950413/125899200 [ln3]^4 [pi]^2 + 2 [ln3]^4 [Li2(-1/2)] + 2363339/3147480 [ln3]^3 [pi] [Cl2(pi/3)=Im Li2(w)] - 5139533/359712 [ln3]^3 [zeta(3)] + 29279399/251798400 [ln3]^2 [pi]^4 - 4 [ln3]^2 [pi]^2 [Li2(-1/2)] + 392321/437150 [ln3]^2 [pi] [Im Li3(i/sqrt3)] + 6/5 [ln3]^2 [pi] [Im Li2,1(w,-1)] - 6554/1249 [ln3]^2 [Cl2(pi/3)=Im Li2(w)]^2 + 16944/8743 [ln3]^2 [Li4(1/2)] + 92323/2498 [ln3]^2 [Li4(1/3)] - 92323/4996 [ln3]^2 [Li4(-1/3)] - 1973/134892 [ln3] [pi]^3 [Cl2(pi/3)=Im Li2(w)] + 12241051/2517984 [ln3] [pi]^2 [zeta(3)] + 10979/52458 [ln3] [pi] [Cl4(pi/3)=Im Li4(w)] + 15718/8743 [ln3] [pi] [Im Li4(i/sqrt3)] - 372612/6245 [ln3] [Cl2(pi/3)=Im Li2(w)] [Im Li3(i/sqrt3)] + 1674/1249 [ln3] [Cl2(pi/3)=Im Li2(w)] [Im Li2,1(w,-1)] - 1301329747/15107904 [ln3] [zeta(5)] + 38124/8743 [ln3] [Li5(1/2)] - 12708/8743 [ln3] [Li5(-1/2)] + 805568/8743 [ln3] [Li5(1/3)] - 404902/8743 [ln3] [Li5(-1/3)] - 25416/8743 [ln3] [Li5(2/3)] - 6354/8743 [ln3] [Li5(3/4)] + 706/8743 [ln3] [Li5(8/9)] - 125505/2498 [ln3] [Re -Li_{1,3,1}(-w,1,1)] + 16944/8743 [ln3] [Re -Li_{3,1,1}(-1,1,w)] - 69605930497/265143715200 [pi]^6 - 9958979/2697840 [pi]^4 [Li2(-1/2)] + 191213/281025 [pi]^3 [Im Li3(i/sqrt3)] + 128503/56205 [pi]^3 [Im Li2,1(w,-1)] + 6313/9992 [pi]^2 [Cl2(pi/3)=Im Li2(w)]^2 + 125462/3747 [pi]^2 [Li4(1/2)] + 120199/29976 [pi]^2 [Li4(1/3)] - 120199/59952 [pi]^2 [Li4(-1/3)] + 2051417/89928 [pi] [Cl2(pi/3)=Im Li2(w)] [zeta(3)] + 31436/8743 [pi] [Im Li5(i/sqrt3)] + 3749987/1888488 [pi] [Ls5^(0)(pi/3)] - 2624339/209832 [pi] [Ls5^(0)(2pi/3)] - 18246/1249 [pi] [Im Li4,1(w,-1)] - 36791/1249 [Li2(-1/2)] [Cl2(pi/3)=Im Li2(w)]^2 + 211584/1249 [Li2(-1/2)] [Li4(1/2)] + 96 [Li2(-1/2)] [Li4(1/3)] - 48 [Li2(-1/2)] [Li4(-1/3)] - 5943353/18735 [Cl2(pi/3)=Im Li2(w)] [Cl4(pi/3)=Im Li4(w)] - 997464/6245 [Cl2(pi/3)=Im Li2(w)] [Im Li4(i/sqrt3)] + 60438/1249 [Cl2(pi/3)=Im Li2(w)] [Im -Li_{1,2,1}(-1,1,w^2)] - 343095/1249 [Cl2(pi/3)=Im Li2(w)] [Im -Li_{1,2,1}(-1,w^2,1)] + 24 [Cl2(pi/3)=Im Li2(w)] [Im -Li_{2,1,1}(-w,-w^2,1)] - 172555645/359712 [zeta(3)]^2 - 284 [zeta(3)] [Li3(-1/2)] + 127778/1249 [zeta(3)] [Li3(1/3)] - 335736/31225 [Im Li3(i/sqrt3)]^2 - 288/5 [Im Li3(i/sqrt3)] [Im Li2,1(w,-1)] + 1674/1249 [Im Li2,1(w,-1)]^2 + 100586792/48711 [Li6(1/2)] + 43272024/16237 [Li6(-1/2)] + 308395/4996 [Li6(1/3)] - 308395/9992 [Li6(-1/3)] - 7212004/1315197 [Li6(-1/8)] + 92323/4996 [Ls6^(1)(2pi/3)] + 959169/2498 [Re Li5,1(-1,w)] - 33480/1249 [Re Li_{1,3,1,1}(-w^2,-w,1,1)] + 125505/2498 [Re Li_{3,1,1,1}(-w,1,-w,w^2)] + 122184/1249 [Re Li_{1,2,2,1}(-1,1,w^2,1)] - 54828/1249 [Re Li_{2,1,1,2}(-w^2,-w,w^2,1)] - 12708/1249 [Re Li_{1,1,1,3}(-w^2,-w,w^2,1)] - 63504/1249 [Re Li_{1,1,3,1}(-w,-w^2,w,-w^2)] + 12708/1249 [Re Li_{1,1,3,1}(-w,1,-w^2,w)] - 41634/1249 [Re Li_{2,1,1,2}(-w^2,1,-w,w^2)] + 14112/1249 [Re Li_{1,2,2,1}(-1,1,w^2,-w)] - 3348/1249 [Re Li_{1,2,2,1}(-w^2,-w,w^2,-w)] + 96 [Re Li_{1,2,2,1}(-w^2,1,-1,-1)]
  (119 terms, height 10^13.89; full check: agree 20008.0 d vs claimed 19998)

- **T111bar4** = + 1/20 [ln3]^5 [pi] - 3/4 [ln3]^4 [Cl2(pi/3)=Im Li2(w)] - 17/180 [ln3]^3 [pi]^3 - 24/5 [ln3]^3 [Im Li3(i/sqrt3)] + 42/5 [ln3]^2 [Cl4(pi/3)=Im Li4(w)] - 72/5 [ln3]^2 [Im Li4(i/sqrt3)] + 19/120 [ln3] [pi]^5 + 3 [ln3] [Ls5^(0)(2pi/3)] + [pi]^3 [zeta(3)] + 18 [pi] [zeta(5)] - 6/5 [Ls6^(0)(2pi/3)]
  (12 terms, height 10^3.33; full check: agree 20003.9 d vs claimed 19998)

## weight 7

- **T111bar5** = - 1/48 [ln3]^6 [pi] + 3/10 [ln3]^5 [Cl2(pi/3)=Im Li2(w)] + 17/720 [ln3]^4 [pi]^3 + 9/5 [ln3]^4 [Im Li3(i/sqrt3)] - 14/5 [ln3]^3 [Cl4(pi/3)=Im Li4(w)] + 24/5 [ln3]^3 [Im Li4(i/sqrt3)] - 19/240 [ln3]^2 [pi]^5 - 3/2 [ln3]^2 [Ls5^(0)(2pi/3)] - [ln3] [pi]^3 [zeta(3)] - 18 [ln3] [pi] [zeta(5)] + 6/5 [ln3] [Ls6^(0)(2pi/3)] - 55/1008 [pi]^7 - 6 [pi] [zeta(3)]^2 - 2/5 [Ls7^(0)(2pi/3)]
  (15 terms, height 10^4.48; full check: agree 20003.4 d vs claimed 19998)

- **BNbar5** = - 768/35 [ln2]^7 + 384/5 [ln2]^5 [pi]^2 + 1088/5 [ln2]^3 [pi]^4 + 44640 [ln2]^2 [zeta(5)] + 2944/105 [ln2] [pi]^6 + 19520 [ln2] [zeta(3)]^2 - 46080 [ln2] [Re Li5,1(-1,-1)] - 688/3 [pi]^4 [zeta(3)] - 9440/3 [pi]^2 [zeta(5)] - 47373 [zeta(7)] + 110592 [Li7(1/2)] - 40960 [Re -Li_{5,1,1}(-1,1,1)] - 21760 [Re -Li_{4,2,1}(-1,1,1)]
  (14 terms, height 10^6.59; full check: agree 19712.3 d vs claimed 19706)

## constants that do not reduce: standard definitions

See LIFTED-DEFINITIONS.md (Bessel moments c_{5,k} in Broadhurst notation and their eps-jets; every PR*D2Eps*/PR14ep* as an explicit 4-loop Euclidean integral with its propagators, dimension and Taylor order; D5bar3 as the eps^3 coefficient of the MATAD D5 tetrahedron).
