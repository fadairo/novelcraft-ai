#!/usr/bin/env python3
"""
Text Style Transfer Script
Analyzes reference text style and applies it to input text using Claude API
"""

import os
import re
import json
import numpy as np
from typing import Dict, List, Tuple
from collections import Counter
import tiktoken
from transformers import GPT2LMHeadModel, GPT2TokenizerFast
import torch
from anthropic import Anthropic
from dotenv import load_dotenv
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
import string

# Download required NLTK data
nltk.download('punkt', quiet=True)

# Load environment variables
load_dotenv()

class StyleAnalyzer:
    """Analyzes writing style metrics including perplexity and burstiness"""
    
    def __init__(self):
        # Load GPT-2 for perplexity calculation
        self.tokenizer = GPT2TokenizerFast.from_pretrained('gpt2')
        self.model = GPT2LMHeadModel.from_pretrained('gpt2')
        self.model.eval()
        
        # Initialize tiktoken for chunk splitting
        self.tiktoken_enc = tiktoken.get_encoding("cl100k_base")
        
    def calculate_perplexity(self, text: str) -> float:
        """Calculate perplexity using GPT-2"""
        encodings = self.tokenizer(text, return_tensors='pt', max_length=1024, truncation=True)
        
        with torch.no_grad():
            outputs = self.model(**encodings, labels=encodings['input_ids'])
            loss = outputs.loss
            perplexity = torch.exp(loss).item()
            
        return perplexity
    
    def calculate_burstiness_metrics(self, text: str) -> Dict[str, float]:
        """Calculate various burstiness metrics"""
        sentences = sent_tokenize(text)
        
        if not sentences:
            return {
                'sentence_length_variance': 0,
                'word_length_variance': 0,
                'punctuation_density': 0,
                'complexity_variation': 0
            }
        
        # Sentence length variance
        sentence_lengths = [len(word_tokenize(s)) for s in sentences]
        sentence_length_variance = np.var(sentence_lengths) if len(sentence_lengths) > 1 else 0
        
        # Word length variance
        words = word_tokenize(text.lower())
        word_lengths = [len(w) for w in words if w.isalpha()]
        word_length_variance = np.var(word_lengths) if word_lengths else 0
        
        # Punctuation density
        punct_count = sum(1 for char in text if char in string.punctuation)
        punctuation_density = punct_count / len(text) if text else 0
        
        # Complexity variation (using syllable proxy - vowel count)
        vowels = 'aeiouAEIOU'
        syllable_counts = []
        for sentence in sentences:
            words = word_tokenize(sentence.lower())
            syllables = sum(sum(1 for char in word if char in vowels) for word in words if word.isalpha())
            if words:
                syllable_counts.append(syllables / len(words))
        
        complexity_variation = np.std(syllable_counts) if len(syllable_counts) > 1 else 0
        
        return {
            'sentence_length_variance': float(sentence_length_variance),
            'word_length_variance': float(word_length_variance),
            'punctuation_density': float(punctuation_density),
            'complexity_variation': float(complexity_variation)
        }
    
    def analyze_style(self, text: str) -> Dict:
        """Perform complete style analysis"""
        perplexity = self.calculate_perplexity(text)
        burstiness_metrics = self.calculate_burstiness_metrics(text)
        
        # Additional style metrics
        sentences = sent_tokenize(text)
        words = word_tokenize(text.lower())
        
        # Vocabulary diversity
        unique_words = set(w for w in words if w.isalpha())
        vocabulary_diversity = len(unique_words) / len(words) if words else 0
        
        # Average sentence length
        avg_sentence_length = np.mean([len(word_tokenize(s)) for s in sentences]) if sentences else 0
        
        # Paragraph structure
        paragraphs = text.strip().split('\n\n')
        avg_paragraph_length = np.mean([len(p.split()) for p in paragraphs if p.strip()]) if paragraphs else 0
        
        return {
            'perplexity': perplexity,
            'burstiness': burstiness_metrics,
            'vocabulary_diversity': vocabulary_diversity,
            'avg_sentence_length': avg_sentence_length,
            'avg_paragraph_length': avg_paragraph_length,
            'sentence_count': len(sentences),
            'word_count': len(words)
        }
    
    def chunk_text(self, text: str, max_tokens: int = 2000) -> List[str]:
        """Split text into chunks while preserving paragraph boundaries"""
        paragraphs = text.strip().split('\n\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = len(self.tiktoken_enc.encode(para))
            
            if current_tokens + para_tokens > max_tokens and current_chunk:
                # Save current chunk and start new one
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks

class StyleTransferAgent:
    """Handles style transfer using Claude API"""
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.analyzer = StyleAnalyzer()
    
    def create_style_prompt(self, reference_text: str, input_chunk: str, style_metrics: Dict) -> str:
        """Create a detailed prompt for Claude with style instructions"""
        prompt = f"""You are a writing style expert. Your task is to revise the input text to match the writing style of the reference text.

REFERENCE TEXT STYLE ANALYSIS:
- Perplexity: {style_metrics['perplexity']:.2f} ({"low" if style_metrics['perplexity'] < 50 else "moderate" if style_metrics['perplexity'] < 100 else "high"} - {"predictable" if style_metrics['perplexity'] < 50 else "balanced" if style_metrics['perplexity'] < 100 else "surprising"} word choices)
- Sentence Length Variance: {style_metrics['burstiness']['sentence_length_variance']:.2f} ({"low" if style_metrics['burstiness']['sentence_length_variance'] < 20 else "moderate" if style_metrics['burstiness']['sentence_length_variance'] < 50 else "high"} variation)
- Word Length Variance: {style_metrics['burstiness']['word_length_variance']:.2f}
- Punctuation Density: {style_metrics['burstiness']['punctuation_density']:.3f}
- Complexity Variation: {style_metrics['burstiness']['complexity_variation']:.3f}
- Vocabulary Diversity: {style_metrics['vocabulary_diversity']:.3f}
- Average Sentence Length: {style_metrics['avg_sentence_length']:.1f} words
- Average Paragraph Length: {style_metrics['avg_paragraph_length']:.1f} words

REFERENCE TEXT:
{reference_text[:3000]}  # Limiting to manage token count

STYLE INSTRUCTIONS:
1. Match the perplexity level by using {"simple, predictable" if style_metrics['perplexity'] < 50 else "balanced" if style_metrics['perplexity'] < 100 else "creative, unexpected"} word choices
2. Replicate the sentence rhythm with {"consistent" if style_metrics['burstiness']['sentence_length_variance'] < 20 else "moderate" if style_metrics['burstiness']['sentence_length_variance'] < 50 else "highly varied"} sentence lengths
3. Maintain similar punctuation density ({style_metrics['burstiness']['punctuation_density']:.3f})
4. Use {"simple" if style_metrics['vocabulary_diversity'] < 0.3 else "moderate" if style_metrics['vocabulary_diversity'] < 0.5 else "diverse"} vocabulary
5. Target average sentence length of {style_metrics['avg_sentence_length']:.0f} words
6. Preserve the tone, voice, and rhythm of the reference text

CRITICAL CONTENT PRESERVATION RULES:
- DO NOT add any new information, facts, or ideas not present in the input text
- DO NOT remove any information, facts, or ideas from the input text
- DO NOT change the meaning or intent of any statement
- DO NOT add examples, elaborations, or explanations unless they exist in the input
- DO NOT change any numbers, dates, names, or specific facts
- DO NOT merge or split paragraphs differently than in the input
- DO NOT change the logical flow or order of ideas
- ONLY change: word choice, sentence structure, rhythm, and stylistic elements

INPUT TEXT TO REVISE:
{input_chunk}

Please revise the input text to match the reference style while STRICTLY preserving ALL original content, meaning, and information. Output only the revised text without any explanations."""
        
        return prompt
    
    def transfer_style(self, reference_text: str, input_text: str, output_file: str, verify_content: bool = False, strict_mode: bool = False):
        """Main method to transfer style from reference to input text"""
        print("Analyzing reference text style...")
        style_metrics = self.analyzer.analyze_style(reference_text)
        
        print(f"Reference text metrics:")
        print(f"  - Perplexity: {style_metrics['perplexity']:.2f}")
        print(f"  - Sentence variance: {style_metrics['burstiness']['sentence_length_variance']:.2f}")
        print(f"  - Vocabulary diversity: {style_metrics['vocabulary_diversity']:.3f}")
        
        print("\nChunking input text...")
        chunks = self.analyzer.chunk_text(input_text)
        print(f"Processing {len(chunks)} chunks...")
        
        revised_chunks = []
        
        for i, chunk in enumerate(chunks):
            print(f"\nProcessing chunk {i+1}/{len(chunks)}...")
            
            prompt = self.create_style_prompt(reference_text, chunk, style_metrics)
            
            # Add extra strict instructions if in strict mode
            if strict_mode:
                prompt = prompt.replace("CRITICAL CONTENT PRESERVATION RULES:", 
                    """CRITICAL CONTENT PRESERVATION RULES (STRICT MODE):
- You are a COPY EDITOR, not a writer. Do NOT add ANY new content
- Every fact, number, and idea in the output MUST exist in the input
- If the input has 5 points, the output must have exactly 5 points
- Treat this like a translation between styles, not a rewrite""")
            
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                revised_chunk = response.content[0].text
                revised_chunks.append(revised_chunk)
                
                # Content verification if enabled
                if verify_content:
                    input_words = set(chunk.lower().split())
                    output_words = set(revised_chunk.lower().split())
                    
                    # Check for potential additions
                    new_words = output_words - input_words
                    content_words = [w for w in new_words if len(w) > 4 and w.isalpha()]
                    
                    if len(content_words) > len(input_words) * 0.1:  # More than 10% new content words
                        print(f"  ⚠️  Warning: Chunk {i+1} may contain new content")
                        print(f"     New words detected: {', '.join(list(content_words)[:10])}...")
                
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                revised_chunks.append(chunk)  # Keep original on error
        
        # Combine chunks and save
        final_text = '\n\n'.join(revised_chunks)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"\nStyle transfer complete! Output saved to {output_file}")
        
        # Analyze output style for comparison
        print("\nAnalyzing output text style...")
        output_metrics = self.analyzer.analyze_style(final_text)
        
        print("\nStyle comparison:")
        print(f"  Perplexity: {style_metrics['perplexity']:.2f} → {output_metrics['perplexity']:.2f}")
        print(f"  Sentence variance: {style_metrics['burstiness']['sentence_length_variance']:.2f} → {output_metrics['burstiness']['sentence_length_variance']:.2f}")
        print(f"  Vocabulary diversity: {style_metrics['vocabulary_diversity']:.3f} → {output_metrics['vocabulary_diversity']:.3f}")

