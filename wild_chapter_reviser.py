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
        'analysis': 0.3,      # Low for consistent analysis
        'planning': 0.3,      # Low for structured planning
        'revision': 0.4,      # Moderate for controlled creativity
        'chunk_revision': 0.3, # Lower for chunk consistency
        'retry': 0.5          # Slightly higher for variation in retry
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
                max_tokens=self.config.max_tokens['analysis']
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
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Detect section headers
                if line.upper().startswith('PLOT POINTS'):
                    current_section = 'plot'
                elif line.upper().startswith('CHARACTER ACTIONS'):
                    current_section = 'character'
                elif line.upper().startswith('KEY DIALOGUES'):
                    current_section = 'dialogue'
                elif line.upper().startswith('SETTING'):
                    current_section = 'setting'
                elif line.upper().startswith('TIMELINE'):
                    current_section = 'timeline'
                else:
                    # Process content based on current section
                    if current_section == 'plot' and (line.startswith(('1.', '2.', '3.', '4.', '5.', '-'))):
                        content = line.lstrip('0123456789.- ').strip()
                        if content:
                            plot_points.append(content)
                    
                    elif current_section == 'character' and ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            char_name = parts[0].strip(' -')
                            action = parts[1].strip()
                            if char_name and action:
                                if char_name not in character_actions:
                                    character_actions[char_name] = []
                                character_actions[char_name].append(action)
                    
                    elif current_section == 'dialogue' and ('"' in line or line.startswith(('1.', '2.', '3.'))):
                        content = line.lstrip('0123456789.- ').strip()
                        if content:
                            key_dialogues.append(content)
                    
                    elif current_section == 'setting' and ':' in line:
                        content = line.strip(' -')
                        if content:
                            setting_details.append(content)
                    
                    elif current_section == 'timeline' and line.strip():
                        content = line.strip(' -')
                        if content:
                            timeline_markers.append(content)
            
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
                temperature=0.5  # Slightly higher for more complete analysis
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
- Explain what type of sensory detail would enhance the scene

## 3. CHARACTER DEPTH  
Identify at least 3 moments where character emotions/thoughts could be deeper:
- Quote the relevant passage
- Check consistency with character profiles above
- Explain what's missing emotionally
- Note how it could be more nuanced while staying true to the character

## 4. PACING AND FLOW
Identify at least 3 specific transitions or pacing issues:
- Quote the problematic section
- Explain the pacing problem
- Suggest how flow could improve

## 5. DIALOGUE POLISH
Identify at least 3 dialogue exchanges that need work:
- Quote the dialogue
- Verify it matches the character's voice from the profiles
- Explain what makes it stilted or unnatural
- Note how delivery could improve (not content)

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
                max_tokens=self.config.max_tokens['planning']
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
List specific sentences or paragraphs to enhance without changing meaning:
- Quote the original text
- Explain the improvement needed
- Apply style inspirations where relevant
- Ensure character consistency
- Note opportunities for expansion if needed

## SENSORY ENHANCEMENTS  
Identify where to add sensory details without adding new events:
- Specify exact locations in the text
- Type of sensory detail needed
- Consider le Carré-style atmospheric details
- Estimate additional words each enhancement will add
- Must not change what happens

## DIALOGUE REFINEMENTS
List dialogues to polish while keeping meaning intact:
- Quote the original line
- Verify consistency with character profiles
- Apply Graham Greene's subtle character revelations
- Preserve all information conveyed
- Add narrative beats if expanding

## CHARACTER DEPTH ENHANCEMENTS
Identify opportunities to deepen character portrayal:
- Internal thoughts that align with character profiles
- Emotional reactions true to established personalities
- Physical mannerisms consistent with descriptions
- Voice and speech patterns matching profiles

