#!/usr/bin/env python3
"""
Style Analysis Script
Comprehensive analysis of text characteristics without making changes
"""

import os
import re
from typing import Dict, List, Tuple
from collections import Counter
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
import numpy as np

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("Downloading required NLTK data...")
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)

class StyleAnalyzer:
    """Analyze text style characteristics"""
    
    def __init__(self):
        # Common words that might indicate AI writing
        self.ai_indicator_words = {
            'fancy_verbs': {'scrutinized', 'ventured', 'proclaimed', 'materialized', 
                           'emanated', 'permeated', 'cascaded', 'reverberated'},
            'fancy_transitions': {'moreover', 'furthermore', 'nevertheless', 'consequently',
                                'additionally', 'subsequently', 'notwithstanding'},
            'fancy_adjectives': {'myriad', 'plethora', 'paramount', 'quintessential',
                               'ubiquitous', 'enigmatic', 'profound', 'palpable'},
            'overused_phrases': {'it is worth noting', 'it should be noted', 'one might argue',
                               'it is important to note', 'delve into', 'tapestry of'}
        }
        
        # Simple words that indicate human writing
        self.human_indicator_words = {
            'simple_verbs': {'said', 'went', 'got', 'took', 'made', 'looked', 'walked'},
            'simple_connectors': {'and', 'but', 'so', 'then', 'also'},
            'conversational': {'yeah', 'well', 'sure', 'okay', 'just', 'really', 'actually'}
        }
    
    def analyze_vocabulary(self, text: str) -> Dict:
        """Analyze vocabulary choices"""
        words = word_tokenize(text.lower())
        total_words = len(words)
        
        # Count AI indicators
        ai_count = 0
        ai_words_found = []
        for category, word_list in self.ai_indicator_words.items():
            for word in words:
                if word in word_list:
                    ai_count += 1
                    ai_words_found.append(word)
        
        # Count human indicators
        human_count = 0
        human_words_found = []
        for category, word_list in self.human_indicator_words.items():
            for word in words:
                if word in word_list:
                    human_count += 1
                    human_words_found.append(word)
        
        # Calculate vocabulary diversity
        unique_words = set(w for w in words if w.isalpha())
        vocabulary_diversity = len(unique_words) / total_words if total_words > 0 else 0
        
        # Find most common words
        word_freq = Counter(w for w in words if w.isalpha() and len(w) > 3)
        
        return {
            'total_words': total_words,
            'unique_words': len(unique_words),
            'vocabulary_diversity': vocabulary_diversity,
            'ai_indicator_rate': ai_count / total_words if total_words > 0 else 0,
            'human_indicator_rate': human_count / total_words if total_words > 0 else 0,
            'ai_words_found': list(set(ai_words_found))[:10],
            'most_common_words': word_freq.most_common(10),
            'avg_word_length': np.mean([len(w) for w in words if w.isalpha()])
        }
    
    def analyze_sentences(self, text: str) -> Dict:
        """Analyze sentence patterns"""
        sentences = sent_tokenize(text)
        lengths = [len(word_tokenize(s)) for s in sentences]
        
        if not lengths:
            return {}
        
        # Categorize sentences
        categories = {
            'fragments': sum(1 for l in lengths if l <= 3),
            'very_short': sum(1 for l in lengths if 4 <= l <= 6),
            'short': sum(1 for l in lengths if 7 <= l <= 10),
            'medium': sum(1 for l in lengths if 11 <= l <= 20),
            'long': sum(1 for l in lengths if 21 <= l <= 35),
            'very_long': sum(1 for l in lengths if l > 35)
        }
        
        # Find problematic patterns
        problems = []
        
        # Too many fragments in a row
        fragment_runs = 0
        for i in range(len(lengths) - 1):
            if lengths[i] <= 3 and lengths[i+1] <= 3:
                fragment_runs += 1
        if fragment_runs > 3:
            problems.append(f"Excessive consecutive fragments ({fragment_runs} instances)")
        
        # Too many medium sentences
        medium_ratio = categories['medium'] / len(sentences)
        if medium_ratio > 0.5:
            problems.append(f"Too many medium-length sentences ({medium_ratio*100:.0f}%)")
        
        # Check for unnatural patterns
        dramatic_swings = sum(1 for i in range(len(lengths)-1) if abs(lengths[i] - lengths[i+1]) > 20)
        if dramatic_swings > len(sentences) * 0.3:
            problems.append(f"Possibly excessive rhythm variation ({dramatic_swings} dramatic swings)")
        
        return {
            'sentence_count': len(sentences),
            'avg_length': np.mean(lengths),
            'variance': np.var(lengths),
            'min_length': min(lengths),
            'max_length': max(lengths),
            'categories': categories,
            'fragment_rate': categories['fragments'] / len(sentences),
            'problems': problems,
            'dramatic_swings': dramatic_swings
        }
    
    def analyze_dialogue(self, text: str) -> Dict:
        """Analyze dialogue usage"""
        dialogue_pattern = re.compile(r'"[^"]*"')
        dialogues = dialogue_pattern.findall(text)
        
        # Check dialogue naturalness
        natural_dialogue = 0
        for d in dialogues:
            # Natural dialogue often has contractions, simple words, fragments
            if any(marker in d.lower() for marker in ["'ll", "'m", "'re", "'ve", "'d", "'s", "n't"]):
                natural_dialogue += 1
        
        return {
            'dialogue_count': len(dialogues),
            'dialogue_ratio': len(''.join(dialogues)) / len(text) if text else 0,
            'natural_dialogue_rate': natural_dialogue / len(dialogues) if dialogues else 0
        }
    
    def analyze_punctuation(self, text: str) -> Dict:
        """Analyze punctuation patterns"""
        text_len = len(text)
        
        patterns = {
            'comma_density': text.count(',') / text_len * 1000,
            'semicolon_density': text.count(';') / text_len * 1000,
            'dash_density': (text.count('—') + text.count('–') + text.count(' - ')) / text_len * 1000,
            'exclamation_density': text.count('!') / text_len * 1000,
            'question_density': text.count('?') / text_len * 1000,
            'ellipsis_density': text.count('...') / text_len * 1000
        }
        
        return patterns
    
    def calculate_ai_probability(self, analysis: Dict) -> Tuple[float, List[str]]:
        """Estimate AI probability based on various factors"""
        score = 50.0  # Start neutral
        reasons = []
        
        vocab = analysis['vocabulary']
        sentences = analysis['sentences']
        dialogue = analysis['dialogue']
        
        # Vocabulary factors
        if vocab['ai_indicator_rate'] > 0.005:  # >0.5% AI words
            score += 20
            reasons.append(f"High AI vocabulary ({vocab['ai_indicator_rate']*100:.1f}%)")
        
        if vocab['human_indicator_rate'] < 0.02:  # <2% simple words
            score += 15
            reasons.append("Lacks simple, common words")
        
        if vocab['avg_word_length'] > 5.5:
            score += 10
            reasons.append(f"Words too long on average ({vocab['avg_word_length']:.1f} chars)")
        
        # Sentence factors
        if sentences['variance'] > 300:
            score += 15
            reasons.append(f"Excessive sentence variation (variance: {sentences['variance']:.0f})")
        
        if sentences['fragment_rate'] > 0.2:
            score += 10
            reasons.append(f"Too many fragments ({sentences['fragment_rate']*100:.0f}%)")
        
        # Dialogue factors
        if dialogue['dialogue_count'] > 0 and dialogue['natural_dialogue_rate'] < 0.5:
            score += 10
            reasons.append("Unnatural dialogue")
        
        # Adjust score boundaries
        score = max(0, min(100, score))
        
        return score, reasons
    
    def analyze_text(self, text: str) -> Dict:
        """Complete text analysis"""
        print("Analyzing vocabulary...")
        vocabulary = self.analyze_vocabulary(text)
        
        print("Analyzing sentence patterns...")
        sentences = self.analyze_sentences(text)
        
        print("Analyzing dialogue...")
        dialogue = self.analyze_dialogue(text)
        
        print("Analyzing punctuation...")
        punctuation = self.analyze_punctuation(text)
        
        # Combine all analyses
        analysis = {
            'vocabulary': vocabulary,
            'sentences': sentences,
            'dialogue': dialogue,
            'punctuation': punctuation
        }
        
        # Calculate AI probability
        ai_score, ai_reasons = self.calculate_ai_probability(analysis)
        analysis['ai_detection'] = {
            'probability': ai_score,
            'reasons': ai_reasons
        }
        
        return analysis
    
    def print_report(self, analysis: Dict):
        """Print comprehensive analysis report"""
        print("\n" + "="*60)
        print("STYLE ANALYSIS REPORT")
        print("="*60)
        
        # AI Detection Summary
        ai = analysis['ai_detection']
        print(f"\n🤖 AI Detection Score: {ai['probability']:.0f}%")
        if ai['probability'] < 30:
            print("   ✅ Likely human-written")
        elif ai['probability'] < 70:
            print("   ⚠️  Mixed signals - possibly edited")
        else:
            print("   ❌ Likely AI-generated or heavily processed")
        
        if ai['reasons']:
            print("\n   Reasons:")
            for reason in ai['reasons']:
                print(f"   - {reason}")
        
        # Vocabulary Analysis
        vocab = analysis['vocabulary']
        print(f"\n📝 VOCABULARY ANALYSIS")
        print(f"   Total words: {vocab['total_words']:,}")
        print(f"   Unique words: {vocab['unique_words']:,}")
        print(f"   Vocabulary diversity: {vocab['vocabulary_diversity']:.2%}")
        print(f"   Average word length: {vocab['avg_word_length']:.1f} characters")
        
        if vocab['ai_words_found']:
            print(f"\n   AI indicator words found: {', '.join(vocab['ai_words_found'][:5])}")
        
        print(f"\n   Most common words: {', '.join([w[0] for w in vocab['most_common_words'][:5]])}")
        
        # Sentence Analysis
        sent = analysis['sentences']
        print(f"\n📊 SENTENCE PATTERNS")
        print(f"   Total sentences: {sent['sentence_count']}")
        print(f"   Average length: {sent['avg_length']:.1f} words")
        print(f"   Variance: {sent['variance']:.1f}")
        print(f"   Range: {sent['min_length']} to {sent['max_length']} words")
        
        print(f"\n   Distribution:")
        for cat, count in sent['categories'].items():
            percentage = count / sent['sentence_count'] * 100 if sent['sentence_count'] > 0 else 0
            print(f"   - {cat}: {count} ({percentage:.0f}%)")
        
        if sent['problems']:
            print(f"\n   ⚠️  Potential issues:")
            for problem in sent['problems']:
                print(f"   - {problem}")
        
        # Dialogue Analysis
        dial = analysis['dialogue']
        if dial['dialogue_count'] > 0:
            print(f"\n💬 DIALOGUE")
            print(f"   Dialogue instances: {dial['dialogue_count']}")
            print(f"   Natural dialogue rate: {dial['natural_dialogue_rate']:.0%}")
        
        # Punctuation Analysis
        punct = analysis['punctuation']
        print(f"\n🔤 PUNCTUATION DENSITY (per 1000 chars)")
        print(f"   Commas: {punct['comma_density']:.1f}")
        print(f"   Semicolons: {punct['semicolon_density']:.1f}")
        print(f"   Dashes: {punct['dash_density']:.1f}")
        
        print("\n" + "="*60)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Analyze text style and detect potential AI generation',
        epilog='''
This script provides comprehensive style analysis including:
- Vocabulary complexity and AI indicators
- Sentence patterns and rhythm
- Dialogue naturalness
- AI detection probability

Use this before and after any style modifications to track changes.
        '''
    )
    
    parser.add_argument('input', help='Text file to analyze')
    parser.add_argument('--brief', action='store_true', help='Show brief summary only')
    
    args = parser.parse_args()
    
    # Check file exists
    if not os.path.exists(args.input):
        print(f"Error: File '{args.input}' not found")
        return
    
    # Read file
    print(f"Reading file: {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Analyze
    analyzer = StyleAnalyzer()
    analysis = analyzer.analyze_text(text)
    
    # Print report
    if args.brief:
        # Brief summary only
        ai = analysis['ai_detection']
        sent = analysis['sentences']
        vocab = analysis['vocabulary']
        
        print(f"\nQUICK SUMMARY:")
        print(f"AI Score: {ai['probability']:.0f}% - {'Human' if ai['probability'] < 30 else 'Mixed' if ai['probability'] < 70 else 'AI'}")
        print(f"Sentences: {sent['sentence_count']} (avg {sent['avg_length']:.1f} words, variance {sent['variance']:.0f})")
        print(f"Vocabulary: {vocab['vocabulary_diversity']:.2%} diversity")
    else:
        analyzer.print_report(analysis)

if __name__ == "__main__":
    main()