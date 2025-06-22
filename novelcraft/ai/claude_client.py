"""Claude AI client for NovelCraft AI."""

import os
import asyncio
from typing import Dict, List, Optional, Any, AsyncIterator
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import logging

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
        self.max_tokens = 32000  # Maximum supported by Claude Opus 4
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
        existing_chapters: Dict[int, str] = None,
        word_count_target: int = 2500,
        style_notes: str = "",
    ) -> str:
        """Generate a chapter using Claude with normalized title format."""
        from ..core.document import normalize_chapter_title
        
        existing_chapters = existing_chapters or {}
        
        # Ensure the chapter title is normalized
        normalized_title = normalize_chapter_title(chapter_title)
        
        # Build context from existing chapters
        context = ""
        if existing_chapters:
            context = "\n\nPrevious chapters for context:\n"
            for ch_num in sorted(existing_chapters.keys()):
                if ch_num < chapter_number:
                    context += f"\n--- Chapter {ch_num} ---\n{existing_chapters[ch_num][:1000]}...\n"
        
        system_prompt = f"""You are a novelist writing {normalized_title} of a novel.

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
        
        messages = [
            {
                "role": "user",
                "content": f"Please write {normalized_title}"
            }
        ]
        
        # Enable streaming for chapter generation
        self.use_streaming = True
        return await self._make_request(messages, system_prompt)
    
    async def generate_character_description(
        self,
        character_name: str,
        role: str,
        basic_info: str,
        story_context: str = "",
    ) -> str:
        """Generate detailed character description."""
        system_prompt = f"""You are a character development expert helping to flesh out a character for a novel.

CHARACTER BASICS:
- Name: {character_name}
- Role: {role}
- Basic info: {basic_info}

STORY CONTEXT:
{story_context}

Create a detailed character profile including:
- Physical and facial appearance
- Personality traits
- Background/backstory
- Motivations and goals
- Conflicts and challenges
- Character voice/speaking style
- Relationships with other characters

Make the character feel real, complex, and three-dimensional."""
        
        messages = [
            {
                "role": "user",
                "content": f"Please create a detailed character profile for {character_name}."
            }
        ]
        
        # Character descriptions are shorter, so disable streaming
        self.use_streaming = False
        return await self._make_request(messages, system_prompt)
    
    async def generate_chapter_outline(
        self,
        chapter_number: int,
        story_synopsis: str,
        character_info: str,
        previous_events: str = "",
        target_word_count: int = 2000,
    ) -> str:
        """Generate an outline for a specific chapter."""
        system_prompt = f"""You are a story structure expert creating a detailed outline for Chapter {chapter_number}.

STORY SYNOPSIS:
{story_synopsis}

CHARACTER INFORMATION:
{character_info}

PREVIOUS EVENTS:
{previous_events}

TARGET WORD COUNT: {target_word_count} words

Create a detailed chapter outline that includes:
- Opening scene setup
- Key plot points and story beats
- Character interactions and dialogue opportunities
- Conflict and tension moments
- Chapter ending/transition to next chapter
- Pacing notes

Structure the outline with clear beats that can guide the actual writing."""
        
        messages = [
            {
                "role": "user",
                "content": f"Please create a detailed outline for Chapter {chapter_number}."
            }
        ]
        
        # Outlines are shorter, disable streaming
        self.use_streaming = False
        return await self._make_request(messages, system_prompt)
    
    async def analyze_style(self, text_sample: str) -> Dict[str, Any]:
        """Analyze the writing style of a text sample."""
        system_prompt = """You are a writing style analyst. Analyze the given text and provide insights about:

- Sentence structure and length patterns
- Vocabulary level and word choice
- Tone and voice
- Point of view
- Dialogue style
- Pacing and rhythm
- Literary devices used
- Overall writing style characteristics

Provide specific examples and actionable insights for maintaining consistency."""
        
        messages = [
            {
                "role": "user",
                "content": f"Please analyze the writing style of this text:\n\n{text_sample}"
            }
        ]
        
        self.use_streaming = False
        response = await self._make_request(messages, system_prompt)
        
        # Parse response into structured format (simplified)
        return {
            "analysis": response,
            "sentence_length": "varies",  # Could implement actual analysis
            "vocabulary_level": "intermediate",
            "tone": "narrative",
            "pov": "third_person",
        }
    
    async def check_consistency(
        self,
        manuscript: str,
        character_info: str,
        story_context: str,
    ) -> List[str]:
        """Check manuscript for consistency issues."""
        system_prompt = f"""You are an editor checking for consistency issues in a manuscript.

