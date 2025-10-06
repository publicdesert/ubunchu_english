#!/usr/bin/bash
# This script is there to help create the reading aids/public versions of chapters 15 and the specials.
# It creates copies of the full work files with non-free assets removed. build.py can than be used to
# build the reading aid from those assets with --mode aid.
echo "Now creating public versions of the masks by removing the extracted original image at the bottom..."

MASK_SRC_DIR="./mask"
MASK_DST_DIR="./mask_p"

TEXT_SRC_DIR="./text"
TEXT_DST_DIR="./text_p"

if ! command -v gimp >/dev/null 2>&1 && ! command -v gimp-console >/dev/null 2>&1; then
  echo "gimp not found." >&2
  exit 1
fi

GIMP_BIN="$(command -v gimp-console || command -v gimp)"

mkdir -p "$MASK_DST_DIR"
mapfile -d '' files < <(find "$MASK_SRC_DIR" -type f \( -iname '*.xcf' \) -print0)

if (( ${#files[@]} == 0 )); then
  echo "No .xcf files found in $MASK_SRC_DIR"
  exit 0
fi

for f in "${files[@]}"; do
  cp -a -- "$f" "$MASK_DST_DIR/"
done

process_xcf() {
  local xcf_path="$1"

  # Escape for Scheme string literal
  local scheme_path="${xcf_path//\\/\\\\}"
  scheme_path="${scheme_path//\"/\\\"}"

  "$GIMP_BIN" -i -b - <<EOF >/dev/null 2>&1
(define (drop-bottom-layer filename)
  (let* ((load-result (gimp-file-load RUN-NONINTERACTIVE filename filename))
         (img (car load-result)))
    (let* ((layers-info (gimp-image-get-layers img))
           (count (car layers-info))
           (layers (cadr layers-info)))
      (when (> count 0)
        (let* ((bottom (vector-ref layers (- count 1))))
          (gimp-image-remove-layer img bottom))))
    (let* ((drawable (car (gimp-image-get-active-layer img))))
      (gimp-file-save RUN-NONINTERACTIVE img drawable filename filename))
    (gimp-image-delete img)))
(drop-bottom-layer "${scheme_path}")
(gimp-quit 0)
EOF
}

mapfile -d '' masks < <(find "$MASK_DST_DIR" -maxdepth 1 -type f -iname '*.xcf' -print0)

for m in "${masks[@]}"; do
  echo "Processing: $m"
  if ! process_xcf "$m"; then
    echo "Warning: Failed to process $m" >&2
  fi
done

echo "Done processing masks. Now doing the same for the text dir..."


command -v xmlstarlet >/dev/null || {
  echo "xmlstarlet not found." >&2
  exit 1
}

mkdir -p "$TEXT_DST_DIR"

mapfile -d '' files < <(find "$TEXT_SRC_DIR" -type f -iname '*.svg' -print0)
((${#files[@]})) || { echo "No .svg files found in $TEXT_SRC_DIR"; exit 0; }
for f in "${files[@]}"; do cp -a -- "$f" "$TEXT_DST_DIR/"; done

mapfile -d '' svgs < <(find "$TEXT_DST_DIR" -maxdepth 1 -type f -iname '*.svg' -print0)
for s in "${svgs[@]}"; do
  echo "Stripping raster image(s): $s"
  xmlstarlet ed -L -P -d '//*[local-name()="image"]' "$s"
  xmlstarlet ed -L -P -d '//*[local-name()="g"][not(node())]' "$s" || true
done



echo "Done."

