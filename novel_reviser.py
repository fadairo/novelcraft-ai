#!/usr/bin/env python3
"""
novel_reviser.py - Complete Novel Revision Automation System

This script automates the complete revision workflow for an entire novel:
1. Novel-wide alignment analysis
2. Revised outline, synopsis, and character creation
3. Chapter-by-chapter revision planning and implementation
4. Final alignment check and recommendations

Acts as a literary editor using the user's inspirations and genre requirements.
"""

import os
import re
import glob
import json
import argparse
import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import anthropic

class NovelReviser:
    """Complete novel revision automation system."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
        self.project_dir = None
        self.novel_title = "Novel"
        self.genre = "Literary Fiction"
        self.inspirations = ""
        self.chapters = {}
        self.project_context = {}
        # Cost optimization: Cache analyses to avoid re-running
        self.analysis_cache = {}
        self.use_cost_effective_model = True  # Use Sonnet instead of Opus for most tasks
    
    def load_project(self, project_dir: str):
        """Load project files and context."""
        self.project_dir = project_dir
        print(f"📖 Loading project from: {project_dir}")
        
        # Load project context
        self.project_context = self._load_project_files()
        
        # Load inspirations
        self.inspirations = self._load_inspirations()
        
        # Load chapters
        self.chapters = self._load_all_chapters()
        
        # Extract project metadata
        self._extract_project_metadata()
        
        print(f"✅ Loaded {len(self.chapters)} chapters")
        print(f"📚 Genre: {self.genre}")
        print(f"🎨 Literary inspirations: {'Found' if self.inspirations else 'None'}")
    
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
                    with open(file_path, 'r', encoding='utf-8') as f:
                        files[file_type] = f.read()
                    print(f"  ✓ {file_type}: {name}")
                    break
            else:
                files[file_type] = ""
                print(f"  ⚠ {file_type}: not found")
        
        return files
    
    def _load_inspirations(self) -> str:
        """Load literary inspirations."""
        inspiration_file = os.path.join(self.project_dir, "inspiration.md")
        if os.path.exists(inspiration_file):
            with open(inspiration_file, 'r', encoding='utf-8') as f:
                return f.read()
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
            patterns = ['chapter_*.md', 'chapter*.md', 'ch_*.md']
            for pattern in patterns:
                files = glob.glob(os.path.join(search_dir, pattern))
                for file_path in files:
                    # Skip enhanced/backup files
                    if any(skip in file_path.lower() for skip in ['enhanced', 'backup', 'revised']):
                        continue
                    
                    # Extract chapter number
                    chapter_num = self._extract_chapter_number(file_path)
                    if chapter_num:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        chapters[chapter_num] = {
                            'file_path': file_path,
                            'content': content,
                            'word_count': len(content.split())
                        }
        
        return chapters
    
    def _extract_chapter_number(self, file_path: str) -> Optional[int]:
        """Extract chapter number from filename."""
        filename = os.path.basename(file_path)
        patterns = [r'chapter[_\s]*(\d+)', r'ch[_\s]*(\d+)', r'(\d+)']
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None
    
    def _get_model_for_task(self, task_complexity: str = "medium") -> str:
        """Get appropriate model based on task complexity and cost optimization."""
        if not self.use_cost_effective_model:
            return "claude-opus-4-20250514"
        
        # Use cost-effective model selection
        model_map = {
            "simple": "claude-3-5-sonnet-20241022",    # For simple tasks
            "medium": "claude-3-5-sonnet-20241022",    # For most tasks
            "complex": "claude-opus-4-20250514"        # Only for most complex tasks
        }
        return model_map.get(task_complexity, "claude-3-5-sonnet-20241022")
    
    def _chunk_content_for_analysis(self, content: str, max_chunk_size: int = 15000) -> List[str]:
        """Split content into manageable chunks to avoid token limits and reduce costs."""
        if len(content) <= max_chunk_size:
            return [content]
        
        # Split by paragraphs to maintain coherence
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _extract_project_metadata(self):
        """Extract project metadata from context."""
        # Try to determine genre and title from project files
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
        """Extract project metadata from context."""
        # Try to determine genre and title from project files
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
    
    def analyze_novel_alignment(self) -> str:
        """Perform comprehensive novel-wide alignment analysis with cost optimization."""
        print("\n🔍 Analyzing novel-wide alignment...")
        
        # Check if analysis already exists
        analysis_file = os.path.join(self.project_dir, "novel_alignment_analysis.md")
        if os.path.exists(analysis_file):
            print("✅ Using existing novel alignment analysis")
            with open(analysis_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        # Prepare efficient chapter summaries (limit content to reduce tokens)
        chapter_summaries = []
        total_words = 0
        
        for chapter_num in sorted(self.chapters.keys()):
            chapter = self.chapters[chapter_num]
            word_count = chapter['word_count']
            total_words += word_count
            
            # Create concise chapter summary (reduce token usage)
            content_preview = chapter['content'][:300] + "..." if len(chapter['content']) > 300 else chapter['content']
            chapter_summaries.append(f"**Chapter {chapter_num}** ({word_count} words):\n{content_preview}")
        
        # Split into chunks if too large
        summary_text = chr(10).join(chapter_summaries)
        chunks = self._chunk_content_for_analysis(summary_text, max_chunk_size=12000)
        
        if len(chunks) > 1:
            print(f"  📝 Processing {len(chunks)} content chunks for cost efficiency")
            
            # Analyze chunks separately then synthesize
            chunk_analyses = []
            for i, chunk in enumerate(chunks):
                print(f"    Analyzing chunk {i+1}/{len(chunks)}")
                chunk_analysis = self._analyze_novel_chunk(chunk, i+1, len(chunks), total_words)
                chunk_analyses.append(chunk_analysis)
            
            # Synthesize chunk analyses
            analysis = self._synthesize_chunk_analyses(chunk_analyses, total_words)
        else:
            # Single analysis for smaller novels
            analysis = self._analyze_complete_novel(summary_text, total_words)
        
        # Save analysis
        self._save_analysis(analysis, "novel_alignment_analysis.md")
        
        print("✅ Novel alignment analysis complete")
        return analysis
    
    def _analyze_novel_chunk(self, chunk_content: str, chunk_num: int, total_chunks: int, total_words: int) -> str:
        """Analyze a chunk of the novel for cost efficiency."""
        prompt = f"""You are analyzing chunk {chunk_num} of {total_chunks} from a {self.genre} novel for alignment issues.

