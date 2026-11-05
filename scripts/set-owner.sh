#!/bin/sh
# Replace the OWNER placeholder with your GitHub account name in docs, workflows and the video.
# usage: scripts/set-owner.sh <github-username>
set -eu
[ $# -eq 1 ] || { echo "usage: $0 <github-username>" >&2; exit 1; }
cd "$(dirname "$0")/.."
grep -rl --exclude-dir=.git --exclude=set-owner.sh 'OWNER' . | while read -r f; do
  sed -i.bak "s#OWNER/qnxscout#$1/qnxscout#g; s#github.com/OWNER#github.com/$1#g" "$f" && rm -f "$f.bak"
done
grep -rn --exclude-dir=.git --exclude=set-owner.sh 'OWNER' . || echo "all OWNER placeholders replaced with $1"
