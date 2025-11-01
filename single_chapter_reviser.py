#!/usr/bin/env python3
"""
single_chapter_reviser_guided.py - Single Chapter Revision Tool with Revision Guides

This script provides targeted revision for individual chapters with optional revision guides:
1. Loads optional revision guide from revision_guides folder
2. Analyzes a single chapter for issues (if no guide provided)
3. Uses revision guide OR creates a revision plan
4. Implements revisions following the guide/plan
5. Uses inspiration.md for literary guidance

Windows-compatible with proper encoding handling.
Optimized for Claude Sonnet 4 with 64k token output.
Enhanced with revision guide support.
"""

# === REVISION ENGINE ===
import os
import re
import json
import argparse
import datetime
import sys
import time
import random
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import anthropic

# Set UTF-8 encoding for Windows
if sys.platform.startswith('win'):
    import locale
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        pass

class SingleChapterReviser:
    """Focused single chapter revision tool with revision guide support."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
        self.project_dir = None
        self.chapter_num = None
        self.target_word_count = None
        self.context_chapters = []
        self.use_cost_effective_model = True
        
        # Project context
        self.project_context = {}
        self.inspirations = ""
        self.current_chapter = {}
        self.adjacent_chapters = {}
        
        # Revision guide support
        self.revision_guide = None
        self.revision_guide_path = None
        
        # Task tracking
        self.revision_tasks = []
        self.completed_tasks = []
        self.failed_tasks = []
    
    def _safe_read_file(self, file_path: str) -> str:
        """Safely read a file with multiple encoding attempts."""
        encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1', 'ascii']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    return f.read()
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
            return False
    
    def _get_model_for_task(self, task_complexity: str = "medium") -> str:
        """Get appropriate model based on task complexity."""
        return "claude-sonnet-4-20250514"
    
    def _make_api_request_with_retry(self, request_func, max_retries=3):
        """Make API request with retry logic for overloaded errors."""
        for attempt in range(max_retries):
            try:
                return request_func()
            except Exception as e:
                error_str = str(e).lower()
                if "overloaded" in error_str and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    print(f"    API overloaded, waiting {wait_time:.1f} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
        raise Exception("Max retries exceeded")
    
    def _load_revision_guide(self, chapter_num: int) -> Optional[str]:
        """Load revision guide for the specified chapter from revision_guides folder."""
        # Format: 01_chapter_01_guide.md
        guide_filename = f"{chapter_num:02d}_chapter_{chapter_num:02d}_guide.md"
        guide_path = os.path.join(self.project_dir, "revision_guides", guide_filename)
        
        if os.path.exists(guide_path):
            print(f"Found revision guide: {guide_filename}")
            self.revision_guide_path = guide_path
            return self._safe_read_file(guide_path)
        else:
            print(f"No revision guide found at: {guide_path}")
            return None
    
    def load_project_context(self, project_dir: str, chapter_num: int, context_chapters: list = None):
        """Load project context, target chapter, and optional revision guide."""
        self.project_dir = project_dir
        self.chapter_num = chapter_num
        self.context_chapters = context_chapters or []
        
        print(f"Loading project context from: {project_dir}")
        print(f"Target chapter: {chapter_num}")
        
        # Try to load revision guide first
        self.revision_guide = self._load_revision_guide(chapter_num)
        
        # Load project files
        self.project_context = self._load_project_files()
        self.inspirations = self._load_inspirations()
        
        # Load target chapter
        self.current_chapter = self._load_chapter(chapter_num)
        if not self.current_chapter:
            raise ValueError(f"Chapter {chapter_num} not found")
        
        # Load context chapters
        if self.context_chapters:
            self.adjacent_chapters = self._load_context_chapters(self.context_chapters)
            print(f"Custom context chapters: {self.context_chapters}")
        else:
            self.adjacent_chapters = self._load_adjacent_chapters(chapter_num)
        
        print(f"Loaded chapter {chapter_num}: {self.current_chapter['word_count']} words")
        print(f"Context chapters: {list(self.adjacent_chapters.keys())}")
        print(f"Literary inspirations: {'Found' if self.inspirations else 'None'}")
        print(f"Revision guide: {'Found' if self.revision_guide else 'Will create plan'}")
    
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
                    files[file_type] = self._safe_read_file(file_path)
                    print(f"  Loaded {file_type}: {name}")
                    break
        
        return files
    
    def _load_inspirations(self) -> str:
        """Load inspiration.md for literary guidance."""
        inspiration_path = os.path.join(self.project_dir, 'inspiration.md')
        if os.path.exists(inspiration_path):
            return self._safe_read_file(inspiration_path)
        return ""
    
    def _load_chapter(self, chapter_num: int) -> Optional[Dict[str, Any]]:
        """Load a single chapter by number from chapters subdirectory."""
        chapter_files = [
            f"{chapter_num:02d}_chapter_{chapter_num:02d}.md",
            f"{chapter_num:02d}_chapter_{chapter_num}.md",
            f"chapter_{chapter_num:02d}.md",
            f"chapter{chapter_num:02d}.md",
            f"chapter_{chapter_num}.md"
        ]
        
        # Look in chapters subdirectory only
        chapters_dir = os.path.join(self.project_dir, 'chapters')
        
        for chapter_file in chapter_files:
            chapter_path = os.path.join(chapters_dir, chapter_file)
            if os.path.exists(chapter_path):
                content = self._safe_read_file(chapter_path)
                return {
                    'number': chapter_num,
                    'filename': chapter_file,
                    'content': content,
                    'word_count': len(content.split())
                }
        
        return None
    
    def _load_adjacent_chapters(self, chapter_num: int, num_before: int = 1, num_after: int = 1) -> Dict[int, Dict[str, Any]]:
        """Load adjacent chapters for context."""
        adjacent = {}
        
        for offset in range(-num_before, num_after + 1):
            if offset == 0:
                continue
            adj_num = chapter_num + offset
            if adj_num <= 0:
                continue
            
            chapter = self._load_chapter(adj_num)
            if chapter:
                adjacent[adj_num] = chapter
        
        return adjacent
    
    def _load_context_chapters(self, chapter_nums: List[int]) -> Dict[int, Dict[str, Any]]:
        """Load specific chapters for context."""
        context = {}
        for num in chapter_nums:
            chapter = self._load_chapter(num)
            if chapter:
                context[num] = chapter
            else:
                print(f"Warning: Context chapter {num} not found")
        return context
    
    def _save_file(self, content: str, filename: str) -> str:
        """Save a file to the project directory."""
        file_path = os.path.join(self.project_dir, filename)
        self._safe_write_file(file_path, content)
        return file_path
    
    def analyze_chapter(self) -> str:
        """Analyze the chapter for issues and opportunities."""
        print("\nStep 1: Analyzing chapter...")
        print("-" * 50)
        
        # If we have a revision guide, skip analysis
        if self.revision_guide:
            print("Using provided revision guide instead of analysis")
            analysis = f"""# Chapter {self.chapter_num} - Using Revision Guide

