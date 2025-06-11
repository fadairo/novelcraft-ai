#!/usr/bin/env python3
"""
Minimal Style Transfer Script
Uses reference text snippets to guide subtle style shifts
"""

import os
import re
import random
from typing import List, Tuple
import tiktoken
from anthropic import Anthropic
from dotenv import load_dotenv
import nltk
from nltk.tokenize import sent_tokenize

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("Downloading required NLTK data...")
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    print("Downloading required NLTK punkt_tab data...")
    nltk.download('punkt_tab', quiet=True)

# Load environment variables
load_dotenv()

class MinimalStyleTransfer:
    """Minimal intervention style transfer"""
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.tiktoken_enc = tiktoken.get_encoding("cl100k_base")
    
    def extract_style_patterns(self, text: str) -> dict:
        """Extract comprehensive style patterns from reference text"""
        sentences = sent_tokenize(text)
        
        # Sentence rhythm patterns
        lengths = [len(s.split()) for s in sentences]
        
        # Identify characteristic patterns
        patterns = {
            'fragments': [s for s in sentences if len(s.split()) <= 3 and not s.endswith('?')],
            'questions': [s for s in sentences if s.endswith('?')],
            'long_flowing': [s for s in sentences if len(s.split()) > 25],
            'dialogue': [s for s in sentences if '"' in s],
            'single_word': [s for s in sentences if len(s.split()) == 1],
        }
        
        # Common sentence starters
        starters = {}
        for s in sentences:
            first_word = s.split()[0] if s.split() else ""
            if first_word:
                starters[first_word] = starters.get(first_word, 0) + 1
        
        # Frequent unusual words (not common English)
        all_words = ' '.join(sentences).lower().split()
        common_english = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                         'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be',
                         'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                         'should', 'may', 'might', 'must', 'shall', 'can', 'could'}
        
        unusual_words = [w for w in set(all_words) if w.isalpha() and len(w) > 4 and w not in common_english]
        unusual_words = sorted(unusual_words, key=lambda x: all_words.count(x), reverse=True)[:30]
        
        # Punctuation style
        punct_patterns = {
            'emdash_count': text.count('—'),
            'semicolon_count': text.count(';'),
            'colon_count': text.count(':'),
            'ellipsis_count': text.count('...'),
            'exclamation_count': text.count('!'),
        }
        
        # Paragraph structure
        paragraphs = text.strip().split('\n\n')
        para_lengths = [len(p.split()) for p in paragraphs if p.strip()]
        
        return {
            'patterns': patterns,
            'starters': dict(sorted(starters.items(), key=lambda x: x[1], reverse=True)[:10]),
            'unusual_words': unusual_words,
            'punct_patterns': punct_patterns,
            'avg_para_length': sum(para_lengths) / len(para_lengths) if para_lengths else 0,
            'sentence_lengths': lengths,
        }
    
    def create_enhanced_prompt(self, ref_patterns: dict, input_chunk: str, preserve_rate: float = 0.85) -> str:
        """Create prompt using deep reference analysis"""
        
        # Get most characteristic examples
        examples = []
        
        # Add different types of sentences
        if ref_patterns['patterns']['fragments']:
            examples.extend(random.sample(ref_patterns['patterns']['fragments'], 
                                        min(2, len(ref_patterns['patterns']['fragments']))))
        if ref_patterns['patterns']['long_flowing']:
            examples.extend(random.sample(ref_patterns['patterns']['long_flowing'], 
                                        min(2, len(ref_patterns['patterns']['long_flowing']))))
        if ref_patterns['patterns']['questions']:
            examples.extend(random.sample(ref_patterns['patterns']['questions'], 
                                        min(1, len(ref_patterns['patterns']['questions']))))
        
        # Add some regular sentences
        regular = [s for s in sent_tokenize(input_chunk)[:50] 
                  if 5 < len(s.split()) < 20][:3]
        examples.extend(regular)
        
        examples_text = "\n".join([f"- {ex}" for ex in examples[:12]])
        
        # Create vocabulary guidance
        vocab_guide = ", ".join(ref_patterns['unusual_words'][:15])
        
        # Note common sentence starters
        starter_guide = ", ".join([f'"{s}"' for s in list(ref_patterns['starters'].keys())[:5]])
        
        prompt = f"""I need you to subtly adjust the writing style of the text below to match a reference style.

REFERENCE STYLE CHARACTERISTICS:
Example sentences showing the rhythm and tone:
{examples_text}

The reference style often uses these distinctive words: {vocab_guide}

Common sentence starters include: {starter_guide}

Punctuation tendencies:
- Em-dashes: {"frequent" if ref_patterns['punct_patterns']['emdash_count'] > 10 else "occasional"}
- Semicolons: {"yes" if ref_patterns['punct_patterns']['semicolon_count'] > 5 else "rare"}
- Ellipses: {"yes" if ref_patterns['punct_patterns']['ellipsis_count'] > 5 else "rare"}

KEY RULES:
1. Keep {int(preserve_rate * 100)}% of the text EXACTLY as written
2. When you do change something, use the reference style's vocabulary and rhythm
3. NEVER change: facts, names, numbers, events, crude language, fragments
4. NEVER add new information or explanations
5. Think of this as the same author being influenced by reading the reference

Text to adjust:
{input_chunk}

Output the adjusted text only, no explanations."""
        
        return prompt
    
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
    
    def create_minimal_prompt(self, reference_examples: List[str], input_chunk: str, 
                            preserve_rate: float = 0.85) -> str:
        """Create a minimal, focused prompt"""
        
        # Join examples with clear markers
        examples_text = "\n".join([f"- {ex}" for ex in reference_examples])
        
        prompt = f"""I need you to subtly adjust the writing style of the text below. 

Here are some example sentences from the target style:
{examples_text}

KEY RULES:
1. Keep {int(preserve_rate * 100)}% of the text EXACTLY as written
2. Make only subtle changes - think of it as the same author on a different day
3. NEVER change: facts, names, numbers, events, crude language, fragments
4. NEVER add new information or explanations
5. Focus on small rhythm adjustments and occasional word substitutions

Text to adjust:
{input_chunk}

Output the adjusted text only, no explanations."""
        
        return prompt
    
    def transfer_style(self, reference_text: str, input_text: str, output_file: str,
                      preserve_rate: float = 0.85):
        """Main style transfer with enhanced reference analysis"""
        
        print("Analyzing reference text style patterns...")
        ref_patterns = self.extract_style_patterns(reference_text)
        
        print(f"\nReference style characteristics:")
        print(f"  - Fragment sentences: {len(ref_patterns['patterns']['fragments'])}")
        print(f"  - Questions: {len(ref_patterns['patterns']['questions'])}")
        print(f"  - Long flowing sentences: {len(ref_patterns['patterns']['long_flowing'])}")
        print(f"  - Distinctive vocabulary samples: {', '.join(ref_patterns['unusual_words'][:8])}")
        print(f"  - Common starters: {', '.join(list(ref_patterns['starters'].keys())[:5])}")
        
        print("\nChunking input text...")
        chunks = self.chunk_text(input_text)
        print(f"Processing {len(chunks)} chunks with {preserve_rate*100:.0f}% preservation rate...")
        
        revised_chunks = []
        
        for i, chunk in enumerate(chunks):
            print(f"\nProcessing chunk {i+1}/{len(chunks)}...")
            
            # Vary preservation slightly
            chunk_preserve = preserve_rate + random.uniform(-0.05, 0.05)
            chunk_preserve = max(0.75, min(0.95, chunk_preserve))
            
            prompt = self.create_enhanced_prompt(ref_patterns, chunk, chunk_preserve)
            
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=4000,
                    temperature=0.7,  # Add some randomness
                    messages=[{"role": "user", "content": prompt}]
                )
                
                revised_chunk = response.content[0].text
                
                # Em-dash replacement
                revised_chunk = re.sub(r'(\w)—(\w)', r'\1, \2', revised_chunk)
                revised_chunk = re.sub(r'(\w)–(\w)', r'\1, \2', revised_chunk)
                revised_chunk = re.sub(r'(\w)--(\w)', r'\1, \2', revised_chunk)
                revised_chunk = revised_chunk.replace('—', '...')
                revised_chunk = revised_chunk.replace('–', '...')
                revised_chunk = revised_chunk.replace('--', '...')
                
                revised_chunks.append(revised_chunk)
                
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                revised_chunks.append(chunk)
        
        # Combine and save
        final_text = '\n\n'.join(revised_chunks)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"\nStyle transfer complete! Output saved to {output_file}")
        
        # Simple comparison
        self.compare_texts(input_text, final_text)
    
    def compare_texts(self, original: str, revised: str):
        """Simple comparison of texts"""
        orig_sentences = sent_tokenize(original)
        rev_sentences = sent_tokenize(revised)
        
        orig_words = original.split()
        rev_words = revised.split()
        
        print("\nBasic comparison:")
        print(f"  Original sentences: {len(orig_sentences)}")
        print(f"  Revised sentences: {len(rev_sentences)}")
        print(f"  Original words: {len(orig_words)}")
        print(f"  Revised words: {len(rev_words)}")
        
        # Check for major content changes
        orig_numbers = set(re.findall(r'\b\d+\b', original))
        rev_numbers = set(re.findall(r'\b\d+\b', revised))
        
        if orig_numbers != rev_numbers:
            print("  ⚠️  Warning: Numbers may have changed")
        
        # Sample first paragraph changes
        orig_first = original.split('\n\n')[0]
        rev_first = revised.split('\n\n')[0]
        
        if orig_first != rev_first:
            print("\n  First paragraph was modified (this is expected)")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Minimal style transfer - subtle adjustments only',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python style_transfer.py reference.txt input.md output.md
  python style_transfer.py reference.txt input.md output.md --preserve 0.9
  python style_transfer.py -r style.md -i draft.txt -o final.md
        '''
    )
    
    # Arguments
    parser.add_argument('reference', nargs='?', help='Reference text file')
    parser.add_argument('input', nargs='?', help='Input text file')
    parser.add_argument('output', nargs='?', help='Output file (.md)')
    
    parser.add_argument('-r', '--reference', dest='ref_alt', help='Reference text file')
    parser.add_argument('-i', '--input', dest='input_alt', help='Input text file')
    parser.add_argument('-o', '--output', dest='output_alt', help='Output file')
    
    parser.add_argument('--preserve', type=float, default=0.85,
                       help='Preservation rate (0.75-0.95, default: 0.85)')
    
    args = parser.parse_args()
    
    # Determine files
    reference_file = args.reference or args.ref_alt
    input_file = args.input or args.input_alt
    output_file = args.output or args.output_alt
    
    if not all([reference_file, input_file, output_file]):
        parser.print_help()
        print("\nError: All three files required")
        return
    
    # Validate
    valid_extensions = ['.txt', '.md']
    
    if not any(reference_file.endswith(ext) for ext in valid_extensions):
        print(f"Error: Reference file must be .txt or .md")
        return
    
    if not any(input_file.endswith(ext) for ext in valid_extensions):
        print(f"Error: Input file must be .txt or .md")
        return
    
    # Force .md output
    if not output_file.endswith('.md'):
        output_file = output_file.rsplit('.', 1)[0] + '.md' if '.' in output_file else output_file + '.md'
        print(f"Output will be saved as: {output_file}")
    
    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file")
        return
    
    # Check files exist
    if not os.path.exists(reference_file):
        print(f"Error: Reference file '{reference_file}' not found")
        return
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        return
    
    # Read files
    print(f"Reading reference: {reference_file}")
    with open(reference_file, 'r', encoding='utf-8') as f:
        reference_text = f.read()
    
    print(f"Reading input: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        input_text = f.read()
    
    # Validate preservation rate
    preserve_rate = max(0.75, min(0.95, args.preserve))
    if preserve_rate != args.preserve:
        print(f"Preservation rate adjusted to: {preserve_rate}")
    
    # Run transfer
    agent = MinimalStyleTransfer(api_key)
    agent.transfer_style(reference_text, input_text, output_file, preserve_rate)

if __name__ == "__main__":
    main()