"""Claude AI client for NovelCraft AI with improved JSON handling."""

import json
import anthropic
from typing import Dict, Any, List, Optional


class ClaudeClient:
    """Client for interacting with Claude AI for novel writing assistance."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Claude client with API key."""
        self.client = anthropic.Anthropic(api_key=api_key)
    
    async def generate_chapter(
        self,
        chapter_number: int,
        chapter_title: str,
        outline: str,
        synopsis: str,
        character_info: str,
        existing_chapters: Dict[int, str],
        word_count_target: int = 2000,
        style_notes: str = ""
    ) -> str:
        """Generate a new chapter based on project context."""
        
        # Format existing chapters for context
        context_chapters = ""
        if existing_chapters:
            context_chapters = "\n\n".join([
                f"CHAPTER {num}:\n{content[:500]}..."
                for num, content in existing_chapters.items()
            ])
        
        prompt = f"""Generate Chapter {chapter_number}: {chapter_title} for a novel.

SYNOPSIS:
{synopsis}

OUTLINE:
{outline}

CHARACTER INFORMATION:
{character_info}

EXISTING CHAPTERS (for context):
{context_chapters}

STYLE NOTES:
{style_notes}

TARGET WORD COUNT: {word_count_target} words

Generate a complete chapter that:
1. Follows the outline and maintains consistency with existing chapters
2. Develops the characters naturally
3. Advances the plot meaningfully
4. Maintains the established tone and style
5. Reaches approximately {word_count_target} words
6. Has proper narrative structure with beginning, middle, and end

Write the complete chapter content below:"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            raise Exception(f"Failed to generate chapter: {str(e)}")
    
    async def expand_chapter(
        self,
        chapter_number: int,
        chapter_title: str,
        current_content: str,
        expansion_notes: str,
        target_words: int,
        synopsis: str,
        character_info: str,
        outline: str
    ) -> str:
        """Expand an existing chapter with additional content."""
        
        prompt = f"""Expand Chapter {chapter_number}: {chapter_title} by adding approximately {target_words} words.

SYNOPSIS:
{synopsis}

OUTLINE:
{outline}

CHARACTER INFORMATION:
{character_info}

CURRENT CHAPTER CONTENT:
{current_content}

EXPANSION NOTES:
{expansion_notes}

Add approximately {target_words} words to this chapter that:
1. Enhance character development
2. Add depth to the scene
3. Improve pacing and tension
4. Maintain consistency with the existing content
5. Follow the expansion notes if provided

