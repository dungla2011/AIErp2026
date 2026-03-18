#!/usr/bin/env python3
"""
Script to copy MVP-bot-api files to ui folder
"""
import os
import shutil
from pathlib import Path

# Define source and destination directories
source_dir = Path(r"e:\Projects\AI-setup-clawbot\MVP-bot-api")
dest_dir = Path(r"e:\Projects\AIErp2026\ai-agent\ui")

# List of files to copy
files_to_copy = [
    "api.py",
    "bot.py",
    "database.py",
    "memory.py",
    "utils.py",
    "skills.py",
    "embeddings.py",
    "data_provider.py",
    "docs_api.py",
    "doc_processor.py",
    "rag.py",
    ".env",
    "requirements.txt",
]

# Copy files
for file in files_to_copy:
    src_file = source_dir / file
    dst_file = dest_dir / file
    
    if src_file.exists():
        try:
            shutil.copy2(str(src_file), str(dst_file))
            print(f"✓ Copied: {file}")
        except Exception as e:
            print(f"✗ Error copying {file}: {e}")
    else:
        print(f"⚠ File not found: {file}")

# Copy web folder
web_src = source_dir / "web"
web_dst = dest_dir / "web"

if web_src.exists():
    if web_dst.exists():
        shutil.rmtree(str(web_dst))
    shutil.copytree(str(web_src), str(web_dst))
    print(f"✓ Copied web folder with all files")
else:
    print(f"⚠ Web folder not found")

# Copy uploads folder if exists
uploads_src = source_dir / "uploads"
uploads_dst = dest_dir / "uploads"

if uploads_src.exists():
    if uploads_dst.exists():
        shutil.rmtree(str(uploads_dst))
    shutil.copytree(str(uploads_src), str(uploads_dst))
    print(f"✓ Copied uploads folder")

print("\n✅ Copy completed successfully!")
