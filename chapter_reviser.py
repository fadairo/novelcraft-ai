#!/usr/bin/env python3
"""
chapter_reviser.py - Story-Preserving Chapter Revision Tool

A refactored version that maintains story integrity while improving prose quality.
Key changes:
- Explicit story preservation constraints
- Validation of core plot elements
- Enhanced existing content rather than adding new storylines
- Configurable revision boundaries
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
        'revision': 30000,  # Safe limit under 32000 max
        'validation': 4000
    })
    
    # Temperature settings for different operations
    temperatures: Dict[str, float] = field(default_factory=lambda: {
        'analysis': 0.2,      # Very low for factual, consistent analysis/extraction
        'planning': 0.3,      # Low for structured planning
        'revision': 0.4,      # Moderate for controlled creativity in revision
        'chunk_revision': 0.3, # Lower for chunk consistency
        'retry': 0.5,         # Slightly higher for variation in retry attempts
        'validation': 0.2     # Low for factual validation
    })
    
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
# Data Models
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
# Story Element Extraction
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
            response = self.api_client.complete(
                prompt, 
                model_complexity='medium',
                max_tokens=self.config.max_tokens['analysis'],
                temperature=self.config.temperatures['analysis']
            )
            
            # Parse the structured text response instead of JSON
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
                    logger.debug("Skipping empty line")
                    continue

                # Detect section headers using regex
                is_header = False
                if re.match(r'PLOT POINTS:?', line, re.IGNORECASE):
                    current_section = 'plot'
                    logger.debug(f"Switched to section: {current_section}")
                    is_header = True
                elif re.match(r'CHARACTER ACTIONS:?', line, re.IGNORECASE):
                    current_section = 'character'
                    logger.debug(f"Switched to section: {current_section}")
                    is_header = True
                elif re.match(r'KEY DIALOGUES:?', line, re.IGNORECASE):
                    current_section = 'dialogue'
                    logger.debug(f"Switched to section: {current_section}")
                    is_header = True
                elif re.match(r'SETTING:?', line, re.IGNORECASE):
                    current_section = 'setting'
                    logger.debug(f"Switched to section: {current_section}")
                    is_header = True
                elif re.match(r'TIMELINE:?', line, re.IGNORECASE):
                    current_section = 'timeline'
                    logger.debug(f"Switched to section: {current_section}")
                    is_header = True

                if is_header:
                    continue

                # Process content based on current section
                content = None
                if current_section == 'plot':
                    # Capture any non-empty line that isn't a header
                    cleaned_line = list_marker_pattern.sub('', line).strip()
                    if cleaned_line:
                        plot_points.append(cleaned_line)
                        content = cleaned_line

                elif current_section == 'character':
                    # Character actions are expected to have a colon
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            char_name = list_marker_pattern.sub('', parts[0]).strip()
                            action = parts[1].strip()
                            if char_name and action:
                                if char_name not in character_actions:
                                    character_actions[char_name] = []
                                character_actions[char_name].append(action)
                                content = f"{char_name}: {action}"
                    else:
                        logger.debug(f"Skipping character action line (no colon): {line}")


                elif current_section == 'dialogue':
                    cleaned_line = list_marker_pattern.sub('', line).strip()
                    if cleaned_line:
                        key_dialogues.append(cleaned_line)
                        content = cleaned_line

                elif current_section == 'setting':
                    # Setting details can be simple lines or key-value pairs
                    cleaned_line = list_marker_pattern.sub('', line).strip()
                    if cleaned_line:
                        setting_details.append(cleaned_line)
                        content = cleaned_line

                elif current_section == 'timeline':
                    cleaned_line = list_marker_pattern.sub('', line).strip()
                    if cleaned_line:
                        timeline_markers.append(cleaned_line)
                        content = cleaned_line

                if content:
                    logger.debug(f"Captured for {current_section}: {content}")
                elif not is_header: # Avoid double logging for headers
                    logger.debug(f"Skipping line (no current section match or empty content): {line}")

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
# Enhanced Chapter Analysis
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
            
            analysis = self.api_client.complete(
                prompt, 
                model_complexity='medium',
                max_tokens=self.config.max_tokens['analysis'],
                temperature=self.config.temperatures['analysis']
            )
            
            # Validate the analysis is complete
            analysis = self._ensure_complete_analysis(analysis, chapter.number)
            
            return analysis, story_elements
            
        except Exception as e:
            logger.error(f"Failed to analyze chapter {chapter.number}: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception args: {e.args}")
            
            # Try to identify if this is the slice error
            if "slice" in str(e):
                logger.error("This appears to be the slice error - attempting workaround")
                # Return minimal valid response
                return "Analysis failed due to technical error. Chapter should be revised carefully.", StoryElements()
            
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
        
        # Ensure we have chapter content
        if not chapter.content or len(chapter.content.strip()) < 100:
            logger.error(f"Chapter {chapter.number} appears to have no or minimal content")
            logger.error(f"Chapter content length: {len(chapter.content) if chapter.content else 0}")
            logger.error(f"First 200 chars: {chapter.content[:200] if chapter.content else 'EMPTY'}")
        
        # Summarize core elements safely
        plot_points_list = story_elements.plot_points[:5] if story_elements.plot_points else []
        plot_summary = '\n'.join(f"- {p}" for p in plot_points_list) if plot_points_list else "- No plot points extracted yet"
        
        # Safely truncate context elements
        synopsis_preview = context.synopsis[:500] + "..." if len(context.synopsis) > 500 else context.synopsis
        characters_preview = context.characters[:800] + "..." if len(context.characters) > 800 else context.characters
        
        # Log what we're sending
        logger.debug(f"Building analysis prompt for chapter {chapter.number}")
        logger.debug(f"Chapter word count: {chapter.word_count}")
        logger.debug(f"Chapter content preview: {chapter.content[:100]}...")
        
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
# Story-Preserving Revision Planning
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
            plan_content = self.api_client.complete(
                prompt,
                model_complexity='medium',
                max_tokens=self.config.max_tokens['planning'],
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
# Story-Preserving Chapter Revision
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
        
        # Extract specific changes from the plan
        specific_changes = self._extract_specific_changes(plan)
        target_words = getattr(plan, 'target_word_count', chapter.word_count)
        
        logger.info(f"Revising chapter {chapter.number} with {len(specific_changes)} specific changes")
        logger.info(f"Target: {target_words} words (from {chapter.word_count})")
        
        try:
            # Apply the plan changes directly
            revised_content = self._apply_plan_changes(
                chapter, 
                plan, 
                specific_changes,
                target_words
            )
            
            # Ensure chapter heading
            if not revised_content.strip().lower().startswith(('chapter', '# chapter')):
                revised_content = f"# Chapter {chapter.number}\n\n{revised_content}"
            
            # Clean any AI commentary
            cleaned_content = self._clean_ai_commentary(revised_content)
            revised_word_count = len(cleaned_content.split())

            # Initial validation of chapter structure
            if not self._is_valid_chapter_revision(cleaned_content, chapter):
                logger.warning(f"Initial revision for chapter {chapter.number} (word count {revised_word_count}) is structurally invalid. Attempting strict retry.")
                cleaned_content = self._retry_with_stricter_constraints(chapter, plan)
                revised_word_count = len(cleaned_content.split()) # Update word count

                if not self._is_valid_chapter_revision(cleaned_content, chapter):
                    logger.error(f"Strict retry also failed to produce structurally valid chapter content for chapter {chapter.number}.")
                    return RevisionResult(
                        chapter_number=chapter.number,
                        original_content=chapter.content,
                        revised_content=chapter.content, # Fallback to original
                        original_word_count=chapter.word_count,
                        revised_word_count=chapter.word_count,
                        success=False,
                        validation_passed=False,
                        deviation_score=1.0, # Max deviation
                        error_message="Failed to produce a structurally valid chapter after initial attempt and strict retry."
                    )
                logger.info(f"Content for chapter {chapter.number} is now structurally valid after strict retry (word count {revised_word_count}).")

            # Determine target_words for length check
            current_target_words = plan.target_word_count if plan.target_word_count > 0 else chapter.word_count
            # Define tolerance for word count (e.g., +/- 15% of target_words)
            # This tolerance is for deciding whether to enter the length retry logic.
            # The retry methods themselves might have stricter final tolerances.
            lower_bound_for_retry = current_target_words * 0.85
            upper_bound_for_retry = current_target_words * 1.15

            if not (lower_bound_for_retry <= revised_word_count <= upper_bound_for_retry):
                logger.info(
                    f"Structurally valid revision word count ({revised_word_count}) is outside target range "
                    f"({lower_bound_for_retry:.0f}-{upper_bound_for_retry:.0f} for target {current_target_words}). "
                    f"Initiating length retry process."
                )
                cleaned_content = self._retry_for_length(chapter, plan, current_target_words)
                revised_word_count = len(cleaned_content.split())

                # Final check for structural validity after length retries.
                # _retry_for_length and _final_length_attempt now internally call _retry_with_stricter_constraints if they produce invalid content.
                # So, if content is original, it means all attempts (incl. strict) failed within the retry loop.
                if cleaned_content == chapter.content and not self._is_valid_chapter_revision(cleaned_content, chapter): # check if it resorted to original AND original is invalid (edge case)
                     # This means even the original content might be an issue if it's being returned by failed retries.
                     # However, _is_valid_chapter_revision should handle original content correctly.
                     # More likely, if it's chapter.content, it means strict_retry failed from a deeper call.
                    logger.error(f"Length retry process for chapter {chapter.number} resulted in returning original content due to persistent invalid structure.")
                    return RevisionResult(
                        chapter_number=chapter.number,
                        original_content=chapter.content,
                        revised_content=chapter.content,
                        original_word_count=chapter.word_count,
                        revised_word_count=chapter.word_count,
                        success=False,
                        validation_passed=False,
                        deviation_score=1.0,
                        error_message="Failed to produce structurally valid content during length retry."
                    )
                elif not self._is_valid_chapter_revision(cleaned_content, chapter): # Check if a non-original but invalid content came back
                    logger.error(f"Content from length retry process for chapter {chapter.number} is structurally invalid.")
                    return RevisionResult(
                        chapter_number=chapter.number,
                        original_content=chapter.content,
                        revised_content=cleaned_content, # Show the problematic content
                        original_word_count=chapter.word_count,
                        revised_word_count=revised_word_count,
                        success=False,
                        validation_passed=False,
                        deviation_score=1.0,
                        error_message="Content became structurally invalid after length retry attempts."
                    )
                logger.info(f"Word count after length retry process for chapter {chapter.number}: {revised_word_count}")
            
            # Validate the revision preserved story elements (using content that is now structurally valid and length-adjusted)
            validation_passed, deviation_score = self._validate_revision(
                chapter.content, cleaned_content, plan.story_elements
            )
            
            # Final check on word count against a stricter tolerance for success reporting, if desired.
            # For now, success is true if we have structurally valid content that passed story validation.
            # The reported revised_word_count will show the final length.

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
    
    def _extract_specific_changes(self, plan: RevisionPlan) -> Dict[str, List[str]]:
        """Extract specific changes from the revision plan."""
        changes = {
            'prose_improvements': [],
            'sensory_enhancements': [],
            'dialogue_refinements': [],
            'character_depth': []
        }
        
        # Parse the plan to extract specific changes
        plan_text = plan.plan_content
        
        # Extract prose improvements
        if '## PROSE IMPROVEMENTS' in plan_text:
            prose_section = plan_text.split('## PROSE IMPROVEMENTS')[1].split('##')[0]
            # Look for "Original:" and "Improvement needed:" patterns
            improvements = re.findall(r'\*\*Original:\*\* "(.*?)"\s*\n\s*\*\*Improvement needed:\*\* (.*?)(?=\n|$)', prose_section, re.DOTALL)
            changes['prose_improvements'] = improvements[:5]  # Limit to prevent overload
        
        # Extract sensory enhancements
        if '## SENSORY ENHANCEMENTS' in plan_text:
            sensory_section = plan_text.split('## SENSORY ENHANCEMENTS')[1].split('##')[0]
            enhancements = re.findall(r'\*\*Location:\*\* (.*?)\n\s*\*\*Enhancement:\*\* (.*?)(?=\n|$)', sensory_section)
            changes['sensory_enhancements'] = enhancements[:3]
        
        # Extract dialogue refinements  
        if '## DIALOGUE REFINEMENTS' in plan_text:
            dialogue_section = plan_text.split('## DIALOGUE REFINEMENTS')[1].split('##')[0]
            refinements = re.findall(r'\*\*Original:\*\* "(.*?)"\s*\n\s*\*\*Refinement:\*\* (.*?)(?=\n|$)', dialogue_section)
            changes['dialogue_refinements'] = refinements[:3]
        
        logger.info(f"Extracted {sum(len(v) for v in changes.values())} specific changes from plan")
        return changes
    
    def _apply_plan_changes(self, chapter: Chapter, plan: RevisionPlan, 
                           specific_changes: Dict[str, List[str]], 
                           target_words: int) -> str:
        """Apply specific changes from the plan to the chapter."""

        # --- 1. CORE STORY ELEMENTS TO PRESERVE ---
        preserve_section = "CORE STORY ELEMENTS TO PRESERVE UNCHANGED:\n"
        if plan.story_elements.plot_points:
            preserve_section += "Plot Points:\n" + "\n".join(f"- {p}" for p in plan.story_elements.plot_points[:5]) + "\n\n" # Max 5
        if plan.story_elements.character_actions:
            preserve_section += "Key Character Actions (who did what):\n"
            for char, actions in list(plan.story_elements.character_actions.items())[:3]: # Max 3 characters
                preserve_section += f"- {char}:\n" + "\n".join(f"  - {a}" for a in actions[:2]) + "\n" # Max 2 actions
            preserve_section += "\n"
        if plan.story_elements.key_dialogues:
            preserve_section += "Key Dialogues (essential meaning and speaker must be preserved):\n" + "\n".join(f'- "{d}"' for d in plan.story_elements.key_dialogues[:3]) + "\n\n" # Max 3

        # --- 2. SPECIFIC CHANGES TO MAKE ---
        changes_section = "SPECIFIC CHANGES TO MAKE (as detailed in the revision plan):\n"
        if specific_changes.get('prose_improvements'):
            changes_section += "Prose Improvements:\n"
            for i, (original, improvement) in enumerate(specific_changes['prose_improvements'][:3], 1): # Max 3 examples
                changes_section += f"{i}. Find text similar to: \"{original[:100]}...\"\n   Improve by applying: {improvement}\n\n"
        if specific_changes.get('sensory_enhancements'):
            changes_section += "Sensory Additions:\n"
            for i, (location, enhancement) in enumerate(specific_changes['sensory_enhancements'][:2], 1): # Max 2 examples
                changes_section += f"{i}. At location: {location}\n   Add sensory details like: {enhancement}\n\n"
        if specific_changes.get('dialogue_refinements'):
            changes_section += "Dialogue Improvements (refine delivery, not meaning):\n"
            for i, (original, refinement) in enumerate(specific_changes['dialogue_refinements'][:2], 1): # Max 2 examples
                changes_section += f"{i}. For dialogue like: \"{original}\"\n   Refine to something like: {refinement}\n\n"
        if not specific_changes.get('prose_improvements') and not specific_changes.get('sensory_enhancements') and not specific_changes.get('dialogue_refinements'):
            changes_section += "General prose quality enhancements focusing on vividness, clarity, and flow, as per overall plan.\n\n"

        # --- 3. STYLE AND LENGTH GUIDANCE ---
        style_length_section = "STYLE AND LENGTH REQUIREMENTS:\n"
        if hasattr(plan, 'inspirations') and plan.inspirations:
            style_length_section += f"Adopt a style inspired by: {plan.inspirations}.\n"
        else:
            style_length_section += "Maintain a clear, engaging, and consistent narrative style.\n"
        
        style_length_section += f"Target word count: Approximately {target_words} words. "
        if target_words < chapter.word_count:
            style_length_section += f"(Current: {chapter.word_count}. This requires tightening prose by about {chapter.word_count - target_words} words.)\n"
        elif target_words > chapter.word_count:
            style_length_section += f"(Current: {chapter.word_count}. This requires expanding descriptions and details by about {target_words - chapter.word_count} words.)\n"
        else:
            style_length_section += f"(Current: {chapter.word_count}. Maintain current length.)\n"

        # --- 4. SMOOTH INTEGRATION AND SELF-CORRECTION ---
        integration_correction_section = """