Write only the additional content to be added:"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            raise Exception(f"Failed to expand chapter: {str(e)}")
    
    async def analyze_chapter(
        self,
        chapter_number: int,
        chapter_title: str,
        content: str,
        focus_areas: List[str],
        synopsis: str,
        character_info: str,
        existing_chapters: Dict[int, str]
    ) -> Dict[str, Any]:
        """Analyze a chapter and provide improvement suggestions."""
        
        # Format existing chapters for context
        context_chapters = ""
        if existing_chapters:
            context_chapters = "\n\n".join([
                f"CHAPTER {num}:\n{content[:300]}..."
                for num, content in existing_chapters.items()
                if num != chapter_number
            ])
        
        focus_areas_text = ", ".join(focus_areas)
        
        prompt = f"""Analyze Chapter {chapter_number}: {chapter_title} focusing on: {focus_areas_text}

SYNOPSIS:
{synopsis}

CHARACTER INFORMATION:
{character_info}

OTHER CHAPTERS (for context):
{context_chapters}

CHAPTER TO ANALYZE:
{content}

Provide analysis as a JSON object with this structure:
{{
    "overall_assessment": "brief overall assessment",
    "strengths": ["strength 1", "strength 2"],
    "areas_for_improvement": ["issue 1", "issue 2"],
    "specific_suggestions": [
        {{
            "area": "pacing|dialogue|character_development|continuity|style",
            "priority": "high|medium|low",
            "suggestion": "specific actionable suggestion"
        }}
    ],
    "continuity_issues": ["issue 1", "issue 2"],
    "style_notes": "notes about writing style and voice"
}}

Focus specifically on the requested areas: {focus_areas_text}

IMPORTANT: Return ONLY the JSON object, no other text."""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Try to parse as JSON
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, return as analysis_text
                return {"analysis_text": response_text}
                
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
    
    async def check_continuity(
        self,
        chapter_contents: Dict[int, str],
        character_info: str,
        synopsis: str,
        outline: str
    ) -> Dict[str, Any]:
        """Check continuity across chapters and return structured data."""
        
        chapters_text = self._format_chapters_for_analysis(chapter_contents)
        
        prompt = f"""Analyze the continuity across these chapters and return your analysis as a JSON object.

SYNOPSIS: {synopsis[:500]}
CHARACTERS: {character_info[:500]}
OUTLINE: {outline[:500]}

CHAPTERS TO ANALYZE:
{chapters_text}

Analyze for:
- Character behavior consistency
- Timeline logic
- Plot continuity
- Setting consistency
- Factual accuracy across chapters

Return your analysis as a JSON object with this structure:
{{
    "continuity_score": <number 1-10>,
    "issues_found": [
        {{
            "type": "character|timeline|plot|setting|factual",
            "chapter": <chapter_number>,
            "description": "description of the issue",
            "severity": "low|medium|high"
        }}
    ],
    "suggestions": [
        "suggestion 1",
        "suggestion 2"
    ],
    "character_consistency": {{
        "Character Name": "assessment of their consistency"
    }},
    "timeline_assessment": "overall timeline consistency assessment"
}}

IMPORTANT: Return ONLY the JSON object, no other text or formatting."""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Try to parse as JSON
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, return as analysis_text
                return {"analysis_text": response_text}
                
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
    
    def _format_chapters_for_analysis(self, chapter_contents: Dict[int, str]) -> str:
        """Format chapters for continuity analysis."""
        formatted = []
        for chapter_num in sorted(chapter_contents.keys()):
            content = chapter_contents[chapter_num]
            # Truncate very long chapters
            if len(content) > 1500:
                content = content[:1500] + "..."
            formatted.append(f"CHAPTER {chapter_num}:\n{content}")
        return "\n\n".join(formatted)
    
    async def generate_outline(
        self,
        chapter_start: int,
        chapter_end: int,
        plot_points: str,
        synopsis: str,
        character_info: str,
        existing_outline: str,
        existing_chapters: Dict[int, str]
    ) -> str:
        """Generate outline for a range of chapters."""
        
        # Format existing chapters for context
        context_chapters = ""
        if existing_chapters:
            context_chapters = "\n\n".join([
                f"CHAPTER {num}:\n{content[:300]}..."
                for num, content in existing_chapters.items()
            ])
        
        prompt = f"""Generate a detailed outline for Chapters {chapter_start} through {chapter_end}.

SYNOPSIS:
{synopsis}

CHARACTER INFORMATION:
{character_info}

EXISTING OUTLINE:
{existing_outline}

EXISTING CHAPTERS (for context):
{context_chapters}

PLOT POINTS TO INCLUDE:
{plot_points}

Create a detailed outline that:
1. Builds naturally from existing chapters
2. Incorporates the specified plot points
3. Develops characters meaningfully
4. Maintains pacing and tension
5. Advances toward the story's conclusion
6. Provides clear direction for each chapter

Format as:
Chapter X: Title
- Scene breakdown
- Character development
- Plot advancement
- Key dialogue/moments"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            raise Exception(f"Failed to generate outline: {str(e)}")
    
    async def suggest_chapters(
        self,
        next_chapter_number: int,
        synopsis: str,
        character_info: str,
        outline: str,
        existing_chapters: Dict[int, str],
        num_suggestions: int = 3
    ) -> List[Dict[str, Any]]:
        """Generate suggestions for next chapters to write."""
        
        # Format existing chapters for context
        context_chapters = ""
        if existing_chapters:
            recent_chapters = dict(sorted(existing_chapters.items())[-2:])
            context_chapters = "\n\n".join([
                f"CHAPTER {num}:\n{content[:400]}..."
                for num, content in recent_chapters.items()
            ])
        
        prompt = f"""Suggest {num_suggestions} possible directions for Chapter {next_chapter_number} based on the story so far.

SYNOPSIS:
{synopsis}

CHARACTER INFORMATION:
{character_info}

OUTLINE:
{outline}

RECENT CHAPTERS:
{context_chapters}

Generate {num_suggestions} chapter suggestions as a JSON array with this structure:
[
    {{
        "chapter_number": {next_chapter_number},
        "title": "suggested chapter title",
        "summary": "brief description of what happens",
        "key_events": ["event 1", "event 2"],
        "character_focus": "main character(s) featured",
        "plot_advancement": "how this advances the main plot",
        "estimated_word_count": 2000
    }}
]

Each suggestion should:
1. Build naturally from the existing story
2. Advance character development
3. Move the plot forward meaningfully
4. Maintain narrative tension
5. Be feasible to write as a complete chapter

