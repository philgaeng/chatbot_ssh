#!/bin/bash
# Sync dev branch to main branch
# Usage: ./scripts/sync-dev-to-main.sh [--force]
#
# This script syncs your local dev work to main branch (used on server)
# It will:
# 1. Check for uncommitted changes on dev
# 2. Ensure dev is up to date
# 3. Switch to main and pull latest
# 4. Merge dev into main
# 5. Push main to remote
# 6. Switch back to dev

set -e

FORCE=false
if [ "$1" == "--force" ]; then
    FORCE=true
fi

echo "🔄 Syncing dev → main branch..."

# Ensure we're on dev branch (where you work)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "dev" ]; then
    echo "⚠️  Currently on $CURRENT_BRANCH, switching to dev..."
    git checkout dev
fi

# Check if there are uncommitted changes on dev
if ! git diff-index --quiet HEAD --; then
    echo "❌ Error: You have uncommitted changes on dev. Please commit or stash them first."
    echo "   Run: git status"
    exit 1
fi

# Ensure dev is up to date (pull latest from remote dev if it exists)
if git ls-remote --heads origin dev | grep -q dev; then
    echo "📥 Pulling latest changes from origin/dev..."
    git pull origin dev || echo "⚠️  No remote dev branch or already up to date"
fi

# Switch to main branch
echo "🔄 Switching to main branch..."
git checkout main

# Pull latest main (in case server has updates)
echo "📥 Pulling latest changes from origin/main..."
git pull origin main

# Merge dev into main
if [ "$FORCE" == "true" ]; then
    echo "⚠️  Force merging dev into main (will overwrite main changes)..."
    git merge dev --no-edit
else
    echo "📥 Merging dev into main..."
    git merge dev --no-edit
fi

# Check for conflicts
if [ $? -ne 0 ]; then
    echo "❌ Merge conflicts detected. Please resolve them manually:"
    echo "   1. Resolve conflicts in the files listed above"
    echo "   2. Run: git add ."
    echo "   3. Run: git commit"
    echo "   4. Run: git push origin main"
    echo "   5. Run: git checkout dev"
    exit 1
fi

# Push to remote main
echo "📤 Pushing main branch to remote..."
git push origin main

# Switch back to dev branch (so you end where you started)
echo "🔄 Switching back to dev branch..."
git checkout dev

echo "✅ Successfully synced dev → main!"
echo ""
echo "📋 Summary:"
echo "   - Merged latest changes from dev"
echo "   - Pushed to origin/main"
echo "   - Switched back to dev branch"
echo ""
echo "🚀 Next steps:"
echo "   - Server should pull from main branch"
echo "   - Verify deployment on server"

