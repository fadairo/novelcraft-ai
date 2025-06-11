#!/usr/bin/env python3
"""
Minimal Enhancement Script
Makes subtle, strategic improvements while preserving human quality
"""

import os
import re
import random
from typing import List, Dict, Tuple
import tiktoken
from anthropic import Anthropic
from dotenv import load_dotenv
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("Downloading required NLTK data...")
    nltk.download('punkt', quiet=True)

# Load environment variables
load_dotenv()

class MinimalEnhancer:
    """Make tiny, strategic improvements to preserve human quality"""
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.tiktoken_enc = tiktoken.get_encoding("cl100k_base")
        
        # What NOT to touch
        self.preserve_patterns = {
            'dialogue': re.compile(r'"[^"]*"'),
            'numbers': re.compile(r'\b\d+\b'),
            'fragments': re.compile(r'^[A-Z][^.!?]{0,15}[.!?]$'),
            'simple_sentences': re.compile(r'^[A-Z][^,]{0,50}[.!?]$')
        }
    
    def analyze_text(self, text: str) -> Dict:
        """Light analysis - just identify what's working"""
        sentences = sent_tokenize(text)
        
        # Identify what to preserve
        preserve_indices = []
        issues = []
        
        for i, sent in enumerate(sentences):
            # Preserve dialogue
            if self.preserve_patterns['dialogue'].search(sent):
                preserve_indices.append(i)
            # Preserve good fragments
            elif len(sent.split()) <= 3:
                preserve_indices.append(i)
            # Preserve simple, clear sentences
            elif len(sent.split()) <= 8 and ',' not in sent:
                preserve_indices.append(i)
            # Flag only real problems
            elif len(sent.split()) > 40:
                issues.append((i, 'very_long'))
            elif sent.count(',') > 4:
                issues.append((i, 'over_punctuated'))
        
        # Check for rhythm problems (only flag extremes)
        lengths = [len(word_tokenize(s)) for s in sentences]
        for i in range(len(lengths) - 2):
            if 15 < lengths[i] < 25 and 15 < lengths[i+1] < 25 and 15 < lengths[i+2] < 25:
                issues.append((i, 'three_medium_sentences'))
        
        return {
            'sentence_count': len(sentences),
            'preserve_indices': preserve_indices,
            'preservation_rate': len(preserve_indices) / len(sentences) if sentences else 0,
            'issues': issues[:10],  # Max 10 issues to address
            'sentences': sentences
        }
    
    def chunk_text(self, text: str, max_tokens: int = 2000) -> List[str]:
        """Split text into chunks at paragraph boundaries"""
        paragraphs = text.strip().split('\n\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = len(self.tiktoken_enc.encode(para))
            
            if current_tokens + para_tokens > max_tokens and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks
    
    def create_minimal_prompt(self, input_chunk: str, analysis: Dict) -> str:
        """Create very restrained prompt"""
        
        # Build specific, limited guidance
        issues_str = "None identified - text is already strong" if not analysis['issues'] else \
                    '\n'.join([f"- Sentence {i+1}: {issue}" for i, issue in analysis['issues'][:5]])
        
        prompt = f"""Make minimal improvements to the text below. The text is already good - it just needs light polishing.

CURRENT ANALYSIS:
- {analysis['preservation_rate']*100:.0f}% of sentences are already perfect - DO NOT change these
- Minor issues to address:
{issues_str}

CRITICAL RULES:
1. Change at most 5-10% of the text
2. NEVER touch dialogue (anything in quotes)
3. NEVER replace simple words with fancy ones
4. NEVER add metaphors or flowery language
5. Keep all fragments that work
6. Preserve the author's natural voice

ALLOWED CHANGES ONLY:
- Break up sentences over 40 words (sparingly)
- Add a paragraph break if needed for rhythm
- Fix only awkward constructions
- Remove excessive commas from over-punctuated sentences
- Break up 3+ consecutive medium-length sentences

FORBIDDEN:
- No thesaurus replacements ("said" stays "said", "walked" stays "walked")
- No adding dramatic fragments
- No combining short sentences
- No style flourishes

Think of this as proofreading, not rewriting. The goal is to be invisible.

Text to minimally enhance:
{input_chunk}

Output the lightly polished text only."""
        
        return prompt
    
    def enhance_minimally(self, input_text: str, output_file: str):
        """Main method - enhance with extreme restraint"""
        
        print("Analyzing text...")
        full_analysis = self.analyze_text(input_text)
        
        print(f"\nText Analysis:")
        print(f"  - Total sentences: {full_analysis['sentence_count']}")
        print(f"  - Already perfect: {full_analysis['preservation_rate']*100:.0f}%")
        print(f"  - Issues found: {len(full_analysis['issues'])}")
        
        if full_analysis['preservation_rate'] > 0.9:
            print("\n✓ Text is already very strong - minimal changes needed")
        
        print("\nChunking text...")
        chunks = self.chunk_text(input_text)
        print(f"Processing {len(chunks)} chunks with extreme restraint...")
        
        enhanced_chunks = []
        total_changes = 0
        
        for i, chunk in enumerate(chunks):
            print(f"\nProcessing chunk {i+1}/{len(chunks)}...")
            
            # Re-analyze chunk
            chunk_analysis = self.analyze_text(chunk)
            
            # Skip if chunk is already perfect
            if chunk_analysis['preservation_rate'] > 0.95:
                print("  → Chunk is already excellent, preserving as-is")
                enhanced_chunks.append(chunk)
                continue
            
            prompt = self.create_minimal_prompt(chunk, chunk_analysis)
            
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=4000,
                    temperature=0.3,  # Low temperature for consistency
                    messages=[{"role": "user", "content": prompt}]
                )
                
                enhanced_chunk = response.content[0].text
                
                # Count changes
                orig_words = chunk.split()
                new_words = enhanced_chunk.split()
                changes = abs(len(orig_words) - len(new_words))
                total_changes += changes
                
                # Em-dash replacement
                enhanced_chunk = re.sub(r'(\w)—(\w)', r'\1, \2', enhanced_chunk)
                enhanced_chunk = re.sub(r'(\w)–(\w)', r'\1, \2', enhanced_chunk)
                enhanced_chunk = re.sub(r'(\w)--(\w)', r'\1, \2', enhanced_chunk)
                enhanced_chunk = enhanced_chunk.replace('—', '...')
                enhanced_chunk = enhanced_chunk.replace('–', '...')
                enhanced_chunk = enhanced_chunk.replace('--', '...')
                
                enhanced_chunks.append(enhanced_chunk)
                
                if changes > 0:
                    print(f"  → Made ~{changes} word changes")
                
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                enhanced_chunks.append(chunk)
        
        # Combine and save
        final_text = '\n\n'.join(enhanced_chunks)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"\nMinimal enhancement complete! Output saved to {output_file}")
        
        # Final comparison
        self.compare_changes(input_text, final_text)
    
    def compare_changes(self, original: str, enhanced: str):
        """Show minimal changes made"""
        orig_words = original.split()
        enh_words = enhanced.split()
        
        print("\nChange Summary:")
        print(f"  Original words: {len(orig_words)}")
        print(f"  Enhanced words: {len(enh_words)}")
        print(f"  Change rate: {abs(len(orig_words) - len(enh_words)) / len(orig_words) * 100:.1f}%")
        
        # Check if we stayed minimal
        if abs(len(orig_words) - len(enh_words)) / len(orig_words) < 0.1:
            print("\n✓ Successfully maintained minimal change rate (<10%)")
        else:
            print("\n⚠ Warning: Changes exceeded 10% - may need manual review")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Minimal text enhancement - light touch improvements only',
        epilog='''
This script makes only essential improvements while preserving the human quality of writing.
It aims for <10% changes and focuses on fixing only real problems.

Examples:
  python minimal_enhance.py input.txt output.txt
  python minimal_enhance.py -i draft.md -o polished.md
        '''
    )
    
    # Arguments  
    parser.add_argument('input', nargs='?', help='Input text file')
    parser.add_argument('output', nargs='?', help='Output file')
    
    parser.add_argument('-i', '--input', dest='input_alt', help='Input text file')
    parser.add_argument('-o', '--output', dest='output_alt', help='Output file')
    
    args = parser.parse_args()
    
    # Determine files
    input_file = args.input or args.input_alt
    output_file = args.output or args.output_alt
    
    if not all([input_file, output_file]):
        parser.print_help()
        print("\nError: Both input and output files required")
        return
    
    # Check input exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        return
    
    # Force .md output
    if not output_file.endswith('.md'):
        output_file = output_file.rsplit('.', 1)[0] + '.md' if '.' in output_file else output_file + '.md'
    
    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file")
        return
    
    # Read input
    print(f"Reading input from: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        input_text = f.read()
    
    # Check text length
    word_count = len(input_text.split())
    if word_count < 100:
        print("Warning: Text is very short. Script works best with 500+ words.")
    
    # Run enhancer
    enhancer = MinimalEnhancer(api_key)
    enhancer.enhance_minimally(input_text, output_file)

if __name__ == "__main__":
    main()