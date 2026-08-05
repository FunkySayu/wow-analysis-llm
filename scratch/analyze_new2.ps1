param([double]$ManaFloor=20)
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

$SALVOID='1242974'; $CCID='263725'
$C_AM=5143; $C_AB=44425; $C_PB=1295924; $C_ABl=30451

foreach($F in 1,2){
  $casts=@(Get-Ev "$root\scratch\n_castsR_f$F.json" | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
  $buffs=@(Get-Ev "$root\scratch\n_buffs_f$F.json" | Sort-Object timestamp)
  $t0=[long]$casts[0].timestamp; $tE=[long]$casts[-1].timestamp
  $salvoTL=New-StackTL $buffs $SALVOID
  $ccTL   =New-StackTL $buffs $CCID
  function ManaPct($c){ $r=@($c.classResources | Where-Object {$_.type -eq 0}); if($r.Count -eq 0){return 100}; return 100.0*$r[0].amount/$r[0].max }

  Write-Output "================= PULL $F ================="

  # 1. Blasts that should have been Missiles
  $bl=@($casts|Where-Object{$_.abilityGameID -eq $C_ABl})
  $shouldMis=@(); $blLow=0
  foreach($b in $bl){
    $ts=[long]$b.timestamp
    if((ManaPct $b) -lt $ManaFloor){$blLow++; continue}
    $s=Get-ValAt $salvoTL $ts; $c=Get-ValAt $ccTL $ts
    if($c -ge 1 -and $s -lt 12){ $shouldMis+=[pscustomobject]@{t=[math]::Round(($ts-$t0)/1000,1);s=$s;cc=$c} }
  }
  Write-Output ("ARCANE BLAST: {0} casts ({1} at low mana) | cast while Clearcasting up AND Salvo<12 -> should have been MISSILES: {2}" -f $bl.Count,$blLow,$shouldMis.Count)
  if($shouldMis.Count){ Write-Output ("   e.g. " + (($shouldMis|Select-Object -First 12|ForEach-Object{"t=$($_.t)s salvo=$($_.s) cc=$($_.cc)"}) -join " | ")) }

  # 2. Missiles overflow
  $mis=@($casts|Where-Object{$_.abilityGameID -eq $C_AM})
  $ovf=0; $ovfN=0; $detail=@()
  for($i=0;$i -lt $mis.Count;$i++){
    $ts=[long]$mis[$i].timestamp
    $s=Get-ValAt $salvoTL $ts
    # salvo right before the NEXT cast = where the channel landed
    $nxt=$casts | Where-Object { [long]$_.timestamp -gt $ts } | Select-Object -First 1
    if(-not $nxt){continue}
    $after=Get-ValAt $salvoTL ([long]$nxt.timestamp)
    if($s -ge 12){ $ovfN++; $gained=$after-$s; $lost=[math]::Max(0, 13-$gained); $ovf+=$lost; $detail+="$s->$after" }
  }
  Write-Output ("ARCANE MISSILES: {0} casts | {1} started at Salvo>=12 | est. Salvo stacks overflowed by those: ~{2}" -f $mis.Count,$ovfN,$ovf)
  Write-Output ("   those channels (before->after): " + (($detail|Select-Object -First 14) -join "  "))

  # 3. Clearcasting waste
  $ccEv=@($buffs|Where-Object{[string]$_.abilityGameID -eq $CCID})
  $gain=@($ccEv|Where-Object{$_.type -in @('applybuff','applybuffstack')}).Count
  $wasted=@($ccEv|Where-Object{$_.type -eq 'refreshbuff'}).Count
  $cc3=0;$prev=$null
  foreach($p in $ccTL){ if($null -ne $prev -and $prev.v -ge 3){$cc3+=($p.t-$prev.t)}; $prev=$p }
  Write-Output ("CLEARCASTING: {0} procs used, {1} wasted at 3/3 cap ({2:N0}% of all procs) | {3:N0}s at cap" -f $gain,$wasted,(100*$wasted/[math]::Max($gain+$wasted,1)),($cc3/1000))

  # 4. Salvo throughput
  $barr=@($casts|Where-Object{$_.abilityGameID -eq $C_AB})
  $tot=0; foreach($b in $barr){ $tot += Get-ValAt $salvoTL ([long]$b.timestamp) }
  Write-Output ("SALVO THROUGHPUT: {0} stacks consumed across {1} Barrages ({2:N1}/cast)" -f $tot,$barr.Count,($tot/$barr.Count))

  # 5. mana timeline
  $mana = foreach($c in $casts){ [pscustomobject]@{t=[math]::Round(([long]$c.timestamp-$t0)/1000);m=[math]::Round((ManaPct $c))} }
  $firstLow = $mana | Where-Object {$_.m -lt 20} | Select-Object -First 1
  Write-Output ("MANA: starts {0}%, first drop under 20% at t={1}s, ends {2}%" -f $mana[0].m, $(if($firstLow){$firstLow.t}else{'never'}), $mana[-1].m)
  $s=($mana | Where-Object { $_.t % 30 -eq 0 } | Group-Object t | ForEach-Object { "$($_.Name)s:$($_.Group[0].m)%" }) -join "  "
  Write-Output ("   profile: $s")
  Write-Output ""
}

Write-Output "================= DPS ================="
foreach($F in 1,2){
  $t=(Get-Content "$root\scratch\n_dmg_f$F.json" -Raw | ConvertFrom-Json).data.reportData.report.table.data
  $tot=($t.entries|Measure-Object total -Sum).Sum
  Write-Output ("pull {0}: {1:N0} DPS over {2:N0}s" -f $F,($tot/($t.totalTime/1000)),($t.totalTime/1000))
  $t.entries | Sort-Object total -Descending | Select-Object -First 8 | ForEach-Object {
    Write-Output ("    {0,-20} {1,6:N1}%" -f $_.name,(100*$_.total/$tot)) }
}
