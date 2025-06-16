#!/usr/bin/env python3
"""
chapter_reviser.py - Professional Chapter Revision Tool

A modular, robust tool for revising novel chapters with AI assistance.
Supports selective chapter revision with context awareness.
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
class Config:
    """Central configuration for the application."""
    # API Settings
    api_key: str = field(default_factory=lambda: os.getenv('ANTHROPIC_API_KEY', ''))
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Model Configuration
    models: Dict[str, str] = field(default_factory=lambda: {
            "simple": "claude-3-5-sonnet-20241022",
            "medium": "claude-opus-4-20250514",
            "complex": "claude-opus-4-20250514",
    })
    
    # Token Limits - Reduced for better stability
    max_tokens: Dict[str, int] = field(default_factory=lambda: {
        'analysis': 3000,
        'planning': 2500,
        'revision': 12000  # Increased from 8000
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
    
    # Expansion Settings
    expansion_factor: float = 1.4
    
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
class ProjectContext:
    """Represents the project context."""
    synopsis: str = ""
    outline: str = ""
    characters: str = ""
    inspirations: str = ""
    title: str = "Novel"
    genre: str = "Literary Fiction"

@dataclass
class RevisionPlan:
    """Represents a revision plan for a chapter."""
    chapter_number: int
    analysis: str
    plan_content: str
    target_word_count: int
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
    error_message: Optional[str] = None

# ============================================================================
# Exceptions
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
# File Operations
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

# ============================================================================
# API Client Wrapper
# ============================================================================

class AnthropicClient:
    """Wrapper for Anthropic API with retry logic and error handling."""
    
    def __init__(self, config: Config):
        self.config = config
        if not config.api_key:
            raise ValidationError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(
            api_key=config.api_key,
            timeout=600.0,  # 10 minute timeout
            max_retries=2   # Built-in retries
        )
    
    def complete(self, prompt: str, model_complexity: str = 'medium', 
                 max_tokens: Optional[int] = None, use_streaming: bool = True) -> str:
        """Make API call with retry logic and streaming support."""
        model = self.config.models.get(model_complexity, self.config.models['medium'])
        if max_tokens is None:
            max_tokens = self.config.max_tokens.get('revision', 8000)
        
        # For very long operations, use streaming
        if use_streaming and max_tokens > 4000:
            return self._complete_streaming(prompt, model, max_tokens)
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=0.5,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Extract text from response
                if hasattr(response.content[0], 'text'):
                    return response.content[0].text
                return str(response.content[0])
                
            except RateLimitError:
                if attempt < self.config.max_retries - 1:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise APIError("Rate limit exceeded after retries")
            except Exception as e:
                if "timeout" in str(e).lower():
                    logger.warning("Request timed out, retrying with streaming...")
                    return self._complete_streaming(prompt, model, max_tokens)
                logger.error(f"API error: {e}")
                raise APIError(f"API call failed: {e}")
    
    def _complete_streaming(self, prompt: str, model: str, max_tokens: int) -> str:
        """Make API call with streaming for long operations."""
        logger.info("Using streaming mode for long operation...")
        try:
            stream = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )
            
            # Collect streamed response
            full_response = []
            for event in stream:
                if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                    full_response.append(event.delta.text)
                elif hasattr(event, 'content_block') and hasattr(event.content_block, 'text'):
                    full_response.append(event.content_block.text)
            
            return ''.join(full_response)
            
        except Exception as e:
            logger.error(f"Streaming API error: {e}")
            raise APIError(f"Streaming API call failed: {e}")

# ============================================================================
# Project Management
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
        
        # Extract metadata
        self._extract_metadata(context)
        
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
        inspiration_file = project_dir / 'inspiration.md'
        if inspiration_file.exists():
            context.inspirations = self.file_handler.read_file(inspiration_file)
            logger.info("Loaded inspirations")
        
        return context
    
    def _load_chapters(self, project_dir: Path) -> Dict[int, Chapter]:
        """Load all chapter files."""
        chapters = {}
        
        for chapter_dir in self.config.chapter_dirs:
            search_dir = project_dir / chapter_dir
            if not search_dir.exists():
                continue
            
            files = self.file_handler.find_files(search_dir, self.config.chapter_patterns)
            
            for file_path in files:
                # Skip revised/backup files
                if any(skip in str(file_path).lower() for skip in ['enhanced', 'backup', 'revised']):
                    continue
                
                chapter_num = self._extract_chapter_number(file_path)
                if chapter_num is not None:
                    try:
                        content = self.file_handler.read_file(file_path)
                        if content:
                            chapters[chapter_num] = Chapter(
                                number=chapter_num,
                                file_path=file_path,
                                content=content,
                                word_count=len(content.split())
                            )
                            logger.debug(f"Loaded chapter {chapter_num} from {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to load {file_path}: {e}")
        
        return chapters
    
    def _extract_chapter_number(self, file_path: Path) -> Optional[int]:
        """Extract chapter number from filename."""
        filename = file_path.name
        
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
    
    def _extract_metadata(self, context: ProjectContext) -> None:
        """Extract metadata from project context."""
        # Detect genre
        synopsis_lower = context.synopsis.lower()
        if any(word in synopsis_lower for word in ['spy', 'intelligence', 'espionage']):
            context.genre = "Literary Spy Fiction"
        elif any(word in synopsis_lower for word in ['mystery', 'detective']):
            context.genre = "Literary Mystery"
        
        # Extract title
        if context.synopsis:
            lines = context.synopsis.split('\n')
            for line in lines:
                if 'title' in line.lower() or line.startswith('#'):
                    title = re.sub(r'^#+\s*|title:\s*', '', line, flags=re.IGNORECASE).strip()
                    if title and len(title) < 100:
                        context.title = title
                        break

# ============================================================================
# Chapter Analysis
# ============================================================================

class ChapterAnalyzer:
    """Analyzes chapters for revision opportunities."""
    
    def __init__(self, api_client: AnthropicClient, config: Config):
        self.api_client = api_client
        self.config = config
    
    def analyze_chapter(self, chapter: Chapter, all_chapters: Dict[int, Chapter],
                       context: ProjectContext, context_chapters: List[int]) -> str:
        """Analyze a single chapter."""
        # Get surrounding chapters for context
        surrounding = self._get_surrounding_chapters(chapter.number, all_chapters)
        
        prompt = self._build_analysis_prompt(
            chapter, all_chapters, context, surrounding, context_chapters
        )
        
        try:
            return self.api_client.complete(
                prompt, 
                model_complexity='medium',
                max_tokens=self.config.max_tokens['analysis']
            )
        except Exception as e:
            logger.error(f"Failed to analyze chapter {chapter.number}: {e}")
            raise
    
    def _get_surrounding_chapters(self, chapter_num: int, 
                                 all_chapters: Dict[int, Chapter]) -> List[str]:
        """Get preview of surrounding chapters."""
        surrounding = []
        for i in range(chapter_num - 2, chapter_num + 3):
            if i != chapter_num and i in all_chapters:
                preview = all_chapters[i].content[:500] + "..."
                surrounding.append(f"Chapter {i} (preview): {preview}")
        return surrounding
    
    def _build_analysis_prompt(self, chapter: Chapter, all_chapters: Dict[int, Chapter],
                              context: ProjectContext, surrounding: List[str],
                              context_chapters: List[int]) -> str:
        """Build the analysis prompt."""
        return f"""Analyze Chapter {chapter.number} of this {context.genre} novel for revision opportunities.

