#!/usr/bin/env python3
"""
chapter_analyser.py - Professional Manuscript Analysis Tool (OpenAI version)

A comprehensive tool for analyzing novel manuscripts and generating professional editorial reports
in the style of SixthDraft Academy assessments. Provides detailed literary analysis with actionable feedback.

This version uses OpenAI's Responses API (e.g., GPT-5 family) instead of Anthropic.
"""

import os
import re
import logging
import argparse
import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import sys
import time


# --- OpenAI client ---
try:
    from openai import OpenAI
    from openai import OpenAIError
    try:
        from openai import RateLimitError as OpenAIRateLimit
    except ImportError:
        # Fallback if RateLimitError is not available in this version
        OpenAIRateLimit = OpenAIError

except Exception as _e:
    raise RuntimeError("OpenAI SDK is required. Install with: pip install openai") from _e

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('manuscript_analysis.log', encoding='utf-8')
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
    api_key: str = field(default_factory=lambda: os.getenv('OPENAI_API_KEY', ''))
    max_retries: int = 3
    retry_delay: float = 2.0  # seconds

    # Model Configuration (override via --model if desired)
    model: str = "gpt-5"

    # Token Limits for different report sections (these map to max_output_tokens)
    max_tokens: Dict[str, int] = field(default_factory=lambda: {
        'synopsis': 1500,
        'overview': 1000,
        'full_report': 6000,
        'summary': 1500,
        'chapter_analysis': 3000
    })

    # Report Template File (hardcoded)
    report_template_file: str = "SixthDraftfullreport.md"

    # File Patterns
    chapter_patterns: List[str] = field(default_factory=lambda: [
        'chapter_*.md', 'chapter*.md', 'ch_*.md', 'Chapter*.md',
        '*_chapter_*.md', '*_chapter.md',
        '[0-9]*.md', '[0-9]*.txt',  # Just numbers
        'ch[0-9]*.md', 'ch[0-9]*.txt',  # ch1, ch2, etc.
        '*.txt' # Removed .doc/.docx as they require special libraries
    ])

    # Directories
    chapter_dirs: List[str] = field(default_factory=lambda: [
        'chapters', 'content', 'manuscript', 'text', '.'
    ])

    # Encoding Settings
    file_encodings: List[str] = field(default_factory=lambda: [
        'utf-8', 'utf-8-sig', 'cp1252', 'latin1'
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
    word_count: int = 0
    title: Optional[str] = None

    def __post_init__(self):
        self.file_path = Path(self.file_path)
        self.word_count = self._count_words(self.content)
        self.title = self._extract_title()

    def _count_words(self, text: str) -> int:
        """Accurate word counting."""
        # Remove markdown/formatting for more accurate counting
        text = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'[\*_`]', '', text) # Simplified regex for bold/italic/code
        words = re.findall(r'\b\w+\b', text)
        return len(words)

    def _extract_title(self) -> Optional[str]:
        """Extract chapter title if present."""
        lines = self.content.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line.startswith('#') or line.lower().startswith('chapter'):
                title = re.sub(r'^#+\s*|\bchapter\b\s*\d*\s*:*\s*', '', line, flags=re.IGNORECASE).strip()
                return title if title else None
        return None

@dataclass
class Manuscript:
    """Represents the complete manuscript."""
    title: str
    author: Optional[str]
    genre: str
    chapters: Dict[int, Chapter]
    total_word_count: int = 0
    synopsis: Optional[str] = None

    def __post_init__(self):
        self.total_word_count = sum(ch.word_count for ch in self.chapters.values())

@dataclass
class ManuscriptContext:
    """Additional context about the manuscript."""
    synopsis_file: Optional[str] = None
    outline: Optional[str] = None
    characters: Optional[str] = None
    themes: Optional[str] = None
    author_notes: Optional[str] = None
    target_audience: Optional[str] = None
    comparable_titles: Optional[str] = None

@dataclass
class SixthDraftStyleReport:
    """Represents a SixthDraft Academy style editorial report."""
    manuscript: Manuscript
    synopsis: str
    overview: str
    detailed_report: str
    summary: str
    strengths: List[str]
    areas_for_improvement: List[str]
    market_potential: str
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

# ============================================================================
# Exceptions
# ============================================================================

class AnalyzerError(Exception):
    """Base exception for manuscript analyzer."""
    pass

class FileOperationError(AnalyzerError):
    """Raised when file operations fail."""
    pass

class AnalyzerAPIError(AnalyzerError):
    """Raised when API calls fail after retries."""
    pass

class APICallError(AnalyzerAPIError):
    """Raised when an API call fails after all retries."""
    pass

# ============================================================================
# File Operations
# ============================================================================

class FileHandler:
    """Handles all file operations."""

    def __init__(self, config: Config):
        self.config = config

    def read_file(self, file_path: Path) -> str:
        """Safely read a file with multiple encoding attempts."""
        if not file_path.is_file():
            raise FileOperationError(f"File not found or is not a file: {file_path}")

        for encoding in self.config.file_encodings:
            try:
                return file_path.read_text(encoding=encoding)
            except (UnicodeDecodeError, UnicodeError):
                continue
        # Last resort with error replacement
        try:
            return file_path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            raise FileOperationError(f"Failed to read {file_path} even with replacement: {e}")

    def write_file(self, file_path: Path, content: str) -> None:
        """Write a file with UTF-8 encoding."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
        except Exception as e:
            raise FileOperationError(f"Failed to write to {file_path}: {e}")

    def find_files(self, directory: Path, patterns: List[str]) -> List[Path]:
        """Find files matching patterns in directory."""
        files = set()
        for pattern in patterns:
            files.update(directory.glob(pattern))
        return sorted(list(files))

    def load_template(self) -> Optional[str]:
        """Load the SixthDraft report template if it exists."""
        template_path = Path(self.config.report_template_file)
        if template_path.exists():
            return self.read_file(template_path)
        return None

# ---------------------------------------------------------------------------
# LLM client ─ OpenAI
# ---------------------------------------------------------------------------

class OpenAIClient:
    """Wrapper for openai>=1.0.0 chat API, matching AnthropicClient.complete()."""

    def __init__(self, config: Config):
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise AnalyzerError("OPENAI_API_KEY not set")
        # new SDK client
        self.client = OpenAI(api_key=key)
        self.config = config

    def complete(self, prompt: str, max_tokens: int | None = None) -> str:
        # new parameter name for openai>=1.0.0
        max_completion_tokens = max_tokens or 4096
        last_err = None

        for attempt in range(self.config.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=1,
                    max_completion_tokens=max_completion_tokens,
                )
                return resp.choices[0].message.content.strip()

            except OpenAIRateLimit as e:
                last_err = e
            except OpenAIError as e:
                last_err = e

            if attempt < self.config.max_retries - 1:
                wait = self.config.retry_delay * (2 ** attempt)
                logger.warning("OpenAI error. Retrying in %.1f s… (%s)", wait, last_err)
                time.sleep(wait)

        raise APICallError(f"OpenAI API call failed after retries: {last_err}")


# ============================================================================
# Manuscript Loading
# ============================================================================

class ManuscriptLoader:
    """Loads and processes manuscript files."""

    def __init__(self, file_handler: FileHandler, config: Config):
        self.file_handler = file_handler
        self.config = config

    def load_manuscript(self, project_dir: Path) -> Tuple[Manuscript, ManuscriptContext]:
        """Load complete manuscript and context."""
        if not project_dir.is_dir():
            raise FileOperationError(f"Project directory not found: {project_dir}")

        context = self._load_context(project_dir)
        chapters = self._load_chapters(project_dir)
        title, author, genre = self._detect_metadata(project_dir, chapters, context)

        manuscript = Manuscript(
            title=title,
            author=author,
            genre=genre,
            chapters=chapters,
        )
        return manuscript, context

    def _load_context_file(self, project_dir: Path, file_names: List[str]) -> Optional[str]:
        """Helper to load a single context file."""
        for name in file_names:
            file_path = project_dir / name
            if file_path.is_file():
                logger.info(f"Loaded context from {name}")
                return self.file_handler.read_file(file_path)
        return None

    def _load_context(self, project_dir: Path) -> ManuscriptContext:
        """Load manuscript context files."""
        return ManuscriptContext(
            synopsis_file=self._load_context_file(project_dir, ['synopsis.md', 'synopsis.txt', 'summary.md']),
            outline=self._load_context_file(project_dir, ['outline.md', 'outline.txt', 'structure.md']),
            characters=self._load_context_file(project_dir, ['characters.md', 'characters.txt', 'cast.md']),
            author_notes=self._load_context_file(project_dir, ['notes.md', 'author_notes.md', 'readme.md'])
        )

    def _load_chapters(self, project_dir: Path) -> Dict[int, Chapter]:
        """Load all chapter files."""
        chapters = {}
        all_files = set()

        for chapter_dir_name in self.config.chapter_dirs:
            search_dir = project_dir / chapter_dir_name
            if search_dir.is_dir():
                all_files.update(self.file_handler.find_files(search_dir, self.config.chapter_patterns))

        for file_path in sorted(list(all_files)):
            if any(skip in str(file_path).lower() for skip in
                ['synopsis', 'outline', 'character', 'notes', 'readme', 'draft', 'backup', 'report']):
                continue

            chapter_num = self._extract_chapter_number(file_path)
            if chapter_num is not None and chapter_num not in chapters:
                try:
                    content = self.file_handler.read_file(file_path)
                    if content.strip():
                        chapters[chapter_num] = Chapter(
                            number=chapter_num,
                            file_path=file_path,
                            content=content
                        )
                        logger.debug(f"Loaded chapter {chapter_num} from {file_path}")
                except FileOperationError as e:
                    logger.warning(f"Could not load chapter file {file_path}: {e}")

        if not chapters:
            logger.warning("No chapter files were found. Please check your file names and directories.")
        return dict(sorted(chapters.items()))

    def _extract_chapter_number(self, file_path: Path) -> Optional[int]:
        """Extract chapter number from filename."""
        filename = file_path.stem
        # More robust regex to find numbers, prioritizing those after "chapter" or "ch"
        patterns = [
            r'chapter[_\s-]*(\d+)',
            r'ch[_\s-]*(\d+)',
            r'(\d+)[_\s-]*chapter',
            r'^(\d+)$'
        ]
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Fallback for filenames that are just numbers
        if filename.isdigit():
            return int(filename)

        logger.debug(f"Could not extract chapter number from: {file_path.name}")
        return None

    def _detect_metadata(self, project_dir: Path, chapters: Dict[int, Chapter],
                        context: ManuscriptContext) -> Tuple[str, Optional[str], str]:
        """Detect manuscript title, author, and genre."""
        title = project_dir.name.replace('_', ' ').replace('-', ' ').title()
        author = None
        genre = "Not specified"

        if context.author_notes:
            lines = context.author_notes.split('\n')[:10]
            for line in lines:
                if 'title:' in line.lower():
                    title = line.split(':', 1)[1].strip()
                if 'author:' in line.lower():
                    author = line.split(':', 1)[1].strip()
                if 'genre:' in line.lower():
                    genre = line.split(':', 1)[1].strip()

        return title, author, genre

# ============================================================================
# SixthDraft-Style Analysis
# ============================================================================

class SixthDraftAnalyzer:
    """Generates SixthDraft Academy style manuscript analysis."""

    def __init__(self, api_client: OpenAIClient, config: Config):
        self.api_client = api_client
        self.config = config
        self.template = None

    def set_template(self, template: str):
        """Set the report template for style reference."""
        self.template = template

    def analyze_manuscript(self, manuscript: Manuscript,
                            context: ManuscriptContext,
                            selected_chapters: Optional[List[int]] = None) -> SixthDraftStyleReport:
        """Generate complete SixthDraft-style analysis."""
        if not manuscript.chapters:
            raise AnalyzerError("Cannot analyze an empty manuscript with no chapters.")

        if selected_chapters:
            chapters_to_analyze = {num: manuscript.chapters[num]
                                for num in selected_chapters
                                if num in manuscript.chapters}
        else:
            # Sample first, middle, and last chapters if more than 3
            chapter_nums = sorted(manuscript.chapters.keys())
            if len(chapter_nums) > 3:
                sample_nums = {
                    chapter_nums[0],
                    chapter_nums[len(chapter_nums) // 2],
                    chapter_nums[-1]
                }
                chapters_to_analyze = {num: manuscript.chapters[num] for num in sorted(list(sample_nums))}
            else:
                chapters_to_analyze = manuscript.chapters # Analyze all if 3 or fewer

        logger.info(f"Analyzing chapters: {list(chapters_to_analyze.keys())}")

        synopsis = self._generate_synopsis(manuscript, context)
        overview = self._generate_overview(manuscript, chapters_to_analyze, context)
        detailed_report = self._generate_detailed_report(manuscript, chapters_to_analyze, context)
        summary = self._generate_summary(manuscript, detailed_report)

        strengths = self._extract_points(detailed_report, "strengths")
        improvements = self._extract_points(detailed_report, "areas for improvement")
        market_potential = self._assess_market_potential(manuscript, context, detailed_report)

        return SixthDraftStyleReport(
            manuscript=manuscript,
            synopsis=synopsis,
            overview=overview,
            detailed_report=detailed_report,
            summary=summary,
            strengths=strengths,
            areas_for_improvement=improvements,
            market_potential=market_potential
        )

    def _generate_synopsis(self, manuscript: Manuscript, context: ManuscriptContext) -> str:
        """Generate plot synopsis."""
        if context.synopsis_file:
            logger.info("Using existing synopsis file.")
            return context.synopsis_file

        full_text = "\n\n".join(ch.content for ch in manuscript.chapters.values())
        prompt = f"""
        Please write in plain, accessible language, avoiding jargon and purple prose.
        You are a literary editor. Based on the full text of the manuscript provided, write a clear, engaging, and professional plot synopsis.

MANUSCRIPT TITLE: {manuscript.title}
GENRE: {manuscript.genre}

The synopsis should:
- Be 2-3 paragraphs long.
- Be written in the present tense.
- Capture the main plot arc, key characters, the central conflict, and the stakes.
- Give a clear sense of the story's beginning, middle, and end, including the resolution.
- Avoid getting bogged down in minor subplots or secondary characters.

Here is the full manuscript text:
---
{full_text[:20000]}
---
"""
        return self.api_client.complete(prompt, self.config.max_tokens['synopsis'])

    def _generate_overview(self, manuscript: Manuscript, chapters: Dict[int, Chapter],
                            context: ManuscriptContext) -> str:
        """Generate overview section."""
        chapter_content = "\n".join(f"Chapter {num}: {chap.content[:500]}" for num, chap in chapters.items())
        prompt = f"""
        Please write in plain, accessible language, avoiding jargon and purple prose.
        Write an overview paragraph for a manuscript report.

MANUSCRIPT: {manuscript.title}
GENRE: {manuscript.genre}
CHAPTERS ANALYZED: {list(chapters.keys())}

The overview should:
1. Start with an engaging sentence about the manuscript's premise and potential.
2. Briefly summarize its core strengths (e.g., concept, voice, prose).
3. Indicate the main areas for development (e.g., pacing, character arcs, structure).
4. Set a professional, encouraging, and constructive tone for the rest of the report.

Keep it to one substantial paragraph. Here is some sample content:
---
{chapter_content}
---
"""
        return self.api_client.complete(prompt, self.config.max_tokens['overview'])

    def _generate_detailed_report(self, manuscript: Manuscript, chapters: Dict[int, Chapter],
                                    context: ManuscriptContext) -> str:
        """Generate the main detailed analysis."""
        chapter_samples = "\n\n".join(f"--- CHAPTER {num} (Excerpt) ---\n{chapter.content[:4000]}"
                                    for num, chapter in sorted(chapters.items()))

        prompt = f"""
        Please write in plain, accessible language, avoiding jargon and purple prose.
        You are a senior editor at a top publisher, writing a manuscript assessment in the style of SixthDraft Academy.

MANUSCRIPT DETAILS:
Title: {manuscript.title}
Genre: {manuscript.genre}
Total Word Count: {manuscript.total_word_count}
{f"AUTHOR'S NOTES: {context.author_notes[:1000]}" if context.author_notes else ""}
{f"CHARACTERS: {context.characters[:1000]}" if context.characters else ""}

EXCERPTS FROM ANALYZED CHAPTERS:
{chapter_samples}

Write a comprehensive, constructive, and detailed editorial report (approx. 1000-1500 words). Structure your report with the following sections using markdown headings (##):

1.  **Opening** - First impressions, the core concept, and overall potential.
2.  **Voice and Point of View** - Analyze the narrative voice, its consistency, and the effectiveness of the chosen POV.
3.  **Characterization** - Assess the protagonist's arc, the supporting cast, and their motivations and believability.
4.  **Plot and Pacing** - Evaluate the story structure, narrative drive, tension, and pacing across the sampled chapters.
5.  **Prose and Style** - Comment on the quality of the writing, including dialogue, description, and sentence-level craft.
6.  **World-Building and Setting** - Analyze how effectively the setting is rendered and integrated into the story.
7.  **Theme** - Discuss the central themes and ideas and how well they are explored.

For each section, provide balanced critique (strengths and weaknesses) with specific, actionable suggestions for improvement, and areas for improvement and exploration. Be honest but encouraging, critical but constructive.
"""
        return self.api_client.complete(prompt, self.config.max_tokens['full_report'])

    def _generate_summary(self, manuscript: Manuscript, detailed_report: str) -> str:
        """Generate summary recommendations."""
        prompt = f"""
        Please write in plain, accessible language, avoiding jargon and purple prose.
        Based on the following detailed editorial report, write a final summary paragraph.

This summary should:
1. Reiterate the manuscript's core strengths and potential.
2. Clearly identify the 2-3 most critical areas to focus on for revision.
3. Offer encouragement and concrete next steps for the author.
4. Maintain a professional, motivating, and supportive tone.

DETAILED REPORT:
---
{detailed_report}
---

Write a single, concise summary paragraph that leaves the author feeling clear and motivated.
"""
        return self.api_client.complete(prompt, self.config.max_tokens['summary'])

    def _extract_points(self, detailed_report: str, point_type: str) -> List[str]:
        """Extract key strengths or areas for improvement from the report."""
        prompt = f"""From the following editorial report, extract 4-5 key **{point_type}** of the manuscript.

REPORT:
---
{detailed_report}
---

List the points as short, clear bullet points. Focus on high-level concepts like premise, voice, character, plot, or prose. List each point clearly on its own line, as a markdown bullet starting with '* '. Do not include any introduction or explanation"""
        response = self.api_client.complete(prompt, 1000)
        return [s.strip('* \t-•').strip() for s in response.split('\n') if s.strip()]

    def _assess_market_potential(self, manuscript: Manuscript, context: ManuscriptContext, detailed_report: str) -> str:
        """Assess market potential."""
        prompt = f"""Based on the manuscript's genre and the editorial report, write a brief, 2-3 sentence assessment of its market potential.

MANUSCRIPT GENRE: {manuscript.genre}
{f"AUTHOR'S COMPARABLE TITLES: {context.comparable_titles}" if context and context.comparable_titles else ""}
EDITORIAL REPORT:
---
{detailed_report[:2000]}
---

Consider current market trends, target audience, and unique selling points. Be realistic but encouraging.
"""
        return self.api_client.complete(prompt, 2000)

# ============================================================================
# Report Generator
# ============================================================================

class SixthDraftReportGenerator:
    """Generates formatted reports in SixthDraft Academy style."""

    def __init__(self, file_handler: FileHandler):
        self.file_handler = file_handler

    def generate_report(self, report: SixthDraftStyleReport, output_path: Path) -> str:
        """Generate the formatted markdown report."""
        formatted_report = f"""# Editorial Report

**Manuscript:** {report.manuscript.title}
**Author:** {report.manuscript.author or "Not Specified"}
**Genre:** {report.manuscript.genre}
**Word Count:** {report.manuscript.total_word_count:,}
**Date:** {report.created_at.strftime('%B %d, %Y')}

---

## Synopsis

{report.synopsis.strip()}

---

## Overview

{report.overview.strip()}

---

## Detailed Report

{report.detailed_report.strip()}

---

## Summary of Strengths

{self._format_bullet_points(report.strengths)}

---

## Key Areas for Development

{self._format_bullet_points(report.areas_for_improvement)}

---

## Market Potential

{report.market_potential.strip()}

---

## Final Recommendations

{report.summary.strip()}

---

*This report is intended to provide constructive feedback to assist in the development of your manuscript. The creative decisions ultimately rest with you, the author. We wish you the very best on your writing journey.*

*Report generated at: {report.created_at.strftime('%Y-%m-%d %H:%M:%S')}*
"""
        self.file_handler.write_file(output_path, formatted_report)
        logger.info(f"Full report saved to {output_path}")
        return formatted_report

    def _format_bullet_points(self, items: List[str]) -> str:
        """Format a list as markdown bullet points."""
        return '\n'.join(f"* {item}" for item in items if item)

# ============================================================================
# Main Controller
# ============================================================================

class ManuscriptAnalysisController:
    """Main controller for the analysis workflow."""

    def __init__(self, config: Config):
        self.config = config
        self.file_handler = FileHandler(config)
        self.api_client = OpenAIClient(config)  # <-- OpenAI client
        self.manuscript_loader = ManuscriptLoader(self.file_handler, config)
        self.analyzer = SixthDraftAnalyzer(self.api_client, config)
        self.report_generator = SixthDraftReportGenerator(self.file_handler)

    def run(self, project_dir: str, output_dir: Optional[str] = None,
            analyze_all: bool = False, chapter_list: Optional[List[int]] = None) -> None:
        """Execute the full analysis process."""
        project_path = Path(project_dir).resolve()
        output_path = Path(output_dir).resolve() if output_dir else project_path / "analysis_reports"

        template = self.file_handler.load_template()
        if template:
            self.analyzer.set_template(template)
            logger.info("Loaded SixthDraft report template for style reference.")

        logger.info(f"Loading manuscript from: {project_path}")
        manuscript, context = self.manuscript_loader.load_manuscript(project_path)
        if not manuscript.chapters:
            return  # Stop if no chapters were loaded

        logger.info(f"Loaded '{manuscript.title}': {len(manuscript.chapters)} chapters, {manuscript.total_word_count:,} words.")

        chapters_to_analyze = chapter_list
        if analyze_all:
            chapters_to_analyze = list(manuscript.chapters.keys())

        logger.info("Generating full editorial report...")
        full_report = self.analyzer.analyze_manuscript(
            manuscript, context, chapters_to_analyze
        )

        # Sanitize title for filename
        safe_title = re.sub(r'[^\w\s-]', '', manuscript.title).strip().replace(' ', '_')
        report_filename = f"Editorial_Report_{safe_title}.md"
        report_path = output_path / report_filename

        self.report_generator.generate_report(full_report, report_path)
        logger.info(f"Analysis complete! View your report at: {report_path}")

# ============================================================================
# CLI Interface
# ============================================================================

def parse_chapter_list(spec: str) -> List[int]:
    """Parse chapter specification string (e.g., "1,3,5" or "5-10")."""
    chapters = set()
    parts = spec.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                chapters.update(range(start, end + 1))
            except ValueError:
                raise argparse.ArgumentTypeError(f"Invalid chapter range: '{part}'")
        else:
            try:
                chapters.add(int(part))
            except ValueError:
                raise argparse.ArgumentTypeError(f"Invalid chapter number: '{part}'")
    return sorted(list(chapters))

def main() -> int:
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(
        description="A professional manuscript analysis tool using the OpenAI API.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # Analyze with automatic sampling (first, middle, last chapters)
  %(prog)s /path/to/your_novel

  # Analyze a specific list of chapters
  %(prog)s /path/to/your_novel --chapters 1,5,10

  # Analyze a range of chapters
  %(prog)s /path/to/your_novel --chapters 3-7

  # Analyze all chapters found in the directory
  %(prog)s /path/to/your_novel --all

  # Specify a custom output directory for reports
  %(prog)s /path/to/your_novel --output /path/to/reports

  # Choose a specific model
  %(prog)s /path/to/your_novel --model gpt-5-mini
"""
    )

    parser.add_argument('manuscript_dir', help='Directory containing the manuscript files.')
    parser.add_argument('--output', help='Output directory for reports (default: a new folder in the manuscript directory).')

    chapter_group = parser.add_mutually_exclusive_group()
    chapter_group.add_argument('--chapters', type=parse_chapter_list, help='Specific chapters to analyze (e.g., "1,3,5" or "1-10").')
    chapter_group.add_argument('--all', action='store_true', help='Analyze all chapters (default is to sample).')

    parser.add_argument('--model', help='Override the OpenAI model (e.g., "gpt-5" or "gpt-5-mini").')
    parser.add_argument('--template', help='Path to a custom SixthDraft report template for style reference.')
    parser.add_argument('--debug', action='store_true', help='Enable debug-level logging.')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        config = Config()
        if args.model:
            config.model = args.model
            logger.info(f"Using model: {config.model}")
        if args.template:
            config.report_template_file = args.template
            logger.info(f"Using custom template: {config.report_template_file}")

        controller = ManuscriptAnalysisController(config)
        controller.run(
            args.manuscript_dir,
            output_dir=args.output,
            analyze_all=args.all,
            chapter_list=args.chapters
        )
        return 0
    except (AnalyzerError, FileOperationError, AnalyzerAPIError) as e:
        logger.error(f"A critical error occurred: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("\nAnalysis cancelled by user.")
        return 1
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
