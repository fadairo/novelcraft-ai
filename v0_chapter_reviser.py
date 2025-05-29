#!/usr/bin/env python3
"""
chapter_reviser.py - Selective Chapter Revision Tool

Based on novel_reviser.py but designed for targeted chapter revision.
Can revise single chapters or multiple chapters while maintaining novel context.

Features:
1. Analyze specific chapters in context of the full novel
2. Create revision plans for selected chapters only
3. Revise chapters based on novel-wide alignment
4. Generate reports for revised chapters

Windows-compatible with proper encoding handling.
"""

import os
import re
import glob
import json
import argparse
import datetime
import sys
from typing import List, Dict, Tuple, Optional, Set
from pathlib import Path
import anthropic

# Set UTF-8 encoding for Windows
if sys.platform.startswith('win'):
    import locale
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        pass

class ChapterReviser:
    """Selective chapter revision system based on novel_reviser architecture."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
        self.project_dir = None
        self.novel_title = "Novel"
        self.genre = "Literary Fiction"
        self.inspirations = ""
        self.all_chapters = {}  # All chapters in the novel
        self.target_chapters = {}  # Chapters to revise
        self.project_context = {}
        self.use_cost_effective_model = True
    
    def _safe_read_file(self, file_path: str) -> str:
        """Safely read a file with multiple encoding attempts."""
        encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1', 'ascii']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
                return content
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # Last resort
        try:
            with open(file_path, 'rb') as f:
                raw_content = f.read()
                return raw_content.decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return ""
    
    def _safe_write_file(self, file_path: str, content: str) -> bool:
        """Safely write a file with UTF-8 encoding."""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            cleaned_content = content.encode('utf-8', errors='replace').decode('utf-8')
            
            with open(file_path, 'w', encoding='utf-8', errors='replace', newline='\n') as f:
                f.write(cleaned_content)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            try:
                # ASCII fallback
                ascii_content = content.encode('ascii', errors='replace').decode('ascii')
                with open(file_path, 'w', encoding='ascii', errors='replace') as f:
                    f.write(ascii_content)
                return True
            except:
                return False
    
    def load_project(self, project_dir: str, target_chapters: List[int]):
        """Load project files and identify target chapters."""
        self.project_dir = project_dir
        print(f"Loading project from: {project_dir}")
        
        # Load project context
        self.project_context = self._load_project_files()
        
        # Load inspirations
        self.inspirations = self._load_inspirations()
        
        # Load all chapters
        self.all_chapters = self._load_all_chapters()
        
        # Extract project metadata
        self._extract_project_metadata()
        
        # Set target chapters
        self.target_chapters = {num: self.all_chapters[num] 
                               for num in target_chapters 
                               if num in self.all_chapters}
        
        if not self.target_chapters:
            raise ValueError(f"No valid chapters found from requested: {target_chapters}")
        
        print(f"Total chapters in novel: {len(self.all_chapters)}")
        print(f"Target chapters for revision: {sorted(self.target_chapters.keys())}")
        print(f"Genre: {self.genre}")
        print(f"Literary inspirations: {'Found' if self.inspirations else 'None'}")
    
    def _load_project_files(self) -> Dict[str, str]:
        """Load synopsis, outline, and character files."""
        files = {}
        
        project_files = {
            'synopsis': ['synopsis.md', 'synopsis.txt'],
            'outline': ['outline.md', 'outline.txt', 'Outline.md'],
            'characters': ['characters.md', 'characterList.md', 'characters.txt']
        }
        
        for file_type, possible_names in project_files.items():
            for name in possible_names:
                file_path = os.path.join(self.project_dir, name)
                if os.path.exists(file_path):
                    content = self._safe_read_file(file_path)
                    files[file_type] = content
                    print(f"  Found {file_type}: {name}")
                    break
            else:
                files[file_type] = ""
                print(f"  Missing {file_type}")
        
        return files
    
    def _load_inspirations(self) -> str:
        """Load literary inspirations."""
        inspiration_file = os.path.join(self.project_dir, "inspiration.md")
        if os.path.exists(inspiration_file):
            return self._safe_read_file(inspiration_file)
        return ""
    
    def _load_all_chapters(self) -> Dict[int, Dict[str, str]]:
        """Load all chapter files."""
        chapters = {}
        
        # Look for chapters in various directories
        chapter_dirs = ['chapters', 'content', 'manuscript', '.']
        
        for chapter_dir in chapter_dirs:
            search_dir = os.path.join(self.project_dir, chapter_dir)
            if not os.path.exists(search_dir):
                continue
            
            # Find chapter files
            patterns = [
                'chapter_*.md', 'chapter*.md', 'ch_*.md',
                '*_chapter_*.md', 'Chapter*.md', 'Ch*.md'
            ]
            
            for pattern in patterns:
                files = glob.glob(os.path.join(search_dir, pattern))
                for file_path in files:
                    # Skip revised/backup files
                    if any(skip in file_path.lower() for skip in ['enhanced', 'backup', 'revised']):
                        continue
                    
                    # Extract chapter number
                    chapter_num = self._extract_chapter_number(file_path)
                    if chapter_num is not None:
                        content = self._safe_read_file(file_path)
                        if content:
                            chapters[chapter_num] = {
                                'file_path': file_path,
                                'content': content,
                                'word_count': len(content.split())
                            }
        
        return chapters
    
    def _extract_chapter_number(self, file_path: str) -> Optional[int]:
        """Extract chapter number from filename."""
        filename = os.path.basename(file_path)
        
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
    
    def _extract_project_metadata(self):
        """Extract project metadata from context."""
        if self.project_context.get('synopsis'):
            synopsis = self.project_context['synopsis']
            if any(word in synopsis.lower() for word in ['spy', 'intelligence', 'espionage']):
                self.genre = "Literary Spy Fiction"
            elif any(word in synopsis.lower() for word in ['mystery', 'detective']):
                self.genre = "Literary Mystery"
        
        # Extract title if available
        if 'title' in self.project_context.get('synopsis', '').lower():
            lines = self.project_context['synopsis'].split('\n')
            for line in lines:
                if 'title' in line.lower() or line.startswith('#'):
                    potential_title = re.sub(r'^#+\s*|title:\s*', '', line, flags=re.IGNORECASE).strip()
                    if potential_title and len(potential_title) < 100:
                        self.novel_title = potential_title
                        break
    
    def _get_model_for_task(self, task_complexity: str = "medium") -> str:
        """Get appropriate model based on task complexity."""
        if not self.use_cost_effective_model:
            return "claude-opus-4-20250514"
        
        model_map = {
            "simple": "claude-3-5-sonnet-20241022",
            "medium": "claude-3-5-sonnet-20241022",
            "complex": "claude-opus-4-20250514",
        }
        return model_map.get(task_complexity, "claude-opus-4-20250514")
    
    def analyze_target_chapters(self) -> Dict[int, str]:
        """Analyze target chapters in context of the novel."""
        print(f"\nAnalyzing {len(self.target_chapters)} target chapters...")
        
        analyses = {}
        
        for chapter_num in sorted(self.target_chapters.keys()):
            print(f"  Analyzing Chapter {chapter_num}...")
            
            # Check if analysis exists
            analysis_file = os.path.join(self.project_dir, f"chapter_{chapter_num}_analysis.md")
            if os.path.exists(analysis_file):
                print(f"    Using existing analysis")
                analyses[chapter_num] = self._safe_read_file(analysis_file)
            else:
                analysis = self._analyze_single_chapter(chapter_num)
                analyses[chapter_num] = analysis
                
                # Save analysis
                self._save_analysis(analysis, f"chapter_{chapter_num}_analysis.md", chapter_num)
        
        return analyses
    
    def _analyze_single_chapter(self, chapter_num: int) -> str:
        """Analyze a single chapter in novel context."""
        chapter = self.target_chapters[chapter_num]
        
        # Get context chapters (2 before, 2 after)
        context_chapters = []
        for i in range(chapter_num - 2, chapter_num + 3):
            if i != chapter_num and i in self.all_chapters:
                preview = self.all_chapters[i]['content'][:500] + "..."
                context_chapters.append(f"Chapter {i} (preview): {preview}")
        
        prompt = f"""Analyze Chapter {chapter_num} of this {self.genre} novel for revision opportunities.