NOVEL CONTEXT:
Title: {context.title}
Genre: {context.genre}
Total Chapters: {len(all_chapters)}

LITERARY INSPIRATIONS:
{context.inspirations if context.inspirations else "None specified"}

PROJECT CONTEXT:
SYNOPSIS: {context.synopsis}
OUTLINE: {context.outline}
CHARACTERS: {context.characters}

SURROUNDING CHAPTERS:
{chr(10).join(surrounding)}

CHAPTER {chapter.number} TO ANALYZE ({chapter.word_count} words):
{chapter.content}

Provide comprehensive analysis covering:

## NARRATIVE FUNCTION
- How this chapter serves the overall story arc
- Connection to previous and next chapters
- Plot advancement and pacing

## CHARACTER DEVELOPMENT
- Character consistency with rest of novel
- Voice authenticity and growth
- Relationship dynamics

## LITERARY QUALITY
- Prose style consistency with novel
- Thematic integration
- Literary devices and techniques

## STRUCTURAL INTEGRITY
- Scene organization and transitions
- Opening and closing effectiveness
- Balance of action, dialogue, and reflection

## ALIGNMENT ISSUES
- Inconsistencies with other chapters
- Plot or character continuity problems
- Thematic disconnects

## REVISION OPPORTUNITIES
- Specific areas for expansion
- Literary enhancement possibilities
- Character development potential
- Atmospheric and sensory improvements