INSTRUCTIONS FOR REVISION:
1.  Carefully review all sections above: 'CORE STORY ELEMENTS TO PRESERVE', 'SPECIFIC CHANGES TO MAKE', and 'STYLE AND LENGTH REQUIREMENTS'.
2.  Your primary goal is to improve the prose quality while strictly adhering to all preservation constraints.
3.  Integrate the 'SPECIFIC CHANGES TO MAKE' seamlessly into the narrative. Ensure changes flow naturally with the surrounding text and maintain a consistent tone and style. Do not make these changes sound like inserted instructions.
4.  Do NOT alter any other aspects of the story not mentioned in 'SPECIFIC CHANGES TO MAKE'.

SELF-CORRECTION CHECK:
After drafting the revision, please mentally review your changes against the 'CORE STORY ELEMENTS TO PRESERVE' and the 'SPECIFIC CHANGES TO MAKE'. Ensure all planned changes are implemented correctly and no core story elements have been unintentionally altered. Only output the final, corrected chapter text. Your response should contain ONLY the revised chapter.
"""

        # --- ASSEMBLE THE FULL PROMPT ---
        prompt = f"""You are an expert manuscript editor. Your task is to revise the following chapter based on a detailed plan.

{preserve_section}
{changes_section}
{style_length_section}
{integration_correction_section}

