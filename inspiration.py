#!/usr/bin/env python3
"""
inspiration.py - AI-powered chapter enhancement tool for "A Season of Spies"

This tool reads inspiration sources from inspiration.md and uses AI to enhance
chapters in the style of specified authors and books.
"""

import os
import re
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import anthropic

class InspirationAnalyzer:
    """Analyzes inspiration sources and generates style guidelines."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
        self.style_cache = {}
    
    def load_inspirations(self, inspiration_file: str = "inspiration.md") -> List[Tuple[str, str]]:
        """Load inspiration sources from markdown file."""
        # Try current directory first, then look for project-specific inspiration files
        possible_locations = [
            inspiration_file,  # Exact path provided
            os.path.join(os.getcwd(), inspiration_file),  # Current working directory
            os.path.join(os.getcwd(), "inspiration.md"),  # Default in current dir
        ]
        
        inspiration_path = None
        for location in possible_locations:
            if os.path.exists(location):
                inspiration_path = location
                break
        
        if not inspiration_path:
            raise FileNotFoundError(f"inspiration.md not found in any of these locations: {possible_locations}")
        
        print(f"Using inspiration file: {inspiration_path}")
        
        inspirations = []
        with open(inspiration_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse comma-delimited format: "Author, Book Title"
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        for line in lines:
            if ',' in line:
                author, book = [part.strip() for part in line.split(',', 1)]
                inspirations.append((author, book))
        
        return inspirations
    
    def analyze_style(self, author: str, book: str) -> Dict[str, str]:
        """Analyze the writing style of a specific author/book."""
        cache_key = f"{author}_{book}".replace(' ', '_')
        
        if cache_key in self.style_cache:
            return self.style_cache[cache_key]
        
        prompt = f"""Analyze the writing style of {author} in "{book}" for fiction writing enhancement. 

Provide analysis in these categories:

NARRATIVE VOICE:
- Point of view and narrative distance
- Tone and personality of narrator

PROSE RHYTHM:
- Sentence structure patterns
- Pacing techniques
- Paragraph flow

DIALOGUE STYLE:
- Formality level
- Subtext and implication
- Character voice differentiation

DESCRIPTIVE TECHNIQUES:
- Sensory detail usage
- Metaphor and imagery style
- Setting integration

CHARACTER INTERIORITY:
- How thoughts are presented
- Psychological depth approach
- Emotional revelation methods

TENSION BUILDING:
- Suspense creation techniques
- Information revelation patterns
- Conflict development style

Keep each section concise but specific, focusing on actionable techniques for literary enhancement."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            analysis = response.content[0].text
            self.style_cache[cache_key] = analysis
            return analysis
            
        except Exception as e:
            print(f"Error analyzing {author} - {book}: {e}")
            return ""
    
    def create_combined_style_guide(self, inspirations: List[Tuple[str, str]]) -> str:
        """Create a combined style guide from multiple inspirations."""
        analyses = []
        
        print("Analyzing inspiration sources...")
        for author, book in inspirations:
            print(f"  - {author}: {book}")
            analysis = self.analyze_style(author, book)
            if analysis:
                analyses.append(f"=== {author} - {book} ===\n{analysis}")
        
        combined_guide = "\n\n".join(analyses)
        
        # Create synthesis prompt
        synthesis_prompt = f"""Based on these literary style analyses, create a unified style guide for enhancing spy fiction writing:

{combined_guide}

Create a SYNTHESIS that combines the best techniques from all sources, organized as:

NARRATIVE APPROACH:
PROSE STYLE:
DIALOGUE TECHNIQUES:
DESCRIPTIVE METHODS:
CHARACTER DEVELOPMENT:
SUSPENSE BUILDING:

Focus on techniques that work well together for literary spy fiction."""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": synthesis_prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            print(f"Error creating synthesis: {e}")
            return combined_guide

