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
import os
from pathlib import Path
from typing import Optional, Tuple
import re

# Set up the Python path to find the modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import required modules
try:
    # Try direct import first
    import os
    import json
    import asyncio as async_module
    from typing import Dict, List, Optional, Any, AsyncIterator
    from anthropic import AsyncAnthropic
    from tenacity import retry, stop_after_attempt, wait_exponential
    import logging

    # Copy the ClaudeClient class directly to avoid import issues
    logger = logging.getLogger(__name__)

    class ClaudeClient:
        """Client for interacting with Claude AI API with streaming support."""
        
        def __init__(self, api_key: Optional[str] = None):
            """Initialize Claude client with async support."""
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable or api_key parameter is required")
            
            # Use AsyncAnthropic for proper async support
            self.client = AsyncAnthropic(api_key=self.api_key)
            self.model = "claude-opus-4-20250514"  # Default model
            self.max_tokens = 10000
            self.use_streaming = True  # Enable streaming by default for long operations
        
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
        async def _make_request(self, messages: List[Dict[str, str]], system: str = "") -> str:
            """Make a request to Claude API with retry logic and streaming support."""
            try:
                # For operations that might take long (like chapter generation), use streaming
                if self.use_streaming and self.max_tokens > 10000:
                    return await self._make_streaming_request(messages, system)
                else:
                    # For shorter operations, use regular request
                    response = await self.client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=system,
                        messages=messages,
                        timeout=600.0  # 10 minute timeout
                    )
                    return response.content[0].text
            except Exception as e:
                logger.error(f"API request failed: {e}")
                raise
        
        async def _make_streaming_request(self, messages: List[Dict[str, str]], system: str = "") -> str:
            """Make a streaming request to Claude API for long operations."""
            try:
                full_response = []
                
                # Create streaming response
                async with self.client.messages.stream(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system,
                    messages=messages,
                ) as stream:
                    async for text in stream.text_stream:
                        full_response.append(text)
                
                return ''.join(full_response)
                
            except Exception as e:
                logger.error(f"Streaming API request failed: {e}")
                raise
        
        async def generate_chapter(
            self,
            chapter_number: int,
            chapter_title: str,
            outline: str,
            synopsis: str,
            character_info: str,
            existing_chapters: Optional[Dict[int, str]] = None,
            word_count_target: int = 2500,
            style_notes: str = "",
        ) -> str:
            """Generate a chapter using Claude with normalized title format."""
            normalized_title = f"Chapter {chapter_number}: {chapter_title}"
            
            existing_chapters = existing_chapters or {}
            
            # Build context from existing chapters
            context = self._build_chapter_context(existing_chapters, chapter_number)
            
            system_prompt = self._create_chapter_generation_prompt(
                normalized_title=normalized_title,
                synopsis=synopsis,
                word_count_target=word_count_target,
                character_info=character_info,
                outline=outline,
                style_notes=style_notes,
                context=context
            )
            
            messages = [
                {
                    "role": "user",
                    "content": f"Please write {normalized_title}"
                }
            ]
            
            # Enable streaming for chapter generation
            self.use_streaming = True
            return await self._make_request(messages, system_prompt)
        
        def _build_chapter_context(self, existing_chapters: Dict[int, str], current_chapter: int) -> str:
            """Build context from existing chapters."""
            if not existing_chapters:
                return ""
            
            context = "\n\nPrevious chapters for context:\n"
            for ch_num in sorted(existing_chapters.keys()):
                if ch_num < current_chapter:
                    # Limit context to 1000 chars per chapter to avoid token limits
                    context += f"\n--- Chapter {ch_num} ---\n{existing_chapters[ch_num][:1000]}...\n"
            
            return context
        
        def _create_chapter_generation_prompt(
            self,
            normalized_title: str,
            synopsis: str,
            word_count_target: int,
            character_info: str,
            outline: str,
            style_notes: str,
            context: str
        ) -> str:
            """Create the system prompt for chapter generation."""
            return f"""You are a novelist writing {normalized_title} of a novel.

NOVEL INFORMATION:
- Synopsis: {synopsis}
- Chapter Title: {normalized_title}
- Target word count: {word_count_target} words

CHARACTER INFORMATION:
{character_info}

OUTLINE/PLOT POINTS:
{outline}

STYLE NOTES:
{style_notes}

CONTEXT:
{context}

Write {normalized_title} following the outline and maintaining consistency with previous chapters. 
Focus on:
- Character development and authentic dialogue
- Advancing the plot according to the outline
- Maintaining the established tone and style
- Creating engaging scenes with proper pacing
- Reaching approximately {word_count_target} words

IMPORTANT: Use the exact chapter title format "{normalized_title}" at the beginning of your response.
Write the chapter content directly without any meta-commentary."""

except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please make sure you have installed: anthropic, tenacity")
    sys.exit(1)


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
        
        # Load main project files from project directory
        project_files = {
            'outline': 'outline.md',
            'synopsis': 'synopsis.md',
            'characters': 'characters.md',
            'inspiration': 'inspiration.md',
        }
        
        for key, filename in project_files.items():
            content = self.load_file_content(self.project_path / filename)
            if content:
                context[key] = content
            else:
                print(f"Warning: Could not load {filename}")
                context[key] = ""
        
        # Load revision instructions from root directory
        revision_filename = 'reviser_text_instructions.md'
        
        # Try root directory (parent of project directory if script is in project)
        # or current directory if script is in root
        root_path = Path(revision_filename)
        
        revision_content = self.load_file_content(root_path)
        
        if revision_content:
            context['revision_instructions'] = revision_content
        else:
            print(f"Warning: Could not load {revision_filename} from root directory")
            context['revision_instructions'] = ""
        
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
            
            # Generate revised content using AI
            print("Generating revision...")
            
            # Creatively use generate_chapter by putting our revision context into the style_notes
            # and the current chapter + criticism into the outline
            revision_context = f"""REVISION TASK: You are revising Chapter {chapter_number} based on literary criticism.

REVISION INSTRUCTIONS:
{context.get('revision_instructions', 'No specific revision instructions provided.')}

LITERARY CRITICISM AND SUGGESTIONS:
{criticism_content}

INSPIRATION AND STYLE:
{context.get('inspiration', 'No inspiration notes available.')}

CRITICAL INSTRUCTION: You must output ONLY the revised chapter text. Do not include any preamble, explanation, or meta-commentary. Start immediately with the chapter content."""

            # Create a special "outline" that includes the current chapter to revise
            revision_outline = f"""CURRENT CHAPTER TO REVISE:
{chapter_content}

REVISION REQUIREMENTS:
1. Address all weaknesses identified in the literary criticism
2. Preserve and enhance the identified strengths
3. Maintain consistency with the novel's synopsis, characters, and outline
4. Apply the revision instructions and style guidelines
5. Ensure natural flow and narrative momentum
6. Output ONLY the revised chapter text"""

            # Use generate_chapter creatively by treating this as generating a "new" chapter
            # but with our revision context
            revised_content = await self.ai_client.generate_chapter(
                chapter_number=chapter_number,
                chapter_title=f"Chapter {chapter_number} (Revised Draft)",
                outline=revision_outline,
                synopsis=context.get('synopsis', ''),
                character_info=context.get('characters', ''),
                existing_chapters={},  # Don't pass existing chapters to avoid confusion
                word_count_target=len(chapter_content.split()),  # Aim for similar length
                style_notes=revision_context
            )
            
            # Clean up the response
            revised_content = self._clean_revised_content(revised_content)
            
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