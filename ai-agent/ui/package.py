#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Package Bot MVP UI into a distributable archive
Creates a standalone folder that can be copied anywhere and run immediately
"""
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Fix console encoding for Windows
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')

# Source and output
source_dir = Path(r"e:\Projects\AIErp2026\ai-agent\ui")
output_base = Path(r"e:\Projects\AIErp2026\dist")
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = output_base / f"bot-mvp-ui_{timestamp}"

# Create output directory
output_base.mkdir(exist_ok=True)
output_dir.mkdir(exist_ok=True)

print(f"[PACKAGE] Packaging Bot MVP UI")
print(f"   Source: {source_dir}")
print(f"   Output: {output_dir}\n")

# Folders to copy
folders_to_copy = [
    "web",
    "uploads",
]

# Copy all Python files automatically
print("[FILES] Copying files...")
print("   Python files (*.py):")
python_files = sorted(source_dir.glob("*.py"))
for src in python_files:
    # Skip package.py and copy_files.py (not needed in distribution)
    if src.name in ["package.py", "copy_files.py"]:
        continue
    dst = output_dir / src.name
    shutil.copy2(src, dst)
    print(f"      OK {src.name}")

# Copy required config files
print("   Config files:")
required_files = [
    ".env",
    "requirements.txt",
]
for file in required_files:
    src = source_dir / file
    dst = output_dir / file
    if src.exists():
        shutil.copy2(src, dst)
        print(f"      OK {file}")
    else:
        print(f"      SKIP {file}")

# Copy optional files
optional_files = [
    ".gitignore",
]
for file in optional_files:
    src = source_dir / file
    dst = output_dir / file
    if src.exists():
        shutil.copy2(src, dst)
        print(f"      OK {file}")

# Copy folders
print("\n[FOLDERS] Copying folders...")
for folder in folders_to_copy:
    src = source_dir / folder
    dst = output_dir / folder
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"      OK {folder}/")
    else:
        print(f"      SKIP {folder}/")

# Copy startup scripts
print("\n[SCRIPTS] Copying startup scripts...")
for script in ["quickstart.bat", "quickstart.sh"]:
    src = source_dir / script
    dst = output_dir / script
    if src.exists():
        shutil.copy2(src, dst)
        print(f"      OK {script}")

# Create README for distribution
readme_content = """# Bot MVP - Standalone Distribution

This is a standalone Bot MVP UI package that can be run anywhere.

## Quick Start

### Windows
- Double-click: `quickstart.bat`
- Or run in terminal: `python api.py` (terminal 1) + `python web_server.py` (terminal 2)

### Linux/Mac
```bash
bash quickstart.sh
```

## Manual Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Check .env file:**
   - Ensure `ANTHROPIC_API_KEY` is set
   - Check ports (default: API=8100, Web=8080)

3. **Start API Server:**
   ```bash
   python api.py
   ```

4. **Start Web Server (in another terminal):**
   ```bash
   python web_server.py
   ```

5. **Access URLs:**
   - Chat: http://localhost:8080/index.html
   - API Docs: http://localhost:8100/docs
   - Stats: http://localhost:8080/stats.html
   - Admin: http://localhost:8080/admin.html

## Configuration

Edit `.env` file to customize:
- `API_PORT` - FastAPI port (default: 8100)
- `WEB_PORT` - Web server port (default: 8080)
- `CLAUDE_MODEL` - AI model to use
- `ANTHROPIC_API_KEY` - Your Anthropic API key
- `TZ_OFFSET_HOURS` - Timezone offset

## Features

✅ Chat interface with Claude 3  
✅ Long-term user memory  
✅ RAG (document retrieval)  
✅ Multi-user support with role-based access  
✅ Document management  
✅ Usage tracking & statistics  
✅ Admin dashboard  
✅ Tool-use & function calling  

## Troubleshooting

**API not connecting:**
- Check `ANTHROPIC_API_KEY` in `.env`
- Ensure port 8100 is available

**Web server not loading:**
- Ensure port 8080 is available
- Check web/ folder exists

**Database error:**
- Delete `bot_data.db` to reset
- Restart API server

## Structure

```
├── api.py                 # FastAPI server
├── web_server.py          # Web server
├── bot.py                 # Claude bot logic
├── database.py            # SQLite manager
├── .env                   # Configuration
├── requirements.txt       # Python dependencies
├── web/                   # HTML/CSS/JS files
├── uploads/               # Document storage
├── quickstart.bat         # Windows launcher
└── quickstart.sh          # Linux/Mac launcher
```

---

Enjoy! 🚀
"""

readme_path = output_dir / "README.md"
readme_path.write_text(readme_content, encoding='utf-8')
print(f"      OK README.md")

# Create installation instructions
install_guide = f"""# Installation Guide - Bot MVP UI

## What's Inside

This package contains everything needed to run Bot MVP UI.

## Requirements

- Python 3.7+
- ~500MB disk space
- ~420MB for embedding model (auto-downloaded)

## Installation Steps

### 1. Extract Package
```
Unzip the package to any location
```

### 2. Install Dependencies
```bash
cd bot-mvp-ui
pip install -r requirements.txt
```

This will install:
- FastAPI, Uvicorn (Web server)
- Anthropic SDK (Claude AI)
- Sentence Transformers (Embeddings)
- And more...

### 3. Configure .env
Edit `.env` file and set:
```
ANTHROPIC_API_KEY=your-key-here
API_PORT=8100
WEB_PORT=8080
```

### 4. Run

**Option A - Automatic (Windows):**
```
Double-click: quickstart.bat
```

**Option B - Automatic (Linux/Mac):**
```bash
bash quickstart.sh
```

**Option C - Manual:**
Terminal 1:
```bash
python api.py
```

Terminal 2:
```bash
python web_server.py
```

### 5. Access

Open in browser:
- http://localhost:8080/index.html

## First Run

On first run:
- Embedding model will download (~420MB) - normal, don't interrupt
- Database `bot_data.db` will be created
- Default users will be seeded

## Ports

- **8100**: API Server (FastAPI)
- **8080**: Web Server (static files + proxy)

If ports are busy, edit `.env` and restart.

## Need Help?

1. Check .env configuration
2. Ensure ANTHROPIC_API_KEY is set
3. Check ports are available
4. Delete bot_data.db and restart for fresh database

---

Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

install_path = output_dir / "INSTALL.md"
install_path.write_text(install_guide, encoding='utf-8')
print(f"      OK INSTALL.md")

# Create a ZIP archive
zip_name = f"bot-mvp-ui_{timestamp}.zip"
zip_path = output_base / zip_name

print(f"\n[ZIP] Creating ZIP archive...")
shutil.make_archive(
    str(output_base / f"bot-mvp-ui_{timestamp}"),
    'zip',
    output_dir.parent,
    output_dir.name
)
print(f"      OK {zip_name}")

print(f"\n{'='*60}")
print(f"SUCCESS: Packaging completed!")
print(f"{'='*60}")
print(f"\nFiles created:")
print(f"[FOLDER] {output_dir}")
print(f"[ZIP]    {zip_path}")
print(f"\nFull paths (copy-paste):")
print(f"   Explorer: {output_dir}")
print(f"   ZIP:      {zip_path}")
print(f"\nYou can now:")
print(f"   1. Open folder: {output_dir}")
print(f"   2. Or download ZIP: {zip_path}")
print(f"   3. Copy to any location and run!")
print(f"\n")

# Open folder in Windows Explorer if on Windows
if sys.platform == 'win32':
    import subprocess
    print("[OPENING] Folder in Windows Explorer...")
    subprocess.Popen(f'explorer "{output_dir}"')