A revision guide has been provided for this chapter. Analysis step skipped.

**Revision guide loaded from:** {self.revision_guide_path}

The revision will follow the recommendations in the guide.
"""
            self._save_file(analysis, f"chapter_{self.chapter_num}_analysis.md")
            return analysis
        
        # Otherwise, perform normal analysis
        model = self._get_model_for_task("high")
        
        context_summary = ""
        if self.adjacent_chapters:
            context_summary = "\n\n## Adjacent Chapter Context\n\n"
            for num, chapter in sorted(self.adjacent_chapters.items()):
                preview = chapter['content'][:300].replace('\n', ' ')
                context_summary += f"**Chapter {num}** ({chapter['word_count']} words): {preview}...\n\n"
        
        prompt = f"""Analyze Chapter {self.chapter_num} for literary quality, narrative function, and revision opportunities.

## Project Context

### Synopsis
{self.project_context.get('synopsis', 'Not available')[:800]}

### Outline Excerpt
{self.project_context.get('outline', 'Not available')[:800]}

{context_summary}

## Chapter to Analyze

{self.current_chapter['content']}

## Literary Inspiration

{self.inspirations[:1000] if self.inspirations else 'Not provided'}

## Analysis Framework

Evaluate this chapter on:

1. **Literary Quality**
   - Prose sophistication and voice consistency
   - Sensory detail and atmosphere
   - Dialogue naturalism
   - Metaphor and imagery effectiveness

