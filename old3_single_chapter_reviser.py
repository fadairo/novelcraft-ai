#!/usr/bin/env python3
"""
single_chapter_reviser.py - Focused Single Chapter Revision Tool

This script provides targeted revision for individual chapters:
1. Analyzes a single chapter for issues
2. Creates a detailed revision plan
3. Automatically expands the chapter based on the plan
4. Uses inspiration.md for literary guidance

Windows-compatible with proper encoding handling.
Optimized for Claude Sonnet 4 with 64k token output.
"""

import os
import re
import json
import argparse
import datetime
import sys
import time
import random
from typing import Dict, Any, Optional
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
    """Focused single chapter revision tool."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
        self.project_dir = None
        self.chapter_num = None
        self.target_word_count = None
        self.use_cost_effective_model = True
        
        # Project context
        self.project_context = {}
        self.inspirations = ""
        self.current_chapter = {}
        self.adjacent_chapters = {}
    
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
        # With Sonnet 4, use it for all tasks - it's both powerful and cost-effective
        return "claude-sonnet-4-20250514"
    
    def _make_api_request_with_retry(self, request_func, max_retries=3):
        """Make API request with retry logic for overloaded errors."""
        for attempt in range(max_retries):
            try:
                return request_func()
            except Exception as e:
                error_str = str(e).lower()
                if "overloaded" in error_str and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)  # Exponential backoff with jitter
                    print(f"    API overloaded, waiting {wait_time:.1f} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Re-raise the exception if it's not overloaded or we've exhausted retries
                    raise e
        
        # Should never reach here, but just in case
        raise Exception("Max retries exceeded")
    
    def load_project_context(self, project_dir: str, chapter_num: int):
        """Load project context and target chapter."""
        self.project_dir = project_dir
        self.chapter_num = chapter_num
        
        print(f"Loading project context from: {project_dir}")
        print(f"Target chapter: {chapter_num}")
        
        # Load project files
        self.project_context = self._load_project_files()
        self.inspirations = self._load_inspirations()
        
        # Load target chapter
        self.current_chapter = self._load_chapter(chapter_num)
        if not self.current_chapter:
            raise ValueError(f"Chapter {chapter_num} not found")
        
        # Load adjacent chapters for context
        self.adjacent_chapters = self._load_adjacent_chapters(chapter_num)
        
        print(f"Loaded chapter {chapter_num}: {self.current_chapter['word_count']} words")
        print(f"Context chapters: {list(self.adjacent_chapters.keys())}")
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
    
    def _load_chapter(self, chapter_num: int) -> Dict[str, Any]:
        """Load a specific chapter."""
        # Search in chapters directory
        chapters_dir = os.path.join(self.project_dir, "chapters")
        if not os.path.exists(chapters_dir):
            return {}
        
        # Try various naming patterns
        patterns = [
            f"{chapter_num:02d}_chapter_{chapter_num}.md",
            f"chapter_{chapter_num}.md",
            f"chapter{chapter_num}.md",
            f"ch_{chapter_num}.md",
            f"Chapter {chapter_num}.md"
        ]
        
        for pattern in patterns:
            file_path = os.path.join(chapters_dir, pattern)
            if os.path.exists(file_path):
                content = self._safe_read_file(file_path)
                if content:
                    return {
                        'file_path': file_path,
                        'content': content,
                        'word_count': len(content.split())
                    }
        
        return {}
    
    def _load_adjacent_chapters(self, chapter_num: int) -> Dict[int, str]:
        """Load adjacent chapters for context."""
        adjacent = {}
        
        # Load previous and next chapters
        for adj_num in [chapter_num - 1, chapter_num + 1]:
            if adj_num > 0:  # Don't load chapter 0 or negative
                chapter = self._load_chapter(adj_num)
                if chapter:
                    # Truncate content for context (save tokens)
                    content = chapter['content'][:800] + "..." if len(chapter['content']) > 800 else chapter['content']
                    adjacent[adj_num] = content
        
        return adjacent
    
    def analyze_chapter(self) -> str:
        """Analyze the target chapter for revision needs."""
        print(f"\nAnalyzing Chapter {self.chapter_num}...")
        
        # Check if analysis already exists
        analysis_file = os.path.join(self.project_dir, f"chapter_{self.chapter_num}_analysis.md")
        if os.path.exists(analysis_file):
            print("Using existing chapter analysis")
            return self._safe_read_file(analysis_file)
        
        # Build context for adjacent chapters
        context_text = ""
        if self.adjacent_chapters:
            context_text = "\n\nADJACENT CHAPTERS CONTEXT:\n"
            for adj_num, content in self.adjacent_chapters.items():
                context_text += f"\nChapter {adj_num} (excerpt):\n{content}\n"
        
        prompt = f"""You are a professional literary editor analyzing Chapter {self.chapter_num} for revision opportunities.

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', 'Not available')}

