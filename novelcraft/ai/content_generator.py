"""AI Content generation with file-based architecture support and revision instructions."""

from typing import Dict, List, Optional, Any
import asyncio
from pathlib import Path


class ContentGenerator:
    """Generates novel content using AI with file-based chapter management and revision instructions."""
    
    def __init__(self, ai_client, revision_instructions_path: str = None):
        self.ai_client = ai_client
        self.revision_instructions = None
        
        # Load revision instructions if path provided
        if revision_instructions_path:
            self.load_revision_instructions(revision_instructions_path)
    
    def load_revision_instructions(self, path: str) -> None:
        """Load revision instructions from markdown file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.revision_instructions = f.read()
        except FileNotFoundError:
            print(f"Warning: Revision instructions file not found at {path}")
            self.revision_instructions = None
        except Exception as e:
            print(f"Error loading revision instructions: {e}")
            self.revision_instructions = None
    
    def _enhance_prompt_with_instructions(self, base_prompt: str) -> str:
        """Enhance the base prompt with revision instructions."""
        if not self.revision_instructions:
            return base_prompt
        
        # Prepend the revision instructions to the prompt
        enhanced_prompt = f"""IMPORTANT WRITING STYLE INSTRUCTIONS:
{self.revision_instructions}

---

Now, following the above style instructions carefully, {base_prompt}"""
        
        return enhanced_prompt
    
    async def generate_chapter(
        self,
        project,
        chapter_number: int,
        title: str = None,
        outline_section: str = "",
        word_count_target: int = 3500,
        context_chapters: List[int] = None,
    ) -> str:
        """Generate a new chapter based on project context with revision instructions."""
        
        # Auto-generate title if not provided
        if not title:
            title = f"Chapter {chapter_number}"
        
        # Normalize title
        from ..core.document import normalize_chapter_title
        normalized_title = normalize_chapter_title(title)
        
        # Gather context from project
        context = self._build_generation_context(project, chapter_number, context_chapters)
        
        # Build the enhanced style notes with revision instructions and inspiration
        enhanced_style_notes = context["style_notes"]
        
        # Add inspiration if available
        if context.get("inspiration"):
            enhanced_style_notes = f"INSPIRATION AND STYLE REFERENCES:\n{context['inspiration']}\n\n{enhanced_style_notes}"
        
        # Add revision instructions if available
        if self.revision_instructions:
            enhanced_style_notes = f"{self.revision_instructions}\n\n{enhanced_style_notes}"
        
        # Generate content using existing ClaudeClient method signature
        content = await self.ai_client.generate_chapter(
            chapter_number=chapter_number,
            chapter_title=normalized_title,
            outline=outline_section or context["outline"],
            synopsis=context["synopsis"],
            character_info=context["characters"],
            existing_chapters=context["existing_chapters"],
            word_count_target=word_count_target,
            style_notes=enhanced_style_notes  # Pass revision instructions and inspiration through style_notes
        )
        
        return content
    
    async def generate_and_save_chapter(
        self,
        project,
        chapter_number: int,
        title: str = None,
        outline_section: str = "",
        word_count_target: int = 3500,
        context_chapters: List[int] = None,
    ) -> bool:
        """Generate a chapter and save it to file."""
        try:
            # Check if chapter already exists
            if chapter_number in project.document.chapters:
                raise ValueError(f"Chapter {chapter_number} already exists")
            
            # Generate content
            content = await self.generate_chapter(
                project, chapter_number, title, outline_section, 
                word_count_target, context_chapters
            )
            
            # Create and save chapter
            final_title = title or f"Chapter {chapter_number}"
            success = project.create_chapter(chapter_number, final_title, content)
            
            return success
            
        except Exception as e:
            print(f"Error generating chapter: {e}")
            return False
    
    async def expand_chapter(
        self,
        project,
        chapter_number: int,
        expansion_notes: str = "",
        target_expansion: int = 500,
    ) -> str:
        """Expand an existing chapter by integrating new content throughout."""
        
        chapter = project.document.get_chapter(chapter_number)
        if not chapter:
            raise ValueError(f"Chapter {chapter_number} not found")
        
        # Get current content
        current_content = project.get_chapter_content(chapter_number)
        current_word_count = len(current_content.split())
        
        print(f"Current chapter has {current_word_count} words")
        
        # Build context
        context = self._build_generation_context(project, chapter_number)
        
        # Build enhanced expansion notes with revision instructions
        enhanced_expansion_notes = f"""You must expand this chapter from {current_word_count} words to approximately {current_word_count + target_expansion} words.

CRITICAL INSTRUCTIONS:
1. Return the ENTIRE chapter with expansions integrated throughout
2. Do NOT return just the original text - you MUST add new content
3. Add approximately {target_expansion} new words by:
   - Expanding every scene with more sensory details
   - Adding dialogue beats, pauses, and physical reactions between spoken lines
   - Inserting character thoughts and internal reactions
   - Describing settings and atmosphere in greater detail
   - Adding transitional passages between scenes
   - Expanding action sequences with more specific movements
