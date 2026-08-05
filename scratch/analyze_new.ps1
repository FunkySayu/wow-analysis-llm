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
function New-Ivs($evs,$id){
  $iv=New-Object System.Collections.ArrayList; $st=$null
  foreach($e in $evs){ if([string]$e.abilityGameID -ne $id){continue}
    if($e.type -eq 'applybuff'){$st=[long]$e.timestamp}
    elseif($e.type -eq 'removebuff'){ if($null -ne $st){[void]$iv.Add([pscustomobject]@{s=$st;e=[long]$e.timestamp}); $st=$null} } }
  return $iv }
function Test-In($iv,$t){ foreach($i in $iv){ if($t -ge $i.s -and $t -le $i.e){return $true} }; return $false }

$SALVOID='1242974'; $CCID='263725'; $SOULID='451038'; $CUMID='1296930'; $INTUID='1223797'
$C_AM=5143; $C_AB=44425; $C_PB=1295924; $C_ABl=30451; $C_AO=153626
$names=@{5143='Arcane Missiles';44425='Arcane Barrage';1295924='Prismatic Bolt';30451='Arcane Blast';153626='Arcane Orb';321507='Touch of the Magi';365350='Arcane Surge';12051='Evocation';80353='Time Warp'}

$G=@{bTot=0;bHi=0;b25=0;bCC=0;bBad=0;intu=0;salSum=0;mTot=0;mOver=0;lowN=0}
foreach($F in 1,2){
  $casts=@(Get-Ev "$root\scratch\n_castsR_f$F.json" | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
  $buffs=@(Get-Ev "$root\scratch\n_buffs_f$F.json" | Sort-Object timestamp)
  $res  =@(Get-Ev "$root\scratch\n_res_f$F.json"   | Sort-Object timestamp)
  $t0=[long]$casts[0].timestamp; $tE=[long]$casts[-1].timestamp; $dur=($tE-$t0)/1000

  $salvoTL=New-StackTL $buffs $SALVOID
  $ccTL   =New-StackTL $buffs $CCID
  $cumTL  =New-StackTL $buffs $CUMID
  $soulIV =New-Ivs $buffs $SOULID
  $intuIV =New-Ivs $buffs $INTUID

  function ManaPct($c){ $r=@($c.classResources | Where-Object {$_.type -eq 0}); if($r.Count -eq 0){return 100}; return 100.0*$r[0].amount/$r[0].max }

  Write-Output "================= PULL $F  ($([math]::Round($dur,1))s) ================="
  Write-Output ("casts: " + ((@($casts | Group-Object abilityGameID | Sort-Object Count -Descending | ForEach-Object { $n=$names[[int]$_.Name]; if(-not $n){$n=$_.Name}; "$n x$($_.Count)" })) -join " | "))
  Write-Output ("Arcane Soul windows: {0}" -f $soulIV.Count)

  # mana profile
  $manaSeries = foreach($c in $casts){ ManaPct $c }
  $lowCasts = @($casts | Where-Object { (ManaPct $_) -lt $ManaFloor })
  Write-Output ("mana: min {0:N1}% | casts under {1}%: {2} of {3}" -f (($manaSeries|Measure-Object -Minimum).Minimum),$ManaFloor,$lowCasts.Count,$casts.Count)

  # ---- BARRAGE ----
  $barr=@($casts|Where-Object{$_.abilityGameID -eq $C_AB})
  $b25=0;$bCC=0;$bBad=0;$bLow=0;$intuN=0;$sal=@();$badL=@()
  foreach($b in $barr){
    $ts=[long]$b.timestamp
    if(Test-In $soulIV $ts){continue}
    $mp=ManaPct $b
    if($mp -lt $ManaFloor){$bLow++; continue}
    $s=Get-ValAt $salvoTL $ts; $c=Get-ValAt $ccTL $ts
    $sal+=$s
    if(Test-In $intuIV $ts){$intuN++}
    if($s -ge 25){$b25++}
    elseif($s -ge 12 -and $c -ge 1){$bCC++}
    else{$bBad++; $badL+=[pscustomobject]@{t=[math]::Round(($ts-$t0)/1000,1);s=$s;cc=$c;m=[math]::Round($mp)}}
  }
  $n=$sal.Count
  Write-Output ("BARRAGE: {0} total | {1} excluded (mana<{2}%) | {3} scored" -f $barr.Count,$bLow,$ManaFloor,$n)
  Write-Output ("   avg Salvo {0:N1}/25 | at 25: {1} ({2:N0}%) | Intuition captured: {3} ({4:N0}%)" -f (($sal|Measure-Object -Average).Average),$b25,(100*$b25/$n),$intuN,(100*$intuN/$n))
  Write-Output ("   CC-dump (>=12 +CC): {0} ({1:N0}%) | OFF-PLAN: {2} ({3:N0}%)" -f $bCC,(100*$bCC/$n),$bBad,(100*$bBad/$n))
  if($badL.Count){ Write-Output ("   off-plan (salvo/cc/mana%): " + (($badL|ForEach-Object{"$($_.s)/$($_.cc)/$($_.m)"}) -join "  ")) }
  $h=@{'25'=0;'20-24'=0;'15-19'=0;'12-14'=0;'<12'=0}
  foreach($v in $sal){ if($v -ge 25){$h['25']++} elseif($v -ge 20){$h['20-24']++} elseif($v -ge 15){$h['15-19']++} elseif($v -ge 12){$h['12-14']++} else{$h['<12']++} }
  Write-Output ("   histogram: " + (('25','20-24','15-19','12-14','<12' | ForEach-Object { "$_=$($h[$_]) ($([math]::Round(100*$h[$_]/$n))%)" }) -join "  "))

  # ---- MISSILES ----
  $mis=@($casts|Where-Object{$_.abilityGameID -eq $C_AM})
  $mS=@(foreach($m in $mis){ Get-ValAt $salvoTL ([long]$m.timestamp) })
  $mOver=@($mS|Where-Object{$_ -ge 12}).Count
  Write-Output ("MISSILES: {0} casts | avg Salvo at cast {1:N1} | above the <12 gate: {2} ({3:N0}%)" -f $mis.Count,(($mS|Measure-Object -Average).Average),$mOver,(100*$mOver/$mis.Count))

  # ---- salvo cap time ----
  $cap=0;$prev=$null
  foreach($p in $salvoTL){ if($null -ne $prev -and $prev.v -ge 25){$cap+=($p.t-$prev.t)}; $prev=$p }
  Write-Output ("SALVO pinned at 25/25: {0:N1}s ({1:N0}% of pull)" -f ($cap/1000),(100*$cap/($tE-$t0)))

  # ---- prismatic bolt ----
  $pb=@($casts|Where-Object{$_.abilityGameID -eq $C_PB})
  $pbC=@(foreach($p in $pb){ Get-ValAt $cumTL ([long]$p.timestamp) })
  Write-Output ("PRISMATIC BOLT: {0} casts | at CumulativePower 8/8: {1} ({2:N0}%)" -f $pb.Count,@($pbC|Where-Object{$_ -ge 8}).Count,(100*@($pbC|Where-Object{$_ -ge 8}).Count/[math]::Max($pb.Count,1)))

  # ---- arcane charges ----
  $ch=@($res|Where-Object{$_.resourceChangeType -eq 16})
  $gain=($ch|Measure-Object resourceChange -Sum).Sum
  $waste=($ch|Measure-Object waste -Sum).Sum
  Write-Output ("ARCANE CHARGES: generated {0}, wasted at cap {1} ({2:N0}%)" -f $gain,$waste,(100*$waste/[math]::Max($gain,1)))
  Write-Output ("ARCANE ORB hard casts: {0} | ARCANE BLAST: {1}" -f @($casts|Where-Object{$_.abilityGameID -eq $C_AO}).Count,@($casts|Where-Object{$_.abilityGameID -eq $C_ABl}).Count)

  $G.bTot+=$barr.Count;$G.b25+=$b25;$G.bCC+=$bCC;$G.bBad+=$bBad;$G.intu+=$intuN;$G.bHi+=$n;$G.lowN+=$bLow
  $G.salSum+=($sal|Measure-Object -Sum).Sum; $G.mTot+=$mis.Count;$G.mOver+=$mOver
  Write-Output ""
}
Write-Output "================= BOTH PULLS ================="
Write-Output ("Barrage scored {0} (of {1}; {2} dropped for low mana)" -f $G.bHi,$G.bTot,$G.lowN)
Write-Output ("  at max Salvo {0:N0}%  |  Intuition {1:N0}%  |  avg Salvo {2:N1}" -f (100*$G.b25/$G.bHi),(100*$G.intu/$G.bHi),($G.salSum/$G.bHi))
Write-Output ("  CC-dump {0:N0}%  |  off-plan {1:N0}%" -f (100*$G.bCC/$G.bHi),(100*$G.bBad/$G.bHi))
Write-Output ("Missiles above <12 gate: {0:N0}%" -f (100*$G.mOver/$G.mTot))
Write-Output ""
Write-Output "--- PRIOR SESSION (5 pulls, report vAtQ) for reference ---"
Write-Output "  at max Salvo 42%  |  Intuition 47%  |  avg Salvo 19.6  |  off-plan 19%  |  Missiles above gate 18%"
Write-Output "--- SIM optimum ---"
Write-Output "  at max Salvo 71%  |  Intuition 65%  |  avg Salvo 22.4"