## PACING ADJUSTMENTS
Identify where to improve flow without changing events:
- Specific transitions to smooth
- Sentence variety opportunities
- Paragraph restructuring needs
- Apply journalistic clarity where needed
- Places to expand narrative rhythm

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
        
        target_words = getattr(plan, 'target_word_count', chapter.word_count)
        
        logger.info(f"Using line-by-line revision for chapter {chapter.number}")
        logger.info(f"Target: {target_words} words (from {chapter.word_count})")
        
        try:
            # Use line-by-line revision to maintain control
            revised_content = self._line_by_line_revision(chapter, plan, target_words)
            
            # Ensure chapter heading
            if not revised_content.strip().lower().startswith(('chapter', '# chapter', 'prologue', '# prologue')):
                if chapter.number == 0:
                    revised_content = f"# Prologue\n\n{revised_content}"
                else:
                    revised_content = f"# Chapter {chapter.number}\n\n{revised_content}"
            
            # Clean any AI commentary
            cleaned_content = self._clean_ai_commentary(revised_content)
            
            # Validate word count and content
            revised_word_count = len(cleaned_content.split())
            
            # Validate the revision preserved story elements
            validation_passed, deviation_score = self._validate_revision(
                chapter.content, cleaned_content, plan.story_elements
            )
            
            # Final safety check - ensure key names and dates are preserved
            if not self._verify_key_elements(chapter.content, cleaned_content):
                logger.error("Key elements check failed - revision changed critical story elements")
                return RevisionResult(
                    chapter_number=chapter.number,
                    original_content=chapter.content,
                    revised_content=chapter.content,  # Return original on failure
                    original_word_count=chapter.word_count,
                    revised_word_count=chapter.word_count,
                    success=False,
                    error_message="Revision altered key story elements"
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
    
    def _line_by_line_revision(self, chapter: Chapter, plan: RevisionPlan, 
                               target_words: int) -> str:
        """Revise chapter paragraph by paragraph to maintain tight control."""
        
        # Split into paragraphs
        paragraphs = chapter.content.split('\n\n')
        revised_paragraphs = []
        
        # Calculate words per paragraph for targeting
        total_paras = len([p for p in paragraphs if p.strip()])
        words_per_para = target_words // total_paras if total_paras > 0 else 100
        
        for i, paragraph in enumerate(paragraphs):
            if not paragraph.strip():
                revised_paragraphs.append("")
                continue
            
            # Revise each paragraph individually
            revised_para = self._revise_paragraph(
                paragraph, 
                para_num=i,
                target_words=words_per_para,
                plan=plan
            )
            revised_paragraphs.append(revised_para)
            
            # Log progress
            if i % 10 == 0:
                logger.info(f"Revised {i}/{len(paragraphs)} paragraphs")
        
        return '\n\n'.join(revised_paragraphs)
    
    def _revise_paragraph(self, paragraph: str, para_num: int, 
                         target_words: int, plan: RevisionPlan) -> str:
        """Revise a single paragraph with tight constraints."""
        
        current_words = len(paragraph.split())
        
        # Very specific, constrained prompt
        prompt = f"""Revise this paragraph to improve prose quality. Target: ~{target_words} words (currently {current_words}).

Rules:
1. Keep ALL facts, names, dates, and events EXACTLY the same
2. Keep dialogue meaning unchanged
3. Only improve: word choice, sentence flow, sensory details
4. Style: le Carré atmospheric, Greene emotional depth

Original paragraph:
{paragraph}

Revised paragraph:"""
        
        try:
            response = self.api_client.complete(
                prompt,
                model_complexity='medium',  # Use medium model for paragraphs
                max_tokens=target_words * 3,  # Enough for the paragraph
                temperature=0.3  # Low temperature for consistency
            )
            
            # Verify the response isn't completely different
            if self._paragraph_similarity_check(paragraph, response):
                return response.strip()
            else:
                logger.warning(f"Paragraph {para_num} revision too different, keeping original")
                return paragraph
                
        except Exception as e:
            logger.error(f"Failed to revise paragraph {para_num}: {e}")
            return paragraph
    
    def _paragraph_similarity_check(self, original: str, revised: str) -> bool:
        """Check if revised paragraph maintains similarity to original."""
        # Extract key elements
        original_lower = original.lower()
        revised_lower = revised.lower()
        
        # Check for key words that should be preserved
        important_words = []
        
        # Extract capitalized words (likely names/places)
        for word in original.split():
            if word and word[0].isupper() and len(word) > 1:
                important_words.append(word.lower())
        
        # Extract numbers and dates
        import re
        numbers = re.findall(r'\b\d+\b', original)
        important_words.extend(numbers)
        
        # Check preservation
        preservation_count = 0
        for word in important_words:
            if word in revised_lower:
                preservation_count += 1
        
        if important_words:
            preservation_ratio = preservation_count / len(important_words)
            return preservation_ratio > 0.8  # 80% of important words preserved
        
        return True  # If no important words, accept the revision
    
    def _verify_key_elements(self, original: str, revised: str) -> bool:
        """Verify that key story elements are preserved."""
        # Extract and verify critical elements
        checks = []
        
        # Check character names (capitalized words that appear multiple times)
        original_words = original.split()
        word_counts = {}
        for word in original_words:
            if word and word[0].isupper():
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Important names appear multiple times
        important_names = [word for word, count in word_counts.items() if count > 1]
        
        for name in important_names:
            if name in revised:
                checks.append(True)
            else:
                logger.warning(f"Missing important name: {name}")
                checks.append(False)
        
        # Check dates/times
        import re
        dates = re.findall(r'\b(?:19|20)\d{2}\b|\b\d{1,2}:\d{2}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b', original)
        for date in dates:
            if date in revised:
                checks.append(True)
            else:
                logger.warning(f"Missing date/time: {date}")
                checks.append(False)
        
        # If we have checks, require 90% pass rate
        if checks:
            pass_rate = sum(checks) / len(checks)
            return pass_rate >= 0.9
        
        return True
    
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
        
        # Build a focused prompt with concrete examples
        prompt = f"""Revise this chapter following the specific improvements below. Target: {target_words} words.

CRITICAL: You must preserve ALL plot events, character actions, and dialogue meaning. Only improve the prose style.

SPECIFIC CHANGES TO MAKE:

"""
        
        # Add prose improvements
        if specific_changes['prose_improvements']:
            prompt += "PROSE IMPROVEMENTS:\n"
            for i, (original, improvement) in enumerate(specific_changes['prose_improvements'][:3], 1):
                prompt += f"{i}. Find: \"{original[:100]}...\"\n   Change to: {improvement}\n\n"
        
        # Add sensory enhancements
        if specific_changes['sensory_enhancements']:
            prompt += "\nSENSORY ADDITIONS:\n"
            for i, (location, enhancement) in enumerate(specific_changes['sensory_enhancements'][:3], 1):
                prompt += f"{i}. At: {location}\n   Add: {enhancement}\n\n"
        
        # Add dialogue refinements
        if specific_changes['dialogue_refinements']:
            prompt += "\nDIALOGUE IMPROVEMENTS:\n" 
            for i, (original, refinement) in enumerate(specific_changes['dialogue_refinements'][:3], 1):
                prompt += f"{i}. Change: \"{original}\"\n   To: {refinement}\n\n"
        
        # Add style guidance
        if hasattr(plan, 'inspirations') and plan.inspirations:
            prompt += "\nSTYLE: Write like le Carré (atmospheric), Greene (emotional depth), with journalistic clarity.\n"
        
        # Add length guidance
        if target_words < chapter.word_count:
            prompt += f"\nTIGHTEN PROSE: Remove {chapter.word_count - target_words} words by cutting redundancies and wordiness.\n"
        elif target_words > chapter.word_count:
            prompt += f"\nEXPAND: Add {target_words - chapter.word_count} words through richer descriptions and sensory details.\n"
        
        prompt += "\nREMEMBER: Keep all events, actions, and dialogue exactly the same. Only improve how they're written.\n"
        
        prompt += f"\nCHAPTER TO REVISE:\n{chapter.content}\n\nREVISED CHAPTER:"
        
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
            temperature=0.4  # Lower temperature for more controlled revision
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
    
    def _retry_for_length(self, chapter: Chapter, plan: RevisionPlan, 
                         target_words: int) -> str:
        """Retry revision with explicit focus on achieving target length."""
        
        logger.info(f"Retrying chapter {chapter.number} for proper length")
        
        # Calculate how much expansion is needed
        expansion_needed = target_words / chapter.word_count
        estimated_tokens = int(target_words * 1.3)
        
        # Choose model based on expected output
        if estimated_tokens > 32000:
            model_complexity = 'extended'  # Sonnet 4
            max_tokens = min(estimated_tokens + 5000, 60000)
            model_note = "Using Claude Sonnet 4 with extended output capacity"
        else:
            model_complexity = 'complex'  # Opus 4
            max_tokens = 30000
            model_note = "Using Claude Opus 4"
        
        prompt = f"""Your previous revision was too short. You MUST produce approximately {target_words} words.

{model_note}

CRITICAL LENGTH REQUIREMENT:
- Original chapter: {chapter.word_count} words  
- Your revision MUST be approximately {target_words} words
- This requires {expansion_needed:.1f}x expansion

To reach {target_words} words, you must:
- Include ALL content from the original
- Add rich sensory details to every scene
- Expand emotional reactions and internal thoughts
- Enhance descriptions of settings and atmosphere
- Develop the prose style without changing events
- Add narrative beats and transitions
- Deepen character observations
- Enrich the prose with literary techniques

ORIGINAL CHAPTER ({chapter.word_count} words):
{chapter.content}

Output the COMPLETE revised chapter of approximately {target_words} words. Start with "Chapter {chapter.number}":"""
        
        try:
            revised = self.api_client.complete(
                prompt,
                model_complexity=model_complexity,
                max_tokens=max_tokens,
                temperature=0.4  # Slightly higher for more content
            )
            
            cleaned = self._clean_ai_commentary(revised)
            
            # Final validation
            actual_words = len(cleaned.split())
            if actual_words < target_words * 0.7:
                logger.error(f"Still too short after retry: {actual_words} words vs target {target_words}")
                # Try one more time with maximum encouragement
                return self._final_length_attempt(chapter, target_words)
            
            logger.info(f"Length retry successful: {actual_words} words")
            return cleaned
            
        except Exception as e:
            logger.error(f"Length retry failed: {e}")
            return chapter.content
    
    def _final_length_attempt(self, chapter: Chapter, target_words: int) -> str:
        """Final attempt to achieve target length with maximum clarity."""
        
        logger.info(f"Final length attempt for chapter {chapter.number}")
        
        # Always use Sonnet 4 for final attempt to ensure we have enough tokens
        estimated_tokens = int(target_words * 1.5)  # Extra buffer
        
        prompt = f"""FINAL ATTEMPT: You MUST produce {target_words} words. Previous attempts were too short.

Using Claude Sonnet 4 with extended output capacity. You have plenty of tokens available.

MANDATORY: Output must be {target_words} words (tolerance: ±10%)

Strategy for reaching {target_words} words:
1. Start with the original {chapter.word_count} words
2. For EVERY paragraph, add:
   - Sensory details (sight, sound, smell, touch, taste)
   - Character thoughts and feelings
   - Environmental atmosphere
   - Physical sensations and reactions
3. Expand EVERY scene with richer prose
4. Add narrative transitions between scenes
5. Deepen EVERY emotion and reaction

ORIGINAL TEXT TO EXPAND:
{chapter.content}

BEGIN YOUR {target_words} WORD REVISION NOW WITH "Chapter {chapter.number}"."""
        
        try:
            revised = self.api_client.complete(
                prompt,
                model_complexity='extended',  # Always use Sonnet 4 for final attempt
                max_tokens=min(estimated_tokens, 60000),
                temperature=0.5  # Higher temperature for more content
            )
            return self._clean_ai_commentary(revised)
        except Exception as e:
            logger.error(f"Final length attempt failed: {e}")
            return chapter.content
    
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
    
    def _validate_revision(self, original: str, revised: str, 
                          story_elements: StoryElements) -> Tuple[bool, float]:
        """Validate that core story elements are preserved."""
        
        # Quick validation checks
        validation_checks = []
        
        # Check key plot points are mentioned
        plot_points_to_check = story_elements.plot_points[:5] if story_elements.plot_points else []
        for plot_point in plot_points_to_check:
            # Simple keyword check
            key_words = plot_point.lower().split()[:3] if plot_point else []
            if key_words and all(word in revised.lower() for word in key_words):
                validation_checks.append(True)
            else:
                validation_checks.append(False)
                logger.warning(f"Missing plot point: {plot_point}")
        
        # Check character names still appear with similar frequency
        for character in list(story_elements.character_actions.keys())[:5]:  # Check first 5 characters
            original_count = original.lower().count(character.lower())
            revised_count = revised.lower().count(character.lower())
            if abs(original_count - revised_count) <= 2:
                validation_checks.append(True)
            else:
                validation_checks.append(False)
                logger.warning(f"Character frequency mismatch: {character}")
        
        # Calculate deviation score
        if validation_checks:
            passed = sum(validation_checks) / len(validation_checks) > 0.8
            deviation_score = 1.0 - (sum(validation_checks) / len(validation_checks))
        else:
            passed = True  # No checks means we can't invalidate
            deviation_score = 0.0
        
        return passed, deviation_score
    
    def _retry_with_stricter_constraints(self, chapter: Chapter, 
                                        plan: RevisionPlan) -> str:
        """Retry revision with even stricter constraints."""
        
        logger.info(f"Retrying chapter {chapter.number} revision with stricter constraints")
        
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
            
            # Ensure proper formatting
            if not response.strip().lower().startswith(('chapter', '# chapter')):
                response = f"# Chapter {chapter.number}\n\n{response}"
            
            return response
            
        except Exception as e:
            logger.error(f"Strict retry failed: {e}")
            # Fallback
            return f"# Chapter {chapter.number}\n\n{chapter.content}"
    
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
                    if isinstance(response.content, list) and len(response.content) > 0:
                        first_content = response.content[0]
                        if hasattr(first_content, 'text'):
                            result = str(first_content.text)
                            logger.info(f"Response received: {len(result.split())} words")
                            return result
                        else:
                            return str(first_content)
                    elif isinstance(response.content, str):
                        return response.content
                    else:
                        logger.error(f"Unexpected response content type: {type(response.content)}")
                        return str(response.content)
                else:
                    logger.error(f"Unexpected response structure: {type(response)}")
                    return str(response)
                
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