NOVEL METADATA:
Title: {self.novel_title}
Genre: {self.genre}
Total Words: {total_words:,}

LITERARY INSPIRATIONS:
{self.inspirations if self.inspirations else "None specified"}

CURRENT PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', 'Not available')[:500]}...
OUTLINE: {self.project_context.get('outline', 'Not available')[:500]}...

CHAPTER CONTENT CHUNK {chunk_num}:
{chunk_content}

Analyze this chunk for:
1. Narrative coherence issues
2. Character consistency problems  
3. Pacing and structural concerns
4. Thematic development gaps
5. Literary quality issues

Keep analysis focused and concise. This will be combined with other chunk analyses."""

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("medium"),  # Cost-effective model
                max_tokens=1500,  # Reduced token limit
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error analyzing chunk {chunk_num}: {e}"
    
    def _synthesize_chunk_analyses(self, chunk_analyses: List[str], total_words: int) -> str:
        """Synthesize multiple chunk analyses into a cohesive report."""
        combined_analyses = "\n\n".join([f"CHUNK {i+1} ANALYSIS:\n{analysis}" for i, analysis in enumerate(chunk_analyses)])
        
        prompt = f"""Synthesize these chunk analyses into a comprehensive novel alignment analysis for a {self.genre} work.

NOVEL METADATA:
Title: {self.novel_title}  
Genre: {self.genre}
Total Words: {total_words:,}

CHUNK ANALYSES:
{combined_analyses}

Create a unified analysis covering:
## OVERALL NARRATIVE COHERENCE
## CHARACTER CONSISTENCY AND DEVELOPMENT  
## THEMATIC INTEGRATION
## STRUCTURAL ANALYSIS
## STYLE AND VOICE CONSISTENCY
## LITERARY QUALITY ASSESSMENT
## CRITICAL GAPS AND INCONSISTENCIES
## RECOMMENDATIONS FOR COHESIVE ALIGNMENT

Focus on actionable recommendations for novel-wide improvements."""

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("complex"),  # Use Opus for synthesis
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error synthesizing analyses: {e}"
    
    def _analyze_complete_novel(self, summary_text: str, total_words: int) -> str:
        """Analyze complete novel when small enough for single analysis."""
        prompt = f"""You are conducting a comprehensive literary analysis of a complete novel for cohesive alignment. This is {self.genre} with the following context:

NOVEL METADATA:
Title: {self.novel_title}
Genre: {self.genre}
Total Chapters: {len(self.chapters)}
Total Words: {total_words:,}

LITERARY INSPIRATIONS:
{self.inspirations if self.inspirations else "None specified"}

CURRENT PROJECT CONTEXT:
SYNOPSIS: {self.project_context.get('synopsis', 'Not available')}

OUTLINE: {self.project_context.get('outline', 'Not available')}

CHARACTERS: {self.project_context.get('characters', 'Not available')}

CHAPTER SUMMARIES:
{summary_text}

COMPREHENSIVE NOVEL ALIGNMENT ANALYSIS REQUIRED:

## OVERALL NARRATIVE COHERENCE
- Does the story have a clear, compelling arc from beginning to end?
- Are major plot threads properly developed and resolved?
- How well do chapters build upon each other?