def main():
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Transfer writing style from reference text to input text using Claude API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python style_transfer.py reference.md input.txt output.md
  python style_transfer.py reference.txt input.md revised.md
  python style_transfer.py --reference style_guide.txt --input draft.md --output revised
  python style_transfer.py -r style.md -i content.txt -o result
  
Note: Input and reference files can be .txt or .md
      Output will always be saved as .md
        '''
    )
    
    # Add arguments
    parser.add_argument('reference', nargs='?', help='Path to reference text file')
    parser.add_argument('input', nargs='?', help='Path to input text file to revise')
    parser.add_argument('output', nargs='?', help='Path to output file for revised text')
    
    # Alternative named arguments
    parser.add_argument('-r', '--reference', dest='ref_alt', help='Path to reference text file (.txt or .md)')
    parser.add_argument('-i', '--input', dest='input_alt', help='Path to input text file to revise (.txt or .md)')
    parser.add_argument('-o', '--output', dest='output_alt', help='Path to output file for revised text (.md)')
    
    # Optional arguments
    parser.add_argument('--chunk-size', type=int, default=2000, 
                       help='Maximum tokens per chunk (default: 2000)')
    parser.add_argument('--verify', action='store_true',
                       help='Enable content verification mode (compares input vs output)')
    parser.add_argument('--strict', action='store_true',
                       help='Use stricter content preservation instructions')
    
    args = parser.parse_args()
    
    # Determine which arguments to use (positional or named)
    reference_file = args.reference or args.ref_alt
    input_file = args.input or args.input_alt
    output_file = args.output or args.output_alt
    
    # Validate arguments
    if not all([reference_file, input_file, output_file]):
        parser.print_help()
        print("\nError: All three file paths (reference, input, output) are required")
        return
    
    # Validate file extensions
    valid_input_extensions = ['.txt', '.md']
    
    if not any(reference_file.endswith(ext) for ext in valid_input_extensions):
        print(f"Error: Reference file must be .txt or .md (got '{reference_file}')")
        return
    
    if not any(input_file.endswith(ext) for ext in valid_input_extensions):
        print(f"Error: Input file must be .txt or .md (got '{input_file}')")
        return
    
    # Ensure output is .md
    if not output_file.endswith('.md'):
        output_file = output_file.rsplit('.', 1)[0] + '.md' if '.' in output_file else output_file + '.md'
        print(f"Note: Output file will be saved as '{output_file}' (enforcing .md extension)")
    
    # Check for API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file")
        return
    
    # Check for input files
    if not os.path.exists(reference_file):
        print(f"Error: Reference file '{reference_file}' not found")
        return
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        return
    
    # Read input files
    print(f"Reading reference file: {reference_file}")
    with open(reference_file, 'r', encoding='utf-8') as f:
        reference_text = f.read()
    
    print(f"Reading input file: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        input_text = f.read()
    
    # Check minimum text length
    ref_word_count = len(reference_text.split())
    if ref_word_count < 200:
        print(f"Warning: Reference text is quite short ({ref_word_count} words). For best results, use at least 500-1000 words.")
    
    print(f"Output will be saved to: {output_file}")
    print(f"Using chunk size: {args.chunk_size} tokens\n")
    
    # Create agent and perform style transfer
    agent = StyleTransferAgent(api_key)
    
    # Modify chunk size if specified
    if args.chunk_size != 2000:
        original_chunk_method = agent.analyzer.chunk_text
        agent.analyzer.chunk_text = lambda text: original_chunk_method(text, max_tokens=args.chunk_size)
    
    agent.transfer_style(reference_text, input_text, output_file, 
                        verify_content=args.verify, 
                        strict_mode=args.strict)

if __name__ == "__main__":
    main()