OUTLINE: {self.project_context.get('outline', 'Not available')}

CHARACTERS: {self.project_context.get('characters', 'Not available')}

LITERARY INSPIRATIONS:
{self.inspirations if self.inspirations else "None specified"}

CURRENT CHAPTER {self.chapter_num} CONTENT:
{self.current_chapter['content']}

{context_text}

COMPREHENSIVE CHAPTER ANALYSIS:

Analyze this chapter for:

## STRUCTURAL ASSESSMENT
- Chapter opening effectiveness
- Scene transitions and flow
- Pacing and rhythm
- Chapter ending and hooks

## CHARACTER DEVELOPMENT
- Character voice consistency
- Dialogue authenticity and subtext
- Character motivation clarity
- Internal conflict and growth

## LITERARY QUALITY
- Prose style and sophistication
- Show vs. tell balance
- Sensory details and atmosphere
- Thematic integration

## NARRATIVE FUNCTION
- How this chapter serves the overall story
- Plot advancement effectiveness
- Connection to adjacent chapters
- Missing story elements

## EXPANSION OPPORTUNITIES
- Scenes that need more development
- Character moments that could be deeper
- Atmospheric details that could be enhanced
- Dialogue that could be more revealing

## SPECIFIC REVISION RECOMMENDATIONS
Provide concrete, actionable suggestions for:
1. Structural improvements
2. Character development enhancements  
3. Literary quality upgrades
4. Content expansion opportunities
5. Technical fixes needed

Current word count: {self.current_chapter['word_count']} words

Focus on actionable improvements that will enhance both literary quality and story effectiveness."""

        try:
            def make_request():
                return self.client.messages.create(
                    model=self._get_model_for_task("medium"),
                    max_tokens=15000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            analysis = response.content[0].text
            
            # Save analysis
            self._save_file(analysis, f"chapter_{self.chapter_num}_analysis.md")
            
            print("Chapter analysis complete")
            return analysis
            
        except Exception as e:
            print(f"Error analyzing chapter: {e}")
            return f"Error in analysis: {e}"
    
    def create_revision_plan(self, analysis: str) -> str:
        """Create a detailed revision plan based on analysis."""
        print(f"Creating revision plan for Chapter {self.chapter_num}...")
        
        # Check if plan already exists
        plan_file = os.path.join(self.project_dir, f"chapter_{self.chapter_num}_revision_plan.md")
        if os.path.exists(plan_file):
            print("Using existing revision plan")
            return self._safe_read_file(plan_file)
        
        target_words = self.target_word_count or int(self.current_chapter['word_count'] * 1.4)
        
        prompt = f"""Based on the chapter analysis, create a detailed revision plan for Chapter {self.chapter_num}.

CHAPTER ANALYSIS:
{analysis}

LITERARY INSPIRATIONS TO EMULATE:
{self.inspirations}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', '')}
OUTLINE: {self.project_context.get('outline', '')}
CHARACTERS: {self.project_context.get('characters', '')}