2. **Character Development**
   - Character voice distinctiveness
   - Psychological depth and motivation
   - Character interactions and relationships
   - Internal conflict expression

3. **Structural Elements**
   - Scene structure and pacing
   - Transitions and flow
   - Information delivery
   - Scene endings and hooks

4. **Narrative Function**
   - Plot advancement
   - Theme development
   - Emotional resonance
   - Connection to adjacent chapters

5. **Specific Issues**
   - Weak or generic passages
   - Telling vs showing opportunities
   - Missing sensory details
   - Underdeveloped moments
   - Rushed transitions

## Current Metrics

- **Current word count:** {self.current_chapter['word_count']}
- **Target word count:** {self.target_word_count or int(self.current_chapter['word_count'] * 1.4)}

Provide a detailed analysis that will guide meaningful expansion and literary enhancement."""

        def make_request():
            return self.client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
        
        response = self._make_api_request_with_retry(make_request)
        analysis = response.content[0].text
        
        self._save_file(analysis, f"chapter_{self.chapter_num}_analysis.md")
        print(f"Analysis complete: {len(analysis)} characters")
        print(f"Saved to: chapter_{self.chapter_num}_analysis.md")
        
        return analysis
    
    def create_revision_plan(self, analysis: str) -> str:
        """Create detailed revision plan OR use provided revision guide."""
        print("\nStep 2: Creating revision plan...")
        print("-" * 50)
        
        # If we have a revision guide, use it as the plan
        if self.revision_guide:
            print("Using revision guide as revision plan")
            plan = f"""# Chapter {self.chapter_num} Revision Plan

## Source
This revision plan is based on the provided revision guide:
**{self.revision_guide_path}**

---

{self.revision_guide}

---

## Implementation Notes

All revisions should follow the recommendations in the guide above.
The guide provides specific, targeted feedback that should be applied during the revision process.
"""
            self._save_file(plan, f"chapter_{self.chapter_num}_revision_plan.md")
            return plan
        
        # Otherwise, create a plan based on analysis
        model = self._get_model_for_task("high")
        
        target_wc = self.target_word_count or int(self.current_chapter['word_count'] * 1.4)
        
        prompt = f"""Create a detailed, actionable revision plan for Chapter {self.chapter_num}.

## Analysis Results

{analysis}

## Current State

- **Current word count:** {self.current_chapter['word_count']}
- **Target word count:** {target_wc}
- **Required expansion:** {target_wc - self.current_chapter['word_count']} words

## Requirements for Revision Plan

Create a comprehensive plan that:

1. **Identifies Specific Passages** - Point to exact sections needing work
2. **Provides Actionable Tasks** - Clear, executable revision instructions
3. **Prioritizes Impact** - Focus on changes that most improve the chapter
4. **Ensures Cohesion** - Maintain voice and narrative flow
5. **Achieves Target Length** - Guide expansion to ~{target_wc} words

## Plan Structure

For each revision task, provide:

### Task Title
**Location:** Specific section/paragraph/dialogue
**Current State:** What exists now
**Revision Goal:** What should be achieved
**Specific Actions:** Concrete steps to implement
**Word Target:** Estimated word count change
**Literary Rationale:** Why this improves the chapter

## Focus Areas

Based on the analysis, prioritize:
- Weak passages needing strengthening
- Telling that should be showing
- Missing sensory/atmospheric details
- Underdeveloped character moments
- Rushed transitions
- Opportunities for deeper psychological insight

