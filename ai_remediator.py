import anthropic
import os
import time
import sys
from text_metrics import compute_burstiness, compute_perplexity_proxy

# Load API key from environment
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise EnvironmentError("ANTHROPIC_API_KEY not found in environment variables.")

client = anthropic.Anthropic(api_key=api_key)

def analyze_metrics(text):
    burstiness = compute_burstiness(text)
    perplexity = compute_perplexity_proxy(text)
    return burstiness, perplexity

def build_prompt(text, burstiness, perplexity):
    guidance = []
    if burstiness < 0.45:
        guidance.append("Vary sentence length more dramatically. Add both short fragments and extended clauses.")
    if perplexity < 0.6:
        guidance.append("Use metaphor, contradiction, tangents, or emotional unpredictability to reduce textual predictability.")
    instruction = " ".join(guidance) or "Refine lightly for style, tone, and rhythm with natural language variation."

    return f"""
Human: Revise the following fiction chapter to sound as though written by a human author. Emphasize literary style, emotional variability, sentence-length burstiness, and lexical unpredictability. {instruction}

### ORIGINAL TEXT:
{text}

Assistant:
"""

def clean_response(raw_text):
    if raw_text.strip().lower().startswith("here is") or "### ORIGINAL TEXT:" in raw_text:
        parts = raw_text.split("### ORIGINAL TEXT:")
        if len(parts) > 1:
            return parts[-1].strip()
    return raw_text.strip()

def revise_with_claude(text, model="claude-opus-4-20250514", max_tokens=8000):
    burstiness, perplexity = analyze_metrics(text)
    prompt = build_prompt(text, burstiness, perplexity)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0.5,
        stream=True,
        messages=[{"role": "user", "content": prompt.strip()}]
    )

    output_chunks = []
    for chunk in response:
        if hasattr(chunk, "delta") and hasattr(chunk.delta, "text"):
            output_chunks.append(chunk.delta.text)

    revised_text = clean_response("".join(output_chunks))
    return revised_text, burstiness, perplexity

def loop_until_human(filename, threshold=0.9, max_passes=5):
    with open(filename, 'r', encoding='utf-8') as f:
        current_text = f.read()

    base = os.path.basename(filename)
    name, ext = os.path.splitext(base)
    output_dir = os.path.join(os.path.dirname(filename), "revised", "ai-checked")
    os.makedirs(output_dir, exist_ok=True)

    for i in range(1, max_passes + 1):
        revised_text, b, p = revise_with_claude(current_text)
        avg = (b + p) / 2
        print(f"→ Pass {i}: Burstiness={b:.2f}, Perplexity={p:.2f}, Average={avg:.2f}")

        # Save this pass
        checkpoint_name = f"{name}_pass{i}.md"
        checkpoint_path = os.path.join(output_dir, checkpoint_name)
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            f.write(revised_text)
        print(f"✓ Saved checkpoint: {checkpoint_path}")

        if avg >= threshold:
            print(f"✓ Human-like threshold reached in {i} pass(es).")
            current_text = revised_text
            break

        current_text = revised_text
        time.sleep(2)

    # Save final version
    final_path = os.path.join(output_dir, f"{name}_AIChecked.md")
    with open(final_path, 'w', encoding='utf-8') as f:
        f.write(current_text)
    print(f"✓ Final revision saved to: {final_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ai_remediator.py <chapter_filename.md>")
    else:
        loop_until_human(sys.argv[1])
