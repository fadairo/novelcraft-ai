#!/usr/bin/env python3
"""
Perplexity Boost Script
Increases word choice unpredictability while preserving meaning
"""

import os
import re
import random
from typing import List, Dict, Set, Tuple
import tiktoken
from anthropic import Anthropic
from dotenv import load_dotenv
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import wordnet
from collections import Counter

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("Downloading required NLTK data...")
    nltk.download('punkt', quiet=True)
    nltk.download('wordnet', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)

# Load environment variables
load_dotenv()

class PerplexityBooster:
    """Boost text perplexity by making word choices more surprising"""
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.tiktoken_enc = tiktoken.get_encoding("cl100k_base")
        
        # Common/predictable words to target for replacement
        self.common_words = {
            'verbs': {'said', 'went', 'got', 'made', 'took', 'came', 'saw', 'looked', 
                     'walked', 'ran', 'thought', 'felt', 'knew', 'told', 'asked'},
            'adjectives': {'good', 'bad', 'big', 'small', 'new', 'old', 'great', 
                          'little', 'high', 'low', 'large', 'long', 'young', 'important'},
            'adverbs': {'very', 'really', 'just', 'quite', 'rather', 'pretty', 
                       'actually', 'basically', 'simply', 'totally', 'definitely'},
            'transitions': {'however', 'therefore', 'moreover', 'furthermore', 
                           'nevertheless', 'consequently', 'additionally'}
        }
    
    def analyze_predictability(self, text: str) -> Dict:
        """Analyze text for predictable/common word usage"""
        words = word_tokenize(text.lower())
        word_count = len(words)
        
        # Count common words
        common_count = 0
        common_found = []
        
        for word in words:
            for category, word_list in self.common_words.items():
                if word in word_list:
                    common_count += 1
                    common_found.append((word, category))
                    break
        
        # Identify overused words (appearing too frequently)
        word_freq = Counter(words)
        overused = [(word, count) for word, count in word_freq.items() 
                   if count > 3 and len(word) > 3 and word.isalpha()]
        overused.sort(key=lambda x: x[1], reverse=True)
        
        return {
            'predictability_score': common_count / word_count if word_count > 0 else 0,
            'common_words_found': common_found[:20],  # Top 20
            'overused_words': overused[:10],  # Top 10
            'total_words': word_count
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
    
    def create_perplexity_prompt(self, input_chunk: str, analysis: Dict, 
                                boost_level: str = 'medium') -> str:
        """Create prompt focused on increasing word unpredictability"""
        
        # Set replacement rate based on boost level
        replacement_rates = {
            'low': 0.1,
            'medium': 0.2,
            'high': 0.3
        }
        rate = replacement_rates.get(boost_level, 0.2)
        
        # Create word replacement guidance
        common_words_str = ', '.join([f'"{w[0]}"' for w in analysis['common_words_found'][:10]])
        overused_str = ', '.join([f'"{w[0]}" ({w[1]} times)' for w in analysis['overused_words'][:5]])
        
        prompt = f"""Your task is to increase the unpredictability of word choices in the text below while preserving its exact meaning.

PREDICTABILITY ANALYSIS:
- Current predictability: {analysis['predictability_score']*100:.1f}% of words are common/predictable
- Common words found: {common_words_str}
- Overused words: {overused_str}

REPLACEMENT STRATEGY:
- Replace approximately {int(rate * 100)}% of common/predictable words with more surprising alternatives
- Target: {"aggressive unpredictability" if boost_level == 'high' else "moderate surprises" if boost_level == 'medium' else "subtle variations"}

WORD REPLACEMENT EXAMPLES:
- "said" → whispered, declared, muttered, proclaimed, ventured
- "walked" → ambled, prowled, shuffled, strode, drifted
- "big" → vast, immense, sprawling, monumental, colossal
- "very" → utterly, profoundly, remarkably, decidedly
- "looked at" → scrutinized, surveyed, absorbed, devoured with eyes

CRITICAL RULES:
1. NEVER change proper nouns, numbers, technical terms, or facts
2. NEVER alter the meaning or add new information
3. Keep the same tone and register (formal stays formal, casual stays casual)
4. Preserve all punctuation and paragraph structure
5. Maintain grammatical correctness
6. If a word is already unusual or specific, leave it alone

FOCUS ON:
- Verbs: Make actions more specific and vivid
- Adjectives: Choose more precise, evocative descriptors
- Adverbs: Replace generic intensifiers with specific ones
- Common phrases: Break up clichéd expressions

Text to enhance:
{input_chunk}

Output only the enhanced text with more unpredictable word choices."""
        
        return prompt
    
    def boost_perplexity(self, input_text: str, output_file: str, 
                        boost_level: str = 'medium'):
        """Main method to boost text perplexity"""
        
        print("Analyzing text predictability...")
        analysis = self.analyze_predictability(input_text)
        
        print(f"\nPredictability Analysis:")
        print(f"  - Predictability score: {analysis['predictability_score']*100:.1f}%")
        print(f"  - Common words found: {len(analysis['common_words_found'])}")
        print(f"  - Most overused: {', '.join([f'{w[0]} ({w[1]}x)' for w in analysis['overused_words'][:3]])}")
        print(f"  - Boost level: {boost_level}")
        
        print("\nChunking text...")
        chunks = self.chunk_text(input_text)
        print(f"Processing {len(chunks)} chunks...")
        
        boosted_chunks = []
        
        for i, chunk in enumerate(chunks):
            print(f"\nProcessing chunk {i+1}/{len(chunks)}...")
            
            # Re-analyze each chunk for targeted replacement
            chunk_analysis = self.analyze_predictability(chunk)
            
            prompt = self.create_perplexity_prompt(chunk, chunk_analysis, boost_level)
            
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=4000,
                    temperature=0.8,  # Higher temperature for more variety
                    messages=[{"role": "user", "content": prompt}]
                )
                
                boosted_chunk = response.content[0].text
                
                # Em-dash replacement as requested
                boosted_chunk = re.sub(r'(\w)—(\w)', r'\1, \2', boosted_chunk)
                boosted_chunk = re.sub(r'(\w)–(\w)', r'\1, \2', boosted_chunk)
                boosted_chunk = re.sub(r'(\w)--(\w)', r'\1, \2', boosted_chunk)
                boosted_chunk = boosted_chunk.replace('—', '...')
                boosted_chunk = boosted_chunk.replace('–', '...')
                boosted_chunk = boosted_chunk.replace('--', '...')
                
                boosted_chunks.append(boosted_chunk)
                
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                boosted_chunks.append(chunk)
        
        # Combine and save
        final_text = '\n\n'.join(boosted_chunks)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"\nPerplexity boost complete! Output saved to {output_file}")
        
        # Compare before/after
        self.compare_perplexity(input_text, final_text)
    
    def compare_perplexity(self, original: str, boosted: str):
        """Compare predictability before and after"""
        orig_analysis = self.analyze_predictability(original)
        boost_analysis = self.analyze_predictability(boosted)
        
        print("\nPerplexity Comparison:")
        print(f"  Predictability: {orig_analysis['predictability_score']*100:.1f}% → {boost_analysis['predictability_score']*100:.1f}%")
        
        # Show some word replacements
        orig_words = set(word_tokenize(original.lower()))
        boost_words = set(word_tokenize(boosted.lower()))
        
        new_words = boost_words - orig_words
        removed_words = orig_words - boost_words
        
        print(f"  New words introduced: {len(new_words)}")
        print(f"  Common words replaced: {len(removed_words)}")
        
        # Sample replacements
        if new_words and removed_words:
            print("\n  Sample replacements:")
            for i, (old, new) in enumerate(zip(list(removed_words)[:5], list(new_words)[:5])):
                print(f"    '{old}' → '{new}'")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Boost text perplexity by making word choices more surprising',
        epilog='''
Examples:
  python perplexity_boost.py input.txt output.txt
  python perplexity_boost.py input.txt output.txt --level high
  python perplexity_boost.py -i draft.md -o enhanced.md --level low
        '''
    )
    
    # Arguments
    parser.add_argument('input', nargs='?', help='Input text file')
    parser.add_argument('output', nargs='?', help='Output file')
    
    parser.add_argument('-i', '--input', dest='input_alt', help='Input text file')
    parser.add_argument('-o', '--output', dest='output_alt', help='Output file')
    
    parser.add_argument('--level', choices=['low', 'medium', 'high'], default='medium',
                       help='Boost level: low (10%%), medium (20%%), high (30%%) word replacement')
    
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
    
    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file")
        return
    
    # Read input
    print(f"Reading input from: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        input_text = f.read()
    
    # Run booster
    booster = PerplexityBooster(api_key)
    booster.boost_perplexity(input_text, output_file, args.level)

if __name__ == "__main__":
    main()
    