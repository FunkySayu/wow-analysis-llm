param([int[]]$Fights=@(8,9))
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

$SALVOID='1242974'; $CCID='263725'; $SOULID='451038'
$C_MISSILES=5143; $C_BARRAGE=44425
$MISSILE_DMG=7268   # Arcane Missiles damage tick

foreach($F in $Fights){
  $casts=@(Get-Ev "$root\scratch\casts_f$F.json" | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
  $buffs=@(Get-Ev "$root\scratch\buffev_f$F.json" | Sort-Object timestamp)
  $dmg  =@(Get-Ev "$root\scratch\dmgev_f$F.json"  | Sort-Object timestamp)
  $t0=[long]$casts[0].timestamp; $tEnd=[long]$casts[-1].timestamp
  $salvoTL=New-StackTL $buffs $SALVOID
  $ccTL=New-StackTL $buffs $CCID

  Write-Output "================ FIGHT $F ================"
  # what damage ability id do missiles use?
  $ids = $dmg | Group-Object abilityGameID | Sort-Object Count -Descending | Select-Object -First 5
  Write-Output ("top damage ability ids: " + (($ids|ForEach-Object{"$($_.Name):$($_.Count)"}) -join "  "))

  # --- true dead time: for each cast, find when its "occupancy" ends ---
  $missileTicks = @($dmg | Where-Object { $_.abilityGameID -eq $MISSILE_DMG })
  Write-Output ("missile damage ticks: {0} over {1} Missiles casts" -f $missileTicks.Count, @($casts|Where-Object{$_.abilityGameID -eq $C_MISSILES}).Count)

  $mis=@($casts|Where-Object{$_.abilityGameID -eq $C_MISSILES})
  $gapList=@(); $chanList=@()
  for($i=0;$i -lt $mis.Count;$i++){
    $st=[long]$mis[$i].timestamp
    $nextCast = $casts | Where-Object { [long]$_.timestamp -gt $st } | Select-Object -First 1
    if(-not $nextCast){continue}
    $nt=[long]$nextCast.timestamp
    $ticks = @($missileTicks | Where-Object { [long]$_.timestamp -ge $st -and [long]$_.timestamp -le $nt })
    if($ticks.Count -eq 0){continue}
    $last=[long]$ticks[-1].timestamp
    $chanList += ($last-$st)/1000.0
    $gapList  += ($nt-$last)/1000.0
  }
  $g=$gapList | Sort-Object
  Write-Output ("MISSILES channel->next-cast delay: n={0} avg={1:N2}s median={2:N2}s p75={3:N2}s p90={4:N2}s" -f `
    $g.Count,(($g|Measure-Object -Average).Average),$g[[int]($g.Count*0.5)],$g[[int]($g.Count*0.75)],$g[[int]($g.Count*0.9)])
  Write-Output ("   (avg observed channel length {0:N2}s, ticks/channel {1:N1})" -f (($chanList|Measure-Object -Average).Average), ($missileTicks.Count/$mis.Count))
  $slow = @($gapList | Where-Object {$_ -gt 0.6})
  Write-Output ("   delays >0.6s after channel end: {0}/{1}  totalling {2:N1}s" -f $slow.Count,$gapList.Count,(($slow|Measure-Object -Sum).Sum))

  # --- overall cast-to-cast pacing ---
  $inst = @($casts | Where-Object { $_.abilityGameID -in @($C_BARRAGE,1295924,153626,321507) })
  $ig=@()
  foreach($c in $inst){ $n=$casts|Where-Object{[long]$_.timestamp -gt [long]$c.timestamp}|Select-Object -First 1; if($n){$ig+=([long]$n.timestamp-[long]$c.timestamp)/1000.0} }
  $ig=$ig|Sort-Object
  Write-Output ("INSTANT-cast -> next cast gap: median={0:N2}s p75={1:N2}s p90={2:N2}s  (GCD floor should be ~1.0-1.2s)" -f $ig[[int]($ig.Count*0.5)],$ig[[int]($ig.Count*0.75)],$ig[[int]($ig.Count*0.9)])

  # --- Arcane Soul windows ---
  $soulEv=@($buffs|Where-Object{$_.abilityGameID -eq 451038}|Sort-Object timestamp)
  Write-Output "ARCANE SOUL WINDOWS:"
  for($i=0;$i -lt $soulEv.Count;$i+=2){
    $s=[long]$soulEv[$i].timestamp; $e=[long]$soulEv[$i+1].timestamp
    $inWin=@($casts|Where-Object{[long]$_.timestamp -ge $s -and [long]$_.timestamp -le $e})
    $nb=@($inWin|Where-Object{$_.abilityGameID -eq $C_BARRAGE}).Count
    $entry=Get-ValAt $salvoTL ($s-100)
    $seq=($inWin|ForEach-Object{ switch($_.abilityGameID){44425{'Barrage'}5143{'Missiles'}1295924{'PBolt'}30451{'Blast'}153626{'Orb'}321507{'ToM'}365350{'Surge'}default{$_.abilityGameID}} }) -join " > "
    Write-Output ("   t={0,6:N1}s dur={1:N1}s  Barrages={2}  SalvoEntering={3}/25   casts: {4}" -f (($s-$t0)/1000),(($e-$s)/1000),$nb,$entry,$seq)
  }

  # --- Clearcasting: what was cast while sitting at 3/3 ---
  $cc3=@()
  $prev=$null
  foreach($p in $ccTL){ if($null -ne $prev -and $prev.v -ge 3){ $cc3+=[pscustomobject]@{s=$prev.t;e=$p.t} }; $prev=$p }
  $castsAt3=@()
  foreach($c in $casts){ foreach($w in $cc3){ if([long]$c.timestamp -ge $w.s -and [long]$c.timestamp -le $w.e){ $castsAt3+=$c; break } } }
  Write-Output ("CASTS MADE WHILE CLEARCASTING WAS CAPPED AT 3/3 ({0} casts):" -f $castsAt3.Count)
  $castsAt3 | Group-Object abilityGameID | Sort-Object Count -Descending | ForEach-Object {
    $n=switch($_.Name){'44425'{'Arcane Barrage'}'5143'{'Arcane Missiles'}'1295924'{'Prismatic Bolt'}'30451'{'Arcane Blast'}'153626'{'Arcane Orb'}'321507'{'Touch of the Magi'}'365350'{'Arcane Surge'}default{$_.Name}}
    Write-Output ("     {0,-20} {1}" -f $n,$_.Count) }
  Write-Output ""
}