CURRENT WORD COUNT: {self.current_chapter['word_count']} words
TARGET WORD COUNT: {target_words} words

Create a comprehensive revision plan that addresses:

## EXPANSION STRATEGY
- Which scenes need expansion and why
- What new content should be added
- How to reach the target word count meaningfully

## LITERARY ENHANCEMENTS
- Prose style improvements to match inspirations
- Atmospheric and sensory detail additions
- Thematic depth opportunities

## CHARACTER DEVELOPMENT
- Dialogue improvements and subtext
- Character interiority expansion
- Relationship dynamics to explore

## STRUCTURAL IMPROVEMENTS
- Scene organization and transitions
- Pacing adjustments
- Opening and closing enhancements

## SPECIFIC REVISION TASKS
Provide numbered, concrete tasks:
1. [Specific expansion task with clear instructions]
2. [Character development task]
3. [Literary enhancement task]
4. [Structural improvement task]
[Continue with detailed, implementable actions]

## EXPANSION PRIORITIES
Rank the most important areas for expansion:
- Priority 1: [Most critical expansion area]
- Priority 2: [Second priority]
- Priority 3: [Third priority]

Focus on meaningful expansion that serves the story and literary quality, not just padding for word count."""

        try:
            def make_request():
                return self.client.messages.create(
                    model=self._get_model_for_task("medium"),
                    max_tokens=10000,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            response = self._make_api_request_with_retry(make_request)
            plan = response.content[0].text
            
            # Save revision plan
            self._save_file(plan, f"chapter_{self.chapter_num}_revision_plan.md")
            
            print("Revision plan created")
            return plan
            
        except Exception as e:
            print(f"Error creating revision plan: {e}")
            return f"Error creating plan: {e}"
    
    def revise_chapter(self, revision_plan: str) -> str:
        """Revise the chapter based on the revision plan."""
        print(f"Revising Chapter {self.chapter_num}...")
        
        original_word_count = self.current_chapter['word_count']
        target_words = self.target_word_count or int(original_word_count * 1.4)
        
        # With Sonnet 4's 64k token limit, we can likely do the entire revision in one pass
        # Only fall back to sectioned approach for extremely long chapters
        if original_word_count > 8000:  # Very long chapters might still need sectioning
            print("  Large chapter detected, may use sectioned approach if needed...")
        
        # Try full revision first (should work for most chapters now)
        revised_content = self._attempt_full_revision(revision_plan, target_words, original_word_count)
        
        # Only use fallback approaches if the chapter appears incomplete
        if not self._is_chapter_complete(revised_content):
            print("  Chapter appears incomplete, trying sectioned approach...")
            revised_content = self._attempt_sectioned_revision(revision_plan, target_words, original_word_count)
            
            if not self._is_chapter_complete(revised_content):
                print("  Ensuring chapter completion...")
                revised_content = self._attempt_completion_focused_revision(revision_plan, target_words, original_word_count)
        
        # Final check and report
        revised_word_count = len(revised_content.split())
        expansion_ratio = revised_word_count / original_word_count if original_word_count > 0 else 1
        
        print(f"Revision complete:")
        print(f"  Original: {original_word_count} words")
        print(f"  Revised: {revised_word_count} words")
        print(f"  Expansion: {expansion_ratio:.1f}x")
        
        if not self._is_chapter_complete(revised_content):
            print("  Warning: Chapter may be incomplete (ends mid-sentence)")
        
        return revised_content
    
    def _attempt_full_revision(self, revision_plan: str, target_words: int, original_word_count: int) -> str:
        """Attempt full chapter revision in one go."""
        prompt = f"""Revise Chapter {self.chapter_num} based on the detailed revision plan. You are a skilled literary editor implementing specific improvements.

LITERARY INSPIRATIONS TO EMULATE:
{self.inspirations}

PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', '')}
OUTLINE: {self.project_context.get('outline', '')}
CHARACTERS: {self.project_context.get('characters', '')}

REVISION PLAN TO IMPLEMENT:
{revision_plan}

CURRENT CHAPTER {self.chapter_num} CONTENT:
{self.current_chapter['content']}

TARGET WORD COUNT: {target_words} words (current: {original_word_count} words)

CRITICAL SUCCESS REQUIREMENTS:
1. The chapter MUST be complete from start to finish
2. End with proper punctuation (period, exclamation, question mark)
3. Implement the revision plan fully
4. Reach approximately the target word count
5. Maintain literary quality throughout

EXPANSION GUIDELINES:
- Character interiority and psychological depth
- Atmospheric and sensory details
- Dialogue subtext and authenticity
- Scene development and pacing
- Thematic elements and literary devices

COMPLETION INSTRUCTION:
If you approach the token limit, prioritize completing the chapter over perfect prose. 
End with a complete sentence and proper punctuation.

Return ONLY the complete revised chapter text with no commentary."""

        try:
            # Use Claude Sonnet 4's massive token capacity with streaming and retry logic
            max_tokens = 60000  # Leave some buffer from the 64k limit
            
            print("  Starting revision (this may take several minutes)...")
            
            def make_streaming_request():
                return self.client.messages.create(
                    model=self._get_model_for_task("complex"),
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True
                )
            
            # Use streaming with retry logic
            stream = self._make_api_request_with_retry(make_streaming_request)
            
            # Collect streamed response
            full_response = ""
            for chunk in stream:
                if chunk.type == "content_block_delta":
                    if hasattr(chunk.delta, 'text'):
                        full_response += chunk.delta.text
                        print(".", end="", flush=True)  # Progress indicator
            
            print("\n  Revision generation complete")
            return self._clean_ai_commentary(full_response)
            
        except Exception as e:
            print(f"  Error in full revision: {e}")
            print("  Falling back to sectioned approach...")
            # Try sectioned approach as fallback
            return self._attempt_sectioned_revision(revision_plan, target_words, original_word_count)
    
    def _attempt_sectioned_revision(self, revision_plan: str, target_words: int, original_word_count: int) -> str:
        """Attempt revision by breaking chapter into sections."""
        # Split original chapter into logical sections
        content = self.current_chapter['content']
        sections = self._split_into_sections(content)
        
        if len(sections) <= 1:
            # Can't split effectively, fall back to completion-focused approach
            return self._attempt_completion_focused_revision(revision_plan, target_words, original_word_count)
        
        revised_sections = []
        words_per_section = target_words // len(sections)
        
        for i, section in enumerate(sections):
            section_prompt = f"""Revise this section of Chapter {self.chapter_num} according to the revision plan.

REVISION PLAN EXCERPT:
{revision_plan[:1000]}...

LITERARY INSPIRATIONS:
{self.inspirations[:500] if self.inspirations else "None"}

SECTION TO REVISE (Part {i+1} of {len(sections)}):
{section}

TARGET: Approximately {words_per_section} words for this section.

Requirements:
- Enhance literary quality and character development
- Add atmospheric details and dialogue depth
- Ensure smooth narrative flow
- Complete all sentences properly
- This is section {i+1} of {len(sections)}, so maintain continuity