4. Start immediately with the chapter text (no preamble)
5. Ensure all sentences are complete
6. The expanded version MUST be significantly longer than the original

Original chapter content follows. Expand it throughout:
---
{current_content}
---

Return the complete expanded chapter text now:"""

        if expansion_notes:
            enhanced_expansion_notes = f"{enhanced_expansion_notes}\n\nSpecific expansion focus: {expansion_notes}"
            
        if self.revision_instructions:
            # Add revision instructions but keep them concise for expansion
            enhanced_expansion_notes = f"{enhanced_expansion_notes}\n\nApply these style principles during expansion:\n{self.revision_instructions[:1500]}..."
        
        # Pass the enhanced notes through the expansion_notes parameter
        # Don't pass the current content again since it's already in the notes
        expanded_content = await self.ai_client.expand_chapter(
            chapter_number=chapter_number,
            chapter_title=chapter.title,
            current_content="",  # Empty since we included it in the notes
            expansion_notes=enhanced_expansion_notes,
            target_words=current_word_count + target_expansion,  # Total target, not just addition
            synopsis=context["synopsis"],
            character_info=context["characters"],
            outline=context["outline"]
        )
        
        # Clean up the response
        expanded_content = expanded_content.strip()
        
        # Remove any preamble if it exists
        lines = expanded_content.split('\n')
        if lines:
            # Check first line for common preamble patterns
            first_line_lower = lines[0].lower()
            if any(phrase in first_line_lower for phrase in [
                "here is", "here's", "expanded version", "chapter with", 
                "additional words", "woven throughout", "expanded chapter",
                "complete expanded", "i've expanded", "i have expanded"
            ]) or lines[0].endswith(':'):
                expanded_content = '\n'.join(lines[1:]).strip()
        
        # Double-check we actually got expanded content
        expanded_word_count = len(expanded_content.split())
        print(f"Expanded chapter has {expanded_word_count} words")
        
        if expanded_word_count <= current_word_count:
            print(f"WARNING: Expansion failed. Original: {current_word_count} words, Returned: {expanded_word_count} words")
            # Try to return the original content to avoid data loss
            return current_content
        
        # Ensure the content doesn't end mid-sentence
        if expanded_content and not expanded_content.rstrip().endswith(('.', '!', '?', '"')):
            # Try to find the last complete sentence
            last_sentence_end = max(
                expanded_content.rfind('.'),
                expanded_content.rfind('!'),
                expanded_content.rfind('?')
            )
            
            if last_sentence_end > 0:
                # Check if there's a quote after the punctuation
                quote_after = expanded_content.find('"', last_sentence_end)
                if quote_after > last_sentence_end and quote_after - last_sentence_end < 5:
                    expanded_content = expanded_content[:quote_after + 1]
                else:
                    expanded_content = expanded_content[:last_sentence_end + 1]
        
        return expanded_content
    
    async def improve_chapter(
        self,
        project,
        chapter_number: int,
        focus_areas: List[str] = None,
    ) -> Dict[str, Any]:
        """Analyze and suggest improvements for a chapter."""
        
        chapter = project.document.get_chapter(chapter_number)
        if not chapter:
            raise ValueError(f"Chapter {chapter_number} not found")
        
        # Get current content
        current_content = project.get_chapter_content(chapter_number)
        
        # Build context
        context = self._build_generation_context(project, chapter_number)
        
        # If we have revision instructions, add them to the focus areas context
        enhanced_focus_areas = focus_areas or ["pacing", "dialogue", "character_development", "continuity"]
        
        # Get AI analysis
        analysis = await self.ai_client.analyze_chapter(
            chapter_number=chapter_number,
            chapter_title=chapter.title,
            content=current_content,
            focus_areas=enhanced_focus_areas,
            synopsis=context["synopsis"],
            character_info=context["characters"],
            existing_chapters=context["existing_chapters"]
        )
        
        return analysis
    
    async def generate_outline_section(
        self,
        project,
        chapter_start: int,
        chapter_end: int,
        plot_points: str = "",
    ) -> str:
        """Generate outline for a range of chapters."""
        
        # Build context
        context = self._build_generation_context(project, chapter_start)
        
        # Enhance plot points with style instructions if available
        enhanced_plot_points = plot_points
        if self.revision_instructions:
            enhanced_plot_points = f"""Style guide for outline:
{self.revision_instructions}

