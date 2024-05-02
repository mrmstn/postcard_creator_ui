#!/usr/bin/env bash

readonly JSON_PAYLOAD="${1}"
readonly OUTPUT_DIR="${2:-"$(pwd)"}"

declare -a IMAGE_FIELS=(
"stamp"
"textImage"
"image"
)

for field in  "${IMAGE_FIELS[@]}" ; do
  cat "${JSON_PAYLOAD}" | jq -r ".${field}" | base64 --decode > "${field}.jpeg"
done
