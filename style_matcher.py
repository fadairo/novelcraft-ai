#!/usr/bin/env python3
"""
Style Matcher Script
Matches the style patterns of a reference author without content transfer
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
from collections import Counter
import numpy as np

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("Downloading required NLTK data...")
    nltk.download('punkt', quiet=True)

# Load environment variables
load_dotenv()

class StyleMatcher:
    """Match reference author's style patterns"""
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.tiktoken_enc = tiktoken.get_encoding("cl100k_base")
    
    def analyze_style_patterns(self, text: str) -> Dict:
        """Extract pure style patterns (no content) from text"""
        sentences = sent_tokenize(text)
        all_words = ' '.join(sentences).split()
        
        # Sentence rhythm
        lengths = [len(word_tokenize(s)) for s in sentences]
        
        # Sentence transitions
        transitions = []
        for i in range(len(lengths) - 1):
            if lengths[i] <= 5:
                if lengths[i+1] <= 5:
                    transitions.append('short→short')
                elif lengths[i+1] <= 20:
                    transitions.append('short→medium')
                else:
                    transitions.append('short→long')
            elif lengths[i] <= 20:
                if lengths[i+1] <= 5:
                    transitions.append('medium→short')
                elif lengths[i+1] <= 20:
                    transitions.append('medium→medium')
                else:
                    transitions.append('medium→long')
            else:
                if lengths[i+1] <= 5:
                    transitions.append('long→short')
                elif lengths[i+1] <= 20:
                    transitions.append('long→medium')
                else:
                    transitions.append('long→long')
        
        # Syntactic patterns
        syntax = {
            'starts_with_conjunction': sum(1 for s in sentences if s.split() and s.split()[0].lower() in ['and', 'but', 'or', 'yet', 'so']),
            'starts_with_pronoun': sum(1 for s in sentences if s.split() and s.split()[0].lower() in ['i', 'you', 'he', 'she', 'it', 'we', 'they']),
            'starts_with_article': sum(1 for s in sentences if s.split() and s.split()[0].lower() in ['the', 'a', 'an']),
            'questions': sum(1 for s in sentences if s.endswith('?')),
            'exclamations': sum(1 for s in sentences if s.endswith('!')),
            'fragments': sum(1 for s in sentences if len(s.split()) <= 3),
        }
        
        # Punctuation density
        text_len = len(text)
        punct = {
            'comma_density': text.count(',') / text_len * 1000,
            'semicolon_density': text.count(';') / text_len * 1000,
            'colon_density': text.count(':') / text_len * 1000,
            'dash_density': (text.count('—') + text.count('–') + text.count(' - ')) / text_len * 1000,
            'parenthesis_density': text.count('(') / text_len * 1000,
            'quote_density': (text.count('"') + text.count("'")) / text_len * 1000,
        }
        
        # Paragraph patterns
        paragraphs = [p for p in text.strip().split('\n\n') if p.strip()]
        para_lengths = [len(p.split()) for p in paragraphs]
        
        # Word-level patterns (no specific words)
        word_lengths = [len(w) for w in all_words if w.isalpha()]
        
        return {
            'rhythm': {
                'avg_sentence_length': np.mean(lengths) if lengths else 0,
                'sentence_variance': np.var(lengths) if lengths else 0,
                'min_length': min(lengths) if lengths else 0,
                'max_length': max(lengths) if lengths else 0,
                'common_transitions': Counter(transitions).most_common(5),
            },
            'syntax': {
                'conjunction_start_rate': syntax['starts_with_conjunction'] / len(sentences) if sentences else 0,
                'pronoun_start_rate': syntax['starts_with_pronoun'] / len(sentences) if sentences else 0,
                'article_start_rate': syntax['starts_with_article'] / len(sentences) if sentences else 0,
                'question_rate': syntax['questions'] / len(sentences) if sentences else 0,
                'fragment_rate': syntax['fragments'] / len(sentences) if sentences else 0,
            },
            'punctuation': punct,
            'paragraphs': {
                'avg_length': np.mean(para_lengths) if para_lengths else 0,
                'variance': np.var(para_lengths) if para_lengths else 0,
                'count': len(paragraphs),
            },
            'word_patterns': {
                'avg_word_length': np.mean(word_lengths) if word_lengths else 0,
                'short_word_rate': sum(1 for w in word_lengths if w <= 3) / len(word_lengths) if word_lengths else 0,
                'long_word_rate': sum(1 for w in word_lengths if w >= 8) / len(word_lengths) if word_lengths else 0,
            }
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
    
    def create_style_matching_prompt(self, ref_patterns: Dict, input_chunk: str, 
                                   match_strength: float = 0.8) -> str:
        """Create prompt to match reference style patterns"""
        
        # Build style description
        rhythm = ref_patterns['rhythm']
        syntax = ref_patterns['syntax']
        punct = ref_patterns['punctuation']
        
        # Format transition patterns
        transitions_str = ', '.join([f"{t[0]} ({t[1]} times)" for t in rhythm['common_transitions'][:3]])
        
        prompt = f"""Your task is to adjust the text below to match specific style patterns (rhythm, syntax, punctuation) while preserving all content.

REFERENCE STYLE PATTERNS TO MATCH:

SENTENCE RHYTHM:
- Average length: {rhythm['avg_sentence_length']:.1f} words (variance: {rhythm['sentence_variance']:.1f})
- Range: {rhythm['min_length']} to {rhythm['max_length']} words
- Common transitions: {transitions_str}
- {syntax['fragment_rate']*100:.0f}% are fragments (≤3 words)

SENTENCE BEGINNINGS:
- {syntax['conjunction_start_rate']*100:.0f}% start with conjunctions (And, But, Or)
- {syntax['pronoun_start_rate']*100:.0f}% start with pronouns
- {syntax['article_start_rate']*100:.0f}% start with articles (The, A, An)
- {syntax['question_rate']*100:.0f}% are questions

PUNCTUATION STYLE:
- Commas: {punct['comma_density']:.1f} per 1000 chars ({"heavy" if punct['comma_density'] > 20 else "moderate" if punct['comma_density'] > 10 else "light"})
- Semicolons: {punct['semicolon_density']:.1f} per 1000 chars ({"frequent" if punct['semicolon_density'] > 1 else "occasional" if punct['semicolon_density'] > 0.2 else "rare"})
- Dashes: {punct['dash_density']:.1f} per 1000 chars
- Parentheticals: {punct['parenthesis_density']:.1f} per 1000 chars

MATCHING STRENGTH: {int(match_strength * 100)}% (how closely to match the patterns)

ADJUSTMENT TECHNIQUES:
1. RHYTHM: Fragment or combine sentences to match the target variance and transitions
2. BEGINNINGS: Rearrange sentence starts to match the percentages
3. PUNCTUATION: Add/remove punctuation to match the density patterns
4. FLOW: Create similar transition patterns between sentence lengths

CRITICAL PRESERVATION RULES:
1. NEVER change any facts, names, numbers, or events
2. NEVER add or remove information
3. NEVER change the meaning of any statement
4. ONLY adjust structure, rhythm, and punctuation
5. Maintain the same tone and register

EXAMPLES OF STYLE ADJUSTMENTS:
- Adding conjunction: "The market crashed." → "And the market crashed."
- Creating fragment: "He walked away slowly." → "He walked away. Slowly."
- Combining with semicolon: "It was late. I was tired." → "It was late; I was tired."
- Reordering: "Yesterday, the decision was made." → "The decision was made yesterday."

Text to adjust:
{input_chunk}

Output only the adjusted text that matches the reference style patterns."""
        
        return prompt
    
    def match_style(self, reference_text: str, input_text: str, output_file: str,
                   match_strength: float = 0.8):
        """Main method to match reference style"""
        
        print("Analyzing reference style patterns...")
        ref_patterns = self.analyze_style_patterns(reference_text)
        
        print(f"\nReference Style Characteristics:")
        print(f"  - Avg sentence: {ref_patterns['rhythm']['avg_sentence_length']:.1f} words (var: {ref_patterns['rhythm']['sentence_variance']:.1f})")
        print(f"  - Sentence range: {ref_patterns['rhythm']['min_length']} to {ref_patterns['rhythm']['max_length']} words")
        print(f"  - Fragment rate: {ref_patterns['syntax']['fragment_rate']*100:.0f}%")
        print(f"  - Question rate: {ref_patterns['syntax']['question_rate']*100:.0f}%")
        print(f"  - Punctuation: Commas={'heavy' if ref_patterns['punctuation']['comma_density'] > 20 else 'moderate' if ref_patterns['punctuation']['comma_density'] > 10 else 'light'}")
        print(f"  - Match strength: {int(match_strength * 100)}%")
        
        print("\nChunking input text...")
        chunks = self.chunk_text(input_text)
        print(f"Processing {len(chunks)} chunks...")
        
        matched_chunks = []
        
        for i, chunk in enumerate(chunks):
            print(f"\nProcessing chunk {i+1}/{len(chunks)}...")
            
            prompt = self.create_style_matching_prompt(ref_patterns, chunk, match_strength)
            
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=4000,
                    temperature=0.6,  # Lower temperature for consistency
                    messages=[{"role": "user", "content": prompt}]
                )
                
                matched_chunk = response.content[0].text
                
                # Em-dash replacement
                matched_chunk = re.sub(r'(\w)—(\w)', r'\1, \2', matched_chunk)
                matched_chunk = re.sub(r'(\w)–(\w)', r'\1, \2', matched_chunk)
                matched_chunk = re.sub(r'(\w)--(\w)', r'\1, \2', matched_chunk)
                matched_chunk = matched_chunk.replace('—', '...')
                matched_chunk = matched_chunk.replace('–', '...')
                matched_chunk = matched_chunk.replace('--', '...')
                
                matched_chunks.append(matched_chunk)
                
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                matched_chunks.append(chunk)
        
        # Combine and save
        final_text = '\n\n'.join(matched_chunks)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"\nStyle matching complete! Output saved to {output_file}")
        
        # Compare styles
        self.compare_styles(reference_text, input_text, final_text)
    
    def compare_styles(self, reference: str, original: str, matched: str):
        """Compare style patterns across all three texts"""
        ref_patterns = self.analyze_style_patterns(reference)
        orig_patterns = self.analyze_style_patterns(original)
        match_patterns = self.analyze_style_patterns(matched)
        
        print("\nStyle Comparison:")
        print("                     Reference → Original → Matched")
        print(f"  Avg sentence:      {ref_patterns['rhythm']['avg_sentence_length']:.1f} → "
              f"{orig_patterns['rhythm']['avg_sentence_length']:.1f} → "
              f"{match_patterns['rhythm']['avg_sentence_length']:.1f} words")
        print(f"  Variance:          {ref_patterns['rhythm']['sentence_variance']:.1f} → "
              f"{orig_patterns['rhythm']['sentence_variance']:.1f} → "
              f"{match_patterns['rhythm']['sentence_variance']:.1f}")
        print(f"  Fragment rate:     {ref_patterns['syntax']['fragment_rate']*100:.0f}% → "
              f"{orig_patterns['syntax']['fragment_rate']*100:.0f}% → "
              f"{match_patterns['syntax']['fragment_rate']*100:.0f}%")
        print(f"  Comma density:     {ref_patterns['punctuation']['comma_density']:.1f} → "
              f"{orig_patterns['punctuation']['comma_density']:.1f} → "
              f"{match_patterns['punctuation']['comma_density']:.1f}")
        
        # Calculate style similarity score
        ref_vec = [ref_patterns['rhythm']['avg_sentence_length'], 
                   ref_patterns['rhythm']['sentence_variance'],
                   ref_patterns['syntax']['fragment_rate'],
                   ref_patterns['punctuation']['comma_density']]
        
        match_vec = [match_patterns['rhythm']['avg_sentence_length'],
                     match_patterns['rhythm']['sentence_variance'],
                     match_patterns['syntax']['fragment_rate'],
                     match_patterns['punctuation']['comma_density']]
        
        # Simple similarity metric (inverse of normalized distance)
        distance = sum(abs(r - m) / (r + 0.001) for r, m in zip(ref_vec, match_vec)) / len(ref_vec)
        similarity = (1 - distance) * 100
        
        print(f"\n  Style similarity to reference: {similarity:.1f}%")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Match the style patterns of a reference text',
        epilog='''
Examples:
  python style_matcher.py --reference hemingway.txt --input draft.txt --output matched.md
  python style_matcher.py -r style_guide.md -i manuscript.txt -o final.md --strength 0.9
  python style_matcher.py -r author.txt -i mytext.md -o styled.md --strength 0.7
        '''
    )
    
    # Arguments
    parser.add_argument('-r', '--reference', required=True, help='Reference text file for style')
    parser.add_argument('-i', '--input', required=True, help='Input text file to restyle')
    parser.add_argument('-o', '--output', required=True, help='Output file')
    
    parser.add_argument('--strength', type=float, default=0.8,
                       help='Style matching strength (0.5-1.0, default: 0.8)')
    
    args = parser.parse_args()
    
    # Validate files
    if not os.path.exists(args.reference):
        print(f"Error: Reference file '{args.reference}' not found")
        return
        
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return
    
    # Force .md output
    output_file = args.output
    if not output_file.endswith('.md'):
        output_file = output_file.rsplit('.', 1)[0] + '.md' if '.' in output_file else output_file + '.md'
    
    # Validate strength
    match_strength = max(0.5, min(1.0, args.strength))
    
    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file")
        return
    
    # Read files
    print(f"Reading reference from: {args.reference}")
    with open(args.reference, 'r', encoding='utf-8') as f:
        reference_text = f.read()
    
    print(f"Reading input from: {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        input_text = f.read()
    
    # Check reference length
    if len(reference_text.split()) < 500:
        print("Warning: Reference text is short. Best results with 1000+ words.")
    
    # Run matcher
    matcher = StyleMatcher(api_key)
    matcher.match_style(reference_text, input_text, output_file, match_strength)

if __name__ == "__main__":
    main()