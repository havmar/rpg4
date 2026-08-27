#!/bin/bash
# UNDERSTORY freshness guard (SessionStart hook).
#
# Why this exists: Claude Code on the web starts a session on a freshly
# named branch cut from whatever base the container happened to have, and
# `git pull --ff-only` on that branch is a no-op that proves nothing about
# master. Session 3 (play/vesper) ran an entire opening scene on a checkout
# six commits stale -- old chargen, an empty Ledger over committed canon --
# because nothing forced the new branch to actually start from current
# master. This hook is that force.
#
# What it does: fetch origin's default branch and compare.
#   - branch strictly behind it (a fresh branch off a stale base, the
#     failure case): fast-forward. A ff can never lose work -- it only
#     succeeds when the branch has no commits of its own.
#   - branch has its own commits: never touch it, print which case it is
#     (mid-playthrough play branch = normal; anything else = warn).
#   - no network: warn loudly and let the session start anyway.
# Never blocks the session; always exits 0. Stdout lands in the session's
# context, so the warnings reach the DM before any chargen happens.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

DEFAULT=master

if ! git fetch --quiet origin "$DEFAULT" 2>/dev/null; then
  echo "FRESHNESS GUARD: could not fetch origin/$DEFAULT -- freshness NOT verified."
  echo "Before creating a delver or changing the engine, verify this checkout by hand."
  exit 0
fi

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
head=$(git rev-parse HEAD)
target=$(git rev-parse "origin/$DEFAULT")

if [ "$head" = "$target" ]; then
  echo "Freshness guard: checkout is current with origin/$DEFAULT ($(git rev-parse --short HEAD))."
  exit 0
fi

if git merge-base --is-ancestor "$head" "$target"; then
  behind=$(git rev-list --count "$head..$target")
  if git merge --ff-only --quiet "origin/$DEFAULT" 2>/dev/null; then
    echo "Freshness guard: '$branch' was cut from a STALE base ($behind commits behind" \
         "origin/$DEFAULT) -- fast-forwarded to $(git rev-parse --short HEAD). Docs and" \
         "engine in this checkout are current now; anything read before this line was not."
  else
    echo "FRESHNESS GUARD: '$branch' is $behind commits behind origin/$DEFAULT and the"
    echo "fast-forward FAILED (likely local changes in the way). Resolve by hand before"
    echo "trusting anything in this checkout."
  fi
  exit 0
fi

ahead=$(git rev-list --count "$target..$head")
behind=$(git rev-list --count "$head..$target")
if [ "$behind" = "0" ]; then
  echo "Freshness guard: '$branch' is $ahead commits ahead of origin/$DEFAULT, base current."
elif [[ "$branch" == play/* ]]; then
  echo "Freshness guard: play branch '$branch' has its own commits and origin/$DEFAULT has"
  echo "moved on ($behind behind). Mid-playthrough this is NORMAL -- a playthrough keeps the"
  echo "engine it started on; never merge master into a live game. But if this session is"
  echo "meant to START a new game, this branch is the wrong base: cut a fresh one from"
  echo "origin/$DEFAULT instead."
else
  echo "FRESHNESS GUARD: '$branch' has diverged from origin/$DEFAULT ($ahead ahead,"
  echo "$behind behind). For dev work, merge origin/$DEFAULT before building on this."
fi
exit 0
