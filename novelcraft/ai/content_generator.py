"""Content generation using AI."""

from typing import Dict, List, Optional
import asyncio


class ContentGenerator:
    """Generates novel content using AI."""
    
    def __init__(self, ai_client):
        self.ai_client = ai_client
    
    async def generate_chapter(
        self,
        chapter_number: int,
        title: str,
        outline: str,
        synopsis: str,
        character_info: str,
        existing_chapters: Optional[Dict[int, str]] = None,
        word_count_target: int = 2000,
    ) -> str:
        """Generate a chapter."""
        return await self.ai_client.generate_chapter(
            chapter_number=chapter_number,
            chapter_title=title,
            outline=outline,
            synopsis=synopsis,
            character_info=character_info,
            existing_chapters=existing_chapters or {},
            word_count_target=word_count_target,
        )
    
    async def find_missing_chapters(
        self,
        outline: str,
        existing_chapters: List[int],
    ) -> List[int]:
        """Find missing chapters based on outline."""
        # Simple implementation - extract chapter numbers from outline
        import re
        
        chapter_matches = re.findall(r'chapter\s+(\d+)', outline.lower())
        expected_chapters = [int(match) for match in chapter_matches]
        
        missing = []
        for ch_num in expected_chapters:
            if ch_num not in existing_chapters:
                missing.append(ch_num)
        
        return sorted(missing)
