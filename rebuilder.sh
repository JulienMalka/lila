#!/usr/bin/env bash

REPORT=$1

if [ "x" == "x$REPORT" ]; then
  echo "Usage: $0 <report-name>"
  exit 1
fi

while true; do
  curl -H "Authorization: Bearer $HASH_COLLECTION_TOKEN" http://localhost:8000/reports/$REPORT/suggested | jq .[] | head | tr -d \" | while read out
  do
      (nix derivation show $out || exit 1) | jq keys.[] | tr -d \" | while read drv
      do
	  # TODO select the right output to rebuild?
          nix-build $drv --check
      done
  done
done
