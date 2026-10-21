$HistoryLength=0;
p=20400;z=1;wprec=p+150;n=12000;
w=N[z^2/4,wprec];u=FoldList[#1 w/(#2^2)&,N[1,wprec],Range[n]];
hh=Prepend[Accumulate[N[1/Range[n],wprec]],0];l=N[EulerGamma+Log[z/2],wprec];
i0=Total[u];q=Total[Range[0,n]u];aa=Total[u hh];qh=Total[Range[0,n]u hh];
vals=N[{aa-l i0,(i0+2l q-2qh)/z},p];
Export["/shared/codex-1/vakint_rustred/workspace/precision-periods/bessel/high-guard/mathematica-anchor-one.json",<|"working_decimal_digits"->p,"numerator"->1,"denominator"->1,"values"->(ToString[InputForm[#]]& /@ vals),"method"->"independent Mathematica Frobenius K0/K1 series","working_digits"->wprec,"terms"->n|>,"RawJSON"];
Print["completed independent K0/K1 anchor at one"];
Quit[];