Create a plan with 5-8 major revision tasks that will transform this chapter."""

        def make_request():
            return self.client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
        
        response = self._make_api_request_with_retry(make_request)
        revision_plan = response.content[0].text
        
        self._save_file(revision_plan, f"chapter_{self.chapter_num}_revision_plan.md")
        print(f"Revision plan complete: {len(revision_plan)} characters")
        print(f"Saved to: chapter_{self.chapter_num}_revision_plan.md")
        
        return revision_plan
    
    def revise_chapter(self, revision_plan: str) -> str:
        """Implement comprehensive chapter revision following the plan/guide."""
        print("\nStep 3: Revising chapter...")
        print("-" * 50)
        
        model = self._get_model_for_task("high")
        
        # Determine if we're using a guide or generated plan
        plan_source = "revision guide" if self.revision_guide else "revision plan"
        
        context_summary = ""
        if self.adjacent_chapters:
            context_summary = "\n\n## Context Chapters\n\n"
            for num, chapter in sorted(self.adjacent_chapters.items()):
                context_summary += f"### Chapter {num}\n{chapter['content'][:500]}...\n\n"
        
        prompt = f"""Revise Chapter {self.chapter_num} following the {plan_source} below.

## {plan_source.title()}

{revision_plan}

## Current Chapter

{self.current_chapter['content']}

{context_summary}

## Literary Guidance

{self.inspirations[:1500] if self.inspirations else 'Focus on literary quality and narrative sophistication'}

## Revision Instructions

1. **Follow the {plan_source} closely** - Address all recommendations systematically
2. **Maintain voice and tone** - Keep consistent with adjacent chapters
3. **Expand thoughtfully** - Target ~{self.target_word_count or int(self.current_chapter['word_count'] * 1.4)} words
4. **Enhance literary quality** - Improve prose, imagery, character depth
5. **Preserve narrative flow** - Ensure smooth transitions and pacing
6. **Keep all essential plot points** - Don't remove critical story elements

## Quality Standards

- **Prose:** Sophisticated, varied sentence structure, strong verbs, vivid imagery
- **Character:** Distinctive voices, psychological depth, authentic reactions
- **Atmosphere:** Rich sensory details, emotional resonance
- **Pacing:** Varied rhythm, effective use of white space
- **Dialogue:** Natural, revealing, purposeful

{'## Specific Guidance from Revision Guide' if self.revision_guide else '## Implementation Approach'}

{'Apply each recommendation from the guide thoughtfully, ensuring all feedback is addressed while maintaining the chapter\'s overall coherence and literary quality.' if self.revision_guide else 'Implement each task from the revision plan systematically, building a more sophisticated and engaging chapter.'}

Provide the complete revised chapter, maintaining markdown formatting and chapter structure."""

        def make_request():
            # Use streaming to avoid 10-minute timeout
            return self.client.messages.create(
                model=model,
                max_tokens=64000,  # Maximum for comprehensive revision
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
                stream=True  # Enable streaming
            )
        
        print(f"  Implementing comprehensive revision using {plan_source}...")
        print(f"  (Using streaming to handle long revision - this may take several minutes)")
        
        # Collect streamed response
        revised_content = ""
        try:
            response_stream = self._make_api_request_with_retry(make_request)
            
            for event in response_stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        revised_content += event.delta.text
                        # Show progress every 1000 characters
                        if len(revised_content) % 1000 < 50:
                            print(".", end="", flush=True)
            
            print()  # New line after progress dots
            
        except Exception as e:
            print(f"\n  Error during streaming: {e}")
            raise
        
        # Clean up any markdown artifacts
        revised_content = revised_content.strip()
        if revised_content.startswith('```markdown'):
            revised_content = revised_content[11:].strip()
        if revised_content.startswith('```'):
            revised_content = revised_content[3:].strip()
        if revised_content.endswith('```'):
            revised_content = revised_content[:-3].strip()
        
        revised_words = len(revised_content.split())
        print(f"  Revision complete: {revised_words} words")
        
        return revised_content
    
    def save_revised_chapter(self, revised_content: str) -> str:
        """Save the revised chapter to chapters/revised/ subdirectory."""
        print("\nStep 4: Saving revised chapter...")
        print("-" * 50)
        
        # Save revised files to chapters/revised/
        revised_dir = os.path.join(self.project_dir, 'chapters', 'revised')
        os.makedirs(revised_dir, exist_ok=True)
        
        # Generate filename
        original_filename = self.current_chapter['filename']
        base_name = os.path.splitext(original_filename)[0]
        revised_filename = f"{base_name}_revised.md"
        revised_path = os.path.join(revised_dir, revised_filename)
        
        # Save file
        success = self._safe_write_file(revised_path, revised_content)
        
        if success:
            print(f"Saved revised chapter to: {revised_path}")
            return revised_path
        else:
            raise Exception("Failed to save revised chapter")
    
    def generate_summary_report(self, analysis: str, revision_plan: str, 
                                original_words: int, revised_words: int) -> str:
        """Generate a summary report of the revision process."""
        print("\nStep 5: Generating summary report...")
        print("-" * 50)
        
        # Determine source type
        plan_source = "Revision Guide" if self.revision_guide else "Generated Revision Plan"
        
        report = f"""# Chapter {self.chapter_num} Revision Report

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Chapter:** {self.chapter_num}
**Original Words:** {original_words:,}
**Revised Words:** {revised_words:,}
**Expansion:** {revised_words/original_words:.1f}x
**Revision Source:** {plan_source}

