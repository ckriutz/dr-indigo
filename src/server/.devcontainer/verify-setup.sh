#!/bin/bash

# Verify SQLite and ChromaDB setup for Dr. Indigo development environment

echo "🔍 Checking SQLite and ChromaDB compatibility..."
echo ""

# Check SQLite version
echo "📋 System SQLite version check:"
if command -v sqlite3 &> /dev/null; then
    echo "  Command line: $(sqlite3 --version)"
else
    echo "  Command line sqlite3 not found in PATH"
fi

echo "  Python sqlite3: $(python3 -c 'import sqlite3; print(sqlite3.sqlite_version)')"
echo ""

# Check if ChromaDB can be imported
echo "🧪 Testing ChromaDB import:"
if python3 -c "import chromadb" 2>/dev/null; then
    echo "  ✅ ChromaDB import successful!"
    
    # Test basic ChromaDB functionality
    echo ""
    echo "🚀 Testing basic ChromaDB functionality:"
    python3 -c "
import chromadb
client = chromadb.Client()
print('  ✅ ChromaDB client created successfully!')
"
else
    echo "  ❌ ChromaDB import failed!"
    echo ""
    echo "💡 Troubleshooting tips:"
    echo "  1. Make sure you're in the devcontainer"
    echo "  2. Check that dependencies are installed: pip install -e ."
    echo "  3. Verify LD_LIBRARY_PATH includes /usr/local/lib"
    exit 1
fi

echo ""
echo "🎉 Environment verification complete!"
echo ""
echo "📚 You can now:"
echo "  • Import chromadb in your Python scripts"
echo "  • Run the Dr. Indigo server: uvicorn api:app --host 0.0.0.0 --port 8000 --reload"
echo "  • Test the workflow: python main.py"