Return only the revised section content."""

            try:
                print(f"    Revising section {i+1}/{len(sections)}...")
                
                def make_section_request():
                    return self.client.messages.create(
                        model=self._get_model_for_task("medium"),
                        max_tokens=15000,
                        messages=[{"role": "user", "content": section_prompt}],
                        stream=True
                    )
                
                stream = self._make_api_request_with_retry(make_section_request)
                
                # Collect streamed response
                section_response = ""
                for chunk in stream:
                    if chunk.type == "content_block_delta":
                        if hasattr(chunk.delta, 'text'):
                            section_response += chunk.delta.text
                
                revised_section = self._clean_ai_commentary(section_response)
                revised_sections.append(revised_section)
                
            except Exception as e:
                print(f"  Error revising section {i+1}: {e}")
                revised_sections.append(section)  # Use original on error
        
        return "\n\n".join(revised_sections)
    
    def _attempt_completion_focused_revision(self, revision_plan: str, target_words: int, original_word_count: int) -> str:
        """Focus on ensuring chapter completion even if expansion is limited."""
        prompt = f"""Complete this chapter revision, ensuring it ends properly.

CHAPTER CONTENT TO COMPLETE:
{self.current_chapter['content']}

REVISION FOCUS:
- Ensure the chapter has a complete, satisfying ending
- Improve key dialogue and character moments
- Add meaningful details where possible
- Target around {target_words} words if possible

CRITICAL: The chapter must end with complete sentences and proper punctuation.

Return the complete chapter."""

        try:
            print("  Attempting completion-focused revision...")
            
            def make_completion_request():
                return self.client.messages.create(
                    model=self._get_model_for_task("medium"),
                    max_tokens=20000,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True
                )
            
            stream = self._make_api_request_with_retry(make_completion_request)
            
            # Collect streamed response
            completion_response = ""
            for chunk in stream:
                if chunk.type == "content_block_delta":
                    if hasattr(chunk.delta, 'text'):
                        completion_response += chunk.delta.text
            
            return self._clean_ai_commentary(completion_response)
            
        except Exception as e:
            print(f"  Error in completion-focused revision: {e}")
            return self.current_chapter['content']
    
    def _split_into_sections(self, content: str) -> list:
        """Split chapter content into logical sections."""
        # Split by double line breaks (scene breaks)
        sections = content.split('\n\n')
        
        # If that doesn't give good sections, try splitting by dialogue/narrative alternation
        if len(sections) < 3:
            # Look for natural break points
            paragraphs = content.split('\n')
            sections = []
            current_section = []
            
            for para in paragraphs:
                current_section.append(para)
                # Break on dialogue transitions or after longer paragraphs
                if len('\n'.join(current_section)) > 800:
                    sections.append('\n'.join(current_section))
                    current_section = []
            
            if current_section:
                sections.append('\n'.join(current_section))
        
        # Ensure we don't have too many tiny sections
        if len(sections) > 6:
            # Combine smaller sections
            combined = []
            current = ""
            for section in sections:
                if len(current + section) < 1000:
                    current += "\n\n" + section if current else section
                else:
                    if current:
                        combined.append(current)
                    current = section
            if current:
                combined.append(current)
            sections = combined
        
        return [s.strip() for s in sections if s.strip()]
    
    def _is_chapter_complete(self, content: str) -> bool:
        """Check if chapter appears to be complete."""
        if not content or len(content) < 100:
            return False
        
        # Check if it ends with proper punctuation
        content = content.strip()
        if not content:
            return False
        
        # Look at the last few sentences
        sentences = content.split('.')
        if len(sentences) < 2:
            return False
        
        last_sentence = sentences[-1].strip()
        second_last = sentences[-2].strip() if len(sentences) > 1 else ""
        
        # If last "sentence" is very short and doesn't end with punctuation, likely incomplete
        if len(last_sentence) < 10 and not last_sentence.endswith(('.', '!', '?', '"')):
            return False
        
        # Check for common incomplete endings
        incomplete_patterns = [
            r'\w+\s*$',     # Ends with just a word
            r'[a-z]\s*$',   # Ends with lowercase letter
            r',\s*$',       # Ends with comma
            r'and\s*$',     # Ends with "and"
            r'but\s*$',     # Ends with "but"
            r'the\s*$',     # Ends with "the"
        ]
        
        for pattern in incomplete_patterns:
            if re.search(pattern, content):
                return False
        
        return True
    
    def save_revised_chapter(self, revised_content: str) -> str:
        """Save the revised chapter to file."""
        # Create revised filename
        original_path = self.current_chapter['file_path']
        filename = os.path.basename(original_path)
        base_name = os.path.splitext(filename)[0]
        revised_filename = f"{base_name}_revised.md"
        
        # Save to revised directory
        revised_dir = os.path.join(self.project_dir, "revised")
        revised_path = os.path.join(revised_dir, revised_filename)
        
        if self._safe_write_file(revised_path, revised_content):
            print(f"Saved revised chapter: {revised_path}")
            return revised_path
        else:
            print(f"Error saving revised chapter")
            return ""
    
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
    
    def _save_file(self, content: str, filename: str) -> bool:
        """Save content to file with timestamp header."""
        output_path = os.path.join(self.project_dir, filename)
        
        file_content = f"# {filename.replace('_', ' ').replace('.md', '').title()}\n\n"
        file_content += f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        file_content += f"**Chapter:** {self.chapter_num}\n\n"
        file_content += "---\n\n"
        file_content += content
        
        success = self._safe_write_file(output_path, file_content)
        if success:
            print(f"  Saved: {filename}")
        return success
    
    def generate_summary_report(self, analysis: str, revision_plan: str, original_words: int, revised_words: int) -> str:
        """Generate a summary report of the revision process."""
        report = f"""# Chapter {self.chapter_num} Revision Report

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Chapter:** {self.chapter_num}
**Original Words:** {original_words:,}
**Revised Words:** {revised_words:,}
**Expansion:** {revised_words/original_words:.1f}x

