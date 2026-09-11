#!/usr/bin/env bash
# Anti-regression check (S5 J55, after a real OpenAI key leaked into
# backend/.env.example for ~8 weeks). Greps common API key/token formats
# on the LINES ADDED by the current diff against vector-agent -- not the
# whole tracked tree, and not git history. The leaked key was neutralized
# at the provider (OpenAI), not by history rewrite, so it's still present
# in old commits (5375445, 8b35e31) on purpose; a whole-history or
# whole-tree scan would flag that forever. This only ever needs to catch
# a NEW secret being introduced.
#
# Usage: scripts/check_no_secrets.sh
# Exit 0 = clean. Exit 1 = a likely secret was added, listed below.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

BASE_REF="origin/vector-agent"

if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
    git fetch --quiet origin vector-agent 2>/dev/null || true
fi

if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
    # Local run without a vector-agent remote-tracking ref (e.g. a fresh
    # clone that only fetched the current branch) -- fall back to the
    # last commit so the script still does something useful.
    echo "(note: $BASE_REF unavailable, comparing against HEAD~1 instead)"
    BASE_REF="HEAD~1"
fi

PATTERN='sk-proj-[a-zA-Z0-9_-]{20,}|sk-[a-zA-Z0-9]{40,}|tvly-[a-zA-Z0-9]{20,}|hf_[a-zA-Z0-9]{20,}|glpat-[a-zA-Z0-9_-]{20,}|AKIA[A-Z0-9]{16}'

# Exclude this script itself: the pattern above necessarily contains
# fragments (e.g. "sk-proj-") that would otherwise match its own source.
# "^\+[^+]" keeps only added lines, dropping the "+++ b/file" diff header.
MATCHES=$(
    git diff "$BASE_REF"...HEAD -- . ":(exclude)scripts/check_no_secrets.sh" \
        | grep -E '^\+[^+]' \
        | grep -E "$PATTERN" \
        || true
)

if [ -n "$MATCHES" ]; then
    echo "❌ Possible secret(s) added in this diff:"
    echo "$MATCHES"
    echo
    echo "If this is a real key: revoke it at the provider immediately, then"
    echo "replace the value with a placeholder (see backend/.env.example for"
    echo "the expected style) before committing."
    exit 1
fi

echo "✅ No known secret patterns found in the diff against $BASE_REF."