ORIGINAL CHAPTER (Word Count: {chapter.word_count}):
===BEGIN ORIGINAL CHAPTER===
{chapter.content}
===END ORIGINAL CHAPTER===

REVISED CHAPTER (Target Word Count: {target_words}):
[Your revised chapter text starts here. Ensure it is a complete chapter from beginning to end, incorporating all instructions.]
"""
        
        logger.debug(f"Generated revision prompt for chapter {chapter.number}:\n{prompt[:500]}...") # Log prompt preview

        # Use appropriate model based on length
        estimated_tokens = int(target_words * 1.3)
        if estimated_tokens > 25000:
            model_complexity = 'extended'
            max_tokens = min(estimated_tokens + 5000, 60000)
        else:
            model_complexity = 'complex'
            max_tokens = 30000
        
        response = self.api_client.complete(
            prompt,
            model_complexity=model_complexity,
            max_tokens=max_tokens,
            temperature=self.config.temperatures['revision']
        )
        
        return response
    
    def _split_chapter_into_chunks(self, content: str, chunk_size: int = 500) -> List[str]:
        """Split chapter into chunks at natural breaking points."""
        # First try to split by scene breaks (*** or * * *)
        if '***' in content or '* * *' in content:
            scenes = re.split(r'\*\s*\*\s*\*', content)
            return [s.strip() for s in scenes if s.strip()]
        
        # Otherwise split by paragraphs
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
    
    def _revise_chunk(self, chunk: str, chunk_number: int, total_chunks: int,
                      plan: RevisionPlan, target_expansion: float) -> str:
        """Revise a single chunk with focused instructions."""
        
        # Extract key style points from plan
        inspirations = ""
        if hasattr(plan, 'inspirations') and plan.inspirations:
            inspirations = "Style: Le Carré's atmosphere, Greene's emotional depth, journalistic clarity."
        
        prompt = f"""Improve this text's prose quality while keeping all events and dialogue exactly the same.

{inspirations}

Make these improvements:
1. Replace weak verbs with stronger ones
2. Add sensory details (sounds, smells, textures)
3. Deepen emotional reactions
4. Smooth any awkward phrasing
5. {"Expand descriptions to be more vivid" if target_expansion > 1.0 else "Maintain current length"}

Original text:
{chunk}

Revised text with improved prose:"""

        try:
            response = self.api_client.complete(
                prompt,
                model_complexity='medium',  # Use medium for chunks
                max_tokens=int(len(chunk.split()) * 2 * 1.3),  # Allow for expansion
                temperature=0.4
            )
            
            # Clean the response
            revised = response.strip()
            
            # Remove any meta-commentary
            if revised.lower().startswith(('here is', 'here\'s', 'the revised', 'revised text')):
                lines = revised.split('\n')
                revised = '\n'.join(lines[1:]).strip()
            
            return revised
            
        except Exception as e:
            logger.error(f"Failed to revise chunk {chunk_number}: {e}")
            return chunk  # Return original on failure
    
    def _expand_revised_content(self, content: str, target_words: int, 
                               plan: RevisionPlan) -> str:
        """Expand the revised content to reach target word count."""
        current_words = len(content.split())
        expansion_needed = target_words - current_words
        
        if expansion_needed <= 0:
            return content
        
        logger.info(f"Expanding by {expansion_needed} words to reach {target_words}")
        
        prompt = f"""This revised chapter needs {expansion_needed} more words to reach {target_words} words total.

Add more sensory details, emotional depth, and atmospheric description throughout.
Do not add new plot events or change what happens.

Current text ({current_words} words):
{content}

Expanded version ({target_words} words):"""

        try:
            response = self.api_client.complete(
                prompt,
                model_complexity='complex',
                max_tokens=int(target_words * 1.5),
                temperature=0.4
            )
            
            return self._clean_ai_commentary(response)
            
        except Exception as e:
            logger.error(f"Expansion failed: {e}")
            return content
    
    def _extract_length_directives(self, plan: RevisionPlan, expansion_needed_factor: float) -> str:
        """Helper to extract length adjustment directives from the plan."""
        directives = []
        if expansion_needed_factor > 1.0: # Expanding
            directives.append("Focus on elaborating descriptions, deepening character thoughts, and adding sensory details.")
            if "SENSORY ENHANCEMENTS" in plan.plan_content:
                directives.append("Review the plan's 'SENSORY ENHANCEMENTS' section for specific ideas on where to add vivid details.")
            if "CHARACTER DEPTH ENHANCEMENTS" in plan.plan_content:
                directives.append("Consider the 'CHARACTER DEPTH ENHANCEMENTS' for moments to expand on internal monologue or emotional reactions.")
            if "LENGTH EXPANSION STRATEGY" in plan.plan_content:
                 # Try to find specific points in the expansion strategy
                strategy_match = re.search(r"## LENGTH EXPANSION STRATEGY\n(.*?)(?=\n##|$)", plan.plan_content, re.DOTALL | re.IGNORECASE)
                if strategy_match:
                    points = [line.strip('-* ').capitalize() for line in strategy_match.group(1).splitlines() if line.strip() and len(line.strip()) > 10]
                    if points:
                        directives.append("Recall the plan's expansion strategy, such as: '" + "', '".join(points[:2]) + "'.") # Max 2 specific points
        elif expansion_needed_factor < 1.0: # Condensing
            directives.append("Focus on tightening prose, removing redundancies, and ensuring every word contributes.")
            if "TIGHTEN PROSE" in plan.plan_content: # Assuming plan might have such a section if condensing
                directives.append("Review the plan for any notes on conciseness or sections to shorten.")

        if plan.revision_focus:
            focus_relevant = [f for f in plan.revision_focus if "pacing" in f.lower() or "description" in f.lower() or "detail" in f.lower()]
            if focus_relevant:
                directives.append(f"The plan also highlighted focusing on: {', '.join(focus_relevant[:2])}.")

        return "\n- ".join(directives) if directives else "Elaborate on descriptions, character thoughts, and sensory details throughout the chapter."


    def _retry_for_length(self, chapter: Chapter, plan: RevisionPlan, 
                         target_words: int) -> str:
        """Retry revision with explicit focus on achieving target length."""
        
        logger.info(f"Retrying chapter {chapter.number} for proper length, using plan directives.")
        
        # Calculate how much expansion is needed
        expansion_needed_factor = target_words / chapter.word_count if chapter.word_count > 0 else 2.0 # Avoid division by zero
        estimated_tokens = int(target_words * 1.3)
        
        plan_directives = self._extract_length_directives(plan, expansion_needed_factor)

        # Choose model based on expected output
        if estimated_tokens > 32000:
            model_complexity = 'extended'  # Sonnet 4
            max_tokens = min(estimated_tokens + 5000, 60000) # Ensure it does not exceed model's hard limit
            model_note = "Using Claude Sonnet 4 with extended output capacity."
        else:
            model_complexity = 'complex'  # Opus 4
            max_tokens = 30000
            model_note = "Using Claude Opus 4."
        
        prompt = f"""Your previous revision was significantly off the target word count. You MUST produce approximately {target_words} words.

{model_note}

CRITICAL LENGTH REQUIREMENT:
- Original chapter: {chapter.word_count} words.
- Your revision MUST be approximately {target_words} words.
- This requires an approximate {expansion_needed_factor:.1f}x adjustment in length.

DETAILED STRATEGY TO REACH {target_words} WORDS (incorporating the revision plan):
- Include ALL content and story events from the original chapter. Do not omit anything.
- To adjust length, apply the following based on the original revision plan:
  - {plan_directives}
- If expanding: Add rich sensory details to every scene, expand emotional reactions and internal thoughts, enhance descriptions of settings and atmosphere, develop the prose style without changing events, add narrative beats and transitions, and deepen character observations.
- If condensing: Focus on conciseness, remove redundant words or phrases, and ensure each sentence is impactful.
- Enrich the prose with literary techniques suitable for the genre.

