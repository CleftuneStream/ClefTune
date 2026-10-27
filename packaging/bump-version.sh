#!/usr/bin/env bash
# Bump ClefTune's version in cleftune/__init__.py and pyproject.toml (kept in sync).
#
#   packaging/bump-version.sh --minor    1.0.0 -> 1.0.1
#   packaging/bump-version.sh --major    1.0.0 -> 1.1.0
#
# Then commit, push, and run the Installers workflow to publish the release.

set -euo pipefail
cd "$(dirname "$0")/.."

INIT=cleftune/__init__.py
PROJECT=pyproject.toml

usage() {
  sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-1}"
}

die() { echo "error: $*" >&2; exit 1; }

[ $# -eq 1 ] || usage
case "$1" in
  --minor) part=last ;;
  --major) part=middle ;;
  -h|--help) usage 0 ;;
  *) echo "unknown option: $1" >&2; usage ;;
esac

current=$(sed -nE 's/^__version__ = "([0-9]+\.[0-9]+\.[0-9]+)".*/\1/p' "$INIT")
in_project=$(sed -nE 's/^version = "([^"]+)".*/\1/p' "$PROJECT")
[ -n "$current" ] || die "no X.Y.Z __version__ found in $INIT"
[ "$current" = "$in_project" ] || die "$INIT says $current but $PROJECT says $in_project; make them match first"

IFS=. read -r x y z <<< "$current"
case "$part" in
  last) z=$((z + 1)) ;;
  middle) y=$((y + 1)); z=0 ;;
esac
new="$x.$y.$z"

# sed -i differs between GNU and BSD (macOS), so write through a temp file instead
replace() {
  local file=$1 expr=$2 tmp
  tmp=$(mktemp)
  sed -E "$expr" "$file" > "$tmp"
  cat "$tmp" > "$file"
  rm -f "$tmp"
}
escaped=${current//./\\.}
replace "$INIT" "s/^__version__ = \"$escaped\"/__version__ = \"$new\"/"
replace "$PROJECT" "s/^version = \"$escaped\"/version = \"$new\"/"

# make sure both files really changed
grep -q "^__version__ = \"$new\"" "$INIT" || die "failed to update $INIT"
grep -q "^version = \"$new\"" "$PROJECT" || die "failed to update $PROJECT"

echo "ClefTune $current -> $new"
if git rev-parse -q --verify "refs/tags/v$new" >/dev/null 2>&1; then
  echo "warning: tag v$new already exists" >&2
fi
cat <<EOF

Next:
  git add -A && git commit -m "Release v$new"
  git push origin main
  gh workflow run installers.yml --ref main    # or Actions -> Installers -> Run workflow
EOF
