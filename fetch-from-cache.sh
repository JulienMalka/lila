#!/usr/bin/env bash

REPORT=$1
export HASH_COLLECTION_SERVER=http://localhost:8000

if [ "x" == "x$REPORT" ]; then
  echo "Usage: $0 <report-name>"
  exit 1
fi

while true; do
  curl -H "Authorization: Bearer $HASH_COLLECTION_TOKEN" $HASH_COLLECTION_SERVER/reports/$REPORT/suggest | jq -c ".[] | pick(.out_path, .drv_path)" | head -50 | while read out
  do
    OUT_PATH=$(echo $out | cut -d '"' -f 4)
    DRV_PATH=$(echo $out | cut -d '"' -f 8)
    if [[ "x" == "x$DRV_PATH" ]]; then
      DRV_PATH=$(nix derivation show $OUT_PATH | jq "keys.[]" | tr -d \")
    fi
    DRV_IDENT=$(echo $DRV_PATH | tail -c +12)
    echo "Fetching $OUT_PATH from cache with deriver $DRV_PATH"

    # TODO some/most of these can probably also be taken found in the
    # local cache (with a cache.nixos.org signature), so perhaps take them from there?
    copy-from-cache $OUT_PATH $DRV_IDENT
  done
done
