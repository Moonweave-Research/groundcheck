# ⚠️ Generated mirror — do not edit here

This `ref-verify/` directory is a **read-only mirror** of the standalone skill repo,
the canonical source of truth:

  https://github.com/Moonweave-Research/ref-verify

groundcheck bundles the skill here so a single `git clone` of groundcheck delivers the
whole collection — without git submodules (which arrive empty on ZIP downloads and on
`git clone` without `--recursive`).

**Do not edit files in this directory.** Edits here are overwritten on the next sync and
recreate divergence (the exact problem this layout prevents). To change the skill: edit
the standalone repo above, then from the groundcheck root run:

    ./scripts/sync_ref_verify.sh

Last synced: main @ 403bb67