Plot points: {plot_points}"""
        
        # Generate outline section
        outline = await self.ai_client.generate_outline(
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            plot_points=enhanced_plot_points,
            synopsis=context["synopsis"],
            character_info=context["characters"],
            existing_outline=context["outline"],
            existing_chapters=context["existing_chapters"]
        )
        
        return outline
    
    async def check_continuity(
        self,
        project,
        chapter_range: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Check continuity across chapters."""
        
        if not chapter_range:
            chapter_range = list(project.document.chapters.keys())
        
        # Gather content from specified chapters
        chapter_contents = {}
        for chapter_num in chapter_range:
            if chapter_num in project.document.chapters:
                content = project.get_chapter_content(chapter_num)
                chapter_contents[chapter_num] = content
        
        # Build context
        context = self._build_generation_context(project, min(chapter_range))
        
        # Check continuity
        continuity_report = await self.ai_client.check_continuity(
            chapter_contents=chapter_contents,
            character_info=context["characters"],
            synopsis=context["synopsis"],
            outline=context["outline"]
        )
        
        return continuity_report
    
    async def suggest_next_chapters(
        self,
        project,
        num_suggestions: int = 3,
    ) -> List[Dict[str, Any]]:
        """Suggest ideas for next chapters based on current progress."""
        
        # Find the highest chapter number
        if not project.document.chapters:
            next_chapter = 1
        else:
            next_chapter = max(project.document.chapters.keys()) + 1
        
        # Build context
        context = self._build_generation_context(project, next_chapter)
        
        # Build enhanced context with style guide
        enhanced_existing_chapters = context["existing_chapters"]
        if self.revision_instructions:
            # Add style guide as a special entry
            enhanced_existing_chapters["style_guide"] = f"Follow these style instructions:\n{self.revision_instructions}"
        
        # Get suggestions
        suggestions = await self.ai_client.suggest_chapters(
            next_chapter_number=next_chapter,
            synopsis=context["synopsis"],
            character_info=context["characters"],
            outline=context["outline"],
            existing_chapters=enhanced_existing_chapters,
            num_suggestions=num_suggestions
        )
        
        return suggestions
    
    def _load_inspiration_file(self, project_path: Path) -> str:
        """Load inspiration.md file if it exists."""
        inspiration_path = project_path / "inspiration.md"
        if inspiration_path.exists():
            try:
                with open(inspiration_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"Warning: Could not load inspiration file: {e}")
        return ""
    
    def _build_generation_context(
        self, 
        project, 
        current_chapter: int, 
        context_chapters: List[int] = None
    ) -> Dict[str, Any]:
        """Build context information for AI generation."""
        
        # Get synopsis
        synopsis = project.document.synopsis or "No synopsis available."
        
        # Get outline
        outline = project.document.outline or "No outline available."
        
        # Get character information
        characters = project.characters.generate_character_summary()
        
        # Load inspiration file if available
        inspiration = self._load_inspiration_file(project.project_path)
        
        # Get existing chapters for context
        existing_chapters = {}
        
        if context_chapters:
            # Use specified chapters
            chapters_to_include = context_chapters
        else:
            # Use recent chapters (last 3 before current)
            all_chapters = sorted(project.document.chapters.keys())
            chapters_to_include = [
                ch for ch in all_chapters 
                if ch < current_chapter
            ][-3:]  # Last 3 chapters before current
        
        for chapter_num in chapters_to_include:
            if chapter_num in project.document.chapters:
                content = project.get_chapter_content(chapter_num)
                # Truncate content to avoid token limits
                if len(content) > 2000:
                    content = content[:2000] + "..."
                existing_chapters[chapter_num] = content
        
        # Get style notes from recent chapters, enhanced with revision instructions
        style_notes = self._extract_style_notes(project, chapters_to_include)
        
        return {
            "synopsis": synopsis,
            "outline": outline,
            "characters": characters,
            "existing_chapters": existing_chapters,
            "style_notes": style_notes,
            "inspiration": inspiration
        }
    
    def _extract_style_notes(self, project, chapter_numbers: List[int]) -> str:
        """Extract style guidance from existing chapters."""
        base_notes = ""
        
        if not chapter_numbers:
            base_notes = "Maintain consistent narrative voice and pacing."
        else:
            # Simple style analysis based on recent chapters
            total_words = 0
            total_sentences = 0
            dialogue_count = 0
            
            for chapter_num in chapter_numbers[-2:]:  # Last 2 chapters
                if chapter_num in project.document.chapters:
                    content = project.get_chapter_content(chapter_num)
                    
                    # Basic analysis
                    words = len(content.split())
                    sentences = len([s for s in content.split('.') if s.strip()])
                    dialogue_lines = content.count('"')
                    
                    total_words += words
                    total_sentences += sentences
                    dialogue_count += dialogue_lines
            
            if total_sentences > 0:
                avg_sentence_length = total_words / total_sentences
                dialogue_ratio = dialogue_count / total_words if total_words > 0 else 0
                
                base_notes = f"Maintain average sentence length around {avg_sentence_length:.1f} words. "
                
                if dialogue_ratio > 0.02:
                    base_notes += "Continue using dialogue to drive character development. "
                else:
                    base_notes += "Focus on narrative description and internal thoughts. "
            else:
                base_notes = "Maintain consistent narrative voice and pacing."
        
        # If we have revision instructions, they're already being passed through other means
        # This method just extracts style from existing chapters
        return base_notes