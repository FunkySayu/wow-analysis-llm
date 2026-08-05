param([int[]]$Fights = @(1,3,7,8,9))
$ErrorActionPreference='Stop'
$root = Split-Path $PSScriptRoot -Parent

function Get-Ev($f){ ,@((Get-Content $f -Raw | ConvertFrom-Json).data.reportData.report.events.data) }

function New-StackTL($evs, $id){
  $tl=New-Object System.Collections.ArrayList; $cur=0
  foreach($e in $evs){
    if([string]$e.abilityGameID -ne $id){continue}
    switch($e.type){
      'applybuff'       {$cur=1}
      'applybuffstack'  {$cur=[int]$e.stack}
      'removebuffstack' {$cur=[int]$e.stack}
      'removebuff'      {$cur=0}
    }
    [void]$tl.Add([pscustomobject]@{t=[long]$e.timestamp;v=[int]$cur})
  }
  ,$tl
}
function Get-ValAt($tl,$time){
  $v=0
  for($i=0;$i -lt $tl.Count;$i++){ if($tl[$i].t -lt $time){$v=$tl[$i].v} else {break} }
  return $v
}
function New-Ivs($evs,$id,$tEnd){
  $iv=New-Object System.Collections.ArrayList; $st=$null
  foreach($e in $evs){
    if([string]$e.abilityGameID -ne $id){continue}
    if($e.type -eq 'applybuff'){$st=[long]$e.timestamp}
    elseif($e.type -eq 'refreshbuff'){ if($null -ne $st){[void]$iv.Add([pscustomobject]@{s=$st;e=[long]$e.timestamp}); $st=[long]$e.timestamp} }
    elseif($e.type -eq 'removebuff'){ if($null -ne $st){[void]$iv.Add([pscustomobject]@{s=$st;e=[long]$e.timestamp}); $st=$null} }
  }
  if($null -ne $st){[void]$iv.Add([pscustomobject]@{s=$st;e=$tEnd})}
  ,$iv
}
function Test-InIv($iv,$t){ foreach($i in $iv){ if($t -ge $i.s -and $t -le $i.e){return $true} }; return $false }

$SALVO='1242974'; $CC='263725'; $SOUL='451038'; $CUMUL='1296930'
$C_MISSILES=5143; $C_BARRAGE=44425; $C_PBOLT=1295924; $C_BLAST=30451

$A=@{mTot=0;mOver=0;bTot=0;bMax=0;bCC=0;bSoul=0;bBad=0;badSalvo=@();pbTot=0;pb8=0;salvoConsumed=0;salvoPossible=0}

foreach($F in $Fights){
  $casts = @(Get-Ev "$root\scratch\casts_f$F.json") | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp
  $buffs = @(Get-Ev "$root\scratch\buffev_f$F.json") | Sort-Object timestamp
  $t0=[long]$casts[0].timestamp; $tEnd=[long]$casts[-1].timestamp

  $salvoTL = New-StackTL $buffs $SALVO
  $ccTL    = New-StackTL $buffs $CC
  $cumTL   = New-StackTL $buffs $CUMUL
  $soulIV  = New-Ivs $buffs $SOUL $tEnd

  Write-Output "======== FIGHT $F ========"
  # Missiles
  $mis = @($casts | Where-Object {$_.abilityGameID -eq $C_MISSILES})
  $mSalvo = foreach($m in $mis){ Get-ValAt $salvoTL ([long]$m.timestamp) }
  $mOver = @($mSalvo | Where-Object {$_ -ge 12}).Count
  Write-Output ("MISSILES {0} casts | avg Salvo at cast {1:N1} | cast at Salvo>=12 (APL says <12): {2} ({3:N0}%)" -f $mis.Count,(($mSalvo|Measure-Object -Average).Average),$mOver,(100*$mOver/$mis.Count))

  # Barrage
  $barr = @($casts | Where-Object {$_.abilityGameID -eq $C_BARRAGE})
  $max=0;$ccd=0;$soul=0;$bad=0;$badL=@();$consumed=0
  foreach($b in $barr){
    $ts=[long]$b.timestamp
    $s=Get-ValAt $salvoTL $ts; $c=Get-ValAt $ccTL $ts
    if(Test-InIv $soulIV $ts){$soul++}
    elseif($s -ge 25){$max++; $consumed+=$s}
    elseif($s -ge 12 -and $c -ge 1){$ccd++; $consumed+=$s}
    else{$bad++; $badL+=[pscustomobject]@{t=[math]::Round(($ts-$t0)/1000,1);salvo=$s;cc=$c}; $consumed+=$s}
  }
  $nonSoul=$barr.Count-$soul
  Write-Output ("BARRAGE  {0} casts | Soul {1} | Salvo=25 {2} ({3:N0}% of non-Soul) | CC-dump>=12 {4} ({5:N0}%) | OFF-PLAN {6} ({7:N0}%)" -f `
    $barr.Count,$soul,$max,(100*$max/[math]::Max($nonSoul,1)),$ccd,(100*$ccd/[math]::Max($nonSoul,1)),$bad,(100*$bad/[math]::Max($nonSoul,1)))
  if($badL.Count){ Write-Output ("   off-plan salvo values: " + (($badL|ForEach-Object{"$($_.salvo)"}) -join ",")) }

  # Prismatic Bolt
  $pb = @($casts | Where-Object {$_.abilityGameID -eq $C_PBOLT})
  $pbCum = foreach($p in $pb){ Get-ValAt $cumTL ([long]$p.timestamp) }
  $pb8 = @($pbCum|Where-Object{$_ -ge 8}).Count
  Write-Output ("PRISMATIC BOLT {0} casts | avg CumulativePower {1:N1}/8 | at 8/8: {2} ({3:N0}%)" -f $pb.Count,(($pbCum|Measure-Object -Average).Average),$pb8,(100*$pb8/[math]::Max($pb.Count,1)))

  # Blast
  $bl = @($casts | Where-Object {$_.abilityGameID -eq $C_BLAST})
  Write-Output ("ARCANE BLAST {0} casts (pure filler - every one is a GCD the engine failed to fill with something better)" -f $bl.Count)

  $A.mTot+=$mis.Count;$A.mOver+=$mOver;$A.bTot+=$barr.Count;$A.bMax+=$max;$A.bCC+=$ccd;$A.bSoul+=$soul;$A.bBad+=$bad
  $A.pbTot+=$pb.Count;$A.pb8+=$pb8;$A.salvoConsumed+=$consumed
  Write-Output ""
}
Write-Output "========= AGGREGATE ========="
$nonSoulAll=$A.bTot-$A.bSoul
Write-Output ("Missiles {0} casts, {1} ({2:N0}%) above the Salvo<12 gate" -f $A.mTot,$A.mOver,(100*$A.mOver/$A.mTot))
Write-Output ("Barrage  {0} casts | Soul {1} | Salvo=25 {2} ({3:N0}% of non-Soul) | CC-dump {4} ({5:N0}%) | OFF-PLAN {6} ({7:N0}%)" -f `
  $A.bTot,$A.bSoul,$A.bMax,(100*$A.bMax/$nonSoulAll),$A.bCC,(100*$A.bCC/$nonSoulAll),$A.bBad,(100*$A.bBad/$nonSoulAll))
Write-Output ("PrismBolt {0} casts, {1} ({2:N0}%) at CumulativePower 8/8" -f $A.pbTot,$A.pb8,(100*$A.pb8/$A.pbTot))
