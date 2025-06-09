import numpy as np
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

nltk.download('punkt', quiet=True)

def sentence_lengths(text):
    sentences = sent_tokenize(text)
    return [len(word_tokenize(s)) for s in sentences if len(s.strip()) > 0]

def compute_burstiness(text):
    lengths = sentence_lengths(text)
    if not lengths:
        return 0.0
    return np.std(lengths) / (np.mean(lengths) + 1e-6)

def compute_perplexity_proxy(text):
    words = word_tokenize(text)
    if not words:
        return 0.0
    return len(set(words)) / (len(words) + 1e-6)
