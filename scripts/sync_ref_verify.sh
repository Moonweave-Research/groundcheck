#!/usr/bin/env bash
# One-way mirror of the canonical ref-verify skill into groundcheck/ref-verify.
#
# WHY: ref-verify lives in its own flagship repo (its own stars / README / CI).
# groundcheck bundles it so a single `git clone` of groundcheck delivers the whole
# skill collection — without git submodules (which come up empty on ZIP downloads
# and on `git clone` without --recursive).
#
# RULE: never hand-edit groundcheck/ref-verify. Edit the source repo, then run this.
#
# Usage:  ./scripts/sync_ref_verify.sh [ref]      # ref defaults to main
set -euo pipefail

SRC_REPO="https://github.com/Moonweave-Research/ref-verify.git"
SRC_REF="${1:-main}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/ref-verify"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Cloning $SRC_REPO @ $SRC_REF ..."
git clone --quiet --depth 1 --branch "$SRC_REF" "$SRC_REPO" "$TMP/src"
SRC_SHA="$(git -C "$TMP/src" rev-parse --short HEAD)"

echo "Refilling $DEST from $SRC_REF @ $SRC_SHA ..."
rm -rf "$DEST"
mkdir -p "$DEST"
(cd "$TMP/src" && git archive "$SRC_REF") | tar -x -C "$DEST"

cat > "$DEST/_GENERATED_DO_NOT_EDIT.md" <<MARKER
# ⚠️ Generated mirror — do not edit here

Read-only mirror of https://github.com/Moonweave-Research/ref-verify (source of truth).
Edit the source repo, then run ./scripts/sync_ref_verify.sh from the groundcheck root.

Last synced: $SRC_REF @ $SRC_SHA
MARKER

echo "Done. ref-verify synced to $SRC_REF @ $SRC_SHA."
echo "Review with: git -C \"$ROOT\" status   then commit."
