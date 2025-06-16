#!/usr/bin/env python3
"""
Revise a draft chapter based on literary criticism and revision suggestions.

Usage:
    python revise_chapter.py <chapter_number>

Example:
    python revise_chapter.py 16
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple
import re

# Import the AI client from your project structure
from ai.claude_client import ClaudeClient


class ChapterReviser:
    """Handles revision of draft chapters based on literary criticism."""
    
    def __init__(self, ai_client, project_path: str = "project"):
        self.ai_client = ai_client
        self.project_path = Path(project_path)
        self.chapters_path = self.project_path / "chapters"
        self.drafts_path = self.chapters_path / "drafts"
        self.crit_path = self.chapters_path / "crit"
        
        # Ensure directories exist
        self.drafts_path.mkdir(parents=True, exist_ok=True)
        
    def get_next_draft_number(self, chapter_number: int) -> int:
        """Determine the next draft number for a chapter."""
        # Pattern to match draft files: 16_chapter_16_01.md, 16_chapter_16_02.md, etc.
        pattern = re.compile(rf"^{chapter_number}_chapter_{chapter_number}_(\d{{2}})\.md$")
        
        existing_drafts = []
        if self.drafts_path.exists():
            for file in self.drafts_path.iterdir():
                match = pattern.match(file.name)
                if match:
                    draft_num = int(match.group(1))
                    existing_drafts.append(draft_num)
        
        if existing_drafts:
            return max(existing_drafts) + 1
        else:
            return 1
    
    def load_file_content(self, file_path: Path) -> Optional[str]:
        """Load content from a file, return None if not found."""
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        return None
    
    def load_project_context(self) -> dict:
        """Load all project context files."""
        context = {}
        
        # Load main project files
        files_to_load = {
            'outline': 'outline.md',
            'synopsis': 'synopsis.md',
            'characters': 'characters.md',
            'inspiration': 'inspiration.md',
            'revision_instructions': 'reviser_text_instructions.md'
        }
        
        for key, filename in files_to_load.items():
            content = self.load_file_content(self.project_path / filename)
            if content:
                context[key] = content
            else:
                print(f"Warning: Could not load {filename}")
                context[key] = ""
        
        return context
    
    def load_chapter_and_criticism(self, chapter_number: int) -> Tuple[Optional[str], Optional[str]]:
        """Load the current chapter content and its criticism."""
        # Load current chapter
        chapter_filename = f"{chapter_number}_chapter_{chapter_number}.md"
        chapter_path = self.chapters_path / chapter_filename
        chapter_content = self.load_file_content(chapter_path)
        
        if not chapter_content:
            raise FileNotFoundError(f"Chapter file not found: {chapter_path}")
        
        # Load criticism
        crit_filename = f"{chapter_number}_chapter_{chapter_number}_crit.md"
        crit_path = self.crit_path / crit_filename
        criticism_content = self.load_file_content(crit_path)
        
        if not criticism_content:
            raise FileNotFoundError(f"Criticism file not found: {crit_path}")
        
        return chapter_content, criticism_content
    
    def save_draft(self, chapter_number: int, draft_number: int, content: str) -> Path:
        """Save the revised chapter as a new draft."""
        # Format draft number with leading zero
        draft_filename = f"{chapter_number}_chapter_{chapter_number}_{draft_number:02d}.md"
        draft_path = self.drafts_path / draft_filename
        
        # Also save a copy as the main chapter file
        main_filename = f"{chapter_number}_chapter_{chapter_number}.md"
        main_path = self.chapters_path / main_filename
        
        try:
            # Save as draft
            with open(draft_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Saved draft to: {draft_path}")
            
            # Update main chapter file
            with open(main_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated main chapter file: {main_path}")
            
            return draft_path
            
        except Exception as e:
            print(f"Error saving draft: {e}")
            raise
    
    async def revise_chapter(self, chapter_number: int) -> bool:
        """Main method to revise a chapter based on criticism."""
        try:
            # Load all necessary content
            print(f"Loading chapter {chapter_number} and criticism...")
            chapter_content, criticism_content = self.load_chapter_and_criticism(chapter_number)
            
            print("Loading project context...")
            context = self.load_project_context()
            
            # Determine next draft number
            next_draft_number = self.get_next_draft_number(chapter_number)
            print(f"Creating draft {next_draft_number} for chapter {chapter_number}")
            
            # Save the draft
            draft_path = self.save_draft(chapter_number, next_draft_number, revised_content)
            
            print(f"\nRevision complete! Draft {next_draft_number} saved successfully.")
            return True
            
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error during revision: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _clean_revised_content(self, content: str) -> str:
        """Clean up the AI-generated content."""
        # Remove any potential preamble
        lines = content.strip().split('\n')
        
        # Check if first line is a preamble
        if lines:
            first_line_lower = lines[0].lower()
            preamble_indicators = [
                "here is", "here's", "revised", "chapter", "following",
                "based on", "i've", "i have", "below"
            ]
            
            if any(phrase in first_line_lower for phrase in preamble_indicators) or lines[0].endswith(':'):
                # Skip the preamble line(s)
                content = '\n'.join(lines[1:]).strip()
        
        # Ensure content doesn't end mid-sentence
        if content and not content.rstrip().endswith(('.', '!', '?', '"', '"', "'")):
            # Find the last complete sentence
            last_punctuation = max(
                content.rfind('.'),
                content.rfind('!'),
                content.rfind('?')
            )
            
            if last_punctuation > 0:
                # Check for closing quotes after punctuation
                remaining = content[last_punctuation + 1:].strip()
                if remaining and remaining[0] in ['"', '"', "'"]:
                    last_punctuation += 1
                
                content = content[:last_punctuation + 1]
        
        return content.strip()


async def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Revise a draft chapter based on literary criticism"
    )
    parser.add_argument(
        "chapter_number",
        type=int,
        help="Chapter number to revise"
    )
    parser.add_argument(
        "--project-path",
        type=str,
        default="project",
        help="Path to the project directory (default: 'project')"
    )
    
    args = parser.parse_args()
    
    # Initialize AI client using the same pattern as main.py
    ai_client = ClaudeClient()
    
    # Initialize reviser
    reviser = ChapterReviser(ai_client, args.project_path)
    
    # Run revision
    success = await reviser.revise_chapter(args.chapter_number)
    
    if success:
        print("\nRevision completed successfully!")
        sys.exit(0)
    else:
        print("\nRevision failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())