IMPORTANT: Return ONLY the JSON array, no other text."""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Try to parse as JSON
            try:
                suggestions = json.loads(response_text)
                return suggestions if isinstance(suggestions, list) else [suggestions]
            except json.JSONDecodeError:
                # If JSON parsing fails, return as text suggestions
                return [{"suggestion_text": response_text}]
                
        except Exception as e:
            return [{"error": f"Failed to generate suggestions: {str(e)}"}]
    
    async def improve_dialogue(
        self,
        dialogue_text: str,
        character_info: str,
        context: str = ""
    ) -> str:
        """Improve dialogue to make it more natural and character-specific."""
        
        prompt = f"""Improve this dialogue to make it more natural, character-specific, and engaging.

CHARACTER INFORMATION:
{character_info}

CONTEXT:
{context}

CURRENT DIALOGUE:
{dialogue_text}

Improve the dialogue by:
1. Making each character's voice distinct
2. Adding subtext and natural speech patterns
3. Ensuring dialogue serves character development
4. Making it sound more realistic
5. Adding appropriate tags and actions

Return only the improved dialogue:"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            raise Exception(f"Failed to improve dialogue: {str(e)}")
    
    async def enhance_description(
        self,
        description_text: str,
        scene_context: str,
        style_notes: str = ""
    ) -> str:
        """Enhance descriptive passages for better imagery and atmosphere."""
        
        prompt = f"""Enhance this descriptive passage to create stronger imagery and atmosphere.

SCENE CONTEXT:
{scene_context}

STYLE NOTES:
{style_notes}

CURRENT DESCRIPTION:
{description_text}

Enhance the description by:
1. Adding sensory details (sight, sound, smell, touch, taste)
2. Creating stronger atmosphere and mood
3. Using more vivid and specific language
4. Maintaining the narrative flow
5. Supporting character emotions and plot tension

Return only the enhanced description:"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            raise Exception(f"Failed to enhance description: {str(e)}")
    
    async def check_character_consistency(
        self,
        character_name: str,
        character_info: str,
        chapter_contents: Dict[int, str]
    ) -> Dict[str, Any]:
        """Check consistency of a specific character across chapters."""
        
        chapters_text = self._format_chapters_for_analysis(chapter_contents)
        
        prompt = f"""Analyze the consistency of character "{character_name}" across these chapters.

CHARACTER INFORMATION:
{character_info}

CHAPTERS TO ANALYZE:
{chapters_text}

Return analysis as a JSON object:
{{
    "character_name": "{character_name}",
    "consistency_score": <number 1-10>,
    "consistent_traits": ["trait 1", "trait 2"],
    "inconsistencies": [
        {{
            "chapter": <chapter_number>,
            "issue": "description of inconsistency",
            "severity": "low|medium|high"
        }}
    ],
    "character_development": "assessment of character growth/change",
    "dialogue_consistency": "assessment of voice and speech patterns",
    "suggestions": ["suggestion 1", "suggestion 2"]
}}

IMPORTANT: Return ONLY the JSON object."""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Try to parse as JSON
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, return as analysis_text
                return {"analysis_text": response_text}
                
        except Exception as e:
            return {"error": f"Character analysis failed: {str(e)}"}
    
    async def generate_scene_ideas(
        self,
        scene_purpose: str,
        characters_involved: List[str],
        setting: str,
        tone: str,
        word_count_target: int = 500
    ) -> List[str]:
        """Generate ideas for specific scenes."""
        
        characters_text = ", ".join(characters_involved)
        
        prompt = f"""Generate 3-5 scene ideas with the following parameters:

PURPOSE: {scene_purpose}
CHARACTERS: {characters_text}
SETTING: {setting}
TONE: {tone}
TARGET LENGTH: {word_count_target} words

Each scene idea should:
1. Serve the specified purpose
2. Feel natural for the characters and setting
3. Match the desired tone
4. Be substantial enough for the target word count
5. Include potential conflict or tension

Format as a simple list:
1. [Scene idea 1]
2. [Scene idea 2]
3. [Scene idea 3]
etc."""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Parse the numbered list
            lines = response_text.split('\n')
            ideas = []
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    # Remove numbering/bullets and clean up
                    clean_idea = line.split('.', 1)[-1].strip()
                    if clean_idea:
                        ideas.append(clean_idea)
            
            return ideas if ideas else [response_text]
            
        except Exception as e:
            return [f"Error generating scene ideas: {str(e)}"]
    
    def _clean_json_response(self, response_text: str) -> str:
        """Clean JSON response by removing common formatting issues."""
        # Remove markdown code blocks
        response_text = response_text.replace('```json', '').replace('```', '')
        
        # Remove leading/trailing whitespace
        response_text = response_text.strip()
        
        # Find JSON object boundaries
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start != -1 and end > start:
            return response_text[start:end]
        
        # Try array boundaries
        start = response_text.find('[')
        end = response_text.rfind(']') + 1
        
        if start != -1 and end > start:
            return response_text[start:end]
        
        return response_text