NOVEL CONTEXT:
Title: {self.novel_title}
Genre: {self.genre}
Total Chapters: {len(self.all_chapters)}

LITERARY INSPIRATIONS:
{self.inspirations if self.inspirations else "None specified"}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', '')}
OUTLINE: {self.project_context.get('outline', '')}
CHARACTERS: {self.project_context.get('characters', '')}

SURROUNDING CHAPTERS:
{chr(10).join(context_chapters)}

CHAPTER {chapter_num} TO ANALYZE ({chapter['word_count']} words):
{chapter['content']}

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

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("medium"),
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error analyzing chapter {chapter_num}: {e}"
    
    def create_revision_plans(self, analyses: Dict[int, str]) -> Dict[int, str]:
        """Create revision plans for target chapters."""
        print(f"\nCreating revision plans for {len(self.target_chapters)} chapters...")
        
        revision_plans = {}
        
        # Create revision plans directory
        plans_dir = os.path.join(self.project_dir, "revision_plans")
        os.makedirs(plans_dir, exist_ok=True)
        
        for chapter_num in sorted(self.target_chapters.keys()):
            print(f"  Creating plan for Chapter {chapter_num}...")
            
            # Check if plan exists
            plan_filename = f"chapter_{chapter_num:02d}_revision_plan.md"
            plan_path = os.path.join(plans_dir, plan_filename)
            
            if os.path.exists(plan_path):
                print(f"    Using existing plan")
                content = self._safe_read_file(plan_path)
                revision_plans[chapter_num] = content
            else:
                plan = self._create_chapter_plan(chapter_num, analyses[chapter_num])
                revision_plans[chapter_num] = plan
                
                # Save plan
                plan_content = f"# REVISION PLAN FOR CHAPTER {chapter_num}\n\n"
                plan_content += f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                plan_content += f"**Original word count:** {self.target_chapters[chapter_num]['word_count']} words\n\n"
                plan_content += "---\n\n"
                plan_content += plan
                
                self._safe_write_file(plan_path, plan_content)
        
        return revision_plans
    
    def _create_chapter_plan(self, chapter_num: int, analysis: str) -> str:
        """Create revision plan for a single chapter."""
        chapter = self.target_chapters[chapter_num]
        target_words = int(chapter['word_count'] * 1.4)  # 40% expansion target
        
        prompt = f"""Create a detailed revision plan for Chapter {chapter_num} based on the analysis.

CHAPTER ANALYSIS:
{analysis}

LITERARY INSPIRATIONS:
{self.inspirations}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', '')}
OUTLINE: {self.project_context.get('outline', '')}
CHARACTERS: {self.project_context.get('characters', '')}

CURRENT WORD COUNT: {chapter['word_count']} words
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

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("medium"),
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error creating plan for chapter {chapter_num}: {e}"
    
    def revise_chapters(self, revision_plans: Dict[int, str]) -> Dict[int, str]:
        """Revise target chapters based on their plans."""
        print(f"\nRevising {len(self.target_chapters)} chapters...")
        
        revised_chapters = {}
        
        # Create revised directory
        revised_dir = os.path.join(self.project_dir, "revised")
        os.makedirs(revised_dir, exist_ok=True)
        
        for chapter_num in sorted(self.target_chapters.keys()):
            print(f"  Revising Chapter {chapter_num}...")
            
            # Check if revised version exists
            original_filename = os.path.basename(self.target_chapters[chapter_num]['file_path'])
            base_name = os.path.splitext(original_filename)[0]
            revised_filename = f"{base_name}_revised.md"
            revised_path = os.path.join(revised_dir, revised_filename)
            
            if os.path.exists(revised_path):
                print(f"    Using existing revised chapter")
                revised_content = self._safe_read_file(revised_path)
                revised_chapters[chapter_num] = revised_content
            else:
                revised_content = self._revise_single_chapter(
                    chapter_num, 
                    revision_plans[chapter_num]
                )
                revised_chapters[chapter_num] = revised_content
                
                # Save revised chapter
                self._safe_write_file(revised_path, revised_content)
            
            # Report progress
            original_words = self.target_chapters[chapter_num]['word_count']
            revised_words = len(revised_content.split())
            print(f"    Words: {original_words} -> {revised_words} ({revised_words/original_words:.1f}x)")
        
        return revised_chapters
    
    def _revise_single_chapter(self, chapter_num: int, revision_plan: str) -> str:
        """Revise a single chapter based on its plan."""
        chapter = self.target_chapters[chapter_num]
        original_word_count = chapter['word_count']
        target_word_count = int(original_word_count * 1.4)
        
        prompt = f"""Revise Chapter {chapter_num} following the revision plan exactly.

