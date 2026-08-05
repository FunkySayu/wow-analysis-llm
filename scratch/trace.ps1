param([int]$F=8,[double]$From=40,[double]$To=95)
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

$casts=@(Get-Ev "$root\scratch\casts_f$F.json" | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
$buffs=@(Get-Ev "$root\scratch\buffev_f$F.json" | Sort-Object timestamp)
$t0=[long]$casts[0].timestamp
$salvoTL=New-StackTL $buffs '1242974'
$ccTL=New-StackTL $buffs '263725'
$cumTL=New-StackTL $buffs '1296930'
$soulIV=New-Ivs $buffs '451038'
$pbIV=New-Ivs $buffs '1295942'
$opmIV=New-Ivs $buffs '1277009'
$intuIV=New-Ivs $buffs '1223797'

$names=@{5143='Arcane Missiles';44425='Arcane Barrage';1295924='PRISMATIC BOLT';30451='Arcane Blast';153626='Arcane Orb';321507='Touch of the Magi';365350='Arcane Surge';80353='Time Warp';1250533='Flask'}
Write-Output ("FIGHT {0} trace  {1}s - {2}s     [Salvo/25 | CC | CumPow | flags]" -f $F,$From,$To)
Write-Output ("{0,7}  {1,-18} {2,6} {3,4} {4,4}  {5}" -f 'time','cast','salvo','cc','cum','flags')
foreach($c in $casts){
  $rel=([long]$c.timestamp-$t0)/1000.0
  if($rel -lt $From -or $rel -gt $To){continue}
  $ts=[long]$c.timestamp
  $s=Get-ValAt $salvoTL $ts; $cc=Get-ValAt $ccTL $ts; $cum=Get-ValAt $cumTL $ts
  $fl=@()
  if(Test-In $soulIV $ts){$fl+='ARCANE-SOUL'}
  if(Test-In $pbIV $ts){$fl+='PBolt-proc-held'}
  if(Test-In $opmIV $ts){$fl+='OverpwrMissiles-held'}
  if(Test-In $intuIV $ts){$fl+='INTUITION'}
  $nm = $names[[int]$c.abilityGameID]; if(-not $nm){$nm=$c.abilityGameID}
  $mark=''
  if([int]$c.abilityGameID -eq 44425 -and -not (Test-In $soulIV $ts)){
    if($s -ge 25){$mark='<= max salvo, correct'}
    elseif($s -ge 12 -and $cc -ge 1){$mark='<= early dump (legal: CC banked)'}
    else{$mark='<== OFF-PLAN: no CC and salvo<25'}
  }
  Write-Output ("{0,7:N1}  {1,-18} {2,4}   {3,2}   {4,2}   {5} {6}" -f $rel,$nm,$s,$cc,$cum,($fl -join ','),$mark)
}
