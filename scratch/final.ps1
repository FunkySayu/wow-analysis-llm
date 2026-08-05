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

$rows=@()
foreach($FI in 1,3,7,8,9){
  $casts=@(Get-Ev "$root\scratch\casts_f$FI.json" | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
  $buffs=@(Get-Ev "$root\scratch\buffev_f$FI.json" | Sort-Object timestamp)
  $t0=[long]$casts[0].timestamp; $tE=[long]$casts[-1].timestamp; $dur=($tE-$t0)/1000
  $salvoTL=New-StackTL $buffs '1242974'
  $ccTL=New-StackTL $buffs '263725'
  $soulIV=New-Ivs $buffs '451038'
  $intuIV=New-Ivs $buffs '1223797'

  $barr=@($casts|Where-Object{$_.abilityGameID -eq 44425})
  $nonSoul=@($barr|Where-Object{ -not (Test-In $soulIV ([long]$_.timestamp)) })
  $withIntu=@($nonSoul|Where-Object{ Test-In $intuIV ([long]$_.timestamp) })
  $sal=@($nonSoul|ForEach-Object{ Get-ValAt $salvoTL ([long]$_.timestamp) })

  # salvo overcap: time at 25
  $cap=0;$prev=$null
  foreach($p in $salvoTL){ if($null -ne $prev -and $prev.v -ge 25){$cap+=($p.t-$prev.t)}; $prev=$p }

  # missiles above gate
  $mis=@($casts|Where-Object{$_.abilityGameID -eq 5143})
  $mAbove=@($mis|Where-Object{ (Get-ValAt $salvoTL ([long]$_.timestamp)) -ge 12 }).Count

  # arcane soul windows
  $soulQ=@()
  foreach($w in $soulIV){
    $nb=@($barr|Where-Object{[long]$_.timestamp -ge $w.s -and [long]$_.timestamp -le $w.e}).Count
    $soulQ += "$(Get-ValAt $salvoTL ($w.s-100))->${nb}B"
  }

  # cooldowns
  $tom=@($casts|Where-Object{$_.abilityGameID -eq 321507})
  $srg=@($casts|Where-Object{$_.abilityGameID -eq 365350})
  $orb=@($casts|Where-Object{$_.abilityGameID -eq 153626})
  $tomGap=@(); for($i=1;$i -lt $tom.Count;$i++){$tomGap+=([long]$tom[$i].timestamp-[long]$tom[$i-1].timestamp)/1000}
  $srgGap=@(); for($i=1;$i -lt $srg.Count;$i++){$srgGap+=([long]$srg[$i].timestamp-[long]$srg[$i-1].timestamp)/1000}

  $rows += [pscustomobject]@{
    Fight=$FI
    Barrages=$barr.Count
    NonSoul=$nonSoul.Count
    AvgSalvo=[math]::Round((($sal|Measure-Object -Average).Average),1)
    PctAt25=[math]::Round(100*@($sal|Where-Object{$_ -ge 25}).Count/$nonSoul.Count,0)
    IntuitionPct=[math]::Round(100*$withIntu.Count/$nonSoul.Count,0)
    SalvoCappedSec=[math]::Round($cap/1000,1)
    MissilesAboveGate="$mAbove/$($mis.Count)"
    SoulWindows=($soulQ -join ' ')
    OrbCasts=$orb.Count
    ToMavgGap=[math]::Round((($tomGap|Measure-Object -Average).Average),1)
    SurgeAvgGap=[math]::Round((($srgGap|Measure-Object -Average).Average),1)
  }
}
$rows | Format-Table -AutoSize
Write-Output ""
Write-Output ("TOTALS: barrages {0} | non-soul {1} | at max salvo {2:N0}% | with Intuition {3:N0}%" -f `
  (($rows|Measure-Object Barrages -Sum).Sum),(($rows|Measure-Object NonSoul -Sum).Sum),(($rows|Measure-Object PctAt25 -Average).Average),(($rows|Measure-Object IntuitionPct -Average).Average))
Write-Output ("Avg Salvo per Barrage: {0:N1}   |  Salvo capped {1:N1}s/fight avg" -f (($rows|Measure-Object AvgSalvo -Average).Average),(($rows|Measure-Object SalvoCappedSec -Average).Average))
Write-Output ("Arcane Orb hard casts: {0:N1}/fight (sim: 1)  | ToM gap {1:N1}s (cd 45) | Surge gap {2:N1}s (cd 90)" -f `
  (($rows|Measure-Object OrbCasts -Average).Average),(($rows|Measure-Object ToMavgGap -Average).Average),(($rows|Measure-Object SurgeAvgGap -Average).Average))
