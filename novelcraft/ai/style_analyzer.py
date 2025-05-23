"""Style analysis for maintaining author voice."""

from typing import Dict, Any, List
import re


class StyleAnalyzer:
    """Analyzes and maintains writing style."""
    
    def __init__(self, ai_client=None):
        self.ai_client = ai_client
    
    async def analyze_style(self, text_sample: str) -> Dict[str, Any]:
        """Analyze writing style."""
        if self.ai_client:
            return await self.ai_client.analyze_style(text_sample)
        else:
            return self._basic_style_analysis(text_sample)
    
    def _basic_style_analysis(self, text: str) -> Dict[str, Any]:
        """Basic style analysis without AI."""
        sentences = text.split('.')
        words = text.split()
        
        analysis = {
            "avg_sentence_length": len(words) / len(sentences) if sentences else 0,
            "total_words": len(words),
            "total_sentences": len(sentences),
            "dialogue_ratio": self._calculate_dialogue_ratio(text),
            "complexity_score": self._calculate_complexity(text),
        }
        
        return analysis
    
    def _calculate_dialogue_ratio(self, text: str) -> float:
        """Calculate ratio of dialogue to narrative."""
        dialogue_matches = re.findall(r'"[^"]*"', text)
        dialogue_words = sum(len(match.split()) for match in dialogue_matches)
        total_words = len(text.split())
        
        return dialogue_words / total_words if total_words > 0 else 0.0
    
    def _calculate_complexity(self, text: str) -> float:
        """Calculate text complexity score."""
        words = text.split()
        if not words:
            return 0.0
        
        # Simple complexity based on average word length
        avg_word_length = sum(len(word.strip('.,!?";')) for word in words) / len(words)
        return min(avg_word_length / 10.0, 1.0)  # Normalize to 0-1
