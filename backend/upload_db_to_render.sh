#!/bin/bash
# Script to help upload films_complete.db to Render

echo "📦 Preparing database for upload..."

cd "$(dirname "$0")"

if [ ! -f "films_complete.db" ]; then
    echo "❌ Error: films_complete.db not found in backend directory"
    exit 1
fi

# Get file size
SIZE=$(du -h films_complete.db | cut -f1)
echo "📊 Database size: $SIZE"

# Compress
echo "🗜️  Compressing database..."
gzip -k -f films_complete.db

if [ -f "films_complete.db.gz" ]; then
    GZ_SIZE=$(du -h films_complete.db.gz | cut -f1)
    echo "✅ Compressed to: $GZ_SIZE"
    echo ""
    echo "📤 Next steps to upload to Render:"
    echo "1. Go to Render dashboard → Your service → Shell"
    echo "2. Upload films_complete.db.gz to Render"
    echo "3. In Render Shell, run:"
    echo "   cd /opt/render/project/src/backend"
    echo "   gunzip films_complete.db.gz"
    echo "   ls -lh films_complete.db  # Verify"
    echo ""
    echo "Or use Render Disk (persistent storage) - see DEPLOY_DATABASE.md"
else
    echo "❌ Compression failed"
    exit 1
fi

