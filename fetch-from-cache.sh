#!/usr/bin/env bash

REPORT=$1
export HASH_COLLECTION_SERVER=http://localhost:8000

if [ "x" == "x$REPORT" ]; then
  echo "Usage: $0 <report-name>"
  exit 1
fi

while true; do
  curl -H "Authorization: Bearer $HASH_COLLECTION_TOKEN" $HASH_COLLECTION_SERVER/reports/$REPORT/suggested | jq .[] | head -50 | tr -d \" | while read out
  do
    echo $out
    # TODO some/most of these can probably also be taken found in the
    # local cache (with a cache.nixos.org signature), so perhaps take them from there?
    copy-from-cache $out
  done
done
