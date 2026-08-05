$ErrorActionPreference='Stop'
$root = Split-Path $PSScriptRoot -Parent
function Get-Ev($f){ (Get-Content $f -Raw | ConvertFrom-Json).data.reportData.report.events.data }
function New-StackTL($evs,$id){
  $tl=New-Object System.Collections.ArrayList; $cur=0
  foreach($e in $evs){ if([string]$e.abilityGameID -ne $id){continue}
    switch($e.type){'applybuff'{$cur=1}'applybuffstack'{$cur=[int]$e.stack}'removebuffstack'{$cur=[int]$e.stack}'removebuff'{$cur=0}}
    [void]$tl.Add([pscustomobject]@{t=[long]$e.timestamp;v=[int]$cur}) }
  return $tl }
function Get-ValAt($tl,$time){ $v=0; foreach($p in $tl){ if($p.t -lt $time){$v=$p.v} else {break} }; return $v }

$C_AM=5143
$rowsAll=@()
foreach($F in 1,2){
  $casts=@(Get-Ev "$root\scratch\n_castsR_f$F.json" | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
  $buffs=@(Get-Ev "$root\scratch\n_buffs_f$F.json" | Sort-Object timestamp)
  $salvoTL=New-StackTL $buffs '1242974'
  $mis=@($casts|Where-Object{$_.abilityGameID -eq $C_AM})
  foreach($m in $mis){
    $ts=[long]$m.timestamp
    $s=Get-ValAt $salvoTL $ts
    $nxt=$casts | Where-Object { [long]$_.timestamp -gt $ts } | Select-Object -First 1
    if(-not $nxt){continue}
    $after=Get-ValAt $salvoTL ([long]$nxt.timestamp)
    $rowsAll += [pscustomobject]@{pull=$F;start=$s;end=$after;gain=($after-$s);capped=($after -ge 25)}
  }
}
# calibrate the true per-channel yield from UNCAPPED channels only
$clean = @($rowsAll | Where-Object { -not $_.capped -and $_.gain -gt 0 })
$yield = ($clean | Measure-Object gain -Average).Average
$med = ($clean | Sort-Object gain)[[int]($clean.Count/2)].gain
Write-Output ("CALIBRATION: {0} uncapped Missiles channels | mean yield {1:N1} stacks, median {2}" -f $clean.Count,$yield,$med)
Write-Output ("   (gains observed: " + ((($clean | Sort-Object gain | ForEach-Object {$_.gain}) | Select-Object -First 40) -join ",") + ")")
Write-Output ""

Write-Output "MISSILES START-SALVO DISTRIBUTION (both pulls, n=$($rowsAll.Count))"
$b=@{'0-4'=0;'5-11'=0;'12-14'=0;'15-19'=0;'20+'=0}
foreach($r in $rowsAll){ $s=$r.start
  if($s -le 4){$b['0-4']++} elseif($s -le 11){$b['5-11']++} elseif($s -le 14){$b['12-14']++} elseif($s -le 19){$b['15-19']++} else{$b['20+']++} }
foreach($k in '0-4','5-11','12-14','15-19','20+'){ Write-Output ("   {0,-7} {1,3}  {2,5:N1}%" -f $k,$b[$k],(100*$b[$k]/$rowsAll.Count)) }
Write-Output ""

# overflow: only channels that ended capped
$lostTotal=0; $lostRows=@()
foreach($r in $rowsAll){
  if(-not $r.capped){continue}
  $lost=[math]::Round([math]::Max(0, ($r.start + $yield) - 25),1)
  if($lost -gt 0){ $lostTotal+=$lost; $lostRows+=[pscustomobject]@{pull=$r.pull;start=$r.start;lost=$lost} }
}
Write-Output ("OVERFLOW: {0} channels ended pinned at 25 | ~{1:N0} Salvo stacks lost across both pulls (~{2:N0}/pull)" -f @($rowsAll|Where-Object{$_.capped}).Count,$lostTotal,($lostTotal/2))
$byStart = $lostRows | Group-Object start | Sort-Object {[int]$_.Name}
Write-Output ("   worst offenders (start salvo -> stacks lost each):")
$byStart | Where-Object {[int]$_.Name -ge 15} | ForEach-Object {
  Write-Output ("      started at {0,2}:  {1} channels x ~{2:N0} lost" -f $_.Name,$_.Count,($_.Group[0].lost)) }
Write-Output ""
Write-Output "WHAT THAT COSTS (per pull)"
$perPull=$lostTotal/2
Write-Output ("   ~{0:N0} Salvo stacks -> ~{1:N1} Prismatic Bolt procs (2%/stack) and ~{2:N0} Meteorites (1 per 5)" -f $perPull,($perPull*0.02),($perPull/5))
Write-Output ""
Write-Output "SPLIT BY PULL"
$rowsAll | Group-Object pull | ForEach-Object {
  $cap=@($_.Group|Where-Object{$_.capped}).Count
  Write-Output ("   pull {0}: {1} channels, {2} ended capped ({3:N0}%), avg start salvo {4:N1}" -f $_.Name,$_.Count,$cap,(100*$cap/$_.Count),(($_.Group|Measure-Object start -Average).Average)) }
