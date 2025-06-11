#!/usr/bin/env python3
"""
Fix Dialogue Script
Makes dialogue sound more natural and human-like
"""

import os
import re
import random
from typing import List, Dict, Tuple
from anthropic import Anthropic
from dotenv import load_dotenv
import tiktoken

# Load environment variables
load_dotenv()

class DialogueFixer:
    """Fix dialogue to sound more natural"""
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.tiktoken_enc = tiktoken.get_encoding("cl100k_base")
        
        # Common formal -> informal replacements
        self.contraction_map = {
            'do not': "don't",
            'does not': "doesn't",
            'did not': "didn't",
            'will not': "won't",
            'would not': "wouldn't",
            'could not': "couldn't",
            'should not': "shouldn't",
            'cannot': "can't",
            'have not': "haven't",
            'has not': "hasn't",
            'had not': "hadn't",
            'is not': "isn't",
            'are not': "aren't",
            'was not': "wasn't",
            'were not': "weren't",
            'I am': "I'm",
            'you are': "you're",
            'he is': "he's",
            'she is': "she's",
            'it is': "it's",
            'we are': "we're",
            'they are': "they're",
            'I have': "I've",
            'you have': "you've",
            'we have': "we've",
            'they have': "they've",
            'I will': "I'll",
            'you will': "you'll",
            'he will': "he'll",
            'she will': "she'll",
            'we will': "we'll",
            'they will': "they'll",
            'I would': "I'd",
            'you would': "you'd",
            'he would': "he'd",
            'she would': "she'd",
            'we would': "we'd",
            'they would': "they'd"
        }
        
        # Formal words to replace in dialogue
        self.formal_to_casual = {
            'perhaps': 'maybe',
            'certainly': 'sure',
            'indeed': 'yeah',
            'however': 'but',
            'therefore': 'so',
            'regarding': 'about',
            'concerning': 'about',
            'sufficient': 'enough',
            'eliminate': 'get rid of',
            'utilize': 'use',
            'commence': 'start',
            'conclude': 'end',
            'purchase': 'buy',
            'assist': 'help'
        }
    
    def extract_dialogue(self, text: str) -> List[Tuple[str, int, int]]:
        """Extract all dialogue with positions"""
        dialogue_pattern = re.compile(r'"([^"]*)"')
        dialogues = []
        
        for match in dialogue_pattern.finditer(text):
            dialogue = match.group(1)
            start = match.start()
            end = match.end()
            dialogues.append((dialogue, start, end))
        
        return dialogues
    
    def analyze_dialogue_naturalness(self, dialogue: str) -> Dict:
        """Analyze how natural a piece of dialogue sounds"""
        issues = []
        
        # Check for contractions
        contraction_opportunities = 0
        for formal, informal in self.contraction_map.items():
            if formal in dialogue.lower():
                contraction_opportunities += 1
        
        if contraction_opportunities > 0:
            issues.append(f"Could use {contraction_opportunities} contractions")
        
        # Check for formal words
        formal_words = []
        for formal, casual in self.formal_to_casual.items():
            if formal in dialogue.lower():
                formal_words.append(formal)
        
        if formal_words:
            issues.append(f"Formal words: {', '.join(formal_words)}")
        
        # Check for complete sentences (dialogue often has fragments)
        sentences = dialogue.split('.')
        complete_sentences = sum(1 for s in sentences if len(s.split()) > 5)
        if len(sentences) > 1 and complete_sentences == len(sentences):
            issues.append("All complete sentences - needs fragments")
        
        # Check for filler words (natural dialogue has them)
        filler_words = ['um', 'uh', 'well', 'you know', 'I mean', 'like', 'just', 'actually']
        has_fillers = any(filler in dialogue.lower() for filler in filler_words)
        
        return {
            'issues': issues,
            'contraction_opportunities': contraction_opportunities,
            'formal_words': formal_words,
            'has_fillers': has_fillers,
            'naturalness_score': max(0, 100 - len(issues) * 25)
        }
    
    def create_dialogue_prompt(self, dialogues: List[str]) -> str:
        """Create prompt for fixing dialogue"""
        
        # Format dialogues for the prompt
        dialogue_list = '\n'.join([f'{i+1}. "{d}"' for i, d in enumerate(dialogues)])
        
        prompt = f"""Make the following dialogue sound more natural and conversational. 

CURRENT DIALOGUE:
{dialogue_list}

RULES FOR NATURAL DIALOGUE:
1. Use contractions (don't, can't, won't, I'm, you're, etc.)
2. Replace formal words with casual ones (perhaps → maybe, certainly → sure)
3. Add occasional fragments and incomplete sentences
4. Include filler words sparingly (well, just, you know - but don't overdo it)
5. Break up long, perfect sentences
6. Keep character-specific speech patterns if evident

WHAT TO PRESERVE:
- The exact meaning and information
- Character names and relationships
- Any dialect or regional speech patterns
- Plot-relevant information
- Emotional tone

FORBIDDEN:
- Don't add new information
- Don't change the speaker's intent
- Don't make everyone sound the same
- Don't overuse slang or fillers
- Don't change quoted facts or figures

For each dialogue, provide ONLY the revised version, numbered the same way.
Keep changes subtle - the goal is natural, not sloppy speech."""
        
        return prompt
    
    def fix_dialogue_chunk(self, text: str) -> str:
        """Fix dialogue in a chunk of text"""
        # Extract dialogue
        dialogues = self.extract_dialogue(text)
        
        if not dialogues:
            return text
        
        # Analyze each dialogue
        dialogues_to_fix = []
        for dialogue, start, end in dialogues:
            analysis = self.analyze_dialogue_naturalness(dialogue)
            if analysis['naturalness_score'] < 70:
                dialogues_to_fix.append(dialogue)
        
        if not dialogues_to_fix:
            return text
        
        # Process in batches of 10
        batch_size = 10
        fixed_dialogues = []
        
        for i in range(0, len(dialogues_to_fix), batch_size):
            batch = dialogues_to_fix[i:i+batch_size]
            prompt = self.create_dialogue_prompt(batch)
            
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=2000,
                    temperature=0.5,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Parse response
                response_text = response.content[0].text
                fixed_batch = []
                
                for line in response_text.split('\n'):
                    if line.strip() and line[0].isdigit():
                        # Extract the dialogue part
                        match = re.search(r'\d+\.\s*"([^"]*)"', line)
                        if match:
                            fixed_batch.append(match.group(1))
                
                fixed_dialogues.extend(fixed_batch)
                
            except Exception as e:
                print(f"Error processing dialogue batch: {e}")
                # Keep original on error
                fixed_dialogues.extend(batch)
        
        # Replace dialogues in text
        result = text
        dialogue_map = dict(zip(dialogues_to_fix, fixed_dialogues))
        
        for original, fixed in dialogue_map.items():
            # Only replace if actually different
            if original != fixed:
                result = result.replace(f'"{original}"', f'"{fixed}"', 1)
        
        return result
    
    def chunk_text(self, text: str, max_tokens: int = 3000) -> List[str]:
        """Split text into chunks preserving paragraph boundaries"""
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
    
    def fix_dialogue(self, input_text: str, output_file: str):
        """Main method to fix dialogue throughout text"""
        
        print("Analyzing dialogue...")
        all_dialogues = self.extract_dialogue(input_text)
        print(f"Found {len(all_dialogues)} dialogue instances")
        
        # Quick analysis
        natural_count = 0
        for dialogue, _, _ in all_dialogues[:20]:  # Sample first 20
            analysis = self.analyze_dialogue_naturalness(dialogue)
            if analysis['naturalness_score'] >= 70:
                natural_count += 1
        
        sample_rate = natural_count / min(20, len(all_dialogues))
        print(f"Current naturalness rate: {sample_rate:.0%} (from sample)")
        
        print("\nChunking text...")
        chunks = self.chunk_text(input_text)
        print(f"Processing {len(chunks)} chunks...")
        
        fixed_chunks = []
        total_changes = 0
        
        for i, chunk in enumerate(chunks):
            print(f"\nProcessing chunk {i+1}/{len(chunks)}...")
            
            # Count dialogues in chunk
            chunk_dialogues = self.extract_dialogue(chunk)
            if not chunk_dialogues:
                fixed_chunks.append(chunk)
                continue
            
            print(f"  Found {len(chunk_dialogues)} dialogues in chunk")
            
            # Fix the chunk
            fixed_chunk = self.fix_dialogue_chunk(chunk)
            
            # Count changes
            if fixed_chunk != chunk:
                changes = sum(1 for a, b in zip(chunk.split(), fixed_chunk.split()) if a != b)
                total_changes += changes
                print(f"  Made ~{changes} word changes")
            
            fixed_chunks.append(fixed_chunk)
        
        # Combine and save
        final_text = '\n\n'.join(fixed_chunks)
        
        # Final em-dash replacement
        final_text = re.sub(r'(\w)—(\w)', r'\1, \2', final_text)
        final_text = re.sub(r'(\w)–(\w)', r'\1, \2', final_text)
        final_text = final_text.replace('—', '...')
        final_text = final_text.replace('–', '...')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"\nDialogue fixing complete! Output saved to {output_file}")
        
        # Summary
        self.print_summary(input_text, final_text)
    
    def print_summary(self, original: str, fixed: str):
        """Print summary of changes"""
        orig_dialogues = self.extract_dialogue(original)
        fixed_dialogues = self.extract_dialogue(fixed)
        
        print("\nDialogue Fix Summary:")
        print(f"  Total dialogues: {len(orig_dialogues)}")
        
        # Sample analysis
        changes = 0
        for (orig, _, _), (new, _, _) in zip(orig_dialogues[:20], fixed_dialogues[:20]):
            if orig != new:
                changes += 1
        
        print(f"  Changed: ~{changes} of first 20 dialogues")
        print("\nExample changes:")
        
        # Show a few examples
        examples_shown = 0
        for (orig, _, _), (new, _, _) in zip(orig_dialogues, fixed_dialogues):
            if orig != new and examples_shown < 3:
                print(f'\n  Original: "{orig[:60]}..."')
                print(f'  Fixed:    "{new[:60]}..."')
                examples_shown += 1

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fix dialogue to sound more natural and human-like',
        epilog='''
This script focuses only on dialogue, making it sound more conversational by:
- Adding contractions (don't, can't, I'm)
- Using casual words instead of formal ones
- Adding natural speech patterns
- Preserving meaning and character voice

Examples:
  python fix_dialogue.py input.txt output.txt
  python fix_dialogue.py -i story.md -o story_fixed.md
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
    
    # Check for dialogue
    if '"' not in input_text:
        print("Warning: No dialogue found in text (no quotes detected)")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Run fixer
    fixer = DialogueFixer(api_key)
    fixer.fix_dialogue(input_text, output_file)

if __name__ == "__main__":
    main()