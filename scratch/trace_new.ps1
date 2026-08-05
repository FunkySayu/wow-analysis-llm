param([int]$F=1,[double]$From=95,[double]$To=150)
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
$casts=@(Get-Ev "$root\scratch\n_castsR_f$F.json" | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
$buffs=@(Get-Ev "$root\scratch\n_buffs_f$F.json" | Sort-Object timestamp)
$t0=[long]$casts[0].timestamp
$salvo=New-StackTL $buffs '1242974'; $cc=New-StackTL $buffs '263725'; $cum=New-StackTL $buffs '1296930'
$n=@{5143='Missiles';44425='BARRAGE';1295924='PrismBolt';30451='Blast';153626='Orb';12051='Evocation'}
Write-Output ("PULL {0}   {1}s-{2}s      salvo | cc | cumPow | mana%" -f $F,$From,$To)
foreach($c in $casts){
  $rel=([long]$c.timestamp-$t0)/1000.0
  if($rel -lt $From -or $rel -gt $To){continue}
  $ts=[long]$c.timestamp
  $s=Get-ValAt $salvo $ts
  $r=@($c.classResources | Where-Object {$_.type -eq 0})
  $mp=if($r.Count){[math]::Round(100.0*$r[0].amount/$r[0].max)}else{100}
  $nm=$n[[int]$c.abilityGameID]; if(-not $nm){$nm=$c.abilityGameID}
  $mark=''
  if([int]$c.abilityGameID -eq 5143 -and $s -ge 15){$mark='  <== Missiles started at '+$s+' : channel will cap and waste ~'+[math]::Round($s+11.8-25)+' stacks'}
  if([int]$c.abilityGameID -eq 44425 -and $s -ge 25){$mark='  <- max salvo'}
  Write-Output ("{0,7:N1}  {1,-10} {2,4} {3,3} {4,3} {5,4}%{6}" -f $rel,$nm,$s,(Get-ValAt $cc $ts),(Get-ValAt $cum $ts),$mp,$mark)
}
