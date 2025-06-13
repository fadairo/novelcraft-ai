"""AI Content generation with file-based architecture support."""

from typing import Dict, List, Optional, Any
import asyncio
from pathlib import Path


class ContentGenerator:
    """Generates novel content using AI with file-based chapter management."""
    
    def __init__(self, ai_client):
        self.ai_client = ai_client
    
    async def generate_chapter(
        self,
        project,
        chapter_number: int,
        title: str = None,
        outline_section: str = "",
        word_count_target: int = 2500,
        context_chapters: List[int] = None,
    ) -> str:
        """Generate a new chapter based on project context."""
        
        # Auto-generate title if not provided
        if not title:
            title = f"Chapter {chapter_number}"
        
        # Normalize title
        from ..core.document import normalize_chapter_title
        normalized_title = normalize_chapter_title(title)
        
        # Gather context from project
        context = self._build_generation_context(project, chapter_number, context_chapters)
        
        # Generate content
        content = await self.ai_client.generate_chapter(
            chapter_number=chapter_number,
            chapter_title=normalized_title,
            outline=outline_section or context["outline"],
            synopsis=context["synopsis"],
            character_info=context["characters"],
            existing_chapters=context["existing_chapters"],
            word_count_target=word_count_target,
            style_notes=context["style_notes"]
        )
        
        return content
    
    async def generate_and_save_chapter(
        self,
        project,
        chapter_number: int,
        title: str = None,
        outline_section: str = "",
        word_count_target: int = 2000,
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
        """Expand an existing chapter with additional content."""
        
        chapter = project.document.get_chapter(chapter_number)
        if not chapter:
            raise ValueError(f"Chapter {chapter_number} not found")
        
        # Get current content
        current_content = project.get_chapter_content(chapter_number)
        
        # Build context
        context = self._build_generation_context(project, chapter_number)
        
        # Generate expansion
        expanded_content = await self.ai_client.expand_chapter(
            chapter_number=chapter_number,
            chapter_title=chapter.title,
            current_content=current_content,
            expansion_notes=expansion_notes,
            target_words=target_expansion,
            synopsis=context["synopsis"],
            character_info=context["characters"],
            outline=context["outline"]
        )
        
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
        
        # Get AI analysis
        analysis = await self.ai_client.analyze_chapter(
            chapter_number=chapter_number,
            chapter_title=chapter.title,
            content=current_content,
            focus_areas=focus_areas or ["pacing", "dialogue", "character_development", "continuity"],
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
        
        # Generate outline section
        outline = await self.ai_client.generate_outline(
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            plot_points=plot_points,
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
        
        # Get suggestions
        suggestions = await self.ai_client.suggest_chapters(
            next_chapter_number=next_chapter,
            synopsis=context["synopsis"],
            character_info=context["characters"],
            outline=context["outline"],
            existing_chapters=context["existing_chapters"],
            num_suggestions=num_suggestions
        )
        
        return suggestions
    
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
        
        # Get style notes from recent chapters
        style_notes = self._extract_style_notes(project, chapters_to_include)
        
        return {
            "synopsis": synopsis,
            "outline": outline,
            "characters": characters,
            "existing_chapters": existing_chapters,
            "style_notes": style_notes
        }
    
    def _extract_style_notes(self, project, chapter_numbers: List[int]) -> str:
        """Extract style guidance from existing chapters."""
        if not chapter_numbers:
            return "Maintain consistent narrative voice and pacing."
        
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
            
            style_notes = f"Maintain average sentence length around {avg_sentence_length:.1f} words. "
            
            if dialogue_ratio > 0.02:
                style_notes += "Continue using dialogue to drive character development. "
            else:
                style_notes += "Focus on narrative description and internal thoughts. "
                
            return style_notes
        
        return "Maintain consistent narrative voice and pacing."
    
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
        
        # Get suggestions
        suggestions = await self.ai_client.suggest_chapters(
            next_chapter_number=next_chapter,
            synopsis=context["synopsis"],
            character_info=context["characters"],
            outline=context["outline"],
            existing_chapters=context["existing_chapters"],
            num_suggestions=num_suggestions
        )
        
        return suggestions