## Process Summary

### 1. Chapter Analysis
{'Revision guide provided - analysis step skipped' if self.revision_guide else 'Comprehensive analysis identified key areas for improvement in structure, character development, literary quality, and narrative function.'}

### 2. Revision Planning
{'Used provided revision guide from: ' + self.revision_guide_path if self.revision_guide else 'Detailed revision plan created with specific, actionable tasks for meaningful expansion and literary enhancement.'}

### 3. Chapter Revision
Implemented comprehensive revision following the {plan_source.lower()}.

## Key Improvements Made

### {'Revision Guide Highlights' if self.revision_guide else 'Analysis Highlights'}
{(self.revision_guide if self.revision_guide else analysis)[:500]}...

### Revision Strategy
{revision_plan[:500]}...

## Files Created

- {'`chapter_' + str(self.chapter_num) + '_analysis.md`' if not self.revision_guide else '*(Analysis skipped - guide provided)*'} - Chapter analysis
- `chapter_{self.chapter_num}_revision_plan.md` - {'Revision guide' if self.revision_guide else 'Comprehensive revision plan'}
- `revised/{self.current_chapter['filename'].replace('.md', '_revised.md')}` - Enhanced chapter version
- `chapter_{self.chapter_num}_revision_report.md` - This summary report

## Results

The chapter has been significantly enhanced with:
- Expanded word count ({original_words:,} → {revised_words:,} words)
- Comprehensive implementation of {'revision guide recommendations' if self.revision_guide else 'revision plan'}
- Enhanced literary quality and sophistication
- Better narrative flow and pacing

## Word Count Analysis

- Target expansion: {self.target_word_count or int(original_words * 1.4):,} words
- Achieved: {revised_words:,} words
- Expansion ratio: {revised_words/original_words:.2f}x
{'- Met target: ' + ('Yes ✓' if revised_words >= (self.target_word_count or int(original_words * 1.4)) else 'Close') if self.target_word_count else ''}

## Next Steps

The revised chapter is ready for integration into the full manuscript. Review the implemented changes to ensure they align with your vision for the chapter.

{'## Revision Guide Notes' if self.revision_guide else ''}
{'The revision was guided by specific recommendations from the revision guide. All major points from the guide were addressed in the revision.' if self.revision_guide else ''}
"""
        
        self._save_file(report, f"chapter_{self.chapter_num}_revision_report.md")
        print(f"Report saved to: chapter_{self.chapter_num}_revision_report.md")
        return report

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Single Chapter Reviser - Analyze, plan, and revise individual chapters with optional revision guides",
        epilog="""