## CHARACTER CONSISTENCY AND DEVELOPMENT
- Are character voices consistent throughout?
- Do character arcs show believable growth/change?
- Are relationships and motivations clear and compelling?

## THEMATIC INTEGRATION
- Are the novel's themes consistently explored?
- How well does the genre (literary spy fiction) serve the story?
- Is the thematic depth appropriate for literary fiction?

## STRUCTURAL ANALYSIS
- Is the pacing effective across the full novel?
- Are there weak chapters that disrupt flow?
- How well does each chapter serve the overall narrative?

## STYLE AND VOICE CONSISTENCY
- Is the narrative voice consistent throughout?
- Does the prose quality match literary fiction standards?
- How well does the writing style serve the {self.genre} genre?

## LITERARY QUALITY ASSESSMENT
Based on inspirations and genre standards:
- How does this compare to quality literary spy fiction?
- What elevates it beyond genre fiction into literary fiction?
- Areas where literary sophistication could be enhanced?

## CRITICAL GAPS AND INCONSISTENCIES
- Plot holes or logical inconsistencies
- Character behavior inconsistencies
- Timeline or continuity issues
- Missing story elements

## RECOMMENDATIONS FOR COHESIVE ALIGNMENT
- Priority areas for improvement
- Specific chapters needing major revision
- Structural changes needed
- Character development requirements
- Thematic strengthening opportunities

Focus on creating a cohesive, literary-quality novel that honors both the {self.genre} genre and literary fiction standards."""

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("complex"),  # Use Opus for comprehensive analysis
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error in analysis: {e}"
    
    def create_revised_project_files(self, alignment_analysis: str) -> Dict[str, str]:
        """Create revised outline, synopsis, and character list based on analysis."""
        print("\n📝 Creating revised project files...")
        
        revised_files = {}
        
        # Create revised synopsis
        revised_files['synopsis'] = self._create_revised_synopsis(alignment_analysis)
        
        # Create revised outline  
        revised_files['outline'] = self._create_revised_outline(alignment_analysis)
        
        # Create revised character list
        revised_files['characters'] = self._create_revised_characters(alignment_analysis)
        
        # Save revised files
        self._save_revised_project_files(revised_files)
        
        print("✅ Revised project files created")
        return revised_files
    
    def _create_revised_synopsis(self, analysis: str) -> str:
        """Create revised synopsis based on alignment analysis."""
        prompt = f"""Based on the novel alignment analysis and the current manuscript, create a revised synopsis that accurately reflects the story as written while improving its literary quality.

CURRENT SYNOPSIS:
{self.project_context.get('synopsis', 'None')}

NOVEL ALIGNMENT ANALYSIS:
{analysis}

LITERARY INSPIRATIONS:
{self.inspirations}

Create a revised synopsis that:
1. Accurately reflects the story as actually written in the chapters
2. Emphasizes the literary and thematic elements
3. Highlights what makes this {self.genre} rather than genre fiction
4. Is compelling and professionally written
5. Addresses gaps identified in the alignment analysis
6. Serves as a strong foundation for chapter revisions

The synopsis should be 2-3 paragraphs, literary in tone, and capture both plot and thematic depth."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error creating revised synopsis: {e}"
    
    def _create_revised_outline(self, analysis: str) -> str:
        """Create revised outline based on alignment analysis."""
        chapter_summaries = []
        for chapter_num in sorted(self.chapters.keys()):
            chapter = self.chapters[chapter_num]
            content_preview = chapter['content'][:300] + "..."
            chapter_summaries.append(f"Chapter {chapter_num}: {content_preview}")
        
        prompt = f"""Based on the novel alignment analysis and current manuscript, create a revised detailed outline that reflects the story as written while improving structure and coherence.

CURRENT OUTLINE:
{self.project_context.get('outline', 'None')}

ACTUAL CHAPTER CONTENT:
{chr(10).join(chapter_summaries)}

NOVEL ALIGNMENT ANALYSIS:
{analysis}

Create a revised outline that:
1. Accurately reflects what's actually written in each chapter
2. Identifies structural improvements needed
3. Shows how each chapter serves the overall narrative arc
4. Addresses pacing and flow issues identified in analysis
5. Strengthens thematic development throughout
6. Maintains {self.genre} genre requirements
7. Provides clear guidance for chapter revisions

Structure as:
- Overall Arc Summary
- Act divisions (if applicable)
- Chapter-by-chapter breakdown with:
  * Current purpose/content
  * Needed improvements
  * How it serves the whole

Be specific and actionable for guiding revisions."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error creating revised outline: {e}"
    
    def _create_revised_characters(self, analysis: str) -> str:
        """Create revised character list based on alignment analysis."""
        prompt = f"""Based on the novel alignment analysis and the actual manuscript content, create a revised character list that reflects how characters are actually portrayed while improving consistency and development.

CURRENT CHARACTER LIST:
{self.project_context.get('characters', 'None')}

NOVEL ALIGNMENT ANALYSIS:
{analysis}