SELF-CORRECTION CHECK: Before finalizing, double-check that your revised chapter is indeed close to {target_words} words and that all original story events are preserved.

ORIGINAL CHAPTER ({chapter.word_count} words):
{chapter.content}

Output the COMPLETE revised chapter of approximately {target_words} words. Start with "Chapter {chapter.number}":"""
        
        try:
            revised = self.api_client.complete(
                prompt,
                model_complexity=model_complexity,
                max_tokens=max_tokens,
                temperature=self.config.temperatures['retry']
            )
            
            cleaned = self._clean_ai_commentary(revised)
            actual_words = len(cleaned.split()) # Calculate words before validity check

            if not self._is_valid_chapter_revision(cleaned, chapter):
                logger.warning(f"Content from _retry_for_length is invalid for chapter {chapter.number}. Attempting strict retry.")
                cleaned = self._retry_with_stricter_constraints(chapter, plan)
                actual_words = len(cleaned.split()) # Recalculate word count
                # If strict retry still returns original content, it might fail length check again, leading to final_length_attempt
                # which will also validate and call strict_retry if needed. This is acceptable.
                if not self._is_valid_chapter_revision(cleaned, chapter): # Check again after strict_retry
                     logger.error(f"Content remains invalid after strict_retry from _retry_for_length for chapter {chapter.number}.")
                     return chapter.content # Give up on this path, return original

            # Length check for _retry_for_length's own output (potentially after strict_retry)
            if not (target_words * 0.75 <= actual_words <= target_words * 1.25):
                logger.info(f"Content (word count {actual_words}) from plan-based length retry is still off target ({target_words}). Proceeding to final length attempt.")
                return self._final_length_attempt(chapter, plan, target_words)
            
            logger.info(f"Plan-based length retry successful: {actual_words} words (Target: {target_words}). Content appears valid.")
            return cleaned
            
        except Exception as e: # Includes APIError from refusal check in self.api_client.complete
            logger.error(f"Length retry API call failed or content refused: {e}")
            # Attempt strict retry if API call itself failed or content was refused
            logger.warning(f"Attempting strict constraint retry for chapter {chapter.number} due to error in length retry.")
            return self._retry_with_stricter_constraints(chapter, plan)
    
    def _final_length_attempt(self, chapter: Chapter, plan: RevisionPlan, target_words: int) -> str:
        """Final attempt to achieve target length with maximum clarity and plan directives."""
        
        logger.info(f"Final length attempt for chapter {chapter.number}, using plan directives.")
        
        expansion_needed_factor = target_words / chapter.word_count if chapter.word_count > 0 else 2.0
        plan_directives = self._extract_length_directives(plan, expansion_needed_factor)

        # Always use Sonnet 4 for final attempt to ensure we have enough tokens
        estimated_tokens = int(target_words * 1.5)  # Extra buffer
        
        prompt = f"""ABSOLUTE FINAL ATTEMPT: You MUST produce {target_words} words. Previous attempts have failed to meet this critical requirement.

Using Claude Sonnet 4 with extended output capacity. You have sufficient tokens.

MANDATORY OUTPUT LENGTH: Exactly {target_words} words (tolerance: ±5%). This is not a suggestion.

STRATEGY FOR ACHIEVING {target_words} WORDS (incorporating the revision plan):
1.  Start with the original {chapter.word_count} words of content.
2.  Preserve ALL original plot points, character actions, and dialogue meanings.
3.  Systematically adjust length based on the original revision plan:
    - {plan_directives}
4.  If expanding: For EVERY paragraph and scene, consciously add descriptive details (sights, sounds, smells, textures, tastes), deepen character thoughts and internal reactions, expand on atmospheric elements, and elaborate on physical sensations. Do this consistently.
5.  If condensing: For EVERY paragraph, critically evaluate for redundant words, phrases, or sentences. Rephrase for maximum conciseness without losing meaning.
6.  Ensure smooth narrative transitions if adding content.
7.  Do a final word count check yourself before outputting.

ORIGINAL TEXT TO REVISE FOR LENGTH:
{chapter.content}

BEGIN YOUR {target_words} WORD REVISION NOW WITH "Chapter {chapter.number}"."""
        
        try:
            revised = self.api_client.complete(
                prompt,
                model_complexity='extended',  # Always use Sonnet 4
                max_tokens=min(estimated_tokens, 60000), # Ensure it does not exceed model's hard limit
                temperature=self.config.temperatures['retry']
            )
            cleaned_response = self._clean_ai_commentary(revised)

            if not self._is_valid_chapter_revision(cleaned_response, chapter):
                logger.error(f"Content from _final_length_attempt is still invalid for chapter {chapter.number}. Attempting strict retry as last resort.")
                # This is the absolute last attempt for valid structure.
                return self._retry_with_stricter_constraints(chapter, plan)

            logger.info(f"Content from _final_length_attempt for chapter {chapter.number} appears structurally valid.")
            return cleaned_response
        except Exception as e: # Includes APIError from refusal check in self.api_client.complete
            logger.error(f"Final length attempt API call failed or content refused: {e}")
            # Attempt strict retry even on API error during final length attempt, as it might be a model refusal or format issue.
            logger.warning(f"Attempting strict constraint retry for chapter {chapter.number} due to error in final length attempt.")
            return self._retry_with_stricter_constraints(chapter, plan)
    
    def _is_valid_chapter_revision(self, content: str, original_chapter: Chapter) -> bool:
        """Check if the returned content is a valid chapter revision."""
        # Log what we're validating
        logger.debug(f"Validating revision - Length: {len(content.split())} words")
        logger.debug(f"First 100 chars: {content[:100]}...")
        
        # Check if it's clearly not a chapter
        error_indicators = [
            "i apologize",
            "i'm sorry", 
            "appears to be an analysis",
            "need to see the actual",
            "could you please share",
            "this seems to be a technical document"
        ]
        
        content_lower = content.lower()
        for indicator in error_indicators:
            if indicator in content_lower:
                logger.warning(f"Found error indicator: '{indicator}'")
                return False
        
        # Check if it starts like a chapter
        chapter_starts = [
            f"chapter {original_chapter.number}",
            f"# chapter {original_chapter.number}",
            "# prologue",
            "prologue"
        ]
        
        for start in chapter_starts:
            if content_lower.strip().startswith(start):
                logger.debug("Content starts with valid chapter heading")
                return True
        
        # Check if it has reasonable length
        word_count = len(content.split())
        if word_count < original_chapter.word_count * 0.5:
            logger.warning(f"Content too short: {word_count} words vs original {original_chapter.word_count}")
            return False
        
        # If we get here, it might be missing chapter heading but otherwise valid
        logger.warning("Content doesn't start with chapter heading, marking as invalid")
        return False
    
    def _build_preservation_revision_prompt(self, chapter: Chapter, 
                                          plan: RevisionPlan) -> str:
        """Build revision prompt with strict preservation constraints."""
        
        # Validate we have actual chapter content
        if not chapter.content or len(chapter.content.strip()) < 100:
            logger.error(f"Chapter {chapter.number} has insufficient content for revision")
            raise ValidationError(f"Chapter {chapter.number} content is missing or too short")
        
        target_words = getattr(plan, 'target_word_count', chapter.word_count)
        
        # Extract key changes from plan
        plan_text = plan.plan_content
        
        # Find specific prose improvements
        prose_changes = []
        if '**Original:**' in plan_text:
            # Extract the first 3 specific changes
            matches = re.findall(r'\*\*Original:\*\* "(.*?)"\s*\n\s*\*\*Improvement needed:\*\* (.*?)(?=\n\n|\*\*)', plan_text, re.DOTALL)
            prose_changes = [(orig.strip(), imp.strip()) for orig, imp in matches[:3]]
        
        # Build example section
        examples = ""
        if prose_changes:
            examples = "\nEXAMPLES OF REQUIRED CHANGES:\n"
            for i, (original, improvement) in enumerate(prose_changes, 1):
                examples += f"\n{i}. FIND: \"{original[:80]}...\"\n   IMPROVE BY: {improvement}\n"
        
        # Simple, direct prompt
        return f"""Revise Chapter {chapter.number} to improve prose quality. Make it exactly {target_words} words.

REQUIREMENTS:
1. Keep ALL events, actions, and dialogue meanings unchanged
2. Improve prose style: stronger verbs, better descriptions, smoother flow
3. Add sensory details (sounds, smells, textures) to existing scenes
4. Write in the style of le Carré and Greene - atmospheric and emotionally complex
{examples}

ORIGINAL ({chapter.word_count} words):
{chapter.content}

