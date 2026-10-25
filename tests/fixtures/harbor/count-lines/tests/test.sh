#!/usr/bin/env bash
set -u
mkdir -p /logs/verifier
answer="$(tr -d '[:space:]' < /app/answer.txt 2>/dev/null || true)"
if [ "$answer" = "3" ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