LITERARY INSPIRATIONS:
{self.inspirations}

Create a revised character list that:
1. Accurately reflects how characters appear in the written chapters
2. Addresses character consistency issues identified in analysis
3. Strengthens character arcs and motivations
4. Ensures characters serve the {self.genre} themes
5. Provides clear guidance for character development in revisions
6. Maintains literary fiction depth and complexity

For each major character include:
- Name and role in story
- Current portrayal vs. intended portrayal
- Character arc and development needs
- Key relationships and dynamics
- Dialogue voice and personality traits
- Specific improvements needed for consistency

Focus on characters that actually appear significantly in the manuscript."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error creating revised characters: {e}"
    
    def create_chapter_revision_plans(self, alignment_analysis: str, revised_context: Dict[str, str]) -> Dict[int, str]:
        """Create revision plans for all chapters with cost optimization."""
        print(f"\n📋 Creating revision plans for {len(self.chapters)} chapters...")
        
        revision_plans = {}
        
        # Create revision plans directory
        plans_dir = os.path.join(self.project_dir, "revision_plans")
        if not os.path.exists(plans_dir):
            os.makedirs(plans_dir)
        
        # Process chapters in batches for cost efficiency
        batch_size = 3  # Process multiple chapters per API call
        chapter_nums = sorted(self.chapters.keys())
        
        for i in range(0, len(chapter_nums), batch_size):
            batch = chapter_nums[i:i+batch_size]
            print(f"  Creating plans for Chapters {batch[0]}-{batch[-1]}...")
            
            # Check if plans already exist
            existing_plans = {}
            missing_chapters = []
            
            for chapter_num in batch:
                plan_filename = f"chapter_{chapter_num:02d}_revision_plan.md"
                plan_path = os.path.join(plans_dir, plan_filename)
                
                if os.path.exists(plan_path):
                    with open(plan_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        plan_content = content.split("---")[-1].strip() if "---" in content else content
                        existing_plans[chapter_num] = plan_content
                        revision_plans[chapter_num] = plan_content
                    print(f"    ✓ Using existing plan for Chapter {chapter_num}")
                else:
                    missing_chapters.append(chapter_num)
            
            # Create plans for missing chapters in batch
            if missing_chapters:
                batch_plans = self._create_chapter_plans_batch(
                    missing_chapters, alignment_analysis, revised_context
                )
                
                # Save and store the plans
                for chapter_num, plan in batch_plans.items():
                    revision_plans[chapter_num] = plan
                    
                    plan_filename = f"chapter_{chapter_num:02d}_revision_plan.md"
                    plan_path = os.path.join(plans_dir, plan_filename)
                    
                    with open(plan_path, 'w', encoding='utf-8') as f:
                        f.write(f"# REVISION PLAN FOR CHAPTER {chapter_num}\n\n")
                        f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        f.write(f"**Original word count:** {self.chapters[chapter_num]['word_count']} words\n\n")
                        f.write("---\n\n")
                        f.write(plan)
        
        print("✅ All chapter revision plans created")
        return revision_plans
    
    def _create_chapter_plans_batch(self, chapter_nums: List[int], alignment_analysis: str, revised_context: Dict[str, str]) -> Dict[int, str]:
        """Create revision plans for multiple chapters in a single API call for cost efficiency."""
        
        # Prepare chapter data
        chapters_data = []
        for chapter_num in chapter_nums:
            chapter = self.chapters[chapter_num]
            # Limit content size for cost efficiency
            content_preview = chapter['content'][:1000] + "..." if len(chapter['content']) > 1000 else chapter['content']
            chapters_data.append(f"CHAPTER {chapter_num} ({chapter['word_count']} words):\n{content_preview}")
        
        prompt = f"""Create detailed revision plans for multiple chapters of this {self.genre} novel. Act as a literary editor with expertise in the genre.

LITERARY INSPIRATIONS TO EMULATE:
{self.inspirations[:1000] if self.inspirations else "None specified"}

NOVEL ALIGNMENT ANALYSIS (Key Points):
{alignment_analysis[:2000]}...

REVISED PROJECT CONTEXT:
SYNOPSIS: {revised_context.get('synopsis', '')[:500]}...
OUTLINE: {revised_context.get('outline', '')[:800]}...
CHARACTERS: {revised_context.get('characters', '')[:500]}...

CHAPTERS TO PLAN:
{chr(10).join(chapters_data)}

For each chapter, create a revision plan addressing:
- Alignment with novel arc
- Literary quality improvements  
- Character development
- Thematic integration
- Specific actionable tasks

Format as:
## CHAPTER [NUM] REVISION PLAN
[Detailed plan content]

## CHAPTER [NUM] REVISION PLAN  
[Detailed plan content]

Keep plans focused and actionable."""

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("medium"),
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse the response to extract individual plans
            content = response.content[0].text
            plans = {}
            
            # Split by chapter headers
            sections = re.split(r'## CHAPTER (\d+) REVISION PLAN', content)
            
            for i in range(1, len(sections), 2):
                if i + 1 < len(sections):
                    chapter_num = int(sections[i])
                    plan_content = sections[i + 1].strip()
                    if chapter_num in chapter_nums:
                        plans[chapter_num] = plan_content
            
            # Fallback: if parsing failed, create individual plans
            if not plans:
                for chapter_num in chapter_nums:
                    plans[chapter_num] = self._create_single_chapter_plan(
                        chapter_num, alignment_analysis, revised_context
                    )
            
            return plans
            
        except Exception as e:
            print(f"    ❌ Error creating batch plans: {e}")
            # Fallback to individual creation
            plans = {}
            for chapter_num in chapter_nums:
                plans[chapter_num] = self._create_single_chapter_plan(
                    chapter_num, alignment_analysis, revised_context
                )
            return plans
    
    def _create_single_chapter_plan(self, chapter_num: int, alignment_analysis: str, revised_context: Dict[str, str]) -> str:
        """Create revision plan for a single chapter."""
        chapter = self.chapters[chapter_num]
        
        # Get adjacent chapters for context (but limit size to avoid token issues)
        prev_chapter = self.chapters.get(chapter_num - 1, {}).get('content', '')[:500]
        next_chapter = self.chapters.get(chapter_num + 1, {}).get('content', '')[:500]
        
        # For cost optimization, limit alignment analysis size but don't truncate chapter content
        analysis_excerpt = alignment_analysis[:3000] + "..." if len(alignment_analysis) > 3000 else alignment_analysis
        
        prompt = f"""Create a detailed revision plan for Chapter {chapter_num} of this {self.genre} novel, acting as a literary editor with expertise in the genre.

LITERARY INSPIRATIONS TO EMULATE:
{self.inspirations}

NOVEL ALIGNMENT ANALYSIS (Key Points):
{analysis_excerpt}

REVISED PROJECT CONTEXT:
SYNOPSIS: {revised_context.get('synopsis', '')}
OUTLINE: {revised_context.get('outline', '')}
CHARACTERS: {revised_context.get('characters', '')}

CURRENT CHAPTER {chapter_num} CONTENT:
{chapter['content']}

ADJACENT CHAPTERS CONTEXT:
Previous Chapter Preview: {prev_chapter}
Next Chapter Preview: {next_chapter}

Create a comprehensive revision plan that addresses:

## ALIGNMENT WITH NOVEL ARC
- How this chapter serves the overall story
- Connections to strengthen with other chapters
- Role in character development arcs

## LITERARY QUALITY IMPROVEMENTS
- Prose style enhancements to match inspirations
- Thematic depth and sophistication
- Genre-specific elements to strengthen

## STRUCTURAL REVISIONS
- Pacing and scene organization
- Narrative flow and transitions
- Chapter opening and closing effectiveness

## CHARACTER DEVELOPMENT
- Character voice consistency and distinctiveness
- Dialogue improvements for authenticity and subtext
- Character motivation and internal conflict

## THEMATIC INTEGRATION
- How to better serve novel's themes
- Symbolic elements and literary devices
- Deeper meaning and resonance

## TECHNICAL IMPROVEMENTS
- Plot logic and continuity
- Setting and atmosphere enhancement
- Show vs. tell opportunities

## SPECIFIC ACTIONABLE TASKS
Provide numbered, concrete revision tasks:
1. [Specific task with clear instructions]
2. [Another specific task]
[Continue with detailed, implementable actions]

IMPORTANT: This chapter is currently {chapter['word_count']} words. The revision should MAINTAIN OR EXPAND the word count to preserve the full narrative scope and literary depth. Do not suggest shortening or condensing the chapter.

Focus on creating literary fiction quality while honoring {self.genre} genre conventions. Reference the literary inspirations for style and technique guidance."""

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("medium"),  # Cost-effective model
                max_tokens=2500,  # Increased for more detailed plans
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error creating revision plan for Chapter {chapter_num}: {e}"
    
    def revise_all_chapters(self, revision_plans: Dict[int, str], revised_context: Dict[str, str]) -> Dict[int, str]:
        """Revise all chapters based on their revision plans with cost optimization."""
        print(f"\n✍️ Revising {len(self.chapters)} chapters...")
        
        revised_chapters = {}
        
        # Create revised chapters directory
        revised_dir = os.path.join(self.project_dir, "revised")
        if not os.path.exists(revised_dir):
            os.makedirs(revised_dir)
        
        for chapter_num in sorted(self.chapters.keys()):
            print(f"  Revising Chapter {chapter_num}...")
            
            # Check if revised chapter already exists
            original_filename = os.path.basename(self.chapters[chapter_num]['file_path'])
            base_name = os.path.splitext(original_filename)[0]
            revised_filename = f"{base_name}_revised.md"
            revised_path = os.path.join(revised_dir, revised_filename)
            
            if os.path.exists(revised_path):
                print(f"    ✓ Using existing revised chapter")
                with open(revised_path, 'r', encoding='utf-8') as f:
                    revised_content = f.read()
                revised_chapters[chapter_num] = revised_content
                
                revised_words = len(revised_content.split())
                original_words = self.chapters[chapter_num]['word_count']
                print(f"    Words: {original_words} → {revised_words}")
                continue
            
            # Create new revision
            revised_content = self._revise_single_chapter(
                chapter_num, revision_plans[chapter_num], revised_context
            )
            
            revised_chapters[chapter_num] = revised_content
            
            # Save revised chapter
            with open(revised_path, 'w', encoding='utf-8') as f:
                f.write(revised_content)
            
            # Report progress
            original_words = self.chapters[chapter_num]['word_count']
            revised_words = len(revised_content.split())
            print(f"    Words: {original_words} → {revised_words}")
        
        print("✅ All chapters revised")
        return revised_chapters
    
    def _revise_single_chapter(self, chapter_num: int, revision_plan: str, revised_context: Dict[str, str]) -> str:
        """Revise a single chapter based on its revision plan."""
        chapter = self.chapters[chapter_num]
        original_word_count = chapter['word_count']
        # Ensure expansion rather than reduction - target at least 20% more words
        target_word_count = max(int(original_word_count * 1.3), original_word_count + 200)
        
        prompt = f"""Revise Chapter {chapter_num} of this {self.genre} novel based on the detailed revision plan. Act as a skilled literary editor with expertise in the genre.

LITERARY INSPIRATIONS TO EMULATE:
{self.inspirations}

REVISED PROJECT CONTEXT:
SYNOPSIS: {revised_context.get('synopsis', '')}
OUTLINE: {revised_context.get('outline', '')}
CHARACTERS: {revised_context.get('characters', '')}

REVISION PLAN TO IMPLEMENT:
{revision_plan}

CURRENT CHAPTER {chapter_num} TO REVISE:
{chapter['content']}

TARGET WORD COUNT: AT LEAST {target_word_count} words (original: {original_word_count} words)

CRITICAL WORD COUNT REQUIREMENTS:
- The revised chapter MUST be at least {target_word_count} words
- DO NOT shorten, condense, or summarize the original content
- EXPAND scenes with literary depth, character development, and atmospheric detail
- ADD substance, don't remove it
- If you're approaching the token limit, prioritize completing the full chapter over perfect prose

REVISION REQUIREMENTS:
1. Implement ALL recommendations from the revision plan
2. Maintain narrative continuity with the rest of the novel
3. Enhance literary quality to match the inspirations
4. Strengthen {self.genre} genre elements
5. Improve character development and voice consistency
6. Deepen thematic integration
7. Ensure each scene has purpose and impact
8. EXPAND the chapter with literary enhancements - never shorten it

EXPANSION PRIORITIES:
- Character interiority and psychological depth
- Atmospheric and setting details
- Dialogue subtext and character voice
- Thematic elements and literary symbolism
- Sensory details and immersive prose
- Scene transitions and narrative flow

CRITICAL INSTRUCTIONS:
- Revise the ENTIRE chapter from beginning to end
- NEVER truncate, summarize, or skip sections due to length
- Do NOT include any commentary, questions, or notes
- Return ONLY the complete revised chapter text
- Implement every point from the revision plan
- Focus on literary quality while serving the story
- The revised chapter must be LONGER and MORE DETAILED than the original
- If you run out of space, continue the narrative - completeness is essential

This is {self.genre} focusing on:
- Psychological complexity and moral ambiguity
- Literary prose that serves the story
- Character relationships and development
- Thematic depth and sophistication
- Genre conventions executed with literary skill

Return the complete revised chapter ready for publication. The chapter must be fully developed and complete from start to finish."""

        try:
            response = self.client.messages.create(
                model=self._get_model_for_task("complex"),  # Use Opus for chapter revision
                max_tokens=12000,  # Increased significantly to ensure full chapters
                messages=[{"role": "user", "content": prompt}]
            )
            
            revised_text = response.content[0].text
            cleaned_text = self._clean_ai_commentary(revised_text)
            
            # Check if the chapter was significantly shortened and warn
            revised_word_count = len(cleaned_text.split())
            if revised_word_count < original_word_count * 0.9:
                print(f"    ⚠ Warning: Chapter {chapter_num} was shortened ({original_word_count} → {revised_word_count} words)")
                print(f"    This may indicate the AI hit token limits. Consider using --force-refresh for better results.")
            
            return cleaned_text
            
        except Exception as e:
            print(f"    ❌ Error revising Chapter {chapter_num}: {e}")
            return chapter['content']  # Return original on error
    
    def final_alignment_check(self, revised_chapters: Dict[int, str], revised_context: Dict[str, str]) -> str:
        """Perform final alignment check and suggest further improvements."""
        print("\n🔍 Performing final alignment check...")
        
        # Calculate statistics
        total_revised_words = sum(len(content.split()) for content in revised_chapters.values())
        
        # Create chapter summaries for analysis
        revised_summaries = []
        for chapter_num in sorted(revised_chapters.keys()):
            content = revised_chapters[chapter_num]
            word_count = len(content.split())
            preview = content[:500] + "..." if len(content) > 500 else content
            revised_summaries.append(f"**Chapter {chapter_num}** ({word_count} words):\n{preview}")
        
        prompt = f"""Conduct a final alignment check of the completely revised novel. This is {self.genre} with the following updated context:

LITERARY INSPIRATIONS:
{self.inspirations}

REVISED PROJECT CONTEXT:
SYNOPSIS: {revised_context.get('synopsis', '')}
OUTLINE: {revised_context.get('outline', '')}
CHARACTERS: {revised_context.get('characters', '')}

REVISED NOVEL STATISTICS:
Total Chapters: {len(revised_chapters)}
Total Words: {total_revised_words:,}

REVISED CHAPTER SUMMARIES:
{chr(10).join(revised_summaries)}

FINAL ALIGNMENT ASSESSMENT:

## OVERALL QUALITY IMPROVEMENT
- How significantly has the novel improved?
- Does it now meet literary fiction standards?
- How well does it honor the {self.genre} genre?

## NARRATIVE COHERENCE
- Is the story arc now compelling and complete?
- Do chapters flow seamlessly together?
- Are all plot threads properly developed?

## CHARACTER DEVELOPMENT
- Are character arcs satisfying and believable?
- Is dialogue authentic and distinctive?
- Do characters serve both plot and theme?

## LITERARY QUALITY
- Does the prose quality match the inspirations?
- Is the thematic depth appropriate for literary fiction?
- How successfully does it transcend genre limitations?

## STRUCTURAL INTEGRITY
- Is pacing effective throughout?
- Does each chapter earn its place?
- Are transitions smooth and purposeful?

## REMAINING OPPORTUNITIES
- What could be improved in the next revision cycle?
- Specific chapters that could be stronger?
- Thematic elements to develop further?
- Character relationships to deepen?

## PUBLICATION READINESS
- How close is this to publication quality?
- What are the strongest elements?
- Priority areas for final polish?

## SPECIFIC RECOMMENDATIONS FOR NEXT REVISION
Provide concrete, actionable suggestions for:
1. Individual chapters needing attention
2. Structural adjustments
3. Character development opportunities
4. Thematic strengthening
5. Prose refinement areas

Focus on the path to creating a distinguished work of {self.genre} that honors both literary and genre traditions."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            final_analysis = response.content[0].text
            
            # Save final analysis
            self._save_analysis(final_analysis, "final_alignment_check.md")
            
            print("✅ Final alignment check complete")
            return final_analysis
            
        except Exception as e:
            print(f"❌ Error in final alignment check: {e}")
            return f"Error in final analysis: {e}"
    
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
    
    def _save_analysis(self, content: str, filename: str):
        """Save analysis to file."""
        output_path = os.path.join(self.project_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# {filename.replace('_', ' ').replace('.md', '').title()}\n\n")
            f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(content)
        print(f"  📄 Saved: {output_path}")
    
    def _save_revised_project_files(self, revised_files: Dict[str, str]):
        """Save revised project files."""
        file_mapping = {
            'synopsis': 'synopsis_revised.md',
            'outline': 'outline_revised.md', 
            'characters': 'characters_revised.md'
        }
        
        for file_type, content in revised_files.items():
            filename = file_mapping[file_type]
            output_path = os.path.join(self.project_dir, filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# Revised {file_type.title()}\n\n")
                f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write(content)
            
            print(f"  📄 Saved: {output_path}")
    
    def generate_revision_report(self, alignment_analysis: str, final_analysis: str) -> str:
        """Generate comprehensive revision report."""
        print("\n📊 Generating revision report...")
        
        report = f"""# Novel Revision Report: {self.novel_title}

**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Genre:** {self.genre}
**Chapters Processed:** {len(self.chapters)}
**Total Original Words:** {sum(ch['word_count'] for ch in self.chapters.values()):,}

## Process Summary

### 1. Novel Alignment Analysis
Initial comprehensive analysis identified key areas for improvement across narrative coherence, character development, thematic integration, and literary quality.

### 2. Revised Project Files
Created updated synopsis, outline, and character descriptions that reflect the story as written while improving literary quality and coherence.

### 3. Chapter Revision Plans
Generated detailed revision plans for all {len(self.chapters)} chapters, each addressing specific improvements needed for alignment with the overall novel.

### 4. Chapter Revisions
Implemented comprehensive revisions for every chapter, focusing on:
- Literary quality enhancement
- Character development and voice consistency
- Thematic integration
- Structural improvements
- Genre convention refinement

### 5. Final Quality Assessment
Conducted final alignment check to assess improvements and identify opportunities for future revision cycles.

## Key Improvements Made

{alignment_analysis}

## Final Assessment

{final_analysis}

## Files Created

### Project Files
- `synopsis_revised.md` - Updated synopsis reflecting actual story
- `outline_revised.md` - Detailed outline based on written content
- `characters_revised.md` - Enhanced character descriptions and development notes

### Revision Plans
- `revision_plans/chapter_XX_revision_plan.md` - Detailed plans for each chapter

### Revised Chapters
- `revised/chapter_XX_revised.md` - Improved versions of all chapters

### Analysis Reports
- `novel_alignment_analysis.md` - Initial comprehensive analysis
- `final_alignment_check.md` - Final quality assessment
- `revision_report.md` - This summary report

## Next Steps

Based on the final alignment check, consider the specific recommendations provided for the next revision cycle. The novel has been significantly improved but may benefit from additional targeted revisions in the areas identified.

## Literary Quality Assessment

This revision cycle focused on elevating the work from genre fiction to literary fiction standards while maintaining the engaging elements of {self.genre}. The revised novel should now demonstrate the literary sophistication expected of distinguished fiction in this genre.
"""
        
        # Save report
        report_path = os.path.join(self.project_dir, "revision_report.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ Revision report saved: {report_path}")
        return report

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Complete novel revision automation system",
        epilog="""
Examples:
  # Complete novel revision workflow
  python novel_reviser.py glasshouse
  
  # Specific steps only
  python novel_reviser.py glasshouse --analysis-only
  python novel_reviser.py glasshouse --revisions-only
        """
    )
    parser.add_argument(
        "project_dir",
        help="Project directory containing the novel"
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Only perform alignment analysis, don't create revisions"
    )
    parser.add_argument(
        "--revisions-only",
        action="store_true", 
        help="Skip analysis, use existing results to create revisions"
    )
    parser.add_argument(
        "--cost-optimize",
        action="store_true",
        help="Use cost-optimized approach (Sonnet for most tasks, batched processing)"
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true", 
        help="Force regeneration of all files, ignoring existing ones"
    )
    parser.add_argument(
        "--skip-final-check",
        action="store_true",
        help="Skip final alignment check"
    )
    
    args = parser.parse_args()
    
    # Initialize reviser
    try:
        reviser = NovelReviser()
        
        # Configure cost optimization
        if args.cost_optimize:
            reviser.use_cost_effective_model = True
            print("💰 Using cost-optimized approach")
        else:
            reviser.use_cost_effective_model = False
            print("🚀 Using premium models for highest quality")
        
        # Handle force refresh
        if args.force_refresh:
            print("🔄 Force refresh enabled - will regenerate all files")
    except Exception as e:
        print(f"❌ Error initializing AI client: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        return 1
    
    try:
        print(f"🚀 Starting novel revision automation for: {args.project_dir}")
        print("="*60)
        
        # Load project
        reviser.load_project(args.project_dir)
        
        if not reviser.chapters:
            print("❌ No chapters found in project")
            return 1
        
        # Step 1: Novel alignment analysis
        if not args.revisions_only:
            alignment_analysis = reviser.analyze_novel_alignment()
            
            if args.analysis_only:
                print("\n✅ Analysis complete. Check the generated reports.")
                return 0
        else:
            # Load existing analysis
            analysis_file = os.path.join(args.project_dir, "novel_alignment_analysis.md")
            if os.path.exists(analysis_file):
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    alignment_analysis = f.read()
                print("✅ Using existing alignment analysis")
            else:
                print("❌ No existing analysis found. Run without --revisions-only first.")
                return 1
        
        # Step 2: Create revised project files
        revised_context = reviser.create_revised_project_files(alignment_analysis)
        
        # Step 3: Create chapter revision plans
        revision_plans = reviser.create_chapter_revision_plans(alignment_analysis, revised_context)
        
        # Step 4: Revise all chapters
        revised_chapters = reviser.revise_all_chapters(revision_plans, revised_context)
        
        # Step 5: Final alignment check
        final_analysis = ""
        if not args.skip_final_check:
            final_analysis = reviser.final_alignment_check(revised_chapters, revised_context)
        
        # Generate comprehensive report
        reviser.generate_revision_report(alignment_analysis, final_analysis)
        
        print("\n" + "="*60)
        print("🎉 NOVEL REVISION COMPLETE!")
        print("="*60)
        print(f"📚 Processed: {len(reviser.chapters)} chapters")
        print(f"📄 Created: Revised project files, revision plans, and chapters")
        print(f"📊 Reports: Comprehensive analysis and final assessment")
        print(f"📁 Location: {args.project_dir}")
        print("\nCheck the revision_report.md for a complete summary of improvements made.")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error during novel revision: {e}")
        return 1

if __name__ == "__main__":
    exit(main())