CHARACTER INFORMATION:
{character_info}

STORY CONTEXT:
{story_context}

Review the manuscript and identify any consistency issues such as:
- Character name variations or typos
- Character behavior inconsistencies
- Timeline or continuity errors
- Plot contradictions
- Setting inconsistencies

Provide specific examples and suggestions for fixes."""
        
        messages = [
            {
                "role": "user",
                "content": f"Please check this manuscript for consistency issues:\n\n{manuscript[:4000]}..."
            }
        ]
        
        self.use_streaming = False
        response = await self._make_request(messages, system_prompt)
        
        # Parse response into list of issues (simplified)
        issues = []
        for line in response.split('\n'):
            if line.strip() and ('inconsistency' in line.lower() or 'error' in line.lower()):
                issues.append(line.strip())
        
        return issues
    
    async def suggest_improvements(
        self,
        text: str,
        focus_area: str = "general",
    ) -> str:
        """Suggest improvements for a piece of text."""
        system_prompt = f"""You are a professional editor providing constructive feedback.

FOCUS AREA: {focus_area}

Analyze the text and provide specific, actionable suggestions for improvement in areas such as:
- Character development
- Dialogue quality
- Pacing and flow
- Descriptive language
- Plot advancement
- Clarity and readability

Be specific and provide examples where possible."""
        
        messages = [
            {
                "role": "user",
                "content": f"Please suggest improvements for this text:\n\n{text}"
            }
        ]
        
        self.use_streaming = False
        return await self._make_request(messages, system_prompt)
    
    async def expand_chapter(
        self,
        chapter_number: int,
        chapter_title: str,
        current_content: str,
        expansion_notes: str,
        target_words: int,
        synopsis: str,
        character_info: str,
        outline: str,
    ) -> str:
        """Expand an existing chapter with additional content."""
        
        system_prompt = f"""You are a professional novelist expanding Chapter {chapter_number} of a novel.

NOVEL INFORMATION:
- Synopsis: {synopsis}
- Chapter Title: {chapter_title}
- Target expansion: {target_words} additional words

CHARACTER INFORMATION:
{character_info}

OUTLINE CONTEXT:
{outline}

EXPANSION NOTES:
{expansion_notes}

CURRENT CHAPTER CONTENT:
{current_content}

Your task is to expand this chapter by adding approximately {target_words} words while:
- Maintaining the existing narrative flow and style
- Adding depth to character development or plot advancement
- Incorporating the expansion notes if provided
- Ensuring smooth integration with existing content
- Maintaining consistency with the established tone

Provide ONLY the expanded content that should be added, not the entire chapter."""
        
        messages = [
            {
                "role": "user",
                "content": f"Please expand Chapter {chapter_number} based on the provided content and notes."
            }
        ]
        
        # Chapter expansion might be long, enable streaming
        self.use_streaming = True
        return await self._make_request(messages, system_prompt)
    
    async def analyze_chapter(
        self,
        chapter_number: int,
        chapter_title: str,
        content: str,
        focus_areas: List[str],
        synopsis: str,
        character_info: str,
        existing_chapters: Dict[int, str],
    ) -> Dict[str, Any]:
        """Analyze a chapter and provide improvement suggestions."""
        
        context = ""
        if existing_chapters:
            context = "\n\nPREVIOUS CHAPTERS FOR CONTEXT:\n"
            for ch_num in sorted(existing_chapters.keys()):
                context += f"\n--- Chapter {ch_num} (excerpt) ---\n{existing_chapters[ch_num][:500]}...\n"
        
        focus_areas_str = ", ".join(focus_areas)
        
        system_prompt = f"""You are a professional editor analyzing Chapter {chapter_number} of a novel.

NOVEL INFORMATION:
- Synopsis: {synopsis}
- Chapter Title: {chapter_title}

CHARACTER INFORMATION:
{character_info}