Focus on how this chapter fits within the larger novel while identifying specific improvements."""

# ============================================================================
# Revision Planning
# ============================================================================

class RevisionPlanner:
    """Creates revision plans for chapters."""
    
    def __init__(self, api_client: AnthropicClient, config: Config):
        self.api_client = api_client
        self.config = config
    
    def create_plan(self, chapter: Chapter, analysis: str, 
                   context: ProjectContext) -> RevisionPlan:
        """Create a revision plan for a chapter."""
        target_words = int(chapter.word_count * self.config.expansion_factor)
        
        prompt = self._build_planning_prompt(chapter, analysis, context, target_words)
        
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
                target_word_count=target_words
            )
        except Exception as e:
            logger.error(f"Failed to create plan for chapter {chapter.number}: {e}")
            raise
    
    def _build_planning_prompt(self, chapter: Chapter, analysis: str,
                             context: ProjectContext, target_words: int) -> str:
        """Build the planning prompt."""
        return f"""Create a detailed revision plan for Chapter {chapter.number} based on the analysis.

CHAPTER ANALYSIS:
{analysis}

LITERARY INSPIRATIONS:
{context.inspirations}

PROJECT CONTEXT:
SYNOPSIS: {context.synopsis}
OUTLINE: {context.outline}
CHARACTERS: {context.characters}

CURRENT WORD COUNT: {chapter.word_count} words
TARGET WORD COUNT: {target_words} words

Create a structured revision plan with:

## PRIORITY REVISIONS
List the most critical improvements needed based on the analysis.

## EXPANSION STRATEGY
- Specific scenes to expand
- Character moments to develop
- Atmospheric details to add
- Dialogue opportunities

## LITERARY ENHANCEMENTS
- Prose style improvements
- Thematic elements to strengthen
- Literary devices to employ
- Sensory details to include

## CONSISTENCY FIXES
- Character voice adjustments
- Plot detail corrections
- Timeline alignments
- Setting consistency

## STRUCTURAL IMPROVEMENTS
- Scene reorganization if needed
- Transition enhancements
- Pacing adjustments
- Opening/closing refinements

## SPECIFIC TASKS
Provide numbered, concrete revision tasks:
1. [Specific task with location and implementation details]
2. [Another specific task]
[Continue with 8-10 specific tasks]

Focus on meaningful improvements that enhance the chapter's role in the novel while maintaining literary quality."""

# ============================================================================
# Chapter Revision
# ============================================================================