class ChapterEnhancer:
    """Enhances chapter content using AI and style guidelines."""
    
    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
    
    def load_chapter(self, chapter_file: str) -> str:
        """Load chapter content from file, supporting multi-project structure."""
        # Try various locations and naming patterns
        possible_paths = [
            chapter_file,  # Exact path as provided
            os.path.join("chapters", chapter_file),  # chapters/ subdirectory
            os.path.join("content", chapter_file),  # content/ subdirectory
            os.path.join("manuscript", chapter_file),  # manuscript/ subdirectory
        ]
        
        # Add common chapter naming variations
        base_name = os.path.splitext(os.path.basename(chapter_file))[0]
        possible_variations = [
            f"{base_name}.md",
            f"chapter_{base_name}.md",
            f"ch_{base_name}.md",
            f"{base_name}.txt",
        ]
        
        # Combine paths with variations
        for directory in [".", "chapters", "content", "manuscript"]:
            for variation in possible_variations:
                possible_paths.append(os.path.join(directory, variation))
        
        # Find the first existing file
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            raise FileNotFoundError(f"Chapter file not found: {chapter_file}\nTried locations: {possible_paths[:8]}... (and {len(possible_paths)-8} more)")
        
        print(f"Loading chapter from: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def enhance_chapter(self, chapter_content: str, style_guide: str, 
                       preserve_structure: bool = True, target_word_count: int = None) -> str:
        """Enhance chapter using AI and style guide."""
        
        # Calculate original word count
        original_word_count = len(chapter_content.split())
        
        # Determine target word count
        if target_word_count is None:
            # Default: expand by 50-100% for literary enhancement
            target_word_count = int(original_word_count * 1.5)
        
        word_count_guidance = f"""
TARGET WORD COUNT: Approximately {target_word_count} words
ORIGINAL WORD COUNT: {original_word_count} words
EXPANSION GUIDANCE: {"Expand significantly" if target_word_count > original_word_count * 1.3 else "Moderate expansion" if target_word_count > original_word_count else "Maintain similar length"}

Word count priorities:
- Add atmospheric detail and psychological depth
- Expand character interiority and subtext in dialogue
- Enhance descriptive passages without padding
- Deepen the spy craft and academic atmosphere
- Quality over quantity - every word should serve the story
"""
        
        enhancement_prompt = f"""You are enhancing a COMPLETE chapter from "A Season of Spies," a literary spy novel about Dr. Henry Millbank, a retired Cambridge academic and former MI6 agent drawn back into Cold War secrets.

STYLE GUIDE TO FOLLOW:
{style_guide}

{word_count_guidance}

COMPLETE CHAPTER TO ENHANCE (YOU MUST ENHANCE EVERY WORD FROM START TO FINISH):
{chapter_content}

ENHANCEMENT REQUIREMENTS:
1. YOU MUST ENHANCE THE ENTIRE CHAPTER - EVERY SCENE, EVERY PARAGRAPH, EVERY SENTENCE
2. DO NOT STOP UNTIL YOU HAVE REWRITTEN THE COMPLETE CHAPTER FROM BEGINNING TO END
3. Maintain the five-act structure in each scene (Inciting Incident, Rising Action, Crisis, Climax, Resolution)
4. Preserve all plot points and character development
5. Enhance prose style using the provided techniques
6. Deepen atmospheric details (Cambridge academia, Cold War shadows, family tensions)
7. Strengthen character voices and psychological depth
8. Improve dialogue with subtext and tension
9. Enhance descriptive passages without overwhelming the narrative
10. Aim for approximately {target_word_count} words in the enhanced version

MANDATORY COMPLETION REQUIREMENTS:
- START at the very beginning of the chapter
- WORK THROUGH every single scene systematically
- DO NOT skip any content
- DO NOT summarize or abbreviate any sections
- CONTINUE until you reach the very end of the chapter
- ENHANCE every paragraph, not just selected portions
- The final output must be a COMPLETE chapter ready for publication

IMPORTANT: This is literary fiction, not a thriller. Focus on:
- Psychological complexity over action
- Atmospheric tension over dramatic suspense
- Character relationships and moral ambiguity
- Beautiful, precise prose that serves the story

ABSOLUTELY CRITICAL INSTRUCTIONS:
- You MUST enhance the ENTIRE chapter from the very first word to the very last word
- Do NOT stop partway through or ask for permission to continue
- Do NOT include any commentary, questions, or notes in your response
- Do NOT include phrases like "Would you like me to continue..." or "[Commentary about the enhancement]"
- Do NOT say "I'll continue with the rest" or similar - just continue seamlessly
- Return ONLY the complete enhanced chapter text with no meta-commentary
- Work through every scene and every paragraph systematically
- The response should be the full enhanced chapter ready for publication
- Aim for the target word count through quality enhancement, not padding
- If you run out of space, prioritize completing the ENTIRE chapter over perfect prose

VERIFICATION: Your response should start with the enhanced version of the very first sentence of the chapter and end with the enhanced version of the very last sentence. Every word in between must be enhanced.

Return the complete enhanced chapter with elevated prose style."""

        try:
            # Use maximum tokens to ensure complete chapter enhancement
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=8000,  # Increased for complete chapters
                messages=[{"role": "user", "content": enhancement_prompt}]
            )
            
            enhanced_text = response.content[0].text
            
            # Clean up any AI commentary that might have slipped through
            enhanced_text = self._clean_ai_commentary(enhanced_text)
            
            # Verify completion by checking if we have substantial content
            enhanced_word_count = len(enhanced_text.split())
            if enhanced_word_count < original_word_count * 0.8:
                print(f"WARNING: Enhanced chapter seems incomplete ({enhanced_word_count} words vs {original_word_count} original)")
                print("Consider running enhancement again or checking for truncation")
            
            # Report word counts
            print(f"Word count: {original_word_count} → {enhanced_word_count} (target: {target_word_count})")
            
            return enhanced_text
            
        except Exception as e:
            print(f"Error enhancing chapter: {e}")
            return chapter_content
    
    def _clean_ai_commentary(self, text: str) -> str:
        """Remove any AI commentary or meta-text from the enhanced chapter."""
        import re
        
        # Remove common AI commentary patterns
        patterns_to_remove = [
            r'\[.*?\]',  # Anything in square brackets
            r'Would you like.*?\?',  # Questions about continuation
            r'I can continue.*?\.', # Continuation offers
            r'Let me know.*?\.', # Requests for feedback
            r'This enhancement.*?\.', # Commentary about the enhancement
            r'Note:.*?\.', # Notes
            r'Commentary:.*?\.', # Commentary sections
        ]
        
        cleaned_text = text
        for pattern in patterns_to_remove:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        
        # Clean up extra whitespace
        cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text
    
    def save_enhanced_chapter(self, content: str, output_file: str):
        """Save enhanced chapter to file, maintaining project structure."""
        # Smart output path determination
        if not os.path.dirname(output_file):
            # No directory specified, determine appropriate location
            cwd_name = os.path.basename(os.getcwd()).lower()
            
            # Check for common chapter directories
            possible_dirs = ["chapters", "content", "manuscript"]
            target_dir = None
            
            for dir_name in possible_dirs:
                if os.path.exists(dir_name):
                    target_dir = dir_name
                    break
            
            if target_dir:
                output_file = os.path.join(target_dir, output_file)
            # Otherwise save in current directory
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        
        # Create backup of original if it exists
        if os.path.exists(output_file):
            backup_file = f"{output_file}.backup"
            os.rename(output_file, backup_file)
            print(f"Original backed up to: {backup_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Enhanced chapter saved to: {output_file}")

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Enhance chapters using AI and literary inspiration sources",
        epilog="""
Examples:
  # From project root for any novel
  python inspiration.py glasshouse/chapter_01.md --words 3000
  
  # From within a novel directory  
  cd glasshouse && python ../inspiration.py chapter_01.md
  
  # Using relative paths
  python inspiration.py ./my-novel/chapters/chapter1.md
        """
    )
    parser.add_argument(
        "chapter_file", 
        help="Path to the chapter file to enhance (supports relative paths and auto-discovery)"
    )
    parser.add_argument(
        "--inspiration", 
        default="inspiration.md",
        help="Path to inspiration.md file (default: inspiration.md)"
    )
    parser.add_argument(
        "--output", 
        help="Output file path (default: adds '_enhanced' to input filename)"
    )
    parser.add_argument(
        "--words", 
        type=int,
        help="Target word count for enhanced chapter (default: 1.5x original length)"
    )
    parser.add_argument(
        "--style-only", 
        action="store_true",
        help="Only generate and display style guide, don't enhance chapter"
    )
    
    args = parser.parse_args()
    
    # Initialize components
    try:
        analyzer = InspirationAnalyzer()
        enhancer = ChapterEnhancer()
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        return 1
    
    try:
        # Load inspirations
        inspirations = analyzer.load_inspirations(args.inspiration)
        if not inspirations:
            print(f"No inspirations found in {args.inspiration}")
            return 1
        
        print(f"Loaded {len(inspirations)} inspiration sources from {args.inspiration}")
        
        # Create style guide
        style_guide = analyzer.create_combined_style_guide(inspirations)
        
        if args.style_only:
            print("\n" + "="*50)
            print("COMBINED STYLE GUIDE")
            print("="*50)
            print(style_guide)
            return 0
        
        # Load and enhance chapter
        chapter_content = enhancer.load_chapter(args.chapter_file)
        print(f"\nLoaded chapter: {args.chapter_file}")
        
        original_word_count = len(chapter_content.split())
        print(f"Original length: {len(chapter_content)} characters ({original_word_count} words)")
        
        print("\nEnhancing chapter with AI...")
        enhanced_content = enhancer.enhance_chapter(
            chapter_content, 
            style_guide, 
            target_word_count=args.words
        )
        enhanced_word_count = len(enhanced_content.split())
        print(f"Enhanced length: {len(enhanced_content)} characters ({enhanced_word_count} words)")
        
        # Save enhanced chapter
        if args.output:
            output_file = args.output
        else:
            # Smart output file naming
            if "/" in args.chapter_file or "\\" in args.chapter_file:
                # File had a path, maintain the same directory structure
                base, ext = os.path.splitext(args.chapter_file)
                output_file = f"{base}_enhanced{ext}"
            else:
                # Simple filename, check if it should go in chapters/
                base, ext = os.path.splitext(args.chapter_file)
                if "chapter" in base.lower():
                    output_file = f"chapters/{base}_enhanced{ext}"
                else:
                    output_file = f"{base}_enhanced{ext}"
        
        enhancer.save_enhanced_chapter(enhanced_content, output_file)
        print(f"\nEnhancement complete!")
        
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())