REVISION PLAN TO IMPLEMENT:
{revision_plan}

LITERARY INSPIRATIONS:
{self.inspirations}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', '')}
OUTLINE: {self.project_context.get('outline', '')}
CHARACTERS: {self.project_context.get('characters', '')}

CURRENT CHAPTER {chapter_num}:
{chapter['content']}

TARGET WORD COUNT: {target_word_count} words (current: {original_word_count} words)

CRITICAL REQUIREMENTS:
1. Implement EVERY task in the revision plan
2. Expand to approximately {target_word_count} words
3. Maintain consistency with novel context
4. Enhance literary quality throughout
5. Complete the entire chapter without truncation

EXPANSION FOCUS:
- Character interiority and development
- Atmospheric and sensory details
- Dialogue depth and subtext
- Thematic elements
- Scene development

Return ONLY the complete revised chapter text."""

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("complex"),
                max_tokens=60000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            revised_text = response.content[0].text
            cleaned_text = self._clean_ai_commentary(revised_text)
            
            # Check word count
            revised_word_count = len(cleaned_text.split())
            if revised_word_count < original_word_count * 0.9:
                print(f"    Warning: Chapter shortened. Attempting expansion...")
                cleaned_text = self._expand_chapter(cleaned_text, revision_plan, target_word_count)
            
            return cleaned_text
            
        except Exception as e:
            print(f"    Error revising chapter {chapter_num}: {e}")
            return chapter['content']
    
    def _expand_chapter(self, content: str, revision_plan: str, target_words: int) -> str:
        """Expand a chapter if it was shortened."""
        current_words = len(content.split())
        
        prompt = f"""The chapter needs further expansion. Add the missing elements from the revision plan.