FOCUS AREAS: {focus_areas_str}

CONTEXT:
{context}

CHAPTER TO ANALYZE:
{content[:3000]}...

Provide a detailed analysis focusing on the specified areas. Structure your response as JSON with the following format:
{{
    "overall_assessment": "Brief overall assessment",
    "strengths": ["strength1", "strength2", ...],
    "areas_for_improvement": ["issue1", "issue2", ...],
    "specific_suggestions": [
        {{"area": "focus_area", "suggestion": "specific suggestion", "priority": "high/medium/low"}},
        ...
    ],
    "continuity_issues": ["issue1", "issue2", ...],
    "style_notes": "Style and voice observations"
}}

Be specific and actionable in your suggestions."""
        
        messages = [
            {
                "role": "user",
                "content": f"Please analyze Chapter {chapter_number} focusing on: {focus_areas_str}"
            }
        ]
        
        self.use_streaming = False
        response = await self._make_request(messages, system_prompt)
        
        # Try to parse as JSON, fall back to structured text
        try:
            return json.loads(response)
        except:
            return {
                "overall_assessment": "Analysis completed",
                "analysis_text": response,
                "strengths": [],
                "areas_for_improvement": [],
                "specific_suggestions": [],
                "continuity_issues": [],
                "style_notes": ""
            }
    
    async def generate_outline(
        self,
        chapter_start: int,
        chapter_end: int,
        plot_points: str,
        synopsis: str,
        character_info: str,
        existing_outline: str,
        existing_chapters: Dict[int, str],
    ) -> str:
        """Generate outline for a range of chapters."""
        
        context = ""
        if existing_chapters:
            context = "\n\nEXISTING CHAPTERS:\n"
            for ch_num in sorted(existing_chapters.keys()):
                context += f"\nChapter {ch_num}: {existing_chapters[ch_num][:300]}...\n"
        
        system_prompt = f"""You are a story development expert creating a detailed outline.

NOVEL INFORMATION:
- Synopsis: {synopsis}

CHARACTER INFORMATION:
{character_info}

EXISTING OUTLINE:
{existing_outline}

PLOT POINTS TO INCORPORATE:
{plot_points}

CONTEXT:
{context}

Create a detailed outline for Chapters {chapter_start} through {chapter_end} that:
- Builds logically on existing chapters
- Incorporates the specified plot points
- Advances character development
- Maintains narrative momentum
- Provides clear story beats for each chapter

Format as:
## Chapter X: [Title]
- Plot points and key events
- Character development focus
- Scene structure
- Transitions to next chapter"""
        
        messages = [
            {
                "role": "user",
                "content": f"Please create an outline for Chapters {chapter_start}-{chapter_end}."
            }
        ]
        
        # Outlines can be long, enable streaming
        self.use_streaming = True
        return await self._make_request(messages, system_prompt)
    
    async def check_continuity(
        self,
        chapter_contents: Dict[int, str],
        character_info: str,
        synopsis: str,
        outline: str,
    ) -> Dict[str, Any]:
        """Check continuity across multiple chapters."""
        
        # Limit chapter content to avoid token limits
        chapters_text = ""
        for ch_num in sorted(chapter_contents.keys()):
            chapters_text += f"\n--- Chapter {ch_num} ---\n{chapter_contents[ch_num][:2000]}...\n"
        
        system_prompt = f"""You are a continuity editor checking for consistency issues across chapters.

NOVEL INFORMATION:
- Synopsis: {synopsis}

CHARACTER INFORMATION:
{character_info}

OUTLINE:
{outline[:2000]}...

CHAPTERS TO ANALYZE:
{chapters_text}

Check for continuity issues including:
- Character consistency (personality, background, relationships)
- Timeline and chronology issues
- Plot inconsistencies
- Setting and world-building contradictions
- Dialogue voice consistency

