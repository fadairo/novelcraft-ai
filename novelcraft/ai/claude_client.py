"""
Claude AI client for content generation.
"""

import asyncio
import os
from typing import Optional, Dict, Any, List
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Client for interacting with Claude AI API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        """Initialize Claude client.
        
        Args:
            api_key: Anthropic API key. If None, will try to get from environment.
            model: Model to use for generation.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable.")
        
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_tokens = 4000
        self.temperature = 0.7
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APITimeoutError))
    )
    async def generate_content(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate content using Claude API.
        
        Args:
            prompt: The main prompt for content generation.
            system_prompt: System prompt to set context and behavior.
            max_tokens: Maximum tokens to generate.
            temperature: Temperature for generation (0.0 to 1.0).
            
        Returns:
            Generated content as string.
        """
        try:
            messages = [{"role": "user", "content": prompt}]
            
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature or self.temperature,
                "messages": messages,
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self.client.messages.create(**kwargs)
            )
            
            return response.content[0].text
            
        except anthropic.RateLimitError as e:
            logger.warning(f"Rate limit hit: {e}")
            raise
        except anthropic.APITimeoutError as e:
            logger.warning(f"API timeout: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise
    
    async def generate_chapter(
        self,
        chapter_number: int,
        chapter_title: str,
        outline: str,
        synopsis: str,
        character_info: str,
        existing_chapters: Dict[int, str],
        style_guide: Optional[str] = None,
        word_count_target: int = 2000,
    ) -> str:
        """Generate a complete chapter.
        
        Args:
            chapter_number: Number of the chapter to generate.
            chapter_title: Title of the chapter.
            outline: Chapter outline or summary.
            synopsis: Overall story synopsis.
            character_info: Information about characters.
            existing_chapters: Previously written chapters for context.
            style_guide: Author's style guide.
            word_count_target: Target word count for the chapter.
            
        Returns:
            Generated chapter content.
        """
        system_prompt = f"""You are a skilled novelist helping to write a chapter of a novel. 
Your task is to write engaging, well-structured prose that matches the author's style and maintains consistency with the existing story.

Key guidelines:
- Write in a natural, engaging narrative style
- Maintain character consistency
- Follow the provided outline closely
- Target approximately {word_count_target} words
- Use proper chapter formatting
- Avoid clichés and overused phrases
- Show don't tell when possible
- Create vivid scenes and dialogue
"""
        
        if style_guide:
            system_prompt += f"\n\nAuthor's Style Guide:\n{style_guide}"
        
        # Build context from existing chapters
        context_parts = []
        if existing_chapters:
            context_parts.append("EXISTING CHAPTERS FOR CONTEXT:")
            for ch_num in sorted(existing_chapters.keys()):
                if ch_num < chapter_number:  # Only include previous chapters
                    context_parts.append(f"Chapter {ch_num} Summary:")
                    # Include first 500 chars as context
                    content = existing_chapters[ch_num]
                    summary = content[:500] + "..." if len(content) > 500 else content
                    context_parts.append(summary)
                    context_parts.append("")
        
        context_text = "\n".join(context_parts) if context_parts else ""
        
        prompt = f"""Please write Chapter {chapter_number}: {chapter_title}

STORY SYNOPSIS:
{synopsis}

CHAPTER OUTLINE:
{outline}

CHARACTER INFORMATION:
{character_info}

{context_text}

Write the complete chapter now, ensuring it flows naturally from the previous chapters and advances the story according to the outline. Focus on compelling narrative, realistic dialogue, and vivid descriptions."""
        
        return await self.generate_content(prompt, system_prompt)
    
    async def generate_scene(
        self,
        scene_description: str,
        characters: List[str],
        setting: str,
        purpose: str,
        style_context: str,
        word_count_target: int = 800,
    ) -> str:
        """Generate a specific scene.
        
        Args:
            scene_description: Description of what happens in the scene.
            characters: List of characters in the scene.
            setting: Where the scene takes place.
            purpose: What the scene accomplishes for the story.
            style_context: Style information from existing text.
            word_count_target: Target word count.
            
        Returns:
            Generated scene content.
        """
        system_prompt = f"""You are writing a scene for a novel. Create engaging, well-written prose that serves the story.

Guidelines:
- Target approximately {word_count_target} words
- Write in the established style
- Focus on character development and story advancement
- Use vivid descriptions and realistic dialogue
- Maintain appropriate pacing
- Show emotions and motivations through actions and dialogue
"""
        
        prompt = f"""Write a scene with the following specifications:

SCENE DESCRIPTION: {scene_description}

CHARACTERS PRESENT: {', '.join(characters)}

SETTING: {setting}

SCENE PURPOSE: {purpose}

STYLE CONTEXT (match this writing style):
{style_context}

Write the complete scene now."""
        
        return await self.generate_content(prompt, system_prompt)
    
    async def edit_content(
        self,
        content: str,
        editing_instructions: str,
        character_info: str,
        story_context: str,
    ) -> str:
        """Edit existing content based on instructions.
        
        Args:
            content: The content to edit.
            editing_instructions: Specific editing instructions.
            character_info: Character information for consistency.
            story_context: Story context for continuity.
            
        Returns:
            Edited content.
        """
        system_prompt = """You are a professional editor working on a novel. Your job is to improve the provided text according to the given instructions while maintaining the author's voice and story consistency.

Focus on:
- Improving clarity and flow
- Maintaining character consistency
- Ensuring story continuity
- Enhancing prose quality
- Fixing any plot holes or inconsistencies
"""
        
        prompt = f"""Please edit the following content according to the instructions:

EDITING INSTRUCTIONS:
{editing_instructions}

CHARACTER INFORMATION:
{character_info}

STORY CONTEXT:
{story_context}

CONTENT TO EDIT:
{content}

Provide the edited version."""
        
        return await self.generate_content(prompt, system_prompt)
    
    async def analyze_style(self, text_sample: str) -> Dict[str, Any]:
        """Analyze the writing style of a text sample.
        
        Args:
            text_sample: Sample text to analyze.
            
        Returns:
            Style analysis as dictionary.
        """
        system_prompt = """You are a literary analyst. Analyze the writing style of the provided text and return a detailed breakdown of stylistic elements.

Focus on:
- Sentence structure and length
- Vocabulary level and word choice
- Tone and voice
- Dialogue style
- Narrative perspective
- Pacing and rhythm
- Use of literary devices
"""
        
        prompt = f"""Analyze the writing style of this text sample:

{text_sample}

Provide a detailed analysis covering sentence structure, vocabulary, tone, dialogue style, and other notable stylistic elements. Format your response as clear categories with specific observations."""
        
        analysis_text = await self.generate_content(prompt, system_prompt)
        
        # Parse the analysis into structured format
        # This is a simplified parser - in production you might want more sophisticated parsing
        analysis = {
            "raw_analysis": analysis_text,
            "estimated_reading_level": "intermediate",  # Could be enhanced with actual analysis
            "tone": "neutral",  # Could be enhanced with actual analysis
            "style_notes": analysis_text.split('\n')[:5],  # First 5 lines as key points
        }
        
        return analysis
    
    async def check_consistency(
        self,
        text: str,
        character_profiles: str,
        story_bible: str,
    ) -> List[str]:
        """Check text for consistency issues.
        
        Args:
            text: Text to check.
            character_profiles: Character information.
            story_bible: Story world information.
            
        Returns:
            List of potential consistency issues.
        """
        system_prompt = """You are a continuity editor checking for consistency issues in a novel. Identify any inconsistencies related to:

- Character names, descriptions, or behavior
- Timeline and chronology
- World-building elements
- Previously established facts
- Character relationships

Be specific about what inconsistencies you find and reference the source material."""
        
        prompt = f"""Check this text for consistency issues:

CHARACTER PROFILES:
{character_profiles}

STORY BIBLE/CONTEXT:
{story_bible}

TEXT TO CHECK:
{text}

List any inconsistencies you find, being specific about the nature of each issue."""
        
        response = await self.generate_content(prompt, system_prompt)
        
        # Parse response into list of issues
        issues = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('•') or line[0].isdigit()):
                issues.append(line)
        
        return issues
    
    def set_generation_parameters(
        self,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> None:
        """Set default generation parameters.
        
        Args:
            max_tokens: Maximum tokens to generate.
            temperature: Temperature for generation.
        """
        self.max_tokens = max_tokens
        self.temperature = temperature