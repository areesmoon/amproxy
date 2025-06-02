#!/bin/bash

if [ $# -lt 1 ]; then
  echo "Usage: $0 <version> [-m|--message <commit message>]"
  exit 1
fi

VERSION=$1
shift

# Default commit message
COMMIT_MSG="Release $VERSION"

# Parse optional args
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--message)
      if [ -n "$2" ]; then
        COMMIT_MSG="$2"
        shift 2
      else
        echo "Error: Missing commit message after $1"
        exit 1
      fi
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo "📝 Adding and committing changes..."
git add .
git commit -m "$COMMIT_MSG"

echo "🏷 Creating tag $VERSION..."
git tag -a "$VERSION" -m "$COMMIT_MSG"

echo "⬆️ Pushing commits and tags to origin..."
git push origin main --tags

echo "📦 Creating release packages..."
mkdir -p dist
git archive --format=tar.gz -o dist/amproxy-$VERSION.tar.gz HEAD
git archive --format=zip -o dist/amproxy-$VERSION.zip HEAD

echo ""
echo "🚀 Release $VERSION created!"
echo "💬 Last commit message:"
echo "$COMMIT_MSG"