REVISED ({target_words} words):"""
    
    def _truncate_text(self, text: str, max_words: int) -> str:
        """Helper to truncate text to a maximum number of words."""
        words = text.split()
        if len(words) > max_words:
            return " ".join(words[:max_words]) + "..."
        return text

    def _validate_revision(self, original: str, revised: str, 
                          story_elements: StoryElements) -> Tuple[bool, float]:
        """Validate that core story elements are preserved using an AI call."""
        
        logger.info("Validating revision using AI...")

        # Prepare content for the prompt, truncating if necessary
        original_summary = self._truncate_text(original, 500) # Approx 500 words for summary
        revised_excerpt = self._truncate_text(revised, 1000) # More of the revised text

        plot_points_str = "\n".join(f"- {p}" for p in story_elements.plot_points[:10]) # Max 10 plot points
        
        character_actions_str = ""
        for char, actions in list(story_elements.character_actions.items())[:5]: # Max 5 characters
            character_actions_str += f"\n{char}:\n"
            for action in actions[:3]: # Max 3 actions per character
                character_actions_str += f"  - {action}\n"

        key_dialogues_str = "\n".join(f'- "{d}"' for d in story_elements.key_dialogues[:5]) # Max 5 dialogues

        prompt = f"""Please analyze the revised chapter content based on the original story elements and a summary of the original chapter. My goal was to revise the chapter for prose quality ONLY, without changing any core story elements.

STORY ELEMENTS TO PRESERVE:
Plot Points:
{plot_points_str}

Character Actions (Who did what):
{character_actions_str}

Key Dialogues (Essential meaning to be preserved):
{key_dialogues_str}

ORIGINAL CHAPTER SUMMARY:
{original_summary}

REVISED CHAPTER EXCERPT (analyze this entire excerpt):
{revised_excerpt}

ANALYSIS TASK:
1.  Compare the "REVISED CHAPTER EXCERPT" against the "ORIGINAL CHAPTER SUMMARY" and the "STORY ELEMENTS TO PRESERVE".
2.  Identify and list any plot points that have been significantly altered or removed in the revised version.
3.  Identify and list any character actions (who did what) that have been changed or new significant actions introduced for key characters.
4.  Identify and list any key dialogues whose essential meaning has been changed.
5.  List any new plot elements or significant character actions/motivations introduced in the revised text that were not in the original story elements.
6.  Provide an overall assessment: "Overall Assessment: [Your assessment of story preservation - e.g., Well preserved, Minor changes, Significant deviations]."
7.  Suggest a deviation score on a scale of 0.0 (perfect preservation, no unintended changes to plot/character/dialogue meaning) to 1.0 (major deviations). Format: "Deviation Score: [score]"

Focus ONLY on factual changes to the story (plot, character actions, dialogue meaning). Do NOT comment on prose style or quality. Be concise. If no significant deviations are found, state that clearly.
"""
        try:
            response_text = self.api_client.complete(
                prompt,
                model_complexity='medium', # 'simple' might be too weak, 'medium' for better nuance
                max_tokens=self.config.max_tokens.get('validation', 1000), # Use validation specific token limit
                temperature=self.config.temperatures['validation']
            )
            logger.debug(f"AI Validation Response:\n{response_text}")

            deviation_score = 1.0  # Default to max deviation if parsing fails
            validation_passed = False
            identified_changes = []

            # Parse deviation score
            score_match = re.search(r"Deviation Score:\s*([0-9.]+)", response_text, re.IGNORECASE)
            if score_match:
                deviation_score = float(score_match.group(1))
            else:
                logger.warning("Could not parse deviation score from AI response.")

            # Parse overall assessment
            assessment_match = re.search(r"Overall Assessment:\s*(.*)", response_text, re.IGNORECASE)
            assessment_text = assessment_match.group(1).strip() if assessment_match else "No assessment found."
            logger.info(f"AI Overall Assessment: {assessment_text}")

            # Simplistic check for identified changes (look for list items or keywords indicating issues)
            # A more robust parsing would be to look for the lists requested in points 2, 3, 4, 5.
            lines = response_text.splitlines()
            capturing_changes = False
            for line in lines:
                if any(header.lower() in line.lower() for header in ["plot points that have been significantly altered",
                                                                    "character actions that have been changed",
                                                                    "key dialogues whose essential meaning has been changed",
                                                                    "new plot elements or significant character actions"]):
                    capturing_changes = True
                    identified_changes.append(line) # Add the header itself
                    continue
                if capturing_changes and line.strip().startswith(("-", "*", "1.", "2.")): # common list markers
                    identified_changes.append(line.strip())
                elif capturing_changes and not line.strip(): # stop capturing after an empty line
                    capturing_changes = False


            if deviation_score < 0.2 and not identified_changes: # Stricter if no changes explicitly listed
                validation_passed = True
            elif deviation_score < 0.25 and "well preserved" in assessment_text.lower() : # Looser if AI says it's fine
                 validation_passed = True
            elif "minor changes" in assessment_text.lower() and deviation_score < 0.3: # Allow minor if score is low
                validation_passed = True # Could be False depending on strictness desired
                logger.warning(f"AI reported minor changes. Manual review recommended. Score: {deviation_score}")
            else: # Covers "significant deviations" or high scores
                validation_passed = False
                logger.warning(f"AI validation failed or reported significant deviations. Score: {deviation_score}")

            if identified_changes:
                logger.info("AI identified the following potential deviations:")
                for change in identified_changes:
                    logger.info(f"  - {change}")
            elif "no significant deviations" in response_text.lower() or "no deviations found" in response_text.lower() or "well preserved" in assessment_text.lower() :
                 logger.info("AI reported no significant deviations.")


        except APIError as e:
            logger.error(f"API error during AI validation: {e}")
            # Fallback to a high deviation score, indicating failure
            return False, 1.0
        except Exception as e:
            logger.error(f"Error parsing AI validation response: {e}")
            # Fallback to a high deviation score
            return False, 1.0

        logger.info(f"AI Validation Result - Passed: {validation_passed}, Deviation Score: {deviation_score:.2f}")
        return validation_passed, deviation_score

    def _retry_with_stricter_constraints(self, chapter: Chapter, plan: RevisionPlan) -> str:
        """Retry revision with even stricter constraints, aiming for valid chapter structure."""
        
        logger.info(f"Retrying chapter {chapter.number} with stricter constraints to ensure valid chapter format.")
        
        target_words = getattr(plan, 'target_word_count', chapter.word_count)
        
        # Extract one specific change from the plan as an example
        example_change = ""
        if '**Original:**' in plan.plan_content:
            match = re.search(r'\*\*Original:\*\* "(.*?)"\s*\n\s*\*\*Improvement needed:\*\* (.*?)(?=\n)', plan.plan_content)
            if match:
                original_text = match.group(1).strip()[:100]
                improvement = match.group(2).strip()
                example_change = f'\n\nFor example, change phrases like "{original_text}" by {improvement}\n'
        
        prompt = f"""Revise Chapter {chapter.number} to be exactly {target_words} words with better prose.

CRITICAL RULES:
1. Do NOT change any plot events or character actions
2. Do NOT alter what anyone says (dialogue meaning must stay identical)
3. Do NOT add new scenes or remove existing ones
4. Do NOT change the sequence of events
{example_change}
ALLOWED IMPROVEMENTS:
- Replace weak verbs (walked → strode, said → murmured)
- Add sensory details to existing moments (sounds, smells, textures)
- Deepen emotions with physical reactions (not new actions)
- Smooth awkward transitions between existing scenes
- Improve sentence flow and variety

ORIGINAL TEXT:
{chapter.content}

