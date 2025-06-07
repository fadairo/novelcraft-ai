#!/usr/bin/env python3
"""
chapter_reviser.py - Story-Preserving Chapter Revision Tool (V3 - Critical Fixes)

Major fixes in this version:
- Fixed catastrophic length adjustment prompt ambiguity
- Improved model selection logic for large chapters
- Better validation using fuzzy matching
- Enhanced error recovery strategies
- Cleaner duplicate file handling
"""

import os
import re
import json
import glob
import logging
import argparse
import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
from enum import Enum
import time
import sys
import difflib
from difflib import SequenceMatcher

import anthropic
from anthropic import APIError, RateLimitError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('chapter_reviser.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

@dataclass
class RevisionConstraints:
    """Constraints for maintaining story integrity during revision."""
    preserve_plot_points: bool = True
    preserve_character_actions: bool = True
    preserve_dialogue_meaning: bool = True
    allow_new_scenes: bool = False
    allow_new_characters: bool = False
    allow_timeline_changes: bool = False
    max_deviation_score: float = 0.3  # Maximum allowed semantic deviation
    length_tolerance: float = 0.20  # Increased to 20% tolerance for word count

@dataclass
class Config:
    """Central configuration for the application."""
    # API Settings
    api_key: str = field(default_factory=lambda: os.getenv('ANTHROPIC_API_KEY', ''))
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Model Configuration - Using Claude Opus 4 and Sonnet 4
    models: Dict[str, str] = field(default_factory=lambda: {
            "simple": "claude-opus-4-20250514",
            "medium": "claude-opus-4-20250514",
            "complex": "claude-opus-4-20250514",
            "extended": "claude-sonnet-4-20250514",  # For outputs > 32k tokens
    })
    
    # Token Limits - Updated for Claude Opus 4 actual limits
    max_tokens: Dict[str, int] = field(default_factory=lambda: {
        'analysis': 8000,
        'planning': 6000,
        'revision': 30000,  # Safe limit under 32000 max for Opus
        'revision_extended': 60000,  # Sonnet 4 can handle more
        'validation': 4000,
        'length_adjustment': 30000
    })
    
    # Temperature settings for different operations
    temperatures: Dict[str, float] = field(default_factory=lambda: {
        'analysis': 0.3,      # Low for factual analysis
        'planning': 0.4,      # Moderate for structured planning
        'revision': 0.7,      # Higher for natural prose
        'chunk_revision': 0.6, # Moderate for consistency
        'retry': 0.8,         # Higher for variation
        'validation': 0.2,    # Low for factual validation
        'length_adjustment': 0.5  # Moderate for precision
    })
    
    # Token estimation settings
    chars_per_token: float = 4.0  # Average characters per token
    token_buffer: float = 1.3     # Safety buffer for token estimation
    
    # Chapter size thresholds - LOWERED for better handling
    large_chapter_threshold: int = 2500  # Words - force Sonnet 4 above this (lowered from 3000)
    chunk_size_words: int = 2000  # Words per chunk for very large chapters
    
    # File Patterns
    chapter_patterns: List[str] = field(default_factory=lambda: [
        'chapter_*.md', 'chapter*.md', 'ch_*.md',
        '*_chapter_*.md', 'Chapter*.md', 'Ch*.md'
    ])
    
    # Directories
    chapter_dirs: List[str] = field(default_factory=lambda: [
        'chapters', 'content', 'manuscript', '.'
    ])
    
    # Revision Settings
    revision_constraints: RevisionConstraints = field(default_factory=RevisionConstraints)
    
    # Encoding Settings
    file_encodings: List[str] = field(default_factory=lambda: [
        'utf-8', 'utf-8-sig', 'cp1252', 'latin1', 'ascii'
    ])

# ============================================================================
# Helper Functions for Token Estimation
# ============================================================================

def estimate_tokens(*texts: str, chars_per_token: float = 4.0, buffer: float = 1.3) -> int:
    """Estimate total tokens for multiple text inputs."""
    total_chars = sum(len(text) for text in texts if text)
    base_tokens = int(total_chars / chars_per_token)
    return int(base_tokens * buffer)

def select_model_for_task(input_tokens: int, output_tokens: int, 
                         force_extended: bool = False, 
                         chapter_words: int = 0) -> Tuple[str, int]:
    """
    Select appropriate model based on token requirements.
    Returns (model_complexity, max_tokens)
    """
    total_tokens = input_tokens + output_tokens
    
    # FIXED: More aggressive use of Sonnet 4 for large tasks
    if (force_extended or 
        total_tokens > 20000 or  # Lowered from 25000
        output_tokens > 15000 or  # Lowered from 20000
        chapter_words > 2500):  # Lowered from 3000
        logger.info(f"Using Sonnet 4 for large task: ~{total_tokens} total tokens "
                   f"(input: {input_tokens}, output: {output_tokens}, chapter: {chapter_words} words)")
        return 'extended', min(output_tokens + 10000, 60000)
    else:
        return 'complex', min(output_tokens + 5000, 30000)

def fuzzy_match_score(text1: str, text2: str, threshold: float = 0.6) -> float:
    """Calculate fuzzy match score between two strings."""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

def semantic_similarity_check(phrase: str, text: str, min_words: int = 3) -> float:
    """Check semantic similarity by finding overlapping key words."""
    # Extract meaningful words (3+ chars, not common words)
    common_words = {'the', 'and', 'for', 'with', 'that', 'this', 'from', 'was', 'are', 'been', 'were', 'had'}
    
    phrase_words = set(word.lower() for word in phrase.split() 
                      if len(word) > 2 and word.lower() not in common_words)
    
    if len(phrase_words) < min_words:
        return 0.0
    
    # Check how many key words appear in the text
    text_lower = text.lower()
    found_words = sum(1 for word in phrase_words if word in text_lower)
    
    return found_words / len(phrase_words)

# ============================================================================
# Data Models (unchanged from original)
# ============================================================================

@dataclass
class Chapter:
    """Represents a single chapter."""
    number: int
    file_path: Path
    content: str
    word_count: int
    
    def __post_init__(self):
        self.file_path = Path(self.file_path)
        self.word_count = len(self.content.split())

@dataclass
class StoryElements:
    """Core story elements extracted from a chapter."""
    plot_points: List[str] = field(default_factory=list)
    character_actions: Dict[str, List[str]] = field(default_factory=dict)
    key_dialogues: List[str] = field(default_factory=list)
    setting_details: List[str] = field(default_factory=list)
    timeline_markers: List[str] = field(default_factory=list)

@dataclass
class ProjectContext:
    """Represents the project context."""
    synopsis: str = ""
    outline: str = ""
    characters: str = ""
    inspirations: str = ""
    title: str = "Novel"
    genre: str = "Literary Fiction"
    story_bible: str = ""  # New: explicit story rules/constraints

@dataclass
class RevisionPlan:
    """Represents a revision plan for a chapter."""
    chapter_number: int
    analysis: str
    plan_content: str
    story_elements: StoryElements
    revision_focus: List[str]  # Specific areas to improve
    prohibited_changes: List[str]  # What must not change
    target_word_count: int = 0  # Target word count for revision
    inspirations: str = ""  # Literary style inspirations
    characters: str = ""  # Character profiles for consistency
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass
class RevisionResult:
    """Represents the result of a chapter revision."""
    chapter_number: int
    original_content: str
    revised_content: str
    original_word_count: int
    revised_word_count: int
    success: bool
    validation_passed: bool = False
    deviation_score: float = 0.0
    error_message: Optional[str] = None

# ============================================================================
# Custom Exceptions
# ============================================================================

class RevisionError(Exception):
    """Base exception for revision errors."""
    pass

class FileOperationError(RevisionError):
    """Raised when file operations fail."""
    pass

class ValidationError(RevisionError):
    """Raised when validation fails."""
    pass

# ============================================================================
# Story Element Extraction (unchanged)
# ============================================================================

class StoryElementExtractor:
    """Extracts and validates core story elements."""
    
    def __init__(self, api_client: 'AnthropicClient', config: Config):
        self.api_client = api_client
        self.config = config
    
    def extract_story_elements(self, chapter: Chapter) -> StoryElements:
        """Extract core story elements from a chapter."""
        # Validate chapter content
        if not chapter.content or len(chapter.content.strip()) < 50:
            logger.error(f"Chapter {chapter.number} has no or insufficient content")
            logger.error(f"Content length: {len(chapter.content) if chapter.content else 0}")
            return StoryElements()
        
        # Log what we're processing
        logger.info(f"Extracting story elements from chapter {chapter.number} ({chapter.word_count} words)")
        logger.debug(f"Chapter content preview: {chapter.content[:200]}...")
        
        # Use a simpler, more structured approach
        prompt = f"""Analyze this chapter and extract the key story elements. 

CHAPTER {chapter.number} CONTENT:
===BEGIN CHAPTER===
{chapter.content}
===END CHAPTER===

Provide your analysis in the following format:

PLOT POINTS:
1. [First major event]
2. [Second major event]
3. [Continue numbering...]

CHARACTER ACTIONS:
- Character Name: [what they do]
- Character Name: [what they do]

KEY DIALOGUES:
1. "Quote from chapter" - Speaker
2. "Another quote" - Speaker

SETTING:
- Location: [where the scene takes place]
- Time: [when it happens]

TIMELINE:
- [Any references to timing or duration]

Be concise and focus only on elements that are essential to the story."""

        try:
            # Choose model based on chapter length
            input_tokens = estimate_tokens(prompt)
            output_tokens = min(3000, chapter.word_count)  # Expect condensed output
            model_complexity = 'extended' if chapter.word_count > 15000 else 'medium'
            
            response = self.api_client.complete(
                prompt, 
                model_complexity=model_complexity,
                max_tokens=self.config.max_tokens['analysis'],
                temperature=self.config.temperatures['analysis']
            )
            
            # Parse the structured text response
            return self._parse_structured_response(response)
            
        except Exception as e:
            logger.error(f"Failed to extract story elements: {e}")
            logger.error(f"Full exception details: {repr(e)}")
            # Return empty elements as fallback
            return StoryElements(
                plot_points=[],
                character_actions={},
                key_dialogues=[],
                setting_details=[],
                timeline_markers=[]
            )
    
    def _parse_structured_response(self, response: str) -> StoryElements:
        """Parse structured text response into StoryElements."""
        try:
            # Initialize empty collections
            plot_points = []
            character_actions = {}
            key_dialogues = []
            setting_details = []
            timeline_markers = []
            
            # Split response into sections
            lines = response.split('\n')
            current_section = None
            
            # Regex to strip common list markers
            list_marker_pattern = re.compile(r'^\s*(?:[0-9]+\.|[*\-+])\s*')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Detect section headers using regex
                is_header = False
                if re.match(r'PLOT POINTS:?', line, re.IGNORECASE):
                    current_section = 'plot'
                    is_header = True
                elif re.match(r'CHARACTER ACTIONS:?', line, re.IGNORECASE):
                    current_section = 'character'
                    is_header = True
                elif re.match(r'KEY DIALOGUES:?', line, re.IGNORECASE):
                    current_section = 'dialogue'
                    is_header = True
                elif re.match(r'SETTING:?', line, re.IGNORECASE):
                    current_section = 'setting'
                    is_header = True
                elif re.match(r'TIMELINE:?', line, re.IGNORECASE):
                    current_section = 'timeline'
                    is_header = True
                
                if is_header:
                    continue

                # Process content based on current section
                if current_section == 'plot':
                    cleaned_line = list_marker_pattern.sub('', line).strip()
                    if cleaned_line:
                        plot_points.append(cleaned_line)
                
                elif current_section == 'character':
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            char_name = list_marker_pattern.sub('', parts[0]).strip()
                            action = parts[1].strip()
                            if char_name and action:
                                if char_name not in character_actions:
                                    character_actions[char_name] = []
                                character_actions[char_name].append(action)

                elif current_section == 'dialogue':
                    cleaned_line = list_marker_pattern.sub('', line).strip()
                    if cleaned_line:
                        key_dialogues.append(cleaned_line)
                
                elif current_section == 'setting':
                    cleaned_line = list_marker_pattern.sub('', line).strip()
                    if cleaned_line:
                        setting_details.append(cleaned_line)
                
                elif current_section == 'timeline':
                    cleaned_line = list_marker_pattern.sub('', line).strip()
                    if cleaned_line:
                        timeline_markers.append(cleaned_line)

            # Ensure we have at least some elements
            if not plot_points:
                plot_points = ["Chapter events to be preserved"]
            
            return StoryElements(
                plot_points=plot_points,
                character_actions=character_actions,
                key_dialogues=key_dialogues,
                setting_details=setting_details,
                timeline_markers=timeline_markers
            )
            
        except Exception as e:
            logger.error(f"Error parsing structured response: {e}")
            return StoryElements(
                plot_points=["Failed to parse chapter elements"],
                character_actions={},
                key_dialogues=[],
                setting_details=[],
                timeline_markers=[]
            )

# ============================================================================
# Enhanced Chapter Analysis (unchanged)
# ============================================================================

class StoryPreservingAnalyzer:
    """Analyzes chapters with focus on preserving story integrity."""
    
    def __init__(self, api_client: 'AnthropicClient', config: Config, 
                 element_extractor: StoryElementExtractor):
        self.api_client = api_client
        self.config = config
        self.element_extractor = element_extractor
    
    def analyze_for_revision(self, chapter: Chapter, all_chapters: Dict[int, Chapter],
                           context: ProjectContext) -> Tuple[str, StoryElements]:
        """Analyze chapter for revision opportunities while identifying core elements to preserve."""
        
        try:
            # First, extract story elements
            story_elements = self.element_extractor.extract_story_elements(chapter)
            
            # Then analyze for improvements
            prompt = self._build_preservation_analysis_prompt(
                chapter, all_chapters, context, story_elements
            )
            
            # Better model selection based on total context
            input_tokens = estimate_tokens(prompt)
            output_tokens = self.config.max_tokens['analysis']
            
            # Use extended model for very long chapters or complex context
            force_extended = chapter.word_count > 15000 or len(context.characters) > 5000
            model_complexity, max_tokens = select_model_for_task(
                input_tokens, output_tokens, force_extended, chapter.word_count
            )
            
            analysis = self.api_client.complete(
                prompt, 
                model_complexity=model_complexity,
                max_tokens=max_tokens,
                temperature=self.config.temperatures['analysis']
            )
            
            # Validate the analysis is complete
            analysis = self._ensure_complete_analysis(analysis, chapter.number)
            
            return analysis, story_elements
            
        except Exception as e:
            logger.error(f"Failed to analyze chapter {chapter.number}: {e}")
            raise
    
    def _ensure_complete_analysis(self, analysis: str, chapter_num: int) -> str:
        """Ensure the analysis is complete and doesn't end with questions."""
        # Check if analysis ends with a question
        if analysis.strip().endswith('?'):
            logger.warning(f"Analysis for chapter {chapter_num} ended with a question, adding completion")
            analysis += "\n\n---\nAnalysis complete. All sections have been covered."
        
        # Check if analysis is too short
        if len(analysis) < 1000:
            logger.warning(f"Analysis for chapter {chapter_num} seems too short ({len(analysis)} chars)")
            analysis += "\n\n## Additional Notes\nThis analysis covers the key areas for improvement while maintaining story integrity."
        
        # Remove any trailing offers or questions
        question_patterns = [
            r"Would you like.*?\?",
            r"Should I.*?\?", 
            r"Do you want.*?\?",
            r"I can also.*?\.",
            r"I could.*?\.",
            r"Let me know if.*?\."
        ]
        
        for pattern in question_patterns:
            analysis = re.sub(pattern, "", analysis, flags=re.IGNORECASE | re.MULTILINE)
        
        return analysis.strip()
    
    def _build_preservation_analysis_prompt(self, chapter: Chapter, 
                                          all_chapters: Dict[int, Chapter],
                                          context: ProjectContext, 
                                          story_elements: StoryElements) -> str:
        """Build analysis prompt focused on improvement without story changes."""
        
        # Summarize core elements safely
        plot_points_list = story_elements.plot_points[:5] if story_elements.plot_points else []
        plot_summary = '\n'.join(f"- {p}" for p in plot_points_list) if plot_points_list else "- No plot points extracted yet"
        
        # Safely truncate context elements
        synopsis_preview = context.synopsis[:500] + "..." if len(context.synopsis) > 500 else context.synopsis
        characters_preview = context.characters[:800] + "..." if len(context.characters) > 800 else context.characters
        
        return f"""Analyze this chapter for PROSE IMPROVEMENT opportunities while preserving the story exactly.

CRITICAL INSTRUCTIONS:
- Provide a COMPLETE analysis covering ALL sections below
- Do NOT ask questions or offer to do more
- Give specific examples from the actual text
- Be thorough and conclusive

NOVEL CONTEXT:
Title: {context.title}
Genre: {context.genre}
Synopsis: {synopsis_preview}

CHARACTER REFERENCE:
{characters_preview}

CHAPTER {chapter.number} TO ANALYZE ({chapter.word_count} words):
===BEGIN CHAPTER CONTENT===
{chapter.content}
===END CHAPTER CONTENT===

CORE PLOT POINTS THAT MUST BE PRESERVED:
{plot_summary}

PROVIDE A COMPLETE ANALYSIS OF:

## 1. PROSE QUALITY
Identify at least 5 specific sentences or phrases that could be improved:
- Quote the original text
- Explain why it needs improvement
- Suggest the type of improvement (NOT the actual rewrite)

## 2. SENSORY ENHANCEMENT
Identify at least 3 places where sensory details could be added:
- Quote the passage
- Note which senses are missing
- Explain what type of sensory detail would enhance the scene and *suggest 2-3 specific examples of sensory details that could be woven in without altering events* (e.g., 'the smell of damp earth,' 'the distant sound of a train').

## 3. CHARACTER DEPTH  
Identify at least 3 moments where character emotions/thoughts could be deeper:
- Quote the relevant passage
- Check consistency with character profiles above
- Explain what's missing emotionally. *Suggest 1-2 ways to show this missing emotion or nuance through internal thought, subtle action, or physical sensation, without changing the character's overt actions or dialogue content* (e.g., 'a fleeting internal thought of regret,' 'a barely perceptible tightening of the jaw').

## 4. PACING AND FLOW
Identify at least 3 specific transitions or pacing issues:
- Quote the problematic section
- Explain the pacing problem. *Suggest 2-3 specific techniques to improve flow or adjust pacing here without changing events* (e.g., 'shortening sentences in this action sequence,' 'adding a transitional phrase to bridge these two paragraphs,' 'slightly expanding a descriptive beat here to slow the moment').

## 5. DIALOGUE POLISH
Identify at least 3 dialogue exchanges that need work:
- Quote the dialogue
- Verify it matches the character's voice from the profiles
- Explain what makes it stilted or unnatural. *Suggest 1-2 ways to improve the delivery or subtext without changing the core meaning or information conveyed* (e.g., 'adding a brief action beat during this line,' 'rephrasing for a more natural cadence,' 'implying a specific emotion through a tone indicator in the narrative').

## 6. CHARACTER CONSISTENCY CHECK
Review all character appearances against the character profiles:
- Note any actions/dialogue that seem out of character
- Identify opportunities to strengthen character voice
- Ensure physical descriptions match profiles

## SUMMARY
Provide a brief summary of the chapter's main strengths and the top 5 most important improvements needed.

Remember: Focus ONLY on HOW things are written, not WHAT happens. Complete this entire analysis without asking questions."""

# ============================================================================
# Story-Preserving Revision Planning (unchanged)
# ============================================================================

class PreservationRevisionPlanner:
    """Creates revision plans that preserve story integrity."""
    
    def __init__(self, api_client: 'AnthropicClient', config: Config):
        self.api_client = api_client
        self.config = config
    
    def create_preservation_plan(self, chapter: Chapter, analysis: str, 
                               story_elements: StoryElements,
                               context: ProjectContext,
                               target_word_count: Optional[int] = None) -> RevisionPlan:
        """Create a revision plan focused on prose improvement."""
        
        # Determine target word count
        if target_word_count is None:
            target_word_count = chapter.word_count  # Default to maintaining length
        
        # Identify what must be preserved
        prohibited_changes = self._identify_prohibited_changes(story_elements)
        
        # Identify revision focus areas
        revision_focus = self._identify_revision_focus(analysis)
        
        prompt = self._build_preservation_planning_prompt(
            chapter, analysis, story_elements, prohibited_changes, revision_focus,
            target_word_count, context.inspirations, context.characters
        )
        
        try:
            # Better model selection for planning
            input_tokens = estimate_tokens(prompt)
            output_tokens = self.config.max_tokens['planning']
            
            # Planning needs extended model if lots of context
            total_context_size = len(analysis) + len(chapter.content) + len(context.characters) + len(context.inspirations)
            force_extended = total_context_size > 50000  # ~12,500 tokens
            
            model_complexity, max_tokens = select_model_for_task(
                input_tokens, output_tokens, force_extended, chapter.word_count
            )
            
            plan_content = self.api_client.complete(
                prompt,
                model_complexity=model_complexity,
                max_tokens=max_tokens,
                temperature=self.config.temperatures['planning']
            )
            
            return RevisionPlan(
                chapter_number=chapter.number,
                analysis=analysis,
                plan_content=plan_content,
                story_elements=story_elements,
                revision_focus=revision_focus,
                prohibited_changes=prohibited_changes,
                target_word_count=target_word_count,
                inspirations=context.inspirations,
                characters=context.characters
            )
        except Exception as e:
            logger.error(f"Failed to create plan for chapter {chapter.number}: {e}")
            raise
    
    def _identify_prohibited_changes(self, story_elements: StoryElements) -> List[str]:
        """Identify what cannot be changed."""
        prohibited = []
        
        # Core plot points
        plot_points_list = story_elements.plot_points[:10] if story_elements.plot_points else []
        for point in plot_points_list:
            prohibited.append(f"Plot point: {point}")
        
        # Character actions
        for character, actions in story_elements.character_actions.items():
            actions_list = actions[:3] if isinstance(actions, list) else []
            for action in actions_list:
                prohibited.append(f"{character}'s action: {action}")
        
        # Key dialogues
        dialogues_list = story_elements.key_dialogues[:5] if story_elements.key_dialogues else []
        for dialogue in dialogues_list:
            prohibited.append(f"Dialogue: {dialogue[:50]}...")
        
        return prohibited
    
    def _identify_revision_focus(self, analysis: str) -> List[str]:
        """Extract specific revision focus areas from analysis."""
        focus_areas = []
        
        # Look for sections in the analysis
        sections = ['PROSE QUALITY', 'SENSORY ENHANCEMENT', 'CHARACTER DEPTH', 
                   'PACING AND FLOW', 'DIALOGUE POLISH']
        
        for section in sections:
            if section in analysis:
                # Extract a few key points from each section
                section_match = re.search(
                    f'{section}.*?(?=\\n[A-Z]{{2,}}|$)', 
                    analysis, 
                    re.DOTALL
                )
                if section_match:
                    focus_areas.append(f"{section}: Key improvements identified")
        
        return focus_areas
    
    def _build_preservation_planning_prompt(self, chapter: Chapter, analysis: str,
                                          story_elements: StoryElements,
                                          prohibited_changes: List[str],
                                          revision_focus: List[str],
                                          target_word_count: int,
                                          inspirations: str = "",
                                          characters: str = "") -> str:
        """Build planning prompt with preservation focus."""
        
        # Safely limit lists
        prohibited_display = prohibited_changes[:10] if prohibited_changes else []
        prohibited_list = '\n'.join(f"- {p}" for p in prohibited_display) if prohibited_display else "- No specific prohibitions identified"
        
        focus_list = '\n'.join(f"- {f}" for f in revision_focus) if revision_focus else "- General prose improvement"
        
        # Safely truncate analysis
        analysis_preview = analysis[:1000] + "..." if len(analysis) > 1000 else analysis
        
        # Determine expansion/maintenance strategy
        if target_word_count > chapter.word_count * 1.1:
            length_strategy = f"""
## LENGTH EXPANSION STRATEGY
Current: {chapter.word_count} words → Target: {target_word_count} words
- Identify scenes that can be enriched with sensory details
- Find opportunities for deeper emotional exploration
- Expand descriptions of settings and atmosphere
- Develop internal character thoughts
- Enhance transitions between scenes"""
        else:
            length_strategy = f"""
## LENGTH MAINTENANCE STRATEGY  
Current: {chapter.word_count} words → Target: {target_word_count} words
- Maintain all existing content
- Focus on prose quality improvements
- Replace weak phrases with stronger ones
- Ensure no content is cut or condensed"""
        
        # Include inspirations section
        inspirations_section = ""
        if inspirations:
            inspirations_section = f"""
## LITERARY STYLE GUIDANCE
Apply the prose style and techniques inspired by:
{inspirations}

Consider incorporating:
- Le Carré's psychological depth and atmospheric tension
- Larsson's contemporary edge and investigative detail
- Greene's emotional complexity and moral ambiguity
- Journalistic precision and clarity (FT, Guardian style)
- Balance literary sophistication with accessibility
"""
        
        # Include character section
        characters_section = ""
        if characters:
            characters_preview = characters[:800] + "..." if len(characters) > 800 else characters
            characters_section = f"""
## CHARACTER PROFILES FOR CONSISTENCY
{characters_preview}

Ensure all character improvements align with these established profiles:
- Maintain consistent character voices
- Preserve established personality traits
- Keep physical descriptions accurate
- Respect character relationships and dynamics
"""
        
        return f"""Create a DETAILED REVISION PLAN that improves the prose while preserving the story exactly.

CHAPTER {chapter.number} ANALYSIS SUMMARY:
{analysis_preview}

{inspirations_section}

{characters_section}

WORD COUNT REQUIREMENT:
- Current chapter: {chapter.word_count} words
- Target length: {target_word_count} words
- Required change: {'+' if target_word_count > chapter.word_count else ''}{target_word_count - chapter.word_count} words

ELEMENTS THAT MUST NOT CHANGE:
{prohibited_list}

REVISION FOCUS AREAS:
{focus_list}

CREATE A SPECIFIC PLAN WITH:

{length_strategy}

## PROSE IMPROVEMENTS
Review the 'PROSE QUALITY' section of the CHAPTER ANALYSIS SUMMARY. For each specific sentence or phrase identified for improvement:
- Quote the original text.
- Briefly restate the suggested type of improvement from the analysis.
- Formulate a specific task to revise the prose (e.g., "Rephrase for clarity," "Replace weak verbs," "Break into shorter sentences").
- Apply style inspirations where relevant.
- Ensure character consistency is maintained.
- Note opportunities for expansion if needed, aligning with word count goals.

## SENSORY ENHANCEMENTS  
Review the 'SENSORY ENHANCEMENT' section of the CHAPTER ANALYSIS SUMMARY. For each suggestion (e.g., specific sounds, smells, textures identified for particular scenes):
- Identify the exact sentence or paragraph in the original chapter where this enhancement should be applied.
- Formulate a specific task to integrate this sensory detail naturally, using or adapting the examples provided in the analysis (e.g., "Weave in the suggested detail: 'the distant hum of machinery'").
- Briefly note the expected impact (e.g., "enhances industrial atmosphere," "grounds the scene during dialogue").
- Estimate any word count impact for this specific task.
- Must not change what happens or introduce new plot elements.

## DIALOGUE REFINEMENTS
Review the 'DIALOGUE POLISH' section of the CHAPTER ANALYSIS SUMMARY. For each dialogue exchange identified:
- Quote the original dialogue line(s).
- Refer to the analysis's explanation of what makes it stilted or how delivery could improve.
- Formulate a specific task to refine the dialogue delivery or subtext using the suggestions from the analysis (e.g., "Add a character action beat: 'she tapped her fingers impatiently' during this line to convey restlessness," "Rephrase for a more natural cadence as suggested: '...'").
- Preserve all core meaning and information conveyed.
- Verify consistency with character profiles and voices.
- Add narrative beats if expanding and appropriate for pacing.

## CHARACTER DEPTH ENHANCEMENTS
Review the 'CHARACTER DEPTH' section of the CHAPTER ANALYSIS SUMMARY. For each moment identified:
- Quote the relevant passage.
- Refer to the analysis's suggestions for showing missing emotion or nuance (e.g., through internal thought, subtle action, physical sensation).
- Formulate a specific task to integrate these suggestions without changing overt actions or dialogue content (e.g., "Insert internal thought reflecting [suggested emotion] here," "Add subtle physical reaction: [suggested sensation/action] to show internal state").
- Ensure changes align with established character profiles.

## PACING ADJUSTMENTS
Review the 'PACING AND FLOW' section of the CHAPTER ANALYSIS SUMMARY. For each transition or pacing issue identified:
- Quote the problematic section.
- Refer to the analysis's explanation and suggested techniques.
- Formulate a specific task to address the issue using the suggested techniques (e.g., "Apply technique: shorten sentences in this action sequence to increase urgency," "Add suggested transitional phrase: 'Meanwhile, across town...' to bridge paragraphs X and Y," "Expand descriptive beat here to slow the moment as suggested in analysis").
- Apply journalistic clarity where needed for transitions.

## VALIDATION CHECKLIST
Create a checklist to ensure story preservation:
- [ ] All plot points remain unchanged
- [ ] Character actions stay the same
- [ ] Dialogue meaning preserved
- [ ] Timeline unchanged
- [ ] No new scenes or characters added
- [ ] Target word count achieved (~{target_word_count} words)
- [ ] Literary style inspirations applied
- [ ] Character consistency maintained

BE EXTREMELY SPECIFIC. This plan will be followed exactly during revision."""

# ============================================================================
# REFACTORED: Story-Preserving Chapter Revision with critical fixes
# ============================================================================

class PreservingChapterReviser:
    """Revises chapters while strictly preserving story elements."""
    
    def __init__(self, api_client: 'AnthropicClient', config: Config):
        self.api_client = api_client
        self.config = config
    
    def revise_with_preservation(self, chapter: Chapter, plan: RevisionPlan,
                               context_chapters: Dict[int, Chapter]) -> RevisionResult:
        """Revise chapter with strict story preservation."""
        
        # Validate inputs
        if not chapter.content or len(chapter.content.strip()) < 100:
            logger.error(f"Chapter {chapter.number} has no valid content to revise")
            return RevisionResult(
                chapter_number=chapter.number,
                original_content=chapter.content,
                revised_content=chapter.content,
                original_word_count=chapter.word_count,
                revised_word_count=chapter.word_count,
                success=False,
                error_message="Chapter content missing or invalid"
            )
        
        target_words = getattr(plan, 'target_word_count', chapter.word_count)
        
        logger.info(f"Revising chapter {chapter.number} with target: {target_words} words (from {chapter.word_count})")
        
        try:
            # Check if we should use chunked revision for very large chapters
            if chapter.word_count > 6000:
                logger.info(f"Using chunked revision for large chapter ({chapter.word_count} words)")
                revised_content = self._chunked_revision(chapter, plan, target_words)
            else:
                revised_content = self._simple_direct_revision(chapter, plan, target_words)
            
            # Validate it's actually a chapter
            if not self._is_valid_chapter_revision(revised_content, chapter):
                logger.warning(f"First revision attempt invalid for chapter {chapter.number}, trying ultra-simple approach")
                revised_content = self._ultra_simple_revision(chapter, target_words)
                
                if not self._is_valid_chapter_revision(revised_content, chapter):
                    logger.error(f"Both revision attempts failed for chapter {chapter.number}")
                    return RevisionResult(
                        chapter_number=chapter.number,
                        original_content=chapter.content,
                        revised_content=chapter.content,
                        original_word_count=chapter.word_count,
                        revised_word_count=chapter.word_count,
                        success=False,
                        error_message="Failed to produce valid chapter content"
                    )
            
            # Clean and format
            cleaned_content = self._clean_ai_commentary(revised_content)
            
            # Ensure chapter heading
            if not re.match(r'^#?\s*(?:chapter|prologue)', cleaned_content, re.IGNORECASE):
                cleaned_content = f"# Chapter {chapter.number}\n\n{cleaned_content}"
            
            revised_word_count = len(cleaned_content.split())
            
            # FIXED: Better length handling with increased tolerance
            if not self._is_acceptable_length(revised_word_count, target_words):
                logger.info(f"Length adjustment needed: {revised_word_count} → {target_words} words")
                
                # If we're within 15% and validation passes, accept it
                tolerance_ratio = abs(revised_word_count - target_words) / target_words
                if tolerance_ratio < 0.15:
                    # Quick validation check
                    quick_valid, _ = self._improved_story_validation(
                        chapter.content, cleaned_content, plan.story_elements
                    )
                    if quick_valid:
                        logger.info(f"Accepting length variance ({tolerance_ratio:.1%}) due to good validation")
                    else:
                        cleaned_content = self._improved_length_adjustment(
                            cleaned_content, target_words, chapter.number
                        )
                        revised_word_count = len(cleaned_content.split())
                else:
                    # Too far off, must adjust
                    cleaned_content = self._improved_length_adjustment(
                        cleaned_content, target_words, chapter.number
                    )
                    revised_word_count = len(cleaned_content.split())
            
            # Improved validation
            validation_passed, deviation_score = self._improved_story_validation(
                chapter.content, cleaned_content, plan.story_elements
            )
            
            return RevisionResult(
                chapter_number=chapter.number,
                original_content=chapter.content,
                revised_content=cleaned_content,
                original_word_count=chapter.word_count,
                revised_word_count=revised_word_count,
                success=True,
                validation_passed=validation_passed,
                deviation_score=deviation_score
            )
            
        except Exception as e:
            logger.error(f"Failed to revise chapter {chapter.number}: {e}")
            return RevisionResult(
                chapter_number=chapter.number,
                original_content=chapter.content,
                revised_content=chapter.content,
                original_word_count=chapter.word_count,
                revised_word_count=chapter.word_count,
                success=False,
                error_message=str(e)
            )
    
    def _chunked_revision(self, chapter: Chapter, plan: RevisionPlan, target_words: int) -> str:
        """Revise very large chapters in chunks."""
        # Split chapter into manageable chunks
        chunks = self._split_into_chunks(chapter.content, self.config.chunk_size_words)
        revised_chunks = []
        
        # Calculate target words per chunk
        words_per_chunk = target_words // len(chunks)
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Revising chunk {i+1}/{len(chunks)}")
            
            # Create a mini-chapter for this chunk
            chunk_chapter = Chapter(
                number=chapter.number,
                file_path=chapter.file_path,
                content=chunk,
                word_count=len(chunk.split())
            )
            
            # Revise this chunk
            revised_chunk = self._simple_direct_revision(
                chunk_chapter, plan, words_per_chunk
            )
            
            # Clean and add to results
            cleaned_chunk = self._clean_ai_commentary(revised_chunk)
            revised_chunks.append(cleaned_chunk)
        
        # Combine chunks
        combined = "\n\n".join(revised_chunks)
        
        # Do a final smoothing pass
        return self._smooth_chunk_transitions(combined, chapter.number)
    
    def _split_into_chunks(self, content: str, chunk_size: int) -> List[str]:
        """Split content into chunks at natural boundaries."""
        # First try to split by scene breaks
        scene_markers = ['\n\n***\n\n', '\n\n* * *\n\n', '\n\n---\n\n']
        
        for marker in scene_markers:
            if marker in content:
                chunks = content.split(marker)
                # Recombine if chunks are too small
                combined_chunks = []
                current_chunk = ""
                
                for chunk in chunks:
                    if len(current_chunk.split()) + len(chunk.split()) < chunk_size * 1.5:
                        current_chunk += marker + chunk if current_chunk else chunk
                    else:
                        if current_chunk:
                            combined_chunks.append(current_chunk)
                        current_chunk = chunk
                
                if current_chunk:
                    combined_chunks.append(current_chunk)
                
                if len(combined_chunks) > 1:
                    return combined_chunks
        
        # Fall back to paragraph-based chunking
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_words = 0
        
        for para in paragraphs:
            para_words = len(para.split())
            
            if current_words + para_words > chunk_size and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_words = para_words
            else:
                current_chunk.append(para)
                current_words += para_words
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks
    
    def _smooth_chunk_transitions(self, content: str, chapter_num: int) -> str:
        """Smooth the transitions between chunks."""
        prompt = f"""This chapter was revised in sections. Please smooth any abrupt transitions between sections while keeping all content intact.

Do NOT change any events, characters, or dialogue. Only improve the flow between sections.

Chapter {chapter_num}:
{content}

Smoothed chapter:"""
        
        try:
            response = self.api_client.complete(
                prompt,
                model_complexity='complex',
                max_tokens=int(len(content.split()) * 1.5),
                temperature=0.5
            )
            
            return self._clean_ai_commentary(response)
        except Exception as e:
            logger.error(f"Smoothing failed: {e}")
            return content
    
    def _simple_direct_revision(self, chapter: Chapter, plan: RevisionPlan, target_words: int) -> str:
        """FIXED: Better model selection and clearer prompts."""
        
        # Extract 2-3 key improvements from the plan
        improvements = []
        if 'prose' in plan.plan_content.lower():
            improvements.append("Use stronger verbs and more vivid descriptions")
        if 'sensory' in plan.plan_content.lower():
            improvements.append("Add sensory details (sounds, smells, textures) to existing scenes")
        if 'emotion' in plan.plan_content.lower() or 'character' in plan.plan_content.lower():
            improvements.append("Deepen character emotions with physical reactions and inner thoughts")
        
        # If no specific improvements found, use defaults
        if not improvements:
            improvements = [
                "Replace weak verbs with stronger ones",
                "Add sensory details to make scenes more vivid",
                "Show character emotions through physical reactions"
            ]
        
        improvements_text = '\n'.join(f"- {imp}" for imp in improvements[:3])
        
        # Simple, clear prompt with emphasis on exact word count
        prompt = f"""Revise this chapter to EXACTLY {target_words} words with better prose.

CRITICAL: The output must be EXACTLY {target_words} words - count carefully!

Improvements needed:
{improvements_text}

RULES:
1. Keep all plot events exactly the same
2. Keep all dialogue meaning unchanged  
3. Only improve HOW it's written, not WHAT happens
4. Make prose more vivid and engaging
5. Output must be EXACTLY {target_words} words

Chapter {chapter.number}:
{chapter.content}

Output the complete revised chapter of EXACTLY {target_words} words:"""
        
        # Better model selection
        input_tokens = estimate_tokens(prompt)
        output_tokens = int(target_words * 1.3)  # Estimate tokens from words
        
        # FIXED: Force extended model for chapters > 2500 words
        model_complexity, max_tokens = select_model_for_task(
            input_tokens, output_tokens, 
            force_extended=(chapter.word_count > self.config.large_chapter_threshold),
            chapter_words=chapter.word_count
        )
        
        logger.info(f"Revision using {model_complexity} model with max_tokens={max_tokens}")
        
        return self.api_client.complete(
            prompt,
            model_complexity=model_complexity,
            max_tokens=max_tokens,
            temperature=self.config.temperatures['revision']
        )
    
    def _ultra_simple_revision(self, chapter: Chapter, target_words: int) -> str:
        """Ultra-simple fallback with proper model selection."""
        
        prompt = f"""Rewrite this text with better prose style. Target: {target_words} words.

Keep the story the same. Only improve the writing.

{chapter.content}

Chapter {chapter.number}:"""
        
        # Model selection
        input_tokens = estimate_tokens(prompt)
        output_tokens = int(target_words * 1.3)
        
        model_complexity, max_tokens = select_model_for_task(
            input_tokens, output_tokens, 
            force_extended=(output_tokens > 25000 or chapter.word_count > 2500),
            chapter_words=chapter.word_count
        )
        
        return self.api_client.complete(
            prompt,
            model_complexity=model_complexity,
            max_tokens=max_tokens,
            temperature=0.8  # Higher temperature for more natural output
        )
    
    def _is_valid_chapter_revision(self, content: str, original_chapter: Chapter) -> bool:
        """Better validation of chapter content."""
        # Check basic validity
        if not content or len(content.split()) < original_chapter.word_count * 0.5:
            logger.warning("Content too short to be valid")
            return False
        
        # Check for AI refusal/explanation patterns
        refusal_patterns = [
            "i apologize", "i'm sorry", "i cannot", "i can't",
            "i would revise", "i'll revise", "here's how i would",
            "to revise this", "the revision would"
        ]
        
        first_500_lower = content[:500].lower()
        for pattern in refusal_patterns:
            if pattern in first_500_lower:
                logger.warning(f"Found refusal pattern: '{pattern}'")
                return False
        
        # Check it has narrative content
        if content.count('\n\n') < 2:  # Should have paragraphs
            logger.warning("Content lacks paragraph structure")
            return False
        
        # Check it contains some key words from original
        original_words = set(original_chapter.content.lower().split())
        content_words = set(content.lower().split())
        overlap = len(original_words & content_words) / len(original_words)
        
        if overlap < 0.3:  # Less than 30% word overlap is suspicious
            logger.warning(f"Low word overlap with original: {overlap:.2%}")
            return False
        
        return True
    
    def _is_acceptable_length(self, actual: int, target: int) -> bool:
        """Check if word count is within acceptable range."""
        # Use tighter tolerance for better accuracy
        tolerance = 0.10  # 10% tolerance
        return target * (1 - tolerance) <= actual <= target * (1 + tolerance)
    
    def _improved_length_adjustment(self, content: str, target_words: int, chapter_num: int) -> str:
        """CRITICAL FIX: Unambiguous length adjustment prompts."""
        current_words = len(content.split())
        difference = target_words - current_words
        
        # Increased tolerance
        if abs(difference) < 100:  # Increased from 50
            logger.info(f"Length difference of {difference} words is within tolerance")
            return content
        
        # CRITICAL FIX: Clear, unambiguous prompts
        if difference > 0:
            # Need to expand
            prompt = f"""The chapter below is {current_words} words. 
Expand it to EXACTLY {target_words} words total.

Add {difference} more words by:
- Expanding descriptions with sensory details
- Adding character thoughts and reactions
- Enhancing atmosphere and setting
- Deepening emotional moments

DO NOT change any plot events or dialogue meaning.
The output must be EXACTLY {target_words} words.

Current chapter:
{content}

Output the expanded chapter of EXACTLY {target_words} words:"""
        else:
            # Need to reduce - CRITICAL FIX HERE
            prompt = f"""The chapter below is {current_words} words.
Tighten it to EXACTLY {target_words} words total.

Cut {-difference} words by:
- Removing redundant phrases
- Tightening descriptions
- Combining short sentences
- Removing unnecessary adjectives

DO NOT remove any plot events or change dialogue meaning.
The output must be EXACTLY {target_words} words.

Current chapter:
{content}

Output the tightened chapter of EXACTLY {target_words} words:"""
        
        try:
            # Model selection for adjustment
            input_tokens = estimate_tokens(prompt)
            output_tokens = int(target_words * 1.3)
            
            model_complexity, max_tokens = select_model_for_task(
                input_tokens, output_tokens,
                force_extended=(output_tokens > 25000 or current_words > 2500),
                chapter_words=current_words
            )
            
            logger.info(f"Length adjustment using {model_complexity} model")
            
            adjusted = self.api_client.complete(
                prompt,
                model_complexity=model_complexity,
                max_tokens=max_tokens,
                temperature=self.config.temperatures['length_adjustment']
            )
            
            # Clean and validate
            cleaned = self._clean_ai_commentary(adjusted)
            
            # Check it's valid and reasonable length
            adjusted_words = len(cleaned.split())
            logger.info(f"Length adjustment result: {current_words} → {adjusted_words} words (target: {target_words})")
            
            # Validate the adjustment worked
            if self._is_valid_chapter_revision(cleaned, Chapter(chapter_num, Path("temp"), content, current_words)):
                # Check if we got closer to target
                if abs(adjusted_words - target_words) < abs(current_words - target_words):
                    logger.info("Length adjustment successful")
                    return cleaned
                else:
                    logger.warning(f"Length adjustment made it worse: {adjusted_words} vs target {target_words}")
                    return content
            else:
                logger.warning("Length adjustment produced invalid content")
                return content
                
        except Exception as e:
            logger.error(f"Length adjustment failed: {e}")
            return content
    
    def _improved_story_validation(self, original: str, revised: str, 
                                  elements: StoryElements) -> Tuple[bool, float]:
        """ENHANCED: Better validation using fuzzy matching and semantic similarity."""
        
        # Warn about large chapter validation
        total_text_size = len(original) + len(revised)
        if total_text_size > 100000:  # ~25,000 tokens
            logger.warning(f"Large chapter validation: {total_text_size} chars. Using sampling.")
        
        revised_lower = revised.lower()
        scores = []
        
        # Check plot points with semantic similarity
        plot_found = 0
        plot_total = min(len(elements.plot_points), 5)
        for point in elements.plot_points[:plot_total]:
            # Try exact match first
            if point.lower() in revised_lower:
                plot_found += 1
                logger.debug(f"Plot point found (exact): {point[:50]}...")
            else:
                # Try semantic similarity
                similarity = semantic_similarity_check(point, revised_lower)
                if similarity > 0.6:  # 60% of key words found
                    plot_found += similarity
                    logger.debug(f"Plot point found (semantic {similarity:.2f}): {point[:50]}...")
        
        plot_score = plot_found / max(plot_total, 1)
        scores.append(plot_score)
        logger.info(f"Plot validation: {plot_found:.2f}/{plot_total} found")
        
        # Check character presence with variations
        chars_found = 0
        chars_total = min(len(elements.character_actions.keys()), 5)
        for char in list(elements.character_actions.keys())[:chars_total]:
            char_lower = char.lower()
            # Check for character name or common variations
            char_parts = char_lower.split()
            char_variations = [char_lower] + char_parts  # Full name and individual parts
            if any(var in revised_lower for var in char_variations if len(var) > 2):
                chars_found += 1
                logger.debug(f"Character found: {char}")
        
        char_score = chars_found / max(chars_total, 1)
        scores.append(char_score)
        logger.info(f"Character validation: {chars_found}/{chars_total} found")
        
        # Check key dialogues with fuzzy matching
        dialogue_found = 0
        dialogue_total = min(len(elements.key_dialogues), 3)
        for dialogue in elements.key_dialogues[:dialogue_total]:
            # Extract just the quoted part if possible
            quote_match = re.search(r'"([^"]+)"', dialogue)
            if quote_match:
                quote = quote_match.group(1)
                # Check for exact or semantic match
                if quote.lower() in revised_lower:
                    dialogue_found += 1
                    logger.debug(f"Dialogue found (exact): {quote[:30]}...")
                else:
                    # Check semantic similarity for dialogue
                    similarity = semantic_similarity_check(quote, revised_lower, min_words=2)
                    if similarity > 0.7:
                        dialogue_found += similarity
                        logger.debug(f"Dialogue found (semantic {similarity:.2f}): {quote[:30]}...")
        
        if dialogue_total > 0:
            dialogue_score = dialogue_found / dialogue_total
            scores.append(dialogue_score)
            logger.info(f"Dialogue validation: {dialogue_found:.2f}/{dialogue_total} found")
        
        # Calculate overall score
        overall_score = sum(scores) / len(scores)
        deviation_score = 1.0 - overall_score
        validation_passed = deviation_score < self.config.revision_constraints.max_deviation_score
        
        logger.info(f"Validation scores - Plot: {plot_score:.2f}, Chars: {char_score:.2f}, "
                   f"Overall: {overall_score:.2f}, Deviation: {deviation_score:.2f}")
        
        if not validation_passed:
            logger.warning(f"Validation failed: deviation {deviation_score:.2f} > threshold {self.config.revision_constraints.max_deviation_score}")
        
        return validation_passed, deviation_score
    
    def _clean_ai_commentary(self, text: str) -> str:
        """Remove AI commentary from text."""
        # Remove common AI preambles
        preambles = [
            "Here's the revised chapter", "Here is the revised chapter",
            "I'll revise", "I will revise", "Let me revise",
            "Here's my revision", "Here is my revision",
            "Here's the expanded chapter", "Here is the expanded chapter",
            "Here's the tightened chapter", "Here is the tightened chapter"
        ]
        
        for preamble in preambles:
            if text.lower().startswith(preamble.lower()):
                # Find the actual chapter start
                chapter_start = re.search(r'(Chapter \d+|# Chapter|# Prologue|Prologue)', text, re.IGNORECASE)
                if chapter_start:
                    text = text[chapter_start.start():]
                    break
        
        # Clean extra whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text).strip()
        
        return text

# ============================================================================
# File Handling (with duplicate detection)
# ============================================================================

class FileHandler:
    """Handles all file operations with proper error handling."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def read_file(self, file_path: Path) -> str:
        """Safely read a file with multiple encoding attempts."""
        if not file_path.exists():
            raise FileOperationError(f"File not found: {file_path}")
        
        for encoding in self.config.file_encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # Last resort: read as binary and decode with replacement
        try:
            with open(file_path, 'rb') as f:
                return f.read().decode('utf-8', errors='replace')
        except Exception as e:
            raise FileOperationError(f"Failed to read {file_path}: {e}")
    
    def write_file(self, file_path: Path, content: str) -> None:
        """Safely write a file with UTF-8 encoding."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
        except Exception as e:
            raise FileOperationError(f"Failed to write {file_path}: {e}")
    
    def find_files(self, directory: Path, patterns: List[str]) -> List[Path]:
        """Find files matching patterns in directory."""
        files = []
        for pattern in patterns:
            files.extend(directory.glob(pattern))
        
        # Remove duplicates and sort
        unique_files = []
        seen_names = {}
        
        for file in sorted(set(files)):
            # Extract chapter number from filename
            match = re.search(r'chapter[_\s]*(\d+)', file.name, re.IGNORECASE)
            if match:
                chapter_num = int(match.group(1))
                if chapter_num in seen_names:
                    # Prefer files with fewer underscores
                    if file.name.count('_') < seen_names[chapter_num].name.count('_'):
                        logger.warning(f"Duplicate chapter {chapter_num}: preferring {file.name} over {seen_names[chapter_num].name}")
                        seen_names[chapter_num] = file
                else:
                    seen_names[chapter_num] = file
            else:
                unique_files.append(file)
        
        # Add the deduplicated chapter files
        unique_files.extend(seen_names.values())
        
        return sorted(unique_files)

# ============================================================================
# API Client (with better error handling)
# ============================================================================

class AnthropicClient:
    """Wrapper for Anthropic API with retry logic and error handling."""
    
    def __init__(self, config: Config):
        self.config = config
        if not config.api_key:
            raise ValidationError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(
            api_key=config.api_key,
            timeout=600.0,  # 10 minute timeout for long operations
            max_retries=2   # Built-in retries
        )
    
    def complete(self, prompt: str, model_complexity: str = 'medium', 
                 max_tokens: Optional[int] = None, use_streaming: bool = False,
                 temperature: float = 0.3) -> str:
        """Make API call with retry logic."""
        model = self.config.models.get(model_complexity, self.config.models['medium'])
        if max_tokens is None:
            max_tokens = self.config.max_tokens.get('revision', 30000)
        
        # Auto-switch to Sonnet for large requests
        if model_complexity != 'extended' and max_tokens > 32000:
            logger.info(f"Requested {max_tokens} tokens, auto-switching to Claude Sonnet 4")
            model = self.config.models['extended']  # Use Sonnet 4
            model_complexity = 'extended'
        
        # Apply appropriate limits
        if model_complexity == 'extended':
            max_tokens = min(max_tokens, 60000)
        else:
            max_tokens = min(max_tokens, 30000)
        
        # Log token usage
        prompt_tokens = estimate_tokens(prompt)
        logger.info(f"API call - Model: {model}, Max tokens: {max_tokens}, Est. prompt tokens: {prompt_tokens}")
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Extract text from response
                if response and hasattr(response, 'content'):
                    raw_result = ""
                    if isinstance(response.content, list) and len(response.content) > 0:
                        first_content = response.content[0]
                        if hasattr(first_content, 'text'):
                            raw_result = str(first_content.text)
                        else:
                            raw_result = str(first_content)
                    elif isinstance(response.content, str):
                        raw_result = response.content
                    else:
                        logger.error(f"Unexpected response content type: {type(response.content)}")
                        raw_result = str(response.content)

                    # Check for AI refusal patterns
                    if raw_result and isinstance(raw_result, str):
                        if self._is_refusal_response(raw_result):
                            error_message = f"AI responded with a refusal: '{raw_result[:150]}...'"
                            logger.error(error_message)
                            if attempt < self.config.max_retries - 1:
                                logger.info(f"Retrying with attempt {attempt + 2}")
                                time.sleep(self.config.retry_delay)
                                continue
                            raise APIError(error_message)
                        
                        logger.info(f"Response received: {len(raw_result.split())} words")
                        return raw_result
                    else:
                        error_message = f"Received unexpected or null content from AI: {raw_result}"
                        logger.error(error_message)
                        raise APIError(error_message)
                else:
                    logger.error(f"Unexpected response structure or empty response: {type(response)}")
                    raise APIError(f"Unexpected response structure or empty response: {type(response)}")
                
            except RateLimitError:
                if attempt < self.config.max_retries - 1:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise APIError("Rate limit exceeded after retries")
            except Exception as e:
                logger.error(f"API error: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
                    continue
                raise APIError(f"API call failed: {e}")
    
    def _is_refusal_response(self, text: str) -> bool:
        """Check if the response is a refusal."""
        result_lower = text.lower()
        refusal_patterns = [
            "i cannot fulfill this request",
            "i am unable to",
            "i'm sorry, but i cannot",
            "my apologies,",
            "i must decline",
            "i'm not able to",
            "i cannot provide"
        ]
        
        for pattern in refusal_patterns:
            if pattern in result_lower[:500]:  # Check first 500 chars
                return True
        
        return False

# ============================================================================
# Validation Service
# ============================================================================

class ValidationService:
    """Validates revision results against constraints."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def validate_revision(self, original: Chapter, revised: Chapter, 
                         story_elements: StoryElements,
                         target_word_count: Optional[int] = None) -> Tuple[bool, str]:
        """Validate that revision maintains story integrity."""
        issues = []
        
        # Word count validation - use target if provided
        if target_word_count:
            if not self._validate_target_word_count(revised.word_count, target_word_count):
                issues.append(f"Word count missed target: {target_word_count} → {revised.word_count}")
        else:
            if not self._validate_word_count(original.word_count, revised.word_count):
                issues.append(f"Word count deviation too high: {original.word_count} → {revised.word_count}")
        
        # Story element validation
        element_issues = self._validate_story_elements(original.content, revised.content, story_elements)
        issues.extend(element_issues)
        
        # Structure validation - skip if significant length change was intended
        if not target_word_count or abs(target_word_count - original.word_count) / original.word_count < 0.5:
            if not self._validate_structure(original.content, revised.content):
                issues.append("Chapter structure significantly altered")
        
        if issues:
            return False, "\n".join(issues)
        return True, "Validation passed"
    
    def _validate_target_word_count(self, actual: int, target: int) -> bool:
        """Check if word count is within acceptable range of target."""
        tolerance = 0.1  # 10% tolerance for absolute targets
        return target * (1 - tolerance) <= actual <= target * (1 + tolerance)
    
    def _validate_word_count(self, original: int, revised: int) -> bool:
        """Check if word count is within acceptable range."""
        tolerance = self.config.revision_constraints.length_tolerance
        return original * (1 - tolerance) <= revised <= original * (1 + tolerance)
    
    def _validate_story_elements(self, original: str, revised: str, 
                                elements: StoryElements) -> List[str]:
        """Validate story elements are preserved."""
        issues = []
        revised_lower = revised.lower()
        
        # Check plot points
        missing_plots = []
        for point in elements.plot_points[:5]:  # Check top 5
            if point.lower() not in revised_lower:
                # Check semantic similarity
                if semantic_similarity_check(point, revised_lower) < 0.6:
                    missing_plots.append(point[:50] + "...")
        
        if missing_plots:
            issues.append(f"Missing plot points: {', '.join(missing_plots)}")
        
        # Check characters
        missing_chars = []
        for char in list(elements.character_actions.keys())[:5]:
            char_parts = char.lower().split()
            if not any(part in revised_lower for part in char_parts if len(part) > 2):
                missing_chars.append(char)
        
        if missing_chars:
            issues.append(f"Missing characters: {', '.join(missing_chars)}")
        
        return issues
    
    def _validate_structure(self, original: str, revised: str) -> bool:
        """Validate chapter structure is maintained."""
        # Count major structural elements
        original_paras = len([p for p in original.split('\n\n') if p.strip()])
        revised_paras = len([p for p in revised.split('\n\n') if p.strip()])
        
        # Allow some variation but not drastic changes
        para_ratio = revised_paras / max(original_paras, 1)
        return 0.7 <= para_ratio <= 1.3

# ============================================================================
# Chapter Management
# ============================================================================

class ChapterManager:
    """Manages chapter discovery and organization."""
    
    def __init__(self, config: Config, file_handler: FileHandler):
        self.config = config
        self.file_handler = file_handler
    
    def find_all_chapters(self) -> Dict[int, Chapter]:
        """Find all chapter files in the project."""
        chapters = {}
        
        for dir_name in self.config.chapter_dirs:
            directory = Path(dir_name)
            if not directory.exists():
                continue
                
            chapter_files = self.file_handler.find_files(directory, self.config.chapter_patterns)
            
            for file_path in chapter_files:
                try:
                    chapter_num = self._extract_chapter_number(file_path)
                    if chapter_num is not None and chapter_num not in chapters:
                        content = self.file_handler.read_file(file_path)
                        chapters[chapter_num] = Chapter(
                            number=chapter_num,
                            file_path=file_path,
                            content=content,
                            word_count=len(content.split())
                        )
                        logger.info(f"Found chapter {chapter_num}: {file_path} ({chapters[chapter_num].word_count} words)")
                except Exception as e:
                    logger.error(f"Failed to load chapter from {file_path}: {e}")
        
        return chapters
    
    def _extract_chapter_number(self, file_path: Path) -> Optional[int]:
        """Extract chapter number from filename."""
        # Try various patterns
        patterns = [
            r'chapter[_\s]*(\d+)',
            r'ch[_\s]*(\d+)',
            r'^\d+',
            r'_(\d+)\.md'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, file_path.name, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None

# ============================================================================
# Context Management
# ============================================================================

class ContextManager:
    """Manages project context (synopsis, characters, etc.)."""
    
    def __init__(self, file_handler: FileHandler):
        self.file_handler = file_handler
    
    def load_project_context(self) -> ProjectContext:
        """Load project context from various files."""
        context = ProjectContext()
        
        # Define context file mappings
        context_files = {
            'synopsis': ['synopsis.md', 'synopsis.txt', 'summary.md'],
            'outline': ['outline.md', 'outline.txt', 'structure.md'],
            'characters': ['characters.md', 'characters.txt', 'cast.md'],
            'inspirations': ['inspirations.md', 'inspirations.txt', 'influences.md'],
            'story_bible': ['story_bible.md', 'bible.md', 'rules.md']
        }
        
        # Search in common directories
        search_dirs = ['.', 'docs', 'planning', 'context', 'reference']
        
        for attr, filenames in context_files.items():
            content = self._find_and_load_file(filenames, search_dirs)
            if content:
                setattr(context, attr, content)
                logger.info(f"Loaded {attr}: {len(content)} characters")
        
        # Try to detect genre and title from synopsis or outline
        if context.synopsis:
            context.title, context.genre = self._extract_metadata(context.synopsis)
        
        return context
    
    def _find_and_load_file(self, filenames: List[str], directories: List[str]) -> str:
        """Find and load the first matching file."""
        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                continue
                
            for filename in filenames:
                file_path = dir_path / filename
                if file_path.exists():
                    try:
                        return self.file_handler.read_file(file_path)
                    except Exception as e:
                        logger.warning(f"Failed to read {file_path}: {e}")
        
        return ""
    
    def _extract_metadata(self, text: str) -> Tuple[str, str]:
        """Extract title and genre from text."""
        title = "Novel"
        genre = "Literary Fiction"
        
        # Look for title
        title_match = re.search(r'(?:title|novel):\s*(.+)', text, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
        
        # Look for genre
        genre_match = re.search(r'genre:\s*(.+)', text, re.IGNORECASE)
        if genre_match:
            genre = genre_match.group(1).strip()
        
        return title, genre

# ============================================================================
# Main Revision Orchestrator
# ============================================================================

class RevisionOrchestrator:
    """Orchestrates the entire revision process."""
    
    def __init__(self, config: Config):
        self.config = config
        self.file_handler = FileHandler(config)
        self.api_client = AnthropicClient(config)
        self.element_extractor = StoryElementExtractor(self.api_client, config)
        self.analyzer = StoryPreservingAnalyzer(self.api_client, config, self.element_extractor)
        self.planner = PreservationRevisionPlanner(self.api_client, config)
        self.reviser = PreservingChapterReviser(self.api_client, config)
        self.validator = ValidationService(config)
        self.chapter_manager = ChapterManager(config, self.file_handler)
        self.context_manager = ContextManager(self.file_handler)
    
    def revise_chapters(self, chapter_numbers: Optional[List[int]] = None,
                       output_dir: str = "revised_chapters",
                       length_param: float = 1.0) -> Dict[int, RevisionResult]:
        """Revise specified chapters or all chapters."""
        
        # Load all chapters
        all_chapters = self.chapter_manager.find_all_chapters()
        if not all_chapters:
            logger.error("No chapters found!")
            return {}
        
        # Load project context
        context = self.context_manager.load_project_context()
        logger.info(f"Project: {context.title} ({context.genre})")
        
        # Determine which chapters to revise
        if chapter_numbers:
            chapters_to_revise = {num: all_chapters[num] for num in chapter_numbers if num in all_chapters}
        else:
            chapters_to_revise = all_chapters
        
        logger.info(f"Revising {len(chapters_to_revise)} chapters")
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Revise each chapter
        results = {}
        for chapter_num, chapter in sorted(chapters_to_revise.items()):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing Chapter {chapter_num}")
            logger.info(f"{'='*60}")
            
            try:
                result = self._revise_single_chapter(
                    chapter, all_chapters, context, 
                    output_path, length_param
                )
                results[chapter_num] = result
                
                # Save progress after each chapter
                self._save_results_summary(results, output_path)
                
            except Exception as e:
                logger.error(f"Failed to revise chapter {chapter_num}: {e}")
                results[chapter_num] = RevisionResult(
                    chapter_number=chapter_num,
                    original_content=chapter.content,
                    revised_content=chapter.content,
                    original_word_count=chapter.word_count,
                    revised_word_count=chapter.word_count,
                    success=False,
                    error_message=str(e)
                )
        
        return results
    
    def _revise_single_chapter(self, chapter: Chapter, all_chapters: Dict[int, Chapter],
                              context: ProjectContext, output_path: Path,
                              length_param: float) -> RevisionResult:
        """Revise a single chapter."""
        
        # Step 1: Analyze chapter
        logger.info(f"Step 1: Analyzing chapter {chapter.number}...")
        analysis, story_elements = self.analyzer.analyze_for_revision(chapter, all_chapters, context)
        
        # Step 2: Create revision plan
        logger.info(f"Step 2: Creating revision plan...")
        
        # Interpret length parameter
        if length_param < 10:
            # It's a multiplier
            target_word_count = int(chapter.word_count * length_param)
            logger.info(f"Using length multiplier: {length_param}x = {target_word_count} words")
        else:
            # It's an absolute word count
            target_word_count = int(length_param)
            logger.info(f"Using absolute target: {target_word_count} words")
        
        plan = self.planner.create_preservation_plan(
            chapter, analysis, story_elements, context, target_word_count
        )
        
        # Save plan for reference
        plan_path = output_path / f"chapter_{chapter.number}_plan.md"
        self.file_handler.write_file(plan_path, f"# Chapter {chapter.number} Revision Plan\n\n{plan.plan_content}")
        
        # Step 3: Revise chapter
        logger.info(f"Step 3: Revising chapter...")
        result = self.reviser.revise_with_preservation(chapter, plan, all_chapters)
        
        # Step 4: Validate result
        if result.success:
            logger.info(f"Step 4: Validating revision...")
            # Additional validation beyond what's in the reviser
            revised_chapter = Chapter(
                number=chapter.number,
                file_path=chapter.file_path,
                content=result.revised_content,
                word_count=result.revised_word_count
            )
            
            # Pass target word count to validator
            validation_passed, validation_msg = self.validator.validate_revision(
                chapter, revised_chapter, story_elements, target_word_count
            )
            
            if not validation_passed:
                logger.warning(f"Additional validation failed: {validation_msg}")
                result.validation_passed = False
        
        # Step 5: Save result
        if result.success:
            output_file = output_path / f"chapter_{chapter.number}_revised.md"
            self.file_handler.write_file(output_file, result.revised_content)
            logger.info(f"Saved revised chapter to {output_file}")
            
            # Save comparison report
            self._save_comparison_report(chapter, result, output_path)
        
        return result
    
    def _save_comparison_report(self, original: Chapter, result: RevisionResult, output_path: Path):
        """Save a comparison report for the revision."""
        report = f"""# Chapter {original.number} Revision Report

## Statistics
- Original word count: {original.word_count}
- Revised word count: {result.revised_word_count}
- Change: {result.revised_word_count - original.word_count:+d} words ({(result.revised_word_count / original.word_count - 1) * 100:+.1f}%)
- Validation: {'PASSED' if result.validation_passed else 'FAILED'}
- Deviation score: {result.deviation_score:.2f}

## Sample Comparison

### Original (first 500 words):
{' '.join(original.content.split()[:500])}...

### Revised (first 500 words):
{' '.join(result.revised_content.split()[:500])}...
"""
        
        report_path = output_path / f"chapter_{original.number}_comparison.md"
        self.file_handler.write_file(report_path, report)
    
    def _save_results_summary(self, results: Dict[int, RevisionResult], output_path: Path):
        """Save a summary of all results."""
        summary = "# Revision Summary\n\n"
        summary += "| Chapter | Original | Revised | Change | Status | Validation |\n"
        summary += "|---------|----------|---------|--------|--------|------------|\n"
        
        total_original = 0
        total_revised = 0
        
        for chapter_num, result in sorted(results.items()):
            if result.success:
                change = result.revised_word_count - result.original_word_count
                change_pct = (result.revised_word_count / result.original_word_count - 1) * 100
                status = "✓" if result.success else "✗"
                validation = "✓" if result.validation_passed else "✗"
                
                summary += f"| {chapter_num} | {result.original_word_count} | "
                summary += f"{result.revised_word_count} | {change:+d} ({change_pct:+.1f}%) | "
                summary += f"{status} | {validation} |\n"
                
                total_original += result.original_word_count
                total_revised += result.revised_word_count
            else:
                summary += f"| {chapter_num} | {result.original_word_count} | - | - | ✗ | - |\n"
                total_original += result.original_word_count
        
        if total_original > 0:
            total_change = total_revised - total_original
            total_pct = (total_revised / total_original - 1) * 100 if total_original > 0 else 0
            summary += f"\n**Total: {total_original} → {total_revised} words "
            summary += f"({total_change:+d}, {total_pct:+.1f}%)**\n"
        
        summary_path = output_path / "revision_summary.md"
        self.file_handler.write_file(summary_path, summary)

# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Story-preserving chapter revision tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Revise all chapters with default settings
  python chapter_reviser.py
  
  # Revise specific chapters for a project
  python chapter_reviser.py glasshouse --chapters 1 2 3
  
  # Expand chapters by 50%
  python chapter_reviser.py --length 1.5
  
  # Set chapters to exactly 3500 words
  python chapter_reviser.py --length 3500
  
  # Use cost optimization (shorter prompts, fewer API calls)
  python chapter_reviser.py --cost-optimize
        """
    )
    
    parser.add_argument(
        'project',
        type=str,
        nargs='?',
        default='.',
        help='Project directory (default: current directory)'
    )
    
    parser.add_argument(
        '-c', '--chapters',
        type=int,
        nargs='+',
        help='Chapter numbers to revise (default: all chapters)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='revised_chapters',
        help='Output directory for revised chapters (default: revised_chapters)'
    )
    
    parser.add_argument(
        '-l', '--length',
        type=float,
        default=1.0,
        help='Target length: if < 10, used as multiplier (e.g., 1.5 = 150%); if >= 10, used as absolute word count (e.g., 3500 = 3500 words)'
    )
    
    parser.add_argument(
        '--cost-optimize',
        action='store_true',
        help='Use cost optimization mode (fewer API calls, shorter prompts)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='Anthropic API key (or set ANTHROPIC_API_KEY env var)'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create config
    config = Config()
    
    # Apply cost optimization if requested
    if args.cost_optimize:
        logger.info("Using cost optimization mode")
        # Use simpler models and shorter outputs
        config.models = {
            "simple": "claude-opus-4-20250514",
            "medium": "claude-opus-4-20250514",
            "complex": "claude-opus-4-20250514",
            "extended": "claude-sonnet-4-20250514",
        }
        # Reduce max tokens for cost optimization
        config.max_tokens = {
            'analysis': 4000,      # Reduced from 8000
            'planning': 3000,      # Reduced from 6000
            'revision': 20000,     # Reduced from 30000
            'revision_extended': 40000,  # Reduced from 60000
            'validation': 2000,    # Reduced from 4000
            'length_adjustment': 20000   # Reduced from 30000
        }
    
    # Override API key if provided
    if args.api_key:
        config.api_key = args.api_key
    
    # Validate API key
    if not config.api_key:
        logger.error("No API key found! Set ANTHROPIC_API_KEY or use --api-key")
        return 1
    
    # Change to project directory if specified
    if args.project and args.project != '.':
        project_path = Path(args.project)
        if project_path.exists() and project_path.is_dir():
            os.chdir(project_path)
            logger.info(f"Changed to project directory: {project_path}")
        else:
            logger.error(f"Project directory not found: {args.project}")
            return 1
    
    # Create orchestrator and run
    try:
        orchestrator = RevisionOrchestrator(config)
        results = orchestrator.revise_chapters(
            chapter_numbers=args.chapters,
            output_dir=args.output,
            length_param=args.length
        )
        
        # Report results
        successful = sum(1 for r in results.values() if r.success and r.validation_passed)
        total = len(results)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Revision complete: {successful}/{total} chapters successfully revised")
        logger.info(f"Results saved to: {args.output}")
        logger.info(f"{'='*60}")
        
        return 0 if successful == total else 1
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())