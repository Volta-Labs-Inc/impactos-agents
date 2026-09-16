#!/bin/bash
# Auto-backup project to GitHub on session end
cd "$CLAUDE_PROJECT_DIR" || exit 0

# Skip if no git repo
[ -d .git ] || exit 0

# Skip if no changes
if git diff --quiet HEAD 2>/dev/null && [ -z "$(git status --porcelain)" ]; then
  exit 0
fi

git add -A
git commit -m "Auto-backup $(date +%Y-%m-%d\ %H:%M)" --no-gpg-sign 2>/dev/null
git push origin HEAD 2>/dev/null
