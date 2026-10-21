$HistoryLength=0;
p=20120;
points={{15,16},
{5,4},
{25,16},
{15,8},
{75,32},
{45,16},
{225,64},
{135,32},
{675,128},
{405,64},
{2025,256},
{1215,128},
{6075,512},
{3645,256},
{18225,1024},
{10935,512},
{54675,2048},
{32805,1024},
{164025,4096},
{98415,2048},
{492075,8192},
{295245,4096},
{1476225,16384},
{885735,8192},
{4428675,32768},
{2657205,16384},
{13286025,65536},
{7971615,32768},
{39858075,131072},
{23914845,65536},
{119574225,262144},
{71744535,131072},
{358722675,524288},
{215233605,262144},
{1076168025,1048576},
{645700815,524288},
{3228504075,2097152},
{1937102445,1048576},
{9685512225,4194304},
{5811307335,2097152},
{29056536675,8388608},
{17433922005,4194304},
{87169610025,16777216},
{52301766015,8388608},
{261508830075,33554432},
{156905298045,16777216}};
old=Import["/shared/codex-1/vakint_rustred/workspace/precision-periods/bessel/mathematica-builtin-seeds.json","RawJSON"];
rows=old["rows"];
known=({#["numerator"],#["denominator"]}& /@ rows);
points=Select[points,!MemberQ[known,#]&];
Do[
 t=AbsoluteTime[];z=pt[[1]]/pt[[2]];
 wprec=p+Ceiling[2z/Log[10]]+100;
 n=2Ceiling[(wprec+80)/Log[10,wprec+80]]+2Ceiling[z]+200;
 While[N[n Log[z^2/4]-2LogGamma[n+1],40]>-(p+Ceiling[z/Log[10]]+60)Log[10],n=Ceiling[11n/10]];
 w=N[z^2/4,wprec];u=FoldList[#1 w/(#2^2)&,N[1,wprec],Range[n]];
 hh=Prepend[Accumulate[N[1/Range[n],wprec]],0];l=N[EulerGamma+Log[z/2],wprec];
 i0=Total[u];q=Total[Range[0,n]u];aa=Total[u hh];qh=Total[Range[0,n]u hh];
 vals=N[{aa-l i0,(i0+2l q-2qh)/z},p];
 AppendTo[rows,<|"numerator"->pt[[1]],"denominator"->pt[[2]],"values"->(ToString[InputForm[#]]& /@ vals),"seconds"->N[AbsoluteTime[]-t,8],"method"->"independent Mathematica Frobenius K0/K1 series","working_digits"->wprec,"terms"->n|>];
 Export["/shared/codex-1/vakint_rustred/workspace/precision-periods/bessel/mathematica-seeds-v2.json",<|"working_decimal_digits"->p,"rows"->rows,"constants"->old["constants"]|>,"RawJSON"];
 Print["completed ",pt," seconds ",N[AbsoluteTime[]-t,8]," terms ",n],
 {pt,points}];
Quit[];
