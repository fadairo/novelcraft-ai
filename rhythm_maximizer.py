#!/usr/bin/env python3
"""
Rhythm Maximizer Script
Maximizes sentence length variation for dramatic effect
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
import numpy as np

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("Downloading required NLTK data...")
    nltk.download('punkt', quiet=True)

# Load environment variables
load_dotenv()

class RhythmMaximizer:
    """Maximize sentence length variation for dramatic rhythm"""
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.tiktoken_enc = tiktoken.get_encoding("cl100k_base")
    
    def analyze_rhythm(self, text: str) -> Dict:
        """Analyze sentence rhythm patterns"""
        sentences = sent_tokenize(text)
        lengths = [len(word_tokenize(s)) for s in sentences]
        
        if not lengths:
            return {'variance': 0, 'patterns': {}, 'problems': []}
        
        # Calculate variance
        variance = np.var(lengths)
        
        # Categorize sentences
        patterns = {
            'very_short': sum(1 for l in lengths if l <= 3),
            'short': sum(1 for l in lengths if 4 <= l <= 8),
            'medium': sum(1 for l in lengths if 9 <= l <= 20),
            'long': sum(1 for l in lengths if 21 <= l <= 35),
            'very_long': sum(1 for l in lengths if l > 35)
        }
        
        # Find problematic patterns (consecutive similar lengths)
        problems = []
        consecutive_medium = 0
        
        for i in range(len(lengths) - 1):
            # Check for similar consecutive lengths
            if abs(lengths[i] - lengths[i+1]) < 3:
                problems.append(f"Sentences {i+1} and {i+2} too similar ({lengths[i]} vs {lengths[i+1]} words)")
            
            # Track consecutive medium sentences
            if 9 <= lengths[i] <= 20:
                consecutive_medium += 1
                if consecutive_medium >= 3:
                    problems.append(f"Too many consecutive medium sentences starting at {i-1}")
            else:
                consecutive_medium = 0
        
        # Calculate dramatic swings
        dramatic_swings = sum(1 for i in range(len(lengths)-1) if abs(lengths[i] - lengths[i+1]) > 15)
        
        return {
            'variance': variance,
            'sentence_count': len(sentences),
            'lengths': lengths,
            'patterns': patterns,
            'problems': problems[:5],  # Top 5 problems
            'dramatic_swings': dramatic_swings,
            'avg_length': np.mean(lengths),
            'min_length': min(lengths),
            'max_length': max(lengths),
            'sentences': sentences
        }
    
    def chunk_text(self, text: str, max_tokens: int = 1500) -> List[str]:
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
    
    def create_rhythm_prompt(self, input_chunk: str, analysis: Dict, 
                           target_variance: int = 300) -> str:
        """Create prompt focused on maximizing rhythm variation"""
        
        # Build problem summary
        problems_str = '\n'.join([f"- {p}" for p in analysis['problems']]) if analysis['problems'] else "- No major issues found"
        
        # Calculate what changes are needed
        needs_more = []
        if analysis['patterns']['very_short'] < 2:
            needs_more.append("very short sentences (1-3 words)")
        if analysis['patterns']['very_long'] < 1:
            needs_more.append("very long sentences (35+ words)")
        if analysis['dramatic_swings'] < 3:
            needs_more.append("dramatic length swings (15+ word differences)")
        
        prompt = f"""Your task is to maximize sentence length variation in the text below to create dramatic rhythm.

CURRENT RHYTHM ANALYSIS:
- Sentence variance: {analysis['variance']:.1f} (target: {target_variance}+)
- Current pattern: {analysis['patterns']['very_short']} very short, {analysis['patterns']['short']} short, {analysis['patterns']['medium']} medium, {analysis['patterns']['long']} long, {analysis['patterns']['very_long']} very long
- Dramatic swings: {analysis['dramatic_swings']}
- Range: {analysis['min_length']} to {analysis['max_length']} words

PROBLEMS TO FIX:
{problems_str}

NEEDS MORE: {', '.join(needs_more) if needs_more else 'Better distribution across all lengths'}

RHYTHM MAXIMIZATION TECHNIQUES:
1. FRAGMENT long sentences: "She walked to the store and bought milk" → "She walked to the store. Bought milk." OR just "Milk."
2. COMBINE short sentences: "It was cold. It was dark. I was afraid." → "It was cold and dark, the kind of bone-chilling darkness that seeps into your soul and awakens primal fears you didn't know existed."
3. CREATE STACCATO: Use 1-3 word sentences for impact. "Done." "Never." "Perfect."
4. BUILD FLOWING RIVERS: Combine related ideas into 40+ word sentences using semicolons, dashes, and conjunctions
5. DRAMATIC TRANSITIONS: Follow very short with very long (or vice versa)

TARGET RHYTHM PATTERN:
- At least 3 very short sentences (1-3 words)
- At least 2 very long sentences (35+ words)
- No more than 2 consecutive sentences of similar length
- Create 5+ dramatic swings (15+ word differences)

CRITICAL RULES:
1. PRESERVE all facts, names, numbers, and events
2. NEVER add new information or change meaning
3. Only redistribute existing content into different sentence structures
4. Maintain paragraph breaks
5. Keep the same tone and style