CURRENT REVISED CHAPTER ({current_words} words):
{content}

REVISION PLAN ELEMENTS TO ENSURE:
{revision_plan}

TARGET: {target_words} words

Expand by adding:
1. Character development moments
2. Atmospheric descriptions
3. Dialogue with subtext
4. Thematic elements
5. Sensory details

Return the complete expanded chapter."""

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("medium"),
                max_tokens=60000,
                messages=[{"role": "user", "content": prompt}]
            )
            return self._clean_ai_commentary(response.content[0].text)
        except Exception as e:
            print(f"    Error expanding chapter: {e}")
            return content
    
    def generate_report(self, analyses: Dict[int, str], revision_plans: Dict[int, str], 
                       revised_chapters: Dict[int, str]) -> str:
        """Generate comprehensive revision report."""
        print("\nGenerating revision report...")
        
        # Calculate statistics
        total_original_words = sum(ch['word_count'] for ch in self.target_chapters.values())
        total_revised_words = sum(len(ch.split()) for ch in revised_chapters.values())
        
        chapter_details = []
        for chapter_num in sorted(self.target_chapters.keys()):
            original = self.target_chapters[chapter_num]['word_count']
            revised = len(revised_chapters[chapter_num].split())
            chapter_details.append(
                f"- Chapter {chapter_num}: {original:,} → {revised:,} words "
                f"({revised/original:.1f}x expansion)"
            )
        
        report = f"""# Chapter Revision Report

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Project:** {self.novel_title}
**Genre:** {self.genre}
**Chapters Revised:** {sorted(self.target_chapters.keys())}

## Summary

Revised {len(self.target_chapters)} chapters out of {len(self.all_chapters)} total chapters in the novel.

**Word Count Changes:**
- Total Original: {total_original_words:,} words
- Total Revised: {total_revised_words:,} words
- Overall Expansion: {total_revised_words/total_original_words:.1f}x

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

### Analysis Files
{chr(10).join(f"- `chapter_{num}_analysis.md`" for num in sorted(self.target_chapters.keys()))}

### Revision Plans
{chr(10).join(f"- `revision_plans/chapter_{num:02d}_revision_plan.md`" for num in sorted(self.target_chapters.keys()))}

### Revised Chapters
{chr(10).join(f"- `revised/{os.path.splitext(os.path.basename(self.target_chapters[num]['file_path']))[0]}_revised.md`" for num in sorted(self.target_chapters.keys()))}

### Report
- `chapter_revision_report.md` - This summary report

## Next Steps

1. Review the revised chapters for alignment with your vision
2. Consider revising adjacent chapters for better flow
3. Update the novel outline to reflect changes
4. Run a full novel alignment check if significant changes were made

## Notes

