param([int[]]$Fights = @(1,3,7,8,9))

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$map = Get-Content "$root\scratch\abilitymap.json" -Raw | ConvertFrom-Json

# spell ids
$SALVO   = '1242974'
$CC      = '263725'
$PBBUFF  = '1295942'   # "Prismatic Bolt!" proc (replaces next Arcane Blast)
$OPM     = '1277009'   # Overpowered Missiles proc
$INTU    = '1223797'   # Intuition (max-salvo -> next Barrage +25%)
$SOUL    = '451038'    # Arcane Soul
$SURGEB  = '365362'
$SPHERE  = '448604'
$CUMUL   = '1296930'

$C_MISSILES = 5143
$C_BARRAGE  = 44425
$C_PBOLT    = 1295924
$C_BLAST    = 30451
$C_ORB      = 153626
$C_TOM      = 321507
$C_SURGE    = 365350

function Get-Events($file) {
  $j = Get-Content $file -Raw | ConvertFrom-Json
  $j.data.reportData.report.events.data
}

$summary = @()

foreach ($F in $Fights) {
  $casts = @(Get-Events "$root\scratch\casts_f$F.json") | Where-Object { $_.type -eq 'cast' }
  $buffs = @(Get-Events "$root\scratch\buffev_f$F.json")
  $t0 = ($casts | Measure-Object timestamp -Minimum).Minimum
  $tEnd = ($casts | Measure-Object timestamp -Maximum).Maximum

  # ---- build stack timeline for a stacking buff ----
  function Build-StackTimeline($id) {
    $evs = $buffs | Where-Object { [string]$_.abilityGameID -eq $id } | Sort-Object timestamp
    $tl = New-Object System.Collections.ArrayList
    $cur = 0
    foreach ($e in $evs) {
      switch ($e.type) {
        'applybuff'       { $cur = 1 }
        'applybuffstack'  { $cur = $e.stack }
        'removebuffstack' { $cur = $e.stack }
        'refreshbuff'     { }
        'removebuff'      { $cur = 0 }
      }
      [void]$tl.Add([pscustomobject]@{ t = $e.timestamp; v = $cur; type = $e.type })
    }
    return $tl
  }

  function Value-At($tl, $time) {
    $v = 0
    foreach ($p in $tl) { if ($p.t -le $time) { $v = $p.v } else { break } }
    return $v
  }

  # ---- boolean buff intervals ----
  function Build-Intervals($id) {
    $evs = $buffs | Where-Object { [string]$_.abilityGameID -eq $id } | Sort-Object timestamp
    $iv = New-Object System.Collections.ArrayList
    $start = $null
    foreach ($e in $evs) {
      if ($e.type -eq 'applybuff') { $start = $e.timestamp }
      elseif ($e.type -eq 'refreshbuff') { if ($start -ne $null) { [void]$iv.Add([pscustomobject]@{s=$start;e=$e.timestamp;wasted=$true}); $start=$e.timestamp } }
      elseif ($e.type -eq 'removebuff') { if ($start -ne $null) { [void]$iv.Add([pscustomobject]@{s=$start;e=$e.timestamp;wasted=$false}); $start=$null } }
    }
    if ($start -ne $null) { [void]$iv.Add([pscustomobject]@{s=$start;e=$tEnd;wasted=$false}) }
    return $iv
  }

  $salvoTL = Build-StackTimeline $SALVO
  $ccTL    = Build-StackTimeline $CC
  $soulIV  = Build-Intervals $SOUL
  $pbIV    = Build-Intervals $PBBUFF
  $opmIV   = Build-Intervals $OPM
  $intuIV  = Build-Intervals $INTU

  function In-Interval($iv, $time) { foreach ($i in $iv) { if ($time -ge $i.s -and $time -le $i.e) { return $true } }; return $false }

  Write-Output "==================== FIGHT $F  ($([math]::Round(($tEnd-$t0)/1000,1))s) ===================="

  # ---- 1. Arcane Barrage: salvo stacks at cast ----
  $barr = $casts | Where-Object { $_.abilityGameID -eq $C_BARRAGE }
  $rows = foreach ($b in $barr) {
    [pscustomobject]@{
      t = [math]::Round(($b.timestamp-$t0)/1000,1)
      salvo = (Value-At $salvoTL ($b.timestamp+1))
      salvoBefore = (Value-At $salvoTL ($b.timestamp-50))
      soul = (In-Interval $soulIV $b.timestamp)
      intu = (In-Interval $intuIV $b.timestamp)
    }
  }
  $nonSoul = $rows | Where-Object { -not $_.soul }
  $soulR   = $rows | Where-Object { $_.soul }
  Write-Output ("ARCANE BARRAGE: {0} casts ({1} outside Arcane Soul, {2} inside)" -f $rows.Count,$nonSoul.Count,$soulR.Count)
  $avg = ($nonSoul | Measure-Object salvoBefore -Average).Average
  Write-Output ("  Salvo stacks at cast (outside Soul): avg {0:N1} / 25" -f $avg)
  $buckets = @{ '25 (max)'=0; '20-24'=0; '15-19'=0; '10-14'=0; '5-9'=0; '0-4'=0 }
  foreach ($r in $nonSoul) {
    $s = $r.salvoBefore
    if ($s -ge 25) { $buckets['25 (max)']++ }
    elseif ($s -ge 20) { $buckets['20-24']++ }
    elseif ($s -ge 15) { $buckets['15-19']++ }
    elseif ($s -ge 10) { $buckets['10-14']++ }
    elseif ($s -ge 5) { $buckets['5-9']++ }
    else { $buckets['0-4']++ }
  }
  foreach ($k in '25 (max)','20-24','15-19','10-14','5-9','0-4') {
    Write-Output ("    {0,-9} {1,3}  ({2,5:N1}%)" -f $k,$buckets[$k],(100*$buckets[$k]/[math]::Max($nonSoul.Count,1)))
  }
  # salvo stacks wasted by overcapping: time spent at 25
  $capTime = 0; $prev = $null
  foreach ($p in $salvoTL) { if ($prev -ne $null -and $prev.v -ge 25) { $capTime += ($p.t - $prev.t) }; $prev = $p }
  Write-Output ("  Time sitting at 25/25 Salvo (overcapped, generation wasted): {0:N1}s ({1:N1}%)" -f ($capTime/1000),(100*$capTime/($tEnd-$t0)))

  # ---- 2. Clearcasting ----
  $ccEvs = $buffs | Where-Object { [string]$_.abilityGameID -eq $CC }
  $ccRefresh = ($ccEvs | Where-Object { $_.type -eq 'refreshbuff' }).Count
  $cc3Time = 0; $prev=$null
  foreach ($p in $ccTL) { if ($prev -ne $null -and $prev.v -ge 3) { $cc3Time += ($p.t-$prev.t) }; $prev=$p }
  Write-Output ("CLEARCASTING: {0} proc-refreshes at cap (WASTED procs); {1:N1}s at 3/3 stacks ({2:N1}% of fight)" -f $ccRefresh,($cc3Time/1000),(100*$cc3Time/($tEnd-$t0)))

  # ---- 3. Prismatic Bolt proc handling ----
  $pbHold = $pbIV | ForEach-Object { ($_.e - $_.s)/1000 }
  $pbWasted = ($pbIV | Where-Object {$_.wasted}).Count
  if ($pbHold.Count -gt 0) {
    Write-Output ("PRISMATIC BOLT PROC: {0} procs | avg hold {1:N2}s | median {2:N2}s | max {3:N2}s | {4} OVERWRITTEN (lost)" -f `
      $pbIV.Count, (($pbHold | Measure-Object -Average).Average), (($pbHold | Sort-Object)[[int]($pbHold.Count/2)]), (($pbHold | Measure-Object -Maximum).Maximum), $pbWasted)
    $slow = ($pbHold | Where-Object { $_ -gt 3 }).Count
    Write-Output ("    procs held >3s: {0} / {1}" -f $slow,$pbHold.Count)
  }

  # ---- 4. Overpowered Missiles ----
  $opmHold = $opmIV | ForEach-Object { ($_.e-$_.s)/1000 }
  if ($opmHold.Count -gt 0) {
    Write-Output ("OVERPOWERED MISSILES: {0} procs | avg hold {1:N2}s | max {2:N2}s | {3} overwritten" -f `
      $opmIV.Count, (($opmHold|Measure-Object -Average).Average), (($opmHold|Measure-Object -Maximum).Maximum), (($opmIV|Where-Object{$_.wasted}).Count))
  }

  # ---- 5. Arcane Soul windows ----
  Write-Output ("ARCANE SOUL: {0} windows" -f $soulIV.Count)
  foreach ($w in $soulIV) {
    $n = ($barr | Where-Object { $_.timestamp -ge $w.s -and $_.timestamp -le $w.e }).Count
    $entrySalvo = Value-At $salvoTL ($w.s - 50)
    Write-Output ("    t={0,6:N1}s  dur={1:N1}s  Barrages inside={2}  Salvo entering={3}" -f (($w.s-$t0)/1000),(($w.e-$w.s)/1000),$n,$entrySalvo)
  }

  # ---- 6. cooldown usage ----
  $surges = $casts | Where-Object { $_.abilityGameID -eq $C_SURGE }
  $toms   = $casts | Where-Object { $_.abilityGameID -eq $C_TOM }
  Write-Output ("COOLDOWNS: Arcane Surge x{0}, Touch of the Magi x{1}, Arcane Orb x{2} (hard casts)" -f $surges.Count,$toms.Count,($casts|Where-Object{$_.abilityGameID -eq $C_ORB}).Count)
  foreach ($s in $surges) {
    $nearTom = $toms | Where-Object { [math]::Abs($_.timestamp - $s.timestamp) -lt 8000 }
    Write-Output ("    Surge t={0,6:N1}s -> ToM within 8s: {1}" -f (($s.timestamp-$t0)/1000), $(if($nearTom){"yes (dt=$([math]::Round(($nearTom[0].timestamp-$s.timestamp)/1000,1))s)"}else{"NO"}))
  }
  $tomGaps = @()
  for ($i=1; $i -lt $toms.Count; $i++) { $tomGaps += ($toms[$i].timestamp - $toms[$i-1].timestamp)/1000 }
  if ($tomGaps.Count) { Write-Output ("    ToM gaps (cd=45s): {0}" -f (($tomGaps | ForEach-Object { "{0:N1}" -f $_ }) -join ", ")) }
  $surgeGaps = @()
  for ($i=1; $i -lt $surges.Count; $i++) { $surgeGaps += ($surges[$i].timestamp - $surges[$i-1].timestamp)/1000 }
  if ($surgeGaps.Count) { Write-Output ("    Surge gaps (cd=90s): {0}" -f (($surgeGaps | ForEach-Object { "{0:N1}" -f $_ }) -join ", ")) }

  # ---- 7. cast activity / gaps ----
  $ordered = $casts | Where-Object { $_.abilityGameID -in @($C_MISSILES,$C_BARRAGE,$C_PBOLT,$C_BLAST,$C_ORB,$C_TOM,$C_SURGE) } | Sort-Object timestamp
  $gaps = @()
  for ($i=1; $i -lt $ordered.Count; $i++) { $gaps += [pscustomobject]@{ dt=($ordered[$i].timestamp-$ordered[$i-1].timestamp)/1000; after=$map.([string]$ordered[$i-1].abilityGameID); before=$map.([string]$ordered[$i].abilityGameID); t=($ordered[$i-1].timestamp-$t0)/1000 } }
  $bigGaps = $gaps | Where-Object { $_.dt -gt 2.6 }
  $lost = ($bigGaps | ForEach-Object { $_.dt - 2.6 } | Measure-Object -Sum).Sum
  Write-Output ("ACTIVITY: {0} GCD casts | {1} gaps >2.6s | ~{2:N1}s of dead time in those gaps" -f $ordered.Count,$bigGaps.Count,$lost)
  $bigGaps | Sort-Object dt -Descending | Select-Object -First 6 | ForEach-Object { Write-Output ("    t={0,6:N1}s gap={1:N2}s  after {2} -> {3}" -f $_.t,$_.dt,$_.after,$_.before) }

  $summary += [pscustomobject]@{
    Fight=$F; Barrages=$rows.Count; AvgSalvo=[math]::Round($avg,1)
    PctMaxSalvo=[math]::Round(100*$buckets['25 (max)']/[math]::Max($nonSoul.Count,1),1)
    SalvoCapSec=[math]::Round($capTime/1000,1)
    CCWasted=$ccRefresh; CC3Pct=[math]::Round(100*$cc3Time/($tEnd-$t0),1)
    PBProcs=$pbIV.Count; PBAvgHold=[math]::Round((($pbHold|Measure-Object -Average).Average),2); PBLost=$pbWasted
    SoulWindows=$soulIV.Count; Surges=$surges.Count; ToMs=$toms.Count
    DeadTime=[math]::Round($lost,1)
  }
  Write-Output ""
}

Write-Output "==================== CROSS-FIGHT SUMMARY ===================="
$summary | Format-Table -AutoSize
