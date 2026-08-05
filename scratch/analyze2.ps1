param([int[]]$Fights = @(1,3,7,8,9))
$ErrorActionPreference='Stop'
$root = Split-Path $PSScriptRoot -Parent
$map = Get-Content "$root\scratch\abilitymap.json" -Raw | ConvertFrom-Json

$SALVO='1242974'; $CC='263725'; $PBBUFF='1295942'; $OPM='1277009'; $INTU='1223797'; $SOUL='451038'; $CUMUL='1296930'
$C_MISSILES=5143; $C_BARRAGE=44425; $C_PBOLT=1295924; $C_BLAST=30451; $C_ORB=153626; $C_TOM=321507; $C_SURGE=365350

function Get-Ev($f){ (Get-Content $f -Raw | ConvertFrom-Json).data.reportData.report.events.data }

$agg = @{ mTot=0; mOver=0; mOverSum=0; bTot=0; bLegalMax=0; bLegalCC=0; bSoul=0; bIllegal=0; bIllegalSalvo=@();
          pbTot=0; pb8=0; pbLow=@(); ccWasteAtMissiles=0 }

foreach($F in $Fights){
  $casts = @(Get-Ev "$root\scratch\casts_f$F.json") | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp
  $buffs = @(Get-Ev "$root\scratch\buffev_f$F.json") | Sort-Object timestamp
  $t0 = $casts[0].timestamp; $tEnd = $casts[-1].timestamp

  function StackTL($id){
    $tl=New-Object System.Collections.ArrayList; $cur=0
    foreach($e in ($buffs|Where-Object{[string]$_.abilityGameID -eq $id})){
      switch($e.type){ 'applybuff'{$cur=1} 'applybuffstack'{$cur=$e.stack} 'removebuffstack'{$cur=$e.stack} 'removebuff'{$cur=0} }
      [void]$tl.Add([pscustomobject]@{t=$e.timestamp;v=$cur})
    }; ,$tl
  }
  function ValAt($tl,$time){ $v=0; foreach($p in $tl){ if($p.t -lt $time){$v=$p.v} else {break} }; $v }
  function Ivs($id){
    $iv=New-Object System.Collections.ArrayList; $s=$null
    foreach($e in ($buffs|Where-Object{[string]$_.abilityGameID -eq $id})){
      if($e.type -eq 'applybuff'){$s=$e.timestamp}
      elseif($e.type -eq 'refreshbuff'){ if($s -ne $null){[void]$iv.Add([pscustomobject]@{s=$s;e=$e.timestamp}); $s=$e.timestamp} }
      elseif($e.type -eq 'removebuff'){ if($s -ne $null){[void]$iv.Add([pscustomobject]@{s=$s;e=$e.timestamp}); $s=$null} }
    }
    if($s -ne $null){[void]$iv.Add([pscustomobject]@{s=$s;e=$tEnd})}; ,$iv
  }
  function InIv($iv,$t){ foreach($i in $iv){ if($t -ge $i.s -and $t -le $i.e){return $true} }; $false }

  $salvo=StackTL $SALVO; $ccTL=StackTL $CC; $cumTL=StackTL $CUMUL
  $soulIV=Ivs $SOUL

  Write-Output "======== FIGHT $F ========"

  # --- ARCANE MISSILES vs APL gate (salvo < 12) ---
  $mis = $casts | Where-Object {$_.abilityGameID -eq $C_MISSILES}
  $mRows = foreach($m in $mis){ [pscustomobject]@{ t=[math]::Round(($m.timestamp-$t0)/1000,1); salvo=(ValAt $salvo $m.timestamp); cc=(ValAt $ccTL $m.timestamp) } }
  $over = $mRows | Where-Object { $_.salvo -ge 12 }
  $overcapWaste = ($over | ForEach-Object { [math]::Max(0, ($_.salvo + 10) - 25) } | Measure-Object -Sum).Sum
  Write-Output ("ARCANE MISSILES: {0} casts | APL gate = cast only when Salvo<12" -f $mRows.Count)
  Write-Output ("   cast at Salvo>=12 (off-plan): {0} ({1:N0}%)  | avg Salvo on those: {2:N1}" -f $over.Count,(100*$over.Count/$mRows.Count),(($over|Measure-Object salvo -Average).Average))
  Write-Output ("   ~Salvo stacks overflowed by those casts (est, +10.5/channel): {0:N0}" -f $overcapWaste)
  $h=@{}; foreach($r in $mRows){ $b=[math]::Floor($r.salvo/5)*5; $h["$b-$($b+4)"] = 1 + $(if($h.ContainsKey("$b-$($b+4)")){$h["$b-$($b+4)"]}else{0}) }
  Write-Output ("   Salvo at Missiles cast: " + (($h.GetEnumerator()|Sort-Object {[int]($_.Key -split '-')[0]}|ForEach-Object{"$($_.Key):$($_.Value)"}) -join "  "))

  # --- ARCANE BARRAGE vs APL gate ---
  $barr = $casts | Where-Object {$_.abilityGameID -eq $C_BARRAGE}
  $legalMax=0;$legalCC=0;$soulN=0;$illegal=0; $illList=@()
  foreach($b in $barr){
    $s=(ValAt $salvo $b.timestamp); $c=(ValAt $ccTL $b.timestamp)
    if(InIv $soulIV $b.timestamp){$soulN++}
    elseif($s -ge 25){$legalMax++}
    elseif($s -ge 12 -and $c -ge 1){$legalCC++}
    else{$illegal++; $illList += [pscustomobject]@{t=[math]::Round(($b.timestamp-$t0)/1000,1);salvo=$s;cc=$c}}
  }
  Write-Output ("ARCANE BARRAGE: {0} casts" -f $barr.Count)
  Write-Output ("   in Arcane Soul (free)          : {0}" -f $soulN)
  Write-Output ("   at Salvo=25 (Intuition +25%)   : {0}" -f $legalMax)
  Write-Output ("   Salvo>=12 + Clearcasting banked: {0}   <- APL-sanctioned early dump" -f $legalCC)
  Write-Output ("   OFF-PLAN (Salvo<12 or no CC)   : {0}   avg Salvo {1:N1}" -f $illegal,$(if($illList){($illList|Measure-Object salvo -Average).Average}else{0}))
  if($illList){ Write-Output ("      e.g. " + (($illList|Select-Object -First 8|ForEach-Object{"t=$($_.t)s salvo=$($_.salvo) cc=$($_.cc)"}) -join " | ")) }

  # --- PRISMATIC BOLT vs 4pc gate (cumulative_power = 8) ---
  $pb = $casts | Where-Object {$_.abilityGameID -eq $C_PBOLT}
  $pbRows = foreach($p in $pb){ [pscustomobject]@{t=[math]::Round(($p.timestamp-$t0)/1000,1); cum=(ValAt $cumTL $p.timestamp); salvo=(ValAt $salvo $p.timestamp); cc=(ValAt $ccTL $p.timestamp)} }
  $at8 = ($pbRows|Where-Object{$_.cum -ge 8}).Count
  Write-Output ("PRISMATIC BOLT: {0} casts | at Cumulative Power 8/8: {1} ({2:N0}%) | avg CumPower {3:N1}" -f $pbRows.Count,$at8,(100*$at8/[math]::Max($pbRows.Count,1)),(($pbRows|Measure-Object cum -Average).Average))
  Write-Output ("   avg Salvo when PB cast: {0:N1}  (PB grants +4 Salvo; casting near cap overflows)" -f (($pbRows|Measure-Object salvo -Average).Average))
  $pbOver = ($pbRows|Where-Object{$_.salvo -gt 21}).Count
  Write-Output ("   PB cast at Salvo>21 (its +4 overflows): {0}" -f $pbOver)

  $agg.mTot+=$mRows.Count; $agg.mOver+=$over.Count; $agg.mOverSum+=$overcapWaste
  $agg.bTot+=$barr.Count; $agg.bLegalMax+=$legalMax; $agg.bLegalCC+=$legalCC; $agg.bSoul+=$soulN; $agg.bIllegal+=$illegal
  $agg.pbTot+=$pbRows.Count; $agg.pb8+=$at8
  Write-Output ""
}
Write-Output "========= AGGREGATE (5 single-target pulls) ========="
Write-Output ("Missiles: {0} casts, {1} ({2:N0}%) cast at Salvo>=12 against APL gate; ~{3:N0} Salvo stacks overflowed" -f $agg.mTot,$agg.mOver,(100*$agg.mOver/$agg.mTot),$agg.mOverSum)
Write-Output ("Barrage : {0} casts -> Soul {1} | Salvo25 {2} ({3:N0}%) | CC-dump {4} | OFF-PLAN {5} ({6:N0}%)" -f $agg.bTot,$agg.bSoul,$agg.bLegalMax,(100*$agg.bLegalMax/$agg.bTot),$agg.bLegalCC,$agg.bIllegal,(100*$agg.bIllegal/$agg.bTot))
Write-Output ("PrismBolt: {0} casts, {1} ({2:N0}%) at Cumulative Power 8/8" -f $agg.pbTot,$agg.pb8,(100*$agg.pb8/$agg.pbTot))