SPECIFIC TECHNIQUES:
- Break at natural pause points: "and", "but", commas
- Use fragments for emphasis: "Never again." "His mistake."
- Combine with semicolons, colons, dashes for flow
- Move modifiers to create length variation

Text to maximize:
{input_chunk}

Output only the text with maximized rhythm variation."""
        
        return prompt
    
    def maximize_rhythm(self, input_text: str, output_file: str, 
                       target_variance: int = 300):
        """Main method to maximize rhythm variation"""
        
        print("Analyzing current rhythm patterns...")
        full_analysis = self.analyze_rhythm(input_text)
        
        print(f"\nCurrent Rhythm Analysis:")
        print(f"  - Sentence variance: {full_analysis['variance']:.1f}")
        print(f"  - Dramatic swings: {full_analysis['dramatic_swings']}")
        print(f"  - Sentence range: {full_analysis['min_length']} to {full_analysis['max_length']} words")
        print(f"  - Pattern: {full_analysis['patterns']['very_short']} very short, "
              f"{full_analysis['patterns']['medium']} medium, "
              f"{full_analysis['patterns']['very_long']} very long")
        
        if full_analysis['problems']:
            print(f"  - Issues found: {len(full_analysis['problems'])}")
        
        print(f"\nTarget variance: {target_variance}")
        
        print("\nChunking text...")
        chunks = self.chunk_text(input_text)
        print(f"Processing {len(chunks)} chunks...")
        
        maximized_chunks = []
        
        for i, chunk in enumerate(chunks):
            print(f"\nProcessing chunk {i+1}/{len(chunks)}...")
            
            # Analyze each chunk
            chunk_analysis = self.analyze_rhythm(chunk)
            
            prompt = self.create_rhythm_prompt(chunk, chunk_analysis, target_variance)
            
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=4000,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                maximized_chunk = response.content[0].text
                
                # Em-dash replacement
                maximized_chunk = re.sub(r'(\w)—(\w)', r'\1, \2', maximized_chunk)
                maximized_chunk = re.sub(r'(\w)–(\w)', r'\1, \2', maximized_chunk)
                maximized_chunk = re.sub(r'(\w)--(\w)', r'\1, \2', maximized_chunk)
                maximized_chunk = maximized_chunk.replace('—', '...')
                maximized_chunk = maximized_chunk.replace('–', '...')
                maximized_chunk = maximized_chunk.replace('--', '...')
                
                maximized_chunks.append(maximized_chunk)
                
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                maximized_chunks.append(chunk)
        
        # Combine and save
        final_text = '\n\n'.join(maximized_chunks)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"\nRhythm maximization complete! Output saved to {output_file}")
        
        # Compare before/after
        self.compare_rhythm(input_text, final_text)
    
    def compare_rhythm(self, original: str, maximized: str):
        """Compare rhythm patterns before and after"""
        orig_analysis = self.analyze_rhythm(original)
        max_analysis = self.analyze_rhythm(maximized)
        
        print("\nRhythm Comparison:")
        print(f"  Variance: {orig_analysis['variance']:.1f} → {max_analysis['variance']:.1f}")
        print(f"  Dramatic swings: {orig_analysis['dramatic_swings']} → {max_analysis['dramatic_swings']}")
        print(f"  Range: {orig_analysis['min_length']}-{orig_analysis['max_length']} → "
              f"{max_analysis['min_length']}-{max_analysis['max_length']} words")
        
        print("\n  Pattern changes:")
        for category in ['very_short', 'short', 'medium', 'long', 'very_long']:
            orig = orig_analysis['patterns'][category]
            new = max_analysis['patterns'][category]
            if orig != new:
                print(f"    {category}: {orig} → {new}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Maximize sentence rhythm variation for dramatic effect',
        epilog='''
Examples:
  python rhythm_maximizer.py input.txt output.txt
  python rhythm_maximizer.py input.txt output.txt --variance 400
  python rhythm_maximizer.py -i draft.md -o dynamic.md --variance 250
        '''
    )
    
    # Arguments
    parser.add_argument('input', nargs='?', help='Input text file')
    parser.add_argument('output', nargs='?', help='Output file')
    
    parser.add_argument('-i', '--input', dest='input_alt', help='Input text file')
    parser.add_argument('-o', '--output', dest='output_alt', help='Output file')
    
    parser.add_argument('--variance', type=int, default=300,
                       help='Target sentence variance (default: 300, range: 100-500)')
    
    args = parser.parse_args()
    
    # Determine files
    input_file = args.input or args.input_alt
    output_file = args.output or args.output_alt
    
    if not all([input_file, output_file]):
        parser.print_help()
        print("\nError: Both input and output files required")
        return
    
    # Check files exist
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        return
    
    # Force .md output
    if not output_file.endswith('.md'):
        output_file = output_file.rsplit('.', 1)[0] + '.md' if '.' in output_file else output_file + '.md'
    
    # Validate variance
    target_variance = max(100, min(500, args.variance))
    
    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file")
        return
    
    # Read input
    print(f"Reading input from: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        input_text = f.read()
    
    # Run maximizer
    maximizer = RhythmMaximizer(api_key)
    maximizer.maximize_rhythm(input_text, output_file, target_variance)

if __name__ == "__main__":
    main()