class ChapterReviser:
    """Revises chapters based on plans."""
    
    def __init__(self, api_client: AnthropicClient, config: Config):
        self.api_client = api_client
        self.config = config
    
    def revise_chapter(self, chapter: Chapter, plan: RevisionPlan,
                      context_chapters: Dict[int, Chapter]) -> RevisionResult:
        """Revise a chapter based on its plan."""
        # For very long chapters or with many context chapters, break down the task
        total_context_words = sum(ch.word_count for ch in context_chapters.values())
        total_input_words = chapter.word_count + total_context_words
        
        # If input is too large, use a condensed approach
        if total_input_words > 10000:
            logger.info(f"Large input detected ({total_input_words} words), using condensed context")
            context_content = self._get_condensed_context(context_chapters)
        else:
            context_content = self._get_context_content(context_chapters)
        
        # Extract specific tasks
        specific_tasks = self._extract_specific_tasks(plan.plan_content)
        
        # Build revision prompt
        prompt = self._build_revision_prompt(
            chapter, plan, context_content, specific_tasks
        )
        
        try:
            # Use streaming for revision (large output expected)
            revised_content = self.api_client.complete(
                prompt,
                model_complexity='complex',
                max_tokens=self.config.max_tokens['revision'],
                use_streaming=True
            )
            
            # Clean AI commentary
            cleaned_content = self._clean_ai_commentary(revised_content)
            
            # Verify revision
            if self._is_unchanged(chapter.content, cleaned_content):
                logger.warning(f"Chapter {chapter.number} unchanged, retrying...")
                cleaned_content = self._retry_revision(
                    chapter, plan, context_content
                )
            
            return RevisionResult(
                chapter_number=chapter.number,
                original_content=chapter.content,
                revised_content=cleaned_content,
                original_word_count=chapter.word_count,
                revised_word_count=len(cleaned_content.split()),
                success=True
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
    
    def _get_condensed_context(self, context_chapters: Dict[int, Chapter]) -> str:
        """Get condensed context for large inputs."""
        if not context_chapters:
            return "No specific context chapters provided."
        
        content_parts = []
        for num in sorted(context_chapters.keys()):
            chapter = context_chapters[num]
            # Include first and last 500 words of each context chapter
            preview = chapter.content[:1000] + "\n[...middle content omitted...]\n" + chapter.content[-1000:]
            content_parts.append(f"""
=== CONTEXT CHAPTER {num} (condensed from {chapter.word_count} words) ===
{preview}
=== END CHAPTER {num} ===
""")
        
        return "\n".join(content_parts)
    
    def _get_context_content(self, context_chapters: Dict[int, Chapter]) -> str:
        """Get formatted context chapter content."""
        if not context_chapters:
            return "No specific context chapters provided."
        
        content_parts = []
        for num in sorted(context_chapters.keys()):
            chapter = context_chapters[num]
            content_parts.append(f"""
=== CONTEXT CHAPTER {num} ({chapter.word_count} words) ===
{chapter.content}
=== END CHAPTER {num} ===
""")
        
        return "\n".join(content_parts)
    
    def _extract_specific_tasks(self, plan_content: str) -> str:
        """Extract specific tasks from plan."""
        match = re.search(r'## SPECIFIC TASKS(.*?)(?=##|$)', plan_content, re.DOTALL)
        return match.group(1) if match else "No specific tasks found"
    
    def _build_revision_prompt(self, chapter: Chapter, plan: RevisionPlan,
                              context_content: str, specific_tasks: str) -> str:
        """Build the revision prompt."""
        return f"""You are revising Chapter {chapter.number} of a literary novel. Follow the revision plan EXACTLY and implement ALL specified changes.

CONTEXT CHAPTERS FOR REFERENCE:
{context_content}

REVISION PLAN TO IMPLEMENT:
{plan.plan_content}

ORIGINAL CHAPTER {chapter.number} ({chapter.word_count} words):
{chapter.content}

CRITICAL REQUIREMENTS:
1. You MUST implement EVERY task listed in the revision plan
2. You MUST expand the chapter to approximately {plan.target_word_count} words (current: {chapter.word_count})
3. You MUST maintain consistency with the context chapters provided
4. You MUST maintain the original story and characters while adding new content
5. You MUST NOT simply return the original text - make substantial additions

SPECIFIC TASKS TO COMPLETE:
{specific_tasks}

IMPORTANT: Return ONLY the complete revised chapter text. Do not include any commentary, notes, or explanations. The chapter must be significantly longer than the original."""
    
    def _clean_ai_commentary(self, text: str) -> str:
        """Remove AI commentary from text."""
        # Remove common AI preambles
        preambles = [
            "Here's the revised chapter", "Here is the revised chapter",
            "I'll revise Chapter", "I will revise Chapter",
            "Let me revise", "I've revised", "I have revised"
        ]
        
        for preamble in preambles:
            if text.lower().startswith(preamble.lower()):
                # Find the actual chapter start
                chapter_start = re.search(r'(Chapter \d+|# Chapter)', text, re.IGNORECASE)
                if chapter_start:
                    text = text[chapter_start.start():]
                    break
        
        # Remove inline commentary
        patterns = [
            r'\[.*?\]',
            r'Would you like.*?\?',
            r'I can .*?\.',
            r'Note:.*?\.',
            r'Commentary:.*?\.'
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Clean extra newlines
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text).strip()
        
        return text
    
    def _is_unchanged(self, original: str, revised: str) -> bool:
        """Check if content is unchanged."""
        return (revised == original or 
                len(revised) < len(original) or
                revised[:200] == original[:200])
    
    def _retry_revision(self, chapter: Chapter, plan: RevisionPlan,
                       context_content: str) -> str:
        """Retry revision with more explicit instructions."""
        # Use a shorter, more focused prompt for retry
        prompt = f"""CRITICAL: You must revise and EXPAND this chapter. Do NOT return the original text unchanged.

ORIGINAL CHAPTER (DO NOT RETURN THIS UNCHANGED):
{chapter.content}

The revised chapter MUST be approximately {plan.target_word_count} words (currently {chapter.word_count}).

Based on the revision plan, you must add substantial new content while maintaining the story.

Return ONLY the complete revised chapter with all additions integrated smoothly into the narrative."""
        
        try:
            revised = self.api_client.complete(
                prompt,
                model_complexity='complex',
                max_tokens=self.config.max_tokens['revision'],
                use_streaming=True
            )
            return self._clean_ai_commentary(revised)
        except Exception as e:
            logger.error(f"Retry failed: {e}")
            return chapter.content

# ============================================================================
# Report Generation
# ============================================================================

class ReportGenerator:
    """Generates revision reports."""
    
    def __init__(self, file_handler: FileHandler):
        self.file_handler = file_handler
    
    def generate_report(self, project_dir: Path, context: ProjectContext,
                       all_chapters: Dict[int, Chapter],
                       results: List[RevisionResult]) -> str:
        """Generate comprehensive revision report."""
        # Calculate statistics
        total_original = sum(r.original_word_count for r in results)
        total_revised = sum(r.revised_word_count for r in results)
        
        # Build chapter details
        chapter_details = []
        for result in sorted(results, key=lambda r: r.chapter_number):
            if result.success:
                expansion = result.revised_word_count / result.original_word_count
                chapter_details.append(
                    f"- Chapter {result.chapter_number}: "
                    f"{result.original_word_count:,} → {result.revised_word_count:,} words "
                    f"({expansion:.1f}x expansion)"
                )
            else:
                chapter_details.append(
                    f"- Chapter {result.chapter_number}: FAILED - {result.error_message}"
                )
        
        report = f"""# Chapter Revision Report

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Project:** {context.title}
**Genre:** {context.genre}
**Chapters Revised:** {[r.chapter_number for r in results]}

## Summary

Revised {len(results)} chapters out of {len(all_chapters)} total chapters in the novel.

**Word Count Changes:**
- Total Original: {total_original:,} words
- Total Revised: {total_revised:,} words
- Overall Expansion: {total_revised/total_original:.1f}x

**Chapter Details:**
{chr(10).join(chapter_details)}

## Process

### 1. Chapter Analysis
Each target chapter was analyzed in the context of the full novel, considering:
- Narrative function within the story arc
- Character consistency and development
- Literary quality and thematic integration
- Structural integrity and pacing

### 2. Revision Planning
Detailed revision plans were created for each chapter, focusing on:
- Priority improvements identified in analysis
- Expansion strategies for meaningful growth
- Literary enhancements and consistency fixes
- Specific, actionable revision tasks

### 3. Chapter Revision
Each chapter was revised according to its plan, with emphasis on:
- Implementing all planned improvements
- Expanding content meaningfully (target 40% growth)
- Maintaining novel-wide consistency
- Enhancing literary quality

## Files Created

See the project directory for:
- Analysis files (chapter_X_analysis.md)
- Revision plans (revision_plans/chapter_XX_revision_plan.md)
- Revised chapters (revised/chapter_X_revised.md)
- This report (chapter_revision_report.md)

## Next Steps

1. Review the revised chapters for alignment with your vision
2. Consider revising adjacent chapters for better flow
3. Update the novel outline to reflect changes
4. Run a full novel alignment check if significant changes were made

## Notes

The revision process maintained the context of the full novel while focusing on the selected chapters. 
Each revised chapter should now better serve its role in the overall narrative while demonstrating 
enhanced literary quality.
"""
        
        # Save report
        report_path = project_dir / 'chapter_revision_report.md'
        self.file_handler.write_file(report_path, report)
        logger.info(f"Report saved to {report_path}")
        
        return report

# ============================================================================
# Main Application Controller
# ============================================================================

class ChapterRevisionController:
    """Main controller for the chapter revision process."""
    
    def __init__(self, config: Config):
        self.config = config
        self.file_handler = FileHandler(config)
        self.api_client = AnthropicClient(config)
        self.project_loader = ProjectLoader(self.file_handler, config)
        self.analyzer = ChapterAnalyzer(self.api_client, config)
        self.planner = RevisionPlanner(self.api_client, config)
        self.reviser = ChapterReviser(self.api_client, config)
        self.report_generator = ReportGenerator(self.file_handler)
    
    def run(self, project_dir: str, target_chapters: List[int],
            context_map: Optional[Dict[int, List[int]]] = None,
            analysis_only: bool = False,
            use_existing_analysis: bool = False) -> None:
        """Run the chapter revision process."""
        project_path = Path(project_dir)
        
        # Load project
        logger.info(f"Loading project from {project_path}")
        all_chapters, project_context = self.project_loader.load_project(project_path)
        
        # Validate target chapters
        valid_targets = {num: all_chapters[num] for num in target_chapters 
                        if num in all_chapters}
        if not valid_targets:
            raise ValidationError(f"No valid chapters found from: {target_chapters}")
        
        logger.info(f"Processing chapters: {sorted(valid_targets.keys())}")
        
        # Set up context map
        if context_map is None:
            context_map = self._generate_default_context_map(
                target_chapters, all_chapters
            )
        
        # Step 1: Analysis
        analyses = {}
        for chapter_num, chapter in valid_targets.items():
            analysis_file = project_path / f'chapter_{chapter_num}_analysis.md'
            
            if use_existing_analysis and analysis_file.exists():
                logger.info(f"Using existing analysis for chapter {chapter_num}")
                analyses[chapter_num] = self.file_handler.read_file(analysis_file)
            else:
                logger.info(f"Analyzing chapter {chapter_num}")
                analysis = self.analyzer.analyze_chapter(
                    chapter, all_chapters, project_context,
                    context_map.get(chapter_num, [])
                )
                analyses[chapter_num] = analysis
                
                # Save analysis
                self._save_analysis(analysis_file, chapter_num, analysis)
        
        if analysis_only:
            logger.info("Analysis complete (analysis-only mode)")
            return
        
        # Step 2: Planning
        plans = {}
        plans_dir = project_path / 'revision_plans'
        plans_dir.mkdir(exist_ok=True)
        
        for chapter_num, chapter in valid_targets.items():
            plan_file = plans_dir / f'chapter_{chapter_num:02d}_revision_plan.md'
            
            if use_existing_analysis and plan_file.exists():
                logger.info(f"Using existing plan for chapter {chapter_num}")
                plan_content = self.file_handler.read_file(plan_file)
                # Parse plan from file
                plans[chapter_num] = RevisionPlan(
                    chapter_number=chapter_num,
                    analysis=analyses[chapter_num],
                    plan_content=plan_content,
                    target_word_count=int(chapter.word_count * self.config.expansion_factor)
                )
            else:
                logger.info(f"Creating plan for chapter {chapter_num}")
                plan = self.planner.create_plan(
                    chapter, analyses[chapter_num], project_context
                )
                plans[chapter_num] = plan
                
                # Save plan
                self._save_plan(plan_file, plan)
        
        # Step 3: Revision
        results = []
        revised_dir = project_path / 'revised'
        revised_dir.mkdir(exist_ok=True)
        
        for chapter_num, chapter in valid_targets.items():
            logger.info(f"Revising chapter {chapter_num}")
            
            # Get context chapters
            context_chapters = {
                num: all_chapters[num] 
                for num in context_map.get(chapter_num, [])
                if num in all_chapters
            }
            
            # Revise chapter
            result = self.reviser.revise_chapter(
                chapter, plans[chapter_num], context_chapters
            )
            results.append(result)
            
            # Save revised chapter
            if result.success:
                revised_file = revised_dir / f'{chapter.file_path.stem}_revised.md'
                self.file_handler.write_file(revised_file, result.revised_content)
                
                logger.info(
                    f"Chapter {chapter_num}: "
                    f"{result.original_word_count} → {result.revised_word_count} words "
                    f"({result.revised_word_count/result.original_word_count:.1f}x)"
                )
            else:
                logger.error(f"Failed to revise chapter {chapter_num}: {result.error_message}")
        
        # Step 4: Generate report
        logger.info("Generating report")
        self.report_generator.generate_report(
            project_path, project_context, all_chapters, results
        )
        
        logger.info("Chapter revision complete!")
    
    def _generate_default_context_map(self, target_chapters: List[int],
                                    all_chapters: Dict[int, Chapter]) -> Dict[int, List[int]]:
        """Generate default context map with surrounding chapters."""
        context_map = {}
        for chapter_num in target_chapters:
            context_chapters = []
            for i in range(chapter_num - 2, chapter_num + 3):
                if i != chapter_num and i in all_chapters:
                    context_chapters.append(i)
            context_map[chapter_num] = context_chapters
        return context_map
    
    def _save_analysis(self, file_path: Path, chapter_num: int, analysis: str) -> None:
        """Save analysis to file."""
        content = f"""# Chapter {chapter_num} Analysis

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Chapter:** {chapter_num}

---

{analysis}
"""
        self.file_handler.write_file(file_path, content)
    
    def _save_plan(self, file_path: Path, plan: RevisionPlan) -> None:
        """Save revision plan to file."""
        content = f"""# REVISION PLAN FOR CHAPTER {plan.chapter_number}

**Generated:** {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}
**Target word count:** {plan.target_word_count} words

---

{plan.plan_content}
"""
        self.file_handler.write_file(file_path, content)

# ============================================================================
# CLI Interface
# ============================================================================

def parse_chapter_spec(spec: str) -> List[int]:
    """Parse chapter specification string."""
    chapters = []
    
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
    
    # Format: "10:0,5;15:0,10"
    for mapping in spec.split(';'):
        if ':' in mapping:
            try:
                target, contexts = mapping.split(':')
                target_num = int(target.strip())
                context_nums = [int(c.strip()) for c in contexts.split(',')]
                context_map[target_num] = context_nums
            except ValueError:
                raise ValidationError(f"Invalid context mapping: {mapping}")
    
    return context_map

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Professional chapter revision tool for novels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Revise single chapter
  %(prog)s mynovel --chapters 5
  
  # Revise multiple chapters
  %(prog)s mynovel --chapters 3,5,7,9
  
  # Revise chapter range
  %(prog)s mynovel --chapters 10-15
  
  # Use specific context chapters
  %(prog)s mynovel --chapters 10 --context-chapters "10:0,5"
  
  # Use context map file
  %(prog)s mynovel --chapters 10,15 --context-map context.json
  
  # Analysis only
  %(prog)s mynovel --chapters 5 --analysis-only
  
  # Use existing analyses
  %(prog)s mynovel --chapters 5 --use-existing-analysis
"""
    )
    
    parser.add_argument(
        'project_dir',
        help='Project directory containing the novel'
    )
    parser.add_argument(
        '--chapters',
        required=True,
        help='Chapters to revise (e.g., "5" or "3,5,7" or "10-15")'
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
        '--cost-optimize',
        action='store_true',
        help='Use cost-optimized models (may reduce quality)'
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
        
        if context_map:
            logger.info(f"Context map: {context_map}")
        
        # Create config
        config = Config()
        
        # Apply cost optimization if requested
        if args.cost_optimize:
            config.models['complex'] = config.models['medium']
            logger.info("Cost optimization enabled")
        
        # Create controller and run
        controller = ChapterRevisionController(config)
        controller.run(
            args.project_dir,
            target_chapters,
            context_map=context_map,
            analysis_only=args.analysis_only,
            use_existing_analysis=args.use_existing_analysis
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