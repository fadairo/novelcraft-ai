#!/usr/bin/env python3
"""
Manuscript Chapter Splitter

This script reads a manuscript file and splits it into individual Markdown files
for each chapter, including Chapter 0.
"""

import re
from pathlib import Path
from docx import Document
import argparse
import sys


def read_manuscript(file_path):
    """Read manuscript from either .docx or .txt file."""
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if path.suffix.lower() == '.docx':
        # Read Word document
        doc = Document(path)
        content = '\n'.join(paragraph.text for paragraph in doc.paragraphs)
    elif path.suffix.lower() in ['.txt', '.md']:
        # Read plain text file
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")
    
    return content


def split_into_chapters(content):
    """Split manuscript content into chapters."""
    # Pattern to match chapter headings including Chapter 0
    # Looks for "Chapter" followed by a number (including 0)
    chapter_pattern = r'\n\s*(Chapter\s+\d+)\s*\n'
    
    # Split the content using the chapter pattern
    parts = re.split(chapter_pattern, content, flags=re.IGNORECASE)
    
    chapters = {}
    
    # The split creates alternating parts: [before_first_chapter, title1, content1, title2, content2, ...]
    if len(parts) > 1:
        # Skip the content before the first chapter (index 0)
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                chapter_title = parts[i].strip()
                chapter_content = parts[i + 1].strip()
                
                # Extract chapter number from title
                match = re.search(r'Chapter\s+(\d+)', chapter_title, re.IGNORECASE)
                if match:
                    chapter_num = int(match.group(1))
                    chapters[chapter_num] = {
                        'title': chapter_title,
                        'content': chapter_content
                    }
    
    return chapters


def create_chapter_files(chapters, output_dir="chapters"):
    """Create individual Markdown files for each chapter."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    created_files = []
    
    # Sort chapters by number (including Chapter 0)
    for chapter_num in sorted(chapters.keys()):
        chapter_data = chapters[chapter_num]
        
        # Create filename with zero-padding for proper sorting
        filename = f"chapter_{chapter_num:02d}.md"
        file_path = output_path / filename
        
        # Create Markdown content
        markdown_content = f"# {chapter_data['title']}\n\n{chapter_data['content']}\n"
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        created_files.append(file_path)
        print(f"Created: {file_path}")
    
    return created_files


def get_chapter_stats(chapters):
    """Get statistics about the chapters."""
    total_words = 0
    stats = []
    
    for chapter_num in sorted(chapters.keys()):
        content = chapters[chapter_num]['content']
        word_count = len(content.split())
        total_words += word_count
        
        stats.append({
            'number': chapter_num,
            'title': chapters[chapter_num]['title'],
            'words': word_count
        })
    
    return stats, total_words


def main():
    parser = argparse.ArgumentParser(description='Split manuscript into individual chapter files')
    parser.add_argument('manuscript', help='Path to manuscript file (.docx or .txt)')
    parser.add_argument('-o', '--output', default='chapters', help='Output directory for chapter files')
    parser.add_argument('-s', '--stats', action='store_true', help='Show chapter statistics')
    
    args = parser.parse_args()
    
    try:
        print(f"Reading manuscript: {args.manuscript}")
        content = read_manuscript(args.manuscript)
        
        print("Splitting into chapters...")
        chapters = split_into_chapters(content)
        
        if not chapters:
            print("❌ No chapters found. Check that your manuscript has 'Chapter X' headings.")
            return 1
        
        print(f"Found {len(chapters)} chapters (including Chapter 0 if present)")
        
        # Show statistics if requested
        if args.stats:
            stats, total_words = get_chapter_stats(chapters)
            print("\n📊 Chapter Statistics:")
            print("-" * 50)
            for stat in stats:
                print(f"Chapter {stat['number']:2d}: {stat['words']:5,} words - {stat['title']}")
            print("-" * 50)
            print(f"Total: {total_words:,} words across {len(chapters)} chapters")
            print()
        
        # Create chapter files
        print(f"Creating chapter files in '{args.output}/' directory...")
        created_files = create_chapter_files(chapters, args.output)
        
        print(f"\n✅ Successfully created {len(created_files)} chapter files!")
        print(f"📁 Files saved in: {Path(args.output).absolute()}")
        
        # Show next steps
        print("\n📋 Next steps:")
        print("1. Review the generated .md files")
        print("2. Import them into NovelCraft using:")
        print("   novelcraft import-text chapters/chapter_01.md project.json")
        print("   novelcraft import-text chapters/chapter_02.md project.json")
        print("   # etc. for each chapter")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())