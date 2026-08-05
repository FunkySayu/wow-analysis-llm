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
function New-Ivs($evs,$id){
  $iv=New-Object System.Collections.ArrayList; $st=$null
  foreach($e in $evs){ if([string]$e.abilityGameID -ne $id){continue}
    if($e.type -eq 'applybuff'){$st=[long]$e.timestamp}
    elseif($e.type -eq 'removebuff'){ if($null -ne $st){[void]$iv.Add([pscustomobject]@{s=$st;e=[long]$e.timestamp}); $st=$null} } }
  return $iv }
function Test-In($iv,$t){ foreach($i in $iv){ if($t -ge $i.s -and $t -le $i.e){return $true} }; return $false }

$short=@{5143='AM';44425='AB!';1295924='PB';30451='ABl';153626='AO';321507='ToM';365350='AS'}
$full=@{5143='Arcane Missiles';44425='Arcane Barrage';1295924='Prismatic Bolt';30451='Arcane Blast';153626='Arcane Orb';321507='Touch of the Magi';365350='Arcane Surge'}

# ---------- player histogram + kpis ----------
$buckets=@{'25'=0;'20-24'=0;'15-19'=0;'12-14'=0;'<12'=0}
$allSalvo=@(); $totBarr=0; $totNonSoul=0; $intuN=0
$castTotals=@{}
foreach($FI in 1,3,7,8,9){
  $casts=@(Get-Ev "$root\scratch\casts_f$FI.json" | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
  $buffs=@(Get-Ev "$root\scratch\buffev_f$FI.json" | Sort-Object timestamp)
  $salvoTL=New-StackTL $buffs '1242974'
  $soulIV=New-Ivs $buffs '451038'; $intuIV=New-Ivs $buffs '1223797'
  foreach($c in $casts){ $k=$full[[int]$c.abilityGameID]; if($k){ $castTotals[$k]=1+$(if($castTotals.ContainsKey($k)){$castTotals[$k]}else{0}) } }
  foreach($b in @($casts|Where-Object{$_.abilityGameID -eq 44425})){
    $totBarr++
    $ts=[long]$b.timestamp
    if(Test-In $soulIV $ts){continue}
    $totNonSoul++
    if(Test-In $intuIV $ts){$intuN++}
    $s=Get-ValAt $salvoTL $ts; $allSalvo+=$s
    if($s -ge 25){$buckets['25']++} elseif($s -ge 20){$buckets['20-24']++} elseif($s -ge 15){$buckets['15-19']++} elseif($s -ge 12){$buckets['12-14']++} else{$buckets['<12']++}
  }
}
Write-Output "PLAYER HISTOGRAM (n=$totNonSoul non-Soul barrages, 5 pulls)"
foreach($k in '25','20-24','15-19','12-14','<12'){ Write-Output ("  {0,-6} {1,3}  {2:N1}%" -f $k,$buckets[$k],(100*$buckets[$k]/$totNonSoul)) }
Write-Output ("  avg salvo {0:N1} | intuition {1:N0}%" -f (($allSalvo|Measure-Object -Average).Average),(100*$intuN/$totNonSoul))
Write-Output "PLAYER CAST TOTALS (per 300s = total/5)"
$castTotals.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { Write-Output ("  {0,-20} {1,4}  -> {2:N1}/pull" -f $_.Key,$_.Value,($_.Value/5)) }

# ---------- player sequence window: fight 8, 40-88s ----------
Write-Output ""
Write-Output "PLAYER SEQUENCE (fight 8)"
$casts=@(Get-Ev "$root\scratch\casts_f8.json" | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
$buffs=@(Get-Ev "$root\scratch\buffev_f8.json" | Sort-Object timestamp)
$t0=[long]$casts[0].timestamp
$salvoTL=New-StackTL $buffs '1242974'; $ccTL=New-StackTL $buffs '263725'
$soulIV=New-Ivs $buffs '451038'; $intuIV=New-Ivs $buffs '1223797'
$out=@()
foreach($c in $casts){
  $rel=[math]::Round(([long]$c.timestamp-$t0)/1000.0,2)
  if($rel -lt 40 -or $rel -gt 88){continue}
  $k=$short[[int]$c.abilityGameID]; if(-not $k){continue}
  $ts=[long]$c.timestamp
  $out += ('{{"t":{0},"a":"{1}","s":{2},"cc":{3},"i":{4}}}' -f $rel,$k,(Get-ValAt $salvoTL $ts),(Get-ValAt $ccTL $ts),$(if(Test-In $intuIV $ts){'true'}else{'false'}))
}
Write-Output ("[" + ($out -join ",") + "]")