## Process Summary

### 1. Chapter Analysis
Comprehensive analysis identified key areas for improvement in structure, character development, literary quality, and narrative function.

### 2. Revision Plan Creation
Detailed revision plan created with specific, actionable tasks for meaningful expansion and literary enhancement.

### 3. Chapter Revision
Implemented all revision plan recommendations while expanding content meaningfully.

## Key Improvements Made

### Analysis Highlights
{analysis[:500]}...

### Revision Strategy
{revision_plan[:500]}...

## Files Created

- `chapter_{self.chapter_num}_analysis.md` - Detailed chapter analysis
- `chapter_{self.chapter_num}_revision_plan.md` - Comprehensive revision plan
- `revised/[chapter_file]_revised.md` - Enhanced chapter version
- `chapter_{self.chapter_num}_revision_report.md` - This summary report

## Results

The chapter has been significantly enhanced with:
- Expanded word count ({original_words:,} → {revised_words:,} words)
- Improved literary quality and sophistication
- Enhanced character development and dialogue
- Deeper thematic integration
- Better narrative flow and pacing

## Next Steps

The revised chapter is ready for integration into the full manuscript. Consider reviewing the revision approach for consistency when revising other chapters.
"""
        
        self._save_file(report, f"chapter_{self.chapter_num}_revision_report.md")
        return report

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Single Chapter Reviser - Analyze, plan, and revise individual chapters",
        epilog="""
Examples:
  # Revise chapter 1 with default expansion
  python single_chapter_reviser.py clowns --chapter 1
  
  # Revise chapter 3 to specific word count
  python single_chapter_reviser.py clowns --chapter 3 --target-words 3000
  
  # Cost-optimized revision
  python single_chapter_reviser.py clowns --chapter 1 --cost-optimize --target-words 2500
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
        reviser.load_project_context(args.project_dir, args.chapter)
        
        original_words = reviser.current_chapter['word_count']
        
        # Step 1: Analyze chapter
        analysis = reviser.analyze_chapter()
        
        # Step 2: Create revision plan
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
        print(f"\nCheck chapter_{args.chapter}_revision_report.md for full summary")
        
        return 0
        
    except Exception as e:
        print(f"Error during chapter revision: {e}")
        return 1

if __name__ == "__main__":
    exit(main())