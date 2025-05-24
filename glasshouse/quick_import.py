#!/usr/bin/env python3
"""
Fixed Quick Import Script

Creates chapters first, then adds content separately to avoid command line length limits.
"""

import subprocess
import tempfile
import os
from pathlib import Path


def run_command(cmd):
    """Run a command and return the result."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def create_empty_chapter(chapter_num, title):
    """Create an empty chapter."""
    # Use the exact CLI format that works
    cmd = [
        'novelcraft', 'chapter', 'create', 'project.json',
        '--number', str(chapter_num),
        '--title', title
    ]
    
    # Run the command and provide empty content when prompted
    try:
        process = subprocess.Popen(
            cmd, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        # Send empty content when prompted
        stdout, stderr = process.communicate(input='\n')
        
        if process.returncode == 0:
            print(f"✅ Created empty Chapter {chapter_num}: {title}")
            return True
        else:
            print(f"❌ Failed to create Chapter {chapter_num}: {stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating Chapter {chapter_num}: {e}")
        return False


def update_chapter_content(chapter_num, title, content):
    """Update chapter content using a temporary file approach."""
    # Write content to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # Import the temporary file
        cmd = ['novelcraft', 'import-text', tmp_path, 'project.json']
        success, output = run_command(cmd)
        
        if success:
            print(f"✅ Updated content for Chapter {chapter_num}")
        else:
            print(f"❌ Failed to update Chapter {chapter_num}: {output}")
        
        return success
    finally:
        # Clean up temporary file
        try:
            os.unlink(tmp_path)
        except:
            pass


def main():
    chapters_dir = Path("chapters")
    
    if not chapters_dir.exists():
        print("❌ chapters/ directory not found. Make sure you've run the split_manuscript.py script first.")
        return
    
    print("🚀 Starting chapter import process...")
    
    # Process each chapter
    for i in range(24):  # 0 to 23
        chapter_file = chapters_dir / f"chapter_{i:02d}.md"
        
        if not chapter_file.exists():
            print(f"⚠️  Chapter file not found: {chapter_file}")
            continue
        
        print(f"\n📖 Processing Chapter {i}...")
        
        # Read the content
        try:
            content = chapter_file.read_text(encoding='utf-8')
        except Exception as e:
            print(f"❌ Error reading {chapter_file}: {e}")
            continue
        
        # Extract title and content
        if content.startswith('# Chapter'):
            lines = content.split('\n', 2)
            title = lines[0].replace('# ', '') if lines else f"Chapter {i}"
            chapter_content = lines[2] if len(lines) > 2 else content
        else:
            title = f"Chapter {i}"
            chapter_content = content
        
        # Clean up content (remove extra whitespace)
        chapter_content = chapter_content.strip()
        
        if not chapter_content:
            print(f"⚠️  Chapter {i} appears to be empty")
            continue
        
        # Create empty chapter first
        if create_empty_chapter(i, title):
            # Then update with content
            update_chapter_content(i, title, chapter_content)
        
        print(f"📊 Chapter {i} word count: {len(chapter_content.split())} words")
    
    print("\n🎉 Import process completed!")
    print("\n📊 Checking final status...")
    
    # Check final status
    cmd = ['novelcraft', 'status', '.']
    success, output = run_command(cmd)
    if success:
        print(output)
    else:
        print("❌ Error checking status:", output)


if __name__ == "__main__":
    main()