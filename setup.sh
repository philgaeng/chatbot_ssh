#!/bin/bash
# Run from /home/philg/projects/nepal_chatbot on feature/grm-ticketing branch
set -e
mkdir -p docs/claude-tickets/context
git add CLAUDE.md .claudeignore docs/claude-tickets/
git commit -m "chore: add Claude Code session files for GRM ticketing"
git push
echo "Done. Open Claude Code and paste docs/claude-tickets/session-0-prompt.md as your first message."
