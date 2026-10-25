#!/usr/bin/env bash
set -euo pipefail
wc -l < /app/data.txt | tr -d '[:space:]' > /app/answer.txt