The revision process maintained the context of the full novel while focusing on the selected chapters. Each revised chapter should now better serve its role in the overall narrative while demonstrating enhanced literary quality.
"""
        
        # Save report
        report_path = os.path.join(self.project_dir, "chapter_revision_report.md")
        self._safe_write_file(report_path, report)
        print(f"Report saved: {report_path}")
        
        return report
    
    def _clean_ai_commentary(self, text: str) -> str:
        """Remove any AI commentary from text."""
        patterns = [
            r'\[.*?\]',
            r'Would you like.*?\?',
            r'I can .*?\.',
            r'Note:.*?\.',
            r'Commentary:.*?\.'
        ]
        
        cleaned = text
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        return re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned).strip()
    
    def _save_analysis(self, content: str, filename: str, chapter_num: int = None) -> bool:
        """Save analysis to file."""
        output_path = os.path.join(self.project_dir, filename)
        
        file_content = f"# {filename.replace('_', ' ').replace('.md', '').title()}\n\n"
        file_content += f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        if chapter_num:
            file_content += f"**Chapter:** {chapter_num}\n\n"
        file_content += "---\n\n"
        file_content += content
        
        return self._safe_write_file(output_path, file_content)

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Selective chapter revision tool based on novel_reviser",
        epilog="""
Examples:
  # Revise single chapter
  python chapter_reviser.py mynovel --chapters 5
  
  # Revise multiple chapters
  python chapter_reviser.py mynovel --chapters 3,5,7,9
  
  # Revise chapter range
  python chapter_reviser.py mynovel --chapters 10-15
  
  # Analysis only
  python chapter_reviser.py mynovel --chapters 5 --analysis-only
  
  # Use existing analyses
  python chapter_reviser.py mynovel --chapters 5 --revisions-only
        """
    )
    
    parser.add_argument(
        "project_dir",
        help="Project directory containing the novel"
    )
    parser.add_argument(
        "--chapters",
        required=True,
        help="Chapters to revise (e.g., '5' or '3,5,7' or '10-15')"
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Only analyze chapters, don't create revision plans or revise"
    )
    parser.add_argument(
        "--revisions-only",
        action="store_true",
        help="Skip analysis, use existing files"
    )
    parser.add_argument(
        "--cost-optimize",
        action="store_true",
        help="Use cost-optimized approach (Sonnet for most tasks)"
    )
    
    args = parser.parse_args()
    
    # Parse chapter specification
    target_chapters = []
    chapter_spec = args.chapters.strip()
    
    try:
        if '-' in chapter_spec:
            # Range specification
            start, end = chapter_spec.split('-')
            target_chapters = list(range(int(start), int(end) + 1))
        elif ',' in chapter_spec:
            # List specification
            target_chapters = [int(ch.strip()) for ch in chapter_spec.split(',')]
        else:
            # Single chapter
            target_chapters = [int(chapter_spec)]
    except ValueError:
        print(f"Error: Invalid chapter specification '{args.chapters}'")
        print("Use formats: '5' or '3,5,7' or '10-15'")
        return 1
    
    # Set console encoding for Windows
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass
    
    # Initialize reviser
    try:
        reviser = ChapterReviser()
        
        # Configure cost optimization
        if args.cost_optimize:
            reviser.use_cost_effective_model = True
            print("Using cost-optimized approach")
        else:
            reviser.use_cost_effective_model = False
            print("Using premium models for highest quality")
            
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        return 1
    
    try:
        print(f"Starting chapter revision for: {args.project_dir}")
        print(f"Target chapters: {target_chapters}")
        print("="*60)
        
        # Load project
        reviser.load_project(args.project_dir, target_chapters)
        
        # Step 1: Analyze chapters
        if not args.revisions_only:
            analyses = reviser.analyze_target_chapters()
            
            if args.analysis_only:
                print("\nAnalysis complete. Check the generated analysis files.")
                return 0
        else:
            # Load existing analyses
            analyses = {}
            for chapter_num in target_chapters:
                analysis_file = os.path.join(args.project_dir, f"chapter_{chapter_num}_analysis.md")
                if os.path.exists(analysis_file):
                    analyses[chapter_num] = reviser._safe_read_file(analysis_file)
                else:
                    print(f"Warning: No analysis found for Chapter {chapter_num}")
            
            if not analyses:
                print("No existing analyses found. Run without --revisions-only first.")
                return 1
        
        # Step 2: Create revision plans
        revision_plans = reviser.create_revision_plans(analyses)
        
        # Step 3: Revise chapters
        revised_chapters = reviser.revise_chapters(revision_plans)
        
        # Step 4: Generate report
        reviser.generate_report(analyses, revision_plans, revised_chapters)
        
        print("\n" + "="*60)
        print("CHAPTER REVISION COMPLETE!")
        print("="*60)
        print(f"Processed: {len(target_chapters)} chapters")
        print(f"Created: Analyses, revision plans, and revised chapters")
        print(f"Report: chapter_revision_report.md")
        print(f"Location: {args.project_dir}")
        
        return 0
        
    except Exception as e:
        print(f"Error during chapter revision: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())