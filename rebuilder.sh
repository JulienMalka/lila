#!/usr/bin/env bash

REPORT=$1

if [ "x" == "x$REPORT" ]; then
  echo "Usage: $0 <report-name>"
  exit 1
fi

while true; do
  curl -H "Authorization: Bearer $HASH_COLLECTION_TOKEN" http://localhost:8007/reports/$REPORT/suggest | jq -c ".[] | pick(.out_path, .drv_path)" | head -50 | while read out
  do
      echo "Rebuiling output $out"
      OUT_PATH=$(echo $out | cut -d '"' -f 4)
      DRV_PATH=$(echo $out | cut -d '"' -f 8)
      if [[ "x" == "x$DRV_PATH" ]]; then
      DRV_PATH=$(nix derivation show $OUT_PATH | jq "keys.[]" | tr -d \")
          if [[ "$DRV_PATH" != "/"* ]]; then
          DRV_PATH=/nix/store/$DRV_PATH
      fi
      fi
      echo "Rebuiling drv $DRV_PATH for output $OUT_PATH"
      nix build "$DRV_PATH^*" && nix build "$DRV_PATH^*" --rebuild
  done
done