OUTPUT THE REVISED CHAPTER NOW:"""
        
        try:
            # Determine model based on length
            estimated_tokens = int(target_words * 1.3)
            if estimated_tokens > 25000:
                model_complexity = 'extended'
                max_tokens = min(estimated_tokens + 5000, 60000)
            else:
                model_complexity = 'complex'
                max_tokens = 30000
            
            response = self.api_client.complete(
                prompt,
                model_complexity=model_complexity,
                max_tokens=max_tokens,
                temperature=0.5  # Moderate temperature for balance
            )
            
            cleaned_response = self._clean_ai_commentary(response)

            if not self._is_valid_chapter_revision(cleaned_response, chapter):
                logger.error(f"Content from _retry_with_stricter_constraints is still invalid for chapter {chapter.number}.")
                return chapter.content # Ultimate fallback to original content
            
            logger.info(f"Successfully produced valid-looking content for chapter {chapter.number} with strict retry.")
            return cleaned_response
            
        except Exception as e:
            logger.error(f"Strict retry API call failed: {e}") # Clarified log
            return chapter.content # Fallback to original content
    
    def _clean_ai_commentary(self, text: str) -> str:
        """Remove AI commentary from text."""
        # Remove common AI preambles
        preambles = [
            "Here's the revised chapter", "Here is the revised chapter",
            "I'll revise", "I will revise", "Let me revise",
        ]
        
        for preamble in preambles:
            if text.lower().startswith(preamble.lower()):
                # Find the actual chapter start
                chapter_start = re.search(r'(Chapter \d+|# Chapter|# Prologue)', text, re.IGNORECASE)
                if chapter_start:
                    text = text[chapter_start.start():]
                    break
        
        # Clean extra whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text).strip()
        
        return text

# ============================================================================
# Updated File Operations and API Client (same as original)
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
        return sorted(set(files))

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
        
        # Switch to Sonnet 4 if we need more than 32k tokens
        if max_tokens > 32000:
            logger.info(f"Requested {max_tokens} tokens, switching to Claude Sonnet 4")
            model = self.config.models['extended']  # Use Sonnet 4
            # Sonnet 4 can handle more tokens, but let's be safe
            max_tokens = min(max_tokens, 60000)
        
        # Log token usage
        prompt_tokens = len(prompt.split()) * 1.3  # Rough estimate
        logger.info(f"API call - Model: {model}, Max tokens: {max_tokens}, Est. prompt tokens: {int(prompt_tokens)}")
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Extract text from response - being very careful here
                if response and hasattr(response, 'content'):
                    raw_result = ""
                    if isinstance(response.content, list) and len(response.content) > 0:
                        first_content = response.content[0]
                        if hasattr(first_content, 'text'):
                            raw_result = str(first_content.text)
                        else:
                            raw_result = str(first_content) # Should ideally not happen with messages API
                    elif isinstance(response.content, str): # Should ideally not happen with messages API
                        raw_result = response.content
                    else:
                        logger.error(f"Unexpected response content type: {type(response.content)}")
                        raw_result = str(response.content) # Fallback

                    # Check for AI refusal patterns in the response content
                    # Ensure raw_result is not None and is a string before lowercasing
                    if raw_result is not None and isinstance(raw_result, str):
                        result_lower = raw_result.lower()
                        refusal_patterns = [
                            "i cannot fulfill this request",
                            "i am unable to",
                            "i'm sorry, but i cannot",
                            "my apologies, but i am unable",
                            "as a large language model, i cannot", # More specific to avoid false positives
                            "as an ai assistant, i am unable",
                            "i do not have the capability",
                            "error processing request", # Generic error
                            "failed to generate a response", # Generic error
                            "unable to provide an answer",
                            "i cannot provide a response",
                            "my instructions prevent me from"
                        ]
                        for pattern in refusal_patterns:
                            if pattern in result_lower:
                                error_message = f"AI responded with a refusal or error: '{raw_result[:150]}...'"
                                logger.error(error_message)
                                raise APIError(error_message)

                        logger.info(f"Response received: {len(raw_result.split())} words")
                        return raw_result
                    else: # raw_result is None or not a string
                        error_message = f"Received unexpected or null content from AI: {raw_result}"
                        logger.error(error_message)
                        raise APIError(error_message)
                else: # response object itself is problematic
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
                raise APIError(f"API call failed: {e}") 
            except Exception as e:
                logger.error(f"API error: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                raise APIError(f"API call failed: {e}")

# ============================================================================
# Project Management (simplified from original)
# ============================================================================

class ProjectLoader:
    """Loads and manages project data."""
    
    def __init__(self, file_handler: FileHandler, config: Config):
        self.file_handler = file_handler
        self.config = config
    
    def load_project(self, project_dir: Path) -> Tuple[Dict[int, Chapter], ProjectContext]:
        """Load all project data."""
        project_dir = Path(project_dir)
        if not project_dir.exists():
            raise ValidationError(f"Project directory not found: {project_dir}")
        
        # Load context files
        context = self._load_project_context(project_dir)
        
        # Load chapters
        chapters = self._load_chapters(project_dir)
        
        return chapters, context
    
    def _load_project_context(self, project_dir: Path) -> ProjectContext:
        """Load project context files."""
        context = ProjectContext()
        
        # Load synopsis
        for name in ['synopsis.md', 'synopsis.txt']:
            file_path = project_dir / name
            if file_path.exists():
                context.synopsis = self.file_handler.read_file(file_path)
                logger.info(f"Loaded synopsis from {name}")
                break
        
        # Load outline
        for name in ['outline.md', 'outline.txt', 'Outline.md']:
            file_path = project_dir / name
            if file_path.exists():
                context.outline = self.file_handler.read_file(file_path)
                logger.info(f"Loaded outline from {name}")
                break
        
        # Load characters
        for name in ['characters.md', 'characterList.md', 'characters.txt']:
            file_path = project_dir / name
            if file_path.exists():
                context.characters = self.file_handler.read_file(file_path)
                logger.info(f"Loaded characters from {name}")
                break
        
        # Load inspirations
        for name in ['inspirations.md', 'inspiration.md', 'literary_inspirations.md']:
            file_path = project_dir / name
            if file_path.exists():
                context.inspirations = self.file_handler.read_file(file_path)
                logger.info(f"Loaded inspirations from {name}")
                break
        
        # Load story bible if exists
        story_bible_file = project_dir / 'story_bible.md'
        if story_bible_file.exists():
            context.story_bible = self.file_handler.read_file(story_bible_file)
            logger.info("Loaded story bible")
        
        return context
        if story_bible_file.exists():
            context.story_bible = self.file_handler.read_file(story_bible_file)
            logger.info("Loaded story bible")
        
        return context
    
    def _load_chapters(self, project_dir: Path) -> Dict[int, Chapter]:
        """Load all chapter files."""
        chapters = {}
        
        logger.info(f"Searching for chapters in: {project_dir}")
        
        for chapter_dir in self.config.chapter_dirs:
            search_dir = project_dir / chapter_dir
            if not search_dir.exists():
                logger.debug(f"Directory doesn't exist: {search_dir}")
                continue
            
            logger.info(f"Searching in directory: {search_dir}")
            files = self.file_handler.find_files(search_dir, self.config.chapter_patterns)
            logger.info(f"Found {len(files)} potential chapter files")
            
            for file_path in files:
                # Skip revised/backup files
                if any(skip in str(file_path).lower() for skip in ['enhanced', 'backup', 'revised']):
                    logger.debug(f"Skipping file (backup/revised): {file_path}")
                    continue
                
                chapter_num = self._extract_chapter_number(file_path)
                if chapter_num is not None:
                    try:
                        content = self.file_handler.read_file(file_path)
                        if content:
                            word_count = len(content.split())
                            chapters[chapter_num] = Chapter(
                                number=chapter_num,
                                file_path=file_path,
                                content=content,
                                word_count=word_count
                            )
                            logger.info(f"Loaded chapter {chapter_num} from {file_path} ({word_count} words)")
                            logger.debug(f"Chapter {chapter_num} preview: {content[:100]}...")
                        else:
                            logger.warning(f"Empty content in file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to load {file_path}: {e}")
                else:
                    logger.debug(f"Could not extract chapter number from: {file_path}")
        
        logger.info(f"Total chapters loaded: {len(chapters)}")
        logger.info(f"Chapter numbers: {sorted(chapters.keys())}")
        
        return chapters
    
    def _extract_chapter_number(self, file_path: Path) -> Optional[int]:
        """Extract chapter number from filename."""
        filename = file_path.name
        
        # Handle prologue specially
        if 'prologue' in filename.lower():
            return 0
        
        patterns = [
            r'(\d+)_chapter_\d+',
            r'chapter[_\s]*(\d+)',
            r'ch[_\s]*(\d+)',
            r'^(\d+)[_\s]*',
            r'(\d+)\.md$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None

# ============================================================================
# Report Generation
# ============================================================================

class ValidationReportGenerator:
    """Generates reports with validation information."""
    
    def __init__(self, file_handler: FileHandler):
        self.file_handler = file_handler
    
    def generate_report(self, project_dir: Path, context: ProjectContext,
                       all_chapters: Dict[int, Chapter],
                       results: List[RevisionResult]) -> str:
        """Generate comprehensive revision report with validation info."""
        
        # Calculate statistics
        total_original = sum(r.original_word_count for r in results)
        total_revised = sum(r.revised_word_count for r in results)
        successful = [r for r in results if r.success]
        validated = [r for r in results if r.validation_passed]
        
        # Build chapter details
        chapter_details = []
        for result in sorted(results, key=lambda r: r.chapter_number):
            if result.success:
                status = "✓ Validated" if result.validation_passed else "⚠ Needs Review"
                chapter_details.append(
                    f"- Chapter {result.chapter_number}: "
                    f"{result.original_word_count:,} → {result.revised_word_count:,} words "
                    f"({status}, deviation: {result.deviation_score:.2f})"
                )
            else:
                chapter_details.append(
                    f"- Chapter {result.chapter_number}: ✗ FAILED - {result.error_message}"
                )
        
        report = f"""# Story-Preserving Chapter Revision Report

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Project:** {context.title}
**Genre:** {context.genre}
**Revision Mode:** Story-Preserving Prose Enhancement

