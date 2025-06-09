import re
import math

def custom_sent_tokenize(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

def custom_word_tokenize(text):
    return re.findall(r'\b\w+\b', text)

def compute_burstiness(text):
    sentences = custom_sent_tokenize(text)
    sentence_lengths = [len(custom_word_tokenize(sent)) for sent in sentences if len(sent.strip()) > 0]

    if len(sentence_lengths) < 2:
        return 0.0

    avg_length = sum(sentence_lengths) / len(sentence_lengths)
    variance = sum((l - avg_length) ** 2 for l in sentence_lengths) / (len(sentence_lengths) - 1)
    std_dev = math.sqrt(variance)
    burstiness = std_dev / avg_length if avg_length != 0 else 0.0
    return round(min(burstiness, 1.0), 3)

def compute_perplexity_proxy(text):
    tokens = custom_word_tokenize(text)
    if len(tokens) < 2:
        return 0.0

    repeated = sum(1 for i in range(1, len(tokens)) if tokens[i] == tokens[i - 1])
    unique_words = len(set(tokens))
    lexical_variety = unique_words / len(tokens)
    repetition_penalty = 1 - (repeated / len(tokens))

    perplexity_proxy = 0.5 * lexical_variety + 0.5 * repetition_penalty
    return round(min(max(perplexity_proxy, 0.0), 1.0), 3)
