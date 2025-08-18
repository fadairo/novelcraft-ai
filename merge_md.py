#!/usr/bin/env python3
"""
Merge multiple .md files into a single .md file with separator markers.
"""

import os
import glob
import argparse
from pathlib import Path

def merge_markdown_files(input_dir, output_file, separator=None, sort_files=True):
    """
    Merge all .md files from input directory into a single output file.
    
    Args:
        input_dir (str): Directory containing .md files to merge
        output_file (str): Path for the output merged file
        separator (str): Custom separator between files (optional)
        sort_files (bool): Whether to sort files alphabetically
    """
    
    # Default separator
    if separator is None:
        separator = "\n\n---\n\n"
    
    # Find all .md files in the input directory
    pattern = os.path.join(input_dir, "*.md")
    md_files = glob.glob(pattern)
    
    if not md_files:
        print(f"No .md files found in {input_dir}")
        return
    
    # Sort files if requested
    if sort_files:
        md_files.sort()
    
    print(f"Found {len(md_files)} markdown files to merge:")
    for f in md_files:
        print(f"  - {os.path.basename(f)}")
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Merge files
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for i, md_file in enumerate(md_files):
            try:
                with open(md_file, 'r', encoding='utf-8') as infile:
                    # Add filename as comment (optional)
                    filename = os.path.basename(md_file)
                    outfile.write(f"<!-- Source: {filename} -->\n\n")
                    
                    # Write file content
                    content = infile.read().strip()
                    outfile.write(content)
                    
                    # Add separator between files (except after the last file)
                    if i < len(md_files) - 1:
                        outfile.write(separator)
                    else:
                        outfile.write("\n")
                        
            except Exception as e:
                print(f"Error reading {md_file}: {e}")
                continue
    
    print(f"\nMerged {len(md_files)} files into: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple .md files into a single markdown file"
    )
    
    parser.add_argument(
        "input_dir", 
        help="Directory containing .md files to merge"
    )
    
    parser.add_argument(
        "-o", "--output", 
        default="merged.md",
        help="Output file path (default: merged.md)"
    )
    
    parser.add_argument(
        "-s", "--separator",
        default="\n\n---\n\n",
        help="Separator between files (default: \\n\\n---\\n\\n)"
    )
    
    parser.add_argument(
        "--no-sort",
        action="store_true",
        help="Don't sort files alphabetically"
    )
    
    args = parser.parse_args()
    
    # Validate input directory
    if not os.path.isdir(args.input_dir):
        print(f"Error: {args.input_dir} is not a valid directory")
        return 1
    
    # Merge files
    merge_markdown_files(
        input_dir=args.input_dir,
        output_file=args.output,
        separator=args.separator,
        sort_files=not args.no_sort
    )
    
    return 0

# Alternative function for programmatic use
def simple_merge(directory_path, output_path="merged.md"):
    """
    Simple function to merge all .md files in a directory.
    
    Args:
        directory_path (str): Path to directory containing .md files
        output_path (str): Path for output file
    """
    merge_markdown_files(directory_path, output_path)

if __name__ == "__main__":
    # Example usage when run directly
    import sys
    
    if len(sys.argv) < 2:
        print("Usage examples:")
        print("  python merge_md.py /path/to/markdown/files")
        print("  python merge_md.py /path/to/files -o combined.md")
        print("  python merge_md.py /path/to/files -s '\\n\\n### END FILE ###\\n\\n'")
        print("\nFor more options, use: python merge_md.py --help")
        sys.exit(1)
    
    exit_code = main()
    sys.exit(exit_code)