## Summary

Revised {len(results)} chapters with story preservation constraints.

**Success Rate:**
- Chapters Processed: {len(results)}
- Successfully Revised: {len(successful)}
- Validation Passed: {len(validated)}

**Word Count Analysis:**
- Total Original: {total_original:,} words
- Total Revised: {total_revised:,} words
- Average Change: {(total_revised/total_original - 1)*100:.1f}%

**Chapter Details:**
{chr(10).join(chapter_details)}

## Revision Approach

This revision focused on improving prose quality while strictly preserving:
- All plot points and story events
- Character actions and decisions
- Dialogue content and meaning
- Timeline and scene structure
- Existing character relationships

## Validation Results

Each chapter was validated to ensure story elements remained unchanged:
- Chapters with deviation score < 0.1: Excellent preservation
- Chapters with deviation score 0.1-0.3: Good preservation, minor review recommended
- Chapters with deviation score > 0.3: Requires manual review

## Files Created

- Story element extracts: story_elements/chapter_X_elements.json
- Preservation plans: revision_plans/chapter_X_preservation_plan.md
- Revised chapters: revised/chapter_X_revised.md
- This report: story_preserving_revision_report.md

## Recommended Next Steps

1. Review chapters marked "Needs Review" for any unintended changes
2. Compare key scenes between original and revised versions
3. Verify character voice consistency across revised chapters
4. Check that all plot points remain intact

## Quality Assurance Checklist

For each revised chapter, verify:
- [ ] All plot events occur in the same order
- [ ] Character actions remain unchanged
- [ ] Dialogue conveys the same information
- [ ] No new characters or scenes added
- [ ] Timeline and setting details preserved
- [ ] Only prose quality improved

---
*This report was generated by the Story-Preserving Chapter Reviser*
"""
        
        # Save report
        report_path = project_dir / 'story_preserving_revision_report.md'
        self.file_handler.write_file(report_path, report)
        logger.info(f"Report saved to {report_path}")
        
        return report

# ============================================================================
# Main Application Controller
# ============================================================================

class StoryPreservingRevisionController:
    """Main controller for story-preserving chapter revision."""
    
    def __init__(self, config: Config):
        self.config = config
        self.file_handler = FileHandler(config)
        self.api_client = AnthropicClient(config)
        self.project_loader = ProjectLoader(self.file_handler, config)
        self.element_extractor = StoryElementExtractor(self.api_client, config)
        self.analyzer = StoryPreservingAnalyzer(
            self.api_client, config, self.element_extractor
        )
        self.planner = PreservationRevisionPlanner(self.api_client, config)
        self.reviser = PreservingChapterReviser(self.api_client, config)
        self.report_generator = ValidationReportGenerator(self.file_handler)
    
    def run(self, project_dir: str, target_chapters: List[int],
            skip_validation: bool = False,
            analysis_only: bool = False,
            use_existing_analysis: bool = False,
            word_length: Optional[int] = None,
            expansion_factor: float = 1.0,
            context_map: Optional[Dict[int, List[int]]] = None) -> None:
        """Run the story-preserving revision process."""
        project_path = Path(project_dir)
        
        # Load project
        logger.info(f"Loading project from {project_path}")
        all_chapters, project_context = self.project_loader.load_project(project_path)
        
        # Validate target chapters
        valid_targets = {num: all_chapters[num] for num in target_chapters 
                        if num in all_chapters}
        if not valid_targets:
            raise ValidationError(f"No valid chapters found from: {target_chapters}")
        
        # Log chapter details
        for num, chapter in valid_targets.items():
            logger.info(f"Chapter {num}: {chapter.file_path.name} ({chapter.word_count} words)")
            if chapter.word_count == 0:
                logger.error(f"Chapter {num} has no content!")
            elif chapter.word_count < 100:
                logger.warning(f"Chapter {num} seems very short: {chapter.word_count} words")
        
        logger.info(f"Processing chapters with story preservation: {sorted(valid_targets.keys())}")
        
        # Set up context map if not provided
        if context_map is None:
            context_map = self._generate_default_context_map(
                target_chapters, all_chapters
            )
        elif 'default' in context_map:
            # Handle the case where a single context chapter was specified
            default_contexts = context_map['default']
            context_map = {
                chapter_num: default_contexts
                for chapter_num in target_chapters
            }
        
        # Create directories
        elements_dir = project_path / 'story_elements'
        elements_dir.mkdir(exist_ok=True)
        plans_dir = project_path / 'revision_plans'
        plans_dir.mkdir(exist_ok=True)
        revised_dir = project_path / 'revised'
        revised_dir.mkdir(exist_ok=True)
        
        results = []
        
        for chapter_num, chapter in valid_targets.items():
            logger.info(f"Processing chapter {chapter_num}")
            
            try:
                # Step 1: Extract story elements and analyze
                analysis_file = project_path / f'chapter_{chapter_num}_analysis.md'
                elements_file = elements_dir / f'chapter_{chapter_num}_elements.json'
                
                if use_existing_analysis and analysis_file.exists() and elements_file.exists():
                    logger.info(f"Using existing analysis for chapter {chapter_num}")
                    analysis = self.file_handler.read_file(analysis_file)
                    # Load existing story elements
                    elements_data = json.loads(self.file_handler.read_file(elements_file))
                    story_elements = StoryElements(
                        plot_points=elements_data.get('plot_points', []),
                        character_actions=elements_data.get('character_actions', {}),
                        key_dialogues=elements_data.get('key_dialogues', []),
                        setting_details=elements_data.get('setting_details', []),
                        timeline_markers=elements_data.get('timeline_markers', [])
                    )
                else:
                    logger.info(f"Extracting story elements for chapter {chapter_num}")
                    analysis, story_elements = self.analyzer.analyze_for_revision(
                        chapter, all_chapters, project_context
                    )
                    
                    # Save analysis
                    self._save_analysis(analysis_file, chapter_num, analysis)
                    
                    # Save story elements
                    elements_data = {
                        'plot_points': story_elements.plot_points,
                        'character_actions': story_elements.character_actions,
                        'key_dialogues': story_elements.key_dialogues,
                        'setting_details': story_elements.setting_details,
                        'timeline_markers': story_elements.timeline_markers
                    }
                    self.file_handler.write_file(
                        elements_file, 
                        json.dumps(elements_data, indent=2)
                    )
                
                if analysis_only:
                    continue
                
                # Step 2: Create preservation plan
                plan_file = plans_dir / f'chapter_{chapter_num:02d}_preservation_plan.md'
                
                if use_existing_analysis and plan_file.exists():
                    logger.info(f"Using existing plan for chapter {chapter_num}")
                    plan_content = self.file_handler.read_file(plan_file)
                    # Reconstruct plan object
                    plan = RevisionPlan(
                        chapter_number=chapter_num,
                        analysis=analysis,
                        plan_content=plan_content,
                        story_elements=story_elements,
                        revision_focus=[],  # Would need to parse from file
                        prohibited_changes=[]  # Would need to parse from file
                    )
                else:
                    logger.info(f"Creating preservation plan for chapter {chapter_num}")
                    
                    # Calculate target word count
                    if word_length:
                        target_word_count = word_length
                    elif expansion_factor != 1.0:
                        target_word_count = int(chapter.word_count * expansion_factor)
                    else:
                        target_word_count = chapter.word_count
                    
                    logger.info(f"Target word count for chapter {chapter_num}: {target_word_count}")
                    
                    plan = self.planner.create_preservation_plan(
                        chapter, analysis, story_elements, project_context,
                        target_word_count=target_word_count
                    )
                    
                    # Save plan
                    self._save_plan(plan_file, plan)
                
                # Step 3: Revise with preservation
                logger.info(f"Revising chapter {chapter_num} with story preservation")
                
                # Get context chapters based on map
                context_chapters = {
                    num: all_chapters[num] 
                    for num in context_map.get(chapter_num, [])
                    if num in all_chapters
                }
                
                result = self.reviser.revise_with_preservation(
                    chapter, plan, context_chapters
                )
                results.append(result)
                
                # Save revised chapter
                if result.success:
                    revised_file = revised_dir / f'{chapter.file_path.stem}_revised.md'
                    self.file_handler.write_file(revised_file, result.revised_content)
                    
                    validation_status = "validated" if result.validation_passed else "needs review"
                    logger.info(
                        f"Chapter {chapter_num}: "
                        f"{result.original_word_count} → {result.revised_word_count} words "
                        f"({validation_status}, deviation: {result.deviation_score:.2f})"
                    )
                else:
                    logger.error(f"Failed to revise chapter {chapter_num}: {result.error_message}")
                    
            except Exception as e:
                logger.error(f"Error processing chapter {chapter_num}: {e}")
                results.append(RevisionResult(
                    chapter_number=chapter_num,
                    original_content=chapter.content,
                    revised_content=chapter.content,
                    original_word_count=chapter.word_count,
                    revised_word_count=chapter.word_count,
                    success=False,
                    error_message=str(e)
                ))
        
        # Generate report
        if not analysis_only:
            logger.info("Generating validation report")
            self.report_generator.generate_report(
                project_path, project_context, all_chapters, results
            )
        
        logger.info("Story-preserving revision complete!")
    
    def _generate_default_context_map(self, target_chapters: List[int],
                                    all_chapters: Dict[int, Chapter]) -> Dict[int, List[int]]:
        """Generate default context map with adjacent chapters only."""
        context_map = {}
        for chapter_num in target_chapters:
            context_chapters = []
            # Only immediate neighbors for tighter focus
            for offset in [-1, 1]:
                neighbor = chapter_num + offset
                if neighbor in all_chapters:
                    context_chapters.append(neighbor)
            context_map[chapter_num] = context_chapters
        return context_map
    
    def _save_analysis(self, file_path: Path, chapter_num: int, analysis: str) -> None:
        """Save analysis to file."""
        content = f"""# Chapter {chapter_num} Story-Preserving Analysis

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Analysis Type:** Prose Improvement with Story Preservation