Provide results as JSON:
{{
    "continuity_score": "1-10 rating",
    "issues_found": [
        {{"type": "character/plot/timeline/setting", "chapter": number, "description": "specific issue", "severity": "high/medium/low"}},
        ...
    ],
    "suggestions": ["suggestion1", "suggestion2", ...],
    "character_consistency": {{"character_name": "assessment", ...}},
    "timeline_assessment": "overall timeline consistency"
}}"""
        
        messages = [
            {
                "role": "user",
                "content": "Please check continuity across the provided chapters."
            }
        ]
        
        self.use_streaming = False
        response = await self._make_request(messages, system_prompt)
        
        try:
            return json.loads(response)
        except:
            return {
                "continuity_score": "Unable to parse",
                "analysis_text": response,
                "issues_found": [],
                "suggestions": [],
                "character_consistency": {},
                "timeline_assessment": ""
            }
    
    async def suggest_chapters(
        self,
        next_chapter_number: int,
        synopsis: str,
        character_info: str,
        outline: str,
        existing_chapters: Dict[int, str],
        num_suggestions: int,
    ) -> List[Dict[str, Any]]:
        """Suggest ideas for upcoming chapters."""
        
        context = ""
        if existing_chapters:
            recent_chapters = sorted(existing_chapters.keys())[-3:]  # Last 3 chapters
            context = "\n\nRECENT CHAPTERS:\n"
            for ch_num in recent_chapters:
                if ch_num in existing_chapters:
                    context += f"\nChapter {ch_num}: {existing_chapters[ch_num][:400]}...\n"
        
        system_prompt = f"""You are a story development expert suggesting ideas for upcoming chapters.

NOVEL INFORMATION:
- Synopsis: {synopsis}
- Next chapter number: {next_chapter_number}

CHARACTER INFORMATION:
{character_info}

OUTLINE:
{outline}

CONTEXT:
{context}

Suggest {num_suggestions} compelling ideas for Chapter {next_chapter_number} and beyond that:
- Build naturally on existing story progression
- Advance character arcs meaningfully  
- Introduce appropriate conflict or tension
- Move the plot toward resolution
- Maintain reader engagement

Format as JSON:
{{
    "suggestions": [
        {{
            "chapter_number": {next_chapter_number},
            "title": "suggested title",
            "summary": "brief chapter summary",
            "key_events": ["event1", "event2", ...],
            "character_focus": "which characters are featured",
            "plot_advancement": "how this advances the overall plot",
            "estimated_word_count": number
        }},
        ...
    ]
}}"""
        
        messages = [
            {
                "role": "user",
                "content": f"Please suggest {num_suggestions} ideas for Chapter {next_chapter_number}."
            }
        ]
        
        self.use_streaming = False
        response = await self._make_request(messages, system_prompt)
        
        try:
            result = json.loads(response)
            return result.get("suggestions", [])
        except:
            return [{"analysis_text": response, "chapter_number": next_chapter_number}]
    
    async def find_missing_chapters(
        self,
        outline: str,
        existing_chapters: List[int],
        synopsis: str,
    ) -> List[Dict[str, Any]]:
        """Analyze outline to find missing chapters."""
        
        existing_str = ", ".join(map(str, sorted(existing_chapters)))
        
        system_prompt = f"""You are a story structure analyst identifying missing chapters.

SYNOPSIS:
{synopsis}

OUTLINE:
{outline}

EXISTING CHAPTERS: {existing_str}

Analyze the outline and identify chapters that should exist but are missing. Consider:
- Story progression gaps
- Character development needs
- Plot point coverage
- Narrative flow requirements

Format as JSON:
{{
    "missing_chapters": [
        {{
            "suggested_number": number,
            "title": "suggested title", 
            "purpose": "why this chapter is needed",
            "plot_points": ["key events this chapter should cover"],
            "placement_reason": "why it should go in this position",
            "priority": "high/medium/low"
        }},
        ...
    ],
    "outline_analysis": "assessment of outline completeness"
}}"""
        
        messages = [
            {
                "role": "user",
                "content": "Please analyze the outline and identify missing chapters."
            }
        ]
        
        self.use_streaming = False
        response = await self._make_request(messages, system_prompt)
        
        try:
            result = json.loads(response)
            return result.get("missing_chapters", [])
        except:
            return [{"analysis_text": response}]
    
    def set_model(self, model_name: str) -> None:
        """Set the Claude model to use."""
        self.model = model_name
    
    def set_max_tokens(self, max_tokens: int) -> None:
        """Set the maximum tokens for responses."""
        self.max_tokens = max_tokens