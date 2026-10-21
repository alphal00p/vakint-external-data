(* Runtime configuration only: the requested script is loaded unchanged. *)
SetSystemOptions["ParallelOptions" -> {
  "ParallelThreadNumber" -> 1, "MKLThreadNumber" -> 1}];
rustflowThreadOptions = "ParallelOptions" /. SystemOptions["ParallelOptions"];
If[("ParallelThreadNumber" /. rustflowThreadOptions) =!= 1 ||
   ("MKLThreadNumber" /. rustflowThreadOptions) =!= 1,
  Print["RUSTFLOW THREAD CONFIGURATION FAILURE"]; Exit[2]];
Print["RUSTFLOW THREAD CONFIGURATION: ", InputForm[rustflowThreadOptions]];
rustflowOriginalScript = Environment["RUSTFLOW_WOLFRAM_SCRIPT"];
rustflowOriginalArguments = Quiet[Check[
  ImportString[Environment["RUSTFLOW_WOLFRAM_SCRIPT_ARGUMENTS"], "RawJSON"], $Failed]];
If[!StringQ[rustflowOriginalScript] || !FileExistsQ[rustflowOriginalScript] ||
   !MatchQ[rustflowOriginalArguments, {___String}],
  Print["RUSTFLOW SCRIPT CONFIGURATION FAILURE"]; Exit[2]];
(* Get supplies the original $InputFileName; preserve the script argument list
   while the outer kernel command necessarily names this runtime loader. *)
Block[{$ScriptCommandLine = Prepend[rustflowOriginalArguments, rustflowOriginalScript]},
  Get[rustflowOriginalScript]];
Exit[0];