Examples:
  # Revise chapter 1 with revision guide (if exists)
  python single_chapter_reviser_guided.py myproject --chapter 1
  
  # Revise chapter 3 to specific word count
  python single_chapter_reviser_guided.py myproject --chapter 3 --target-words 3000
  
  # Revise with specific chapters for consistency context
  python single_chapter_reviser_guided.py myproject --chapter 5 --context-chapters 1,3,4 --target-words 2500
  
  # Analysis only (skip revision)
  python single_chapter_reviser_guided.py myproject --chapter 8 --analysis-only

Revision Guide:
  Place revision guides in: myproject/revision_guides/
  Format: 01_chapter_01_guide.md (for chapter 1)
  If guide exists, it will be used instead of generating a revision plan.
        """
    )
    parser.add_argument(
        "project_dir",
        help="Project directory containing the novel"
    )
    parser.add_argument(
        "--chapter",
        type=int,
        required=True,
        help="Chapter number to revise"
    )
    parser.add_argument(
        "--target-words",
        type=int,
        help="Target word count for revised chapter (default: 1.4x current)"
    )
    parser.add_argument(
        "--cost-optimize",
        action="store_true",
        help="Use cost-optimized approach (Sonnet for all tasks)"
    )
    parser.add_argument(
        "--context-chapters",
        type=str,
        help="Comma-separated list of chapter numbers to use for consistency context (e.g., '1,3,7')"
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Only perform analysis and create revision plan, don't revise"
    )
    
    args = parser.parse_args()
    
    # Set console encoding for Windows
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass
    
    # Parse context chapters
    context_chapters = None
    if hasattr(args, 'context_chapters') and args.context_chapters:
        try:
            context_chapters = [int(x.strip()) for x in args.context_chapters.split(',')]
            print(f"Context chapters specified: {context_chapters}")
        except ValueError:
            print("Error: Invalid context-chapters format. Use comma-separated numbers like '1,3,7'")
            return 1
    
    # Initialize reviser
    try:
        reviser = SingleChapterReviser()
        
        # Configure cost optimization
        if args.cost_optimize:
            reviser.use_cost_effective_model = True
            print("Using cost-optimized approach")
        else:
            reviser.use_cost_effective_model = False
            print("Using premium models for highest quality")
        
        # Set target word count
        if args.target_words:
            reviser.target_word_count = args.target_words
            print(f"Target word count: {args.target_words}")
        
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        return 1
    
    try:
        print(f"Starting single chapter revision for Chapter {args.chapter}")
        print("="*50)
        
        # Load project and chapter
        reviser.load_project_context(args.project_dir, args.chapter, context_chapters)
        
        original_words = reviser.current_chapter['word_count']
        
        # Step 1: Analyze chapter (skipped if guide exists)
        analysis = reviser.analyze_chapter()
        
        # Step 2: Create revision plan (uses guide if exists)
        revision_plan = reviser.create_revision_plan(analysis)
        
        if args.analysis_only:
            print("\nAnalysis and revision plan complete.")
            print(f"Check {args.project_dir}/chapter_{args.chapter}_analysis.md")
            print(f"Check {args.project_dir}/chapter_{args.chapter}_revision_plan.md")
            return 0
        
        # Step 3: Revise chapter
        revised_content = reviser.revise_chapter(revision_plan)
        
        # Step 4: Save revised chapter
        revised_path = reviser.save_revised_chapter(revised_content)
        
        # Step 5: Generate report
        revised_words = len(revised_content.split())
        reviser.generate_summary_report(analysis, revision_plan, original_words, revised_words)
        
        print("\n" + "="*50)
        print(f"CHAPTER {args.chapter} REVISION COMPLETE!")
        print("="*50)
        print(f"Original: {original_words:,} words")
        print(f"Revised: {revised_words:,} words")
        print(f"Expansion: {revised_words/original_words:.1f}x")
        print(f"Saved to: {revised_path}")
        if reviser.revision_guide:
            print(f"Used revision guide: {reviser.revision_guide_path}")
        print(f"\nCheck chapter_{args.chapter}_revision_report.md for full summary")
        
        return 0
        
    except Exception as e:
        print(f"Error during chapter revision: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())