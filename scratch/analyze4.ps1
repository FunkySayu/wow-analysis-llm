param([int[]]$Fights = @(1,3,7,8,9))
$ErrorActionPreference='Stop'
$root = Split-Path $PSScriptRoot -Parent

function Get-Ev($f){ (Get-Content $f -Raw | ConvertFrom-Json).data.reportData.report.events.data }

function New-StackTL($evs,$id){
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
  return $tl
}
function Get-ValAt($tl,$time){ $v=0; foreach($p in $tl){ if($p.t -lt $time){$v=$p.v} else {break} }; return $v }
function New-Ivs($evs,$id,$tEnd){
  $iv=New-Object System.Collections.ArrayList; $st=$null
  foreach($e in $evs){
    if([string]$e.abilityGameID -ne $id){continue}
    if($e.type -eq 'applybuff'){$st=[long]$e.timestamp}
    elseif($e.type -eq 'refreshbuff'){ if($null -ne $st){[void]$iv.Add([pscustomobject]@{s=$st;e=[long]$e.timestamp}); $st=[long]$e.timestamp} }
    elseif($e.type -eq 'removebuff'){ if($null -ne $st){[void]$iv.Add([pscustomobject]@{s=$st;e=[long]$e.timestamp}); $st=$null} }
  }
  if($null -ne $st){[void]$iv.Add([pscustomobject]@{s=$st;e=$tEnd})}
  return $iv
}
function Test-InIv($iv,$t){ foreach($i in $iv){ if($t -ge $i.s -and $t -le $i.e){return $true} }; return $false }

$SALVO='1242974'; $CC='263725'; $SOUL='451038'; $CUMUL='1296930'
$C_MISSILES=5143; $C_BARRAGE=44425; $C_PBOLT=1295924; $C_BLAST=30451
$A=@{mTot=0;mOver=0;bTot=0;bMax=0;bCC=0;bSoul=0;bBad=0;pbTot=0;pb8=0;blast=0;consumed=0;maxPossible=0}

foreach($F in $Fights){
  $all   = @(Get-Ev "$root\scratch\casts_f$F.json")
  $casts = @($all | Where-Object {$_.type -eq 'cast'} | Sort-Object timestamp)
  $buffs = @(Get-Ev "$root\scratch\buffev_f$F.json" | Sort-Object timestamp)
  $t0=[long]$casts[0].timestamp; $tEnd=[long]$casts[-1].timestamp

  $salvoTL=New-StackTL $buffs $SALVO
  $ccTL   =New-StackTL $buffs $CC
  $cumTL  =New-StackTL $buffs $CUMUL
  $soulIV =New-Ivs $buffs $SOUL $tEnd

  Write-Output "======== FIGHT $F  (sanity: $($casts.Count) cast events) ========"

  $mis=@($casts|Where-Object{$_.abilityGameID -eq $C_MISSILES})
  $mS = @(foreach($m in $mis){ Get-ValAt $salvoTL ([long]$m.timestamp) })
  $mOver=@($mS|Where-Object{$_ -ge 12}).Count
  Write-Output ("MISSILES x{0} | avg Salvo at cast {1:N1} | at Salvo>=12 (APL gate is <12): {2} ({3:N0}%)" -f $mis.Count,(($mS|Measure-Object -Average).Average),$mOver,(100*$mOver/$mis.Count))

  $barr=@($casts|Where-Object{$_.abilityGameID -eq $C_BARRAGE})
  $max=0;$ccd=0;$nSoul=0;$bad=0;$badL=@();$cons=0
  foreach($b in $barr){
    $ts=[long]$b.timestamp; $s=Get-ValAt $salvoTL $ts; $c=Get-ValAt $ccTL $ts
    if(Test-InIv $soulIV $ts){$nSoul++; continue}
    $cons+=$s
    if($s -ge 25){$max++}
    elseif($s -ge 12 -and $c -ge 1){$ccd++}
    else{$bad++; $badL+=[pscustomobject]@{t=[math]::Round(($ts-$t0)/1000,1);salvo=$s;cc=$c}}
  }
  $ns=$barr.Count-$nSoul
  Write-Output ("BARRAGE x{0} | in Soul {1} | Salvo=25 {2} ({3:N0}%) | CC-dump(Salvo>=12+CC) {4} ({5:N0}%) | OFF-PLAN {6} ({7:N0}%)" -f `
    $barr.Count,$nSoul,$max,(100*$max/$ns),$ccd,(100*$ccd/$ns),$bad,(100*$bad/$ns))
  if($badL.Count){ Write-Output ("   off-plan (salvo/cc): " + (($badL|ForEach-Object{"$($_.salvo)/$($_.cc)"}) -join "  ")) }
  Write-Output ("   Salvo actually consumed outside Soul: {0} over {1} casts (avg {2:N1}); theoretical max at 25/cast = {3}" -f $cons,$ns,($cons/$ns),($ns*25))

  $pb=@($casts|Where-Object{$_.abilityGameID -eq $C_PBOLT})
  $pbC=@(foreach($p in $pb){ Get-ValAt $cumTL ([long]$p.timestamp) })
  $pb8=@($pbC|Where-Object{$_ -ge 8}).Count
  Write-Output ("PRISMATIC BOLT x{0} | avg CumulativePower {1:N1}/8 | cast at 8/8: {2} ({3:N0}%)" -f $pb.Count,(($pbC|Measure-Object -Average).Average),$pb8,(100*$pb8/$pb.Count))

  $bl=@($casts|Where-Object{$_.abilityGameID -eq $C_BLAST})
  Write-Output ("ARCANE BLAST x{0} (bottom-priority filler)" -f $bl.Count)

  $A.mTot+=$mis.Count;$A.mOver+=$mOver;$A.bTot+=$barr.Count;$A.bMax+=$max;$A.bCC+=$ccd;$A.bSoul+=$nSoul;$A.bBad+=$bad
  $A.pbTot+=$pb.Count;$A.pb8+=$pb8;$A.blast+=$bl.Count;$A.consumed+=$cons;$A.maxPossible+=($ns*25)
  Write-Output ""
}
Write-Output "========= AGGREGATE (5 x 300s single target) ========="
$ns=$A.bTot-$A.bSoul
Write-Output ("Missiles x{0} | {1} ({2:N0}%) cast above the Salvo<12 gate" -f $A.mTot,$A.mOver,(100*$A.mOver/$A.mTot))
Write-Output ("Barrage  x{0} | Soul {1} | Salvo=25 {2} ({3:N0}%) | CC-dump {4} ({5:N0}%) | OFF-PLAN {6} ({7:N0}%)" -f $A.bTot,$A.bSoul,$A.bMax,(100*$A.bMax/$ns),$A.bCC,(100*$A.bCC/$ns),$A.bBad,(100*$A.bBad/$ns))
Write-Output ("Salvo consumed {0} / {1} theoretical max ({2:N0}% efficiency)" -f $A.consumed,$A.maxPossible,(100*$A.consumed/$A.maxPossible))
Write-Output ("PrismBolt x{0} | {1} ({2:N0}%) at CumulativePower 8/8" -f $A.pbTot,$A.pb8,(100*$A.pb8/$A.pbTot))
Write-Output ("Arcane Blast x{0}" -f $A.blast)

