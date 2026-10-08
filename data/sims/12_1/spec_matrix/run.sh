#!/bin/bash
# run.sh <tag> <profile files...>  -- runs every scenario in scen.txt; outputs out/<tag>__<scen>.json
export MSYS_NO_PATHCONV=1
SIMC=../../../../vendor/simc/build/Release/simc.exe
tag=$1; shift
mkdir -p out
while IFS='|' read -r name opts; do
  [ -z "$name" ] && continue
  [ -f out/${tag}__${name}.json ] && continue
  $SIMC base.simc "$@" $opts iterations=${ITER:-4000} threads=16 json2=out/${tag}__${name}.json > out/${tag}__${name}.txt 2>&1 || echo "FAIL $tag $name"
done < ${SCEN:-scen.txt}
echo "done $tag"