---

{analysis}
"""
        self.file_handler.write_file(file_path, content)
    
    def _save_plan(self, file_path: Path, plan: RevisionPlan) -> None:
        """Save revision plan to file."""
        prohibited = '\n'.join(f"- {p}" for p in plan.prohibited_changes[:20])
        focus = '\n'.join(f"- {f}" for f in plan.revision_focus)
        
        content = f"""# STORY-PRESERVING REVISION PLAN FOR CHAPTER {plan.chapter_number}

**Generated:** {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}
**Revision Type:** Prose Enhancement with Story Preservation

## ELEMENTS THAT MUST NOT CHANGE

{prohibited}

## REVISION FOCUS AREAS

{focus}

## DETAILED PLAN

{plan.plan_content}

---
*This plan focuses on improving prose quality while preserving all story elements*
"""
        self.file_handler.write_file(file_path, content)

# ============================================================================
# Exceptions (from original)
# ============================================================================

class ChapterReviserError(Exception):
    """Base exception for chapter reviser."""
    pass

class FileOperationError(ChapterReviserError):
    """Raised when file operations fail."""
    pass

class APIError(ChapterReviserError):
    """Raised when API calls fail."""
    pass

class ValidationError(ChapterReviserError):
    """Raised when validation fails."""
    pass

# ============================================================================
# CLI Interface
# ============================================================================

def parse_chapter_spec(spec: str) -> List[int]:
    """Parse chapter specification string."""
    chapters = []
    
    # Handle special case for prologue
    spec = spec.replace('prologue', '0').replace('Prologue', '0')
    
    if '-' in spec:
        # Range: "5-10"
        parts = spec.split('-')
        if len(parts) == 2:
            try:
                start, end = int(parts[0]), int(parts[1])
                chapters = list(range(start, end + 1))
            except ValueError:
                raise ValidationError(f"Invalid range: {spec}")
    elif ',' in spec:
        # List: "1,3,5,7"
        try:
            chapters = [int(x.strip()) for x in spec.split(',')]
        except ValueError:
            raise ValidationError(f"Invalid list: {spec}")
    else:
        # Single: "5"
        try:
            chapters = [int(spec)]
        except ValueError:
            raise ValidationError(f"Invalid chapter number: {spec}")
    
    return chapters

def parse_context_map(spec: str) -> Dict[int, List[int]]:
    """Parse context map specification."""
    context_map = {}
    
    # Handle simple case of just a number (applies to all chapters)
    if spec.isdigit():
        # This means use this chapter as context for all
        # We'll handle this in the controller
        return {'default': [int(spec)]}
    
    # Format: "10:0,5;15:0,10"
    for mapping in spec.split(';'):
        if ':' in mapping:
            try:
                target, contexts = mapping.split(':')
                target_num = int(target.strip())
                context_nums = [int(c.strip()) for c in contexts.split(',') if c.strip()]
                context_map[target_num] = context_nums
            except ValueError:
                raise ValidationError(f"Invalid context mapping: {mapping}")
    
    return context_map

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Story-Preserving Chapter Revision Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This tool revises chapters while strictly preserving:
- All plot points and events
- Character actions and decisions  
- Dialogue content and meaning
- Timeline and scene structure

It focuses on improving:
- Prose quality and elegance
- Sensory details and atmosphere
- Emotional depth and nuance
- Pacing and flow
- Dialogue delivery (not content)

Examples:
  # Revise single chapter
  %(prog)s mynovel --chapters 5
  
  # Revise multiple chapters  
  %(prog)s mynovel --chapters 3,5,7,9
  
  # Revise chapter range
  %(prog)s mynovel --chapters 10-15
  
  # Analysis only (no revision)
  %(prog)s mynovel --chapters 5 --analysis-only
  
  # Use existing analysis files
  %(prog)s mynovel --chapters 5 --use-existing-analysis
  
  # Specify target word count
  %(prog)s mynovel --chapters 5 --word-length 5000
  
  # Skip validation checks
  %(prog)s mynovel --chapters 5 --skip-validation
  
  # Use specific context chapters
  %(prog)s mynovel --chapters 10 --context-chapters "10:0,5"
"""
    )
    
    parser.add_argument(
        'project_dir',
        help='Project directory containing the novel'
    )
    parser.add_argument(
        '--chapters',
        required=True,
        help='Chapters to revise (e.g., "5" or "3,5,7" or "10-15" or "prologue")'
    )
    parser.add_argument(
        '--analysis-only',
        action='store_true',
        help='Only analyze chapters, don\'t create revision plans or revise'
    )
    parser.add_argument(
        '--use-existing-analysis',
        action='store_true',
        help='Use existing analysis and plan files if available'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip story preservation validation'
    )
    parser.add_argument(
        '--word-length',
        type=int,
        help='Target word count for revised chapters'
    )
    parser.add_argument(
        '--expansion-factor',
        type=float,
        default=1.0,
        help='Word count multiplier if no word length specified (default: 1.0 = no change)'
    )
    parser.add_argument(
        '--context-chapters',
        help='Context chapters for each target (e.g., "10:0,5;15:0,10")'
    )
    parser.add_argument(
        '--context-map',
        help='JSON file with context chapter mappings'
    )
    parser.add_argument(
        '--cost-optimize',
        action='store_true',
        help='Use less expensive models (may reduce quality)'
    )
    parser.add_argument(
        '--constraints',
        help='JSON file with custom revision constraints'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Parse chapters
        target_chapters = parse_chapter_spec(args.chapters)
        logger.info(f"Target chapters: {target_chapters}")
        
        # Parse context map
        context_map = None
        if args.context_map:
            # Load from file
            with open(args.context_map, 'r') as f:
                raw_map = json.load(f)
            context_map = {int(k): v for k, v in raw_map.items()}
        elif args.context_chapters:
            # Parse from command line
            context_map = parse_context_map(args.context_chapters)
        
        # Create config
        config = Config()
        
        # Note: cost-optimize flag is ignored since we're using Opus 4 for all operations
        if args.cost_optimize:
            logger.info("Note: cost-optimize flag ignored - using Claude Opus 4 for all operations")
        
        # Load custom constraints if provided
        if args.constraints:
            with open(args.constraints, 'r') as f:
                constraints_data = json.load(f)
            config.revision_constraints = RevisionConstraints(**constraints_data)
        
        # Create controller and run
        controller = StoryPreservingRevisionController(config)
        controller.run(
            args.project_dir,
            target_chapters,
            skip_validation=args.skip_validation,
            analysis_only=args.analysis_only,
            use_existing_analysis=args.use_existing_analysis,
            word_length=args.word_length,
            expansion_factor=args.expansion_factor,
            context_map=context_map
        )
        
    except ChapterReviserError as e:
        logger.error(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())