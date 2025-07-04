import torch
from transformers import pipeline

# Load the model and pipeline once (on module import)
# Using a sentiment-analysis pipeline as a proxy for demo; can be replaced with a custom classifier
try:
    nlp = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")
except Exception as e:
    nlp = None
    print(f"Failed to load NLP model: {e}")

def score_text_descriptiveness(text):
    """
    Returns a score (0-1) indicating how descriptive the text is.
    For demo: uses sentiment analysis as a proxy (positive = descriptive, negative = not descriptive).
    Replace with a custom classifier for production.
    """
    if not text or not text.strip():
        return {"score": 0.0, "label": "empty"}
    if nlp is None:
        return {"score": 0.0, "label": "model_unavailable"}
    try:
        result = nlp(text[:512])[0]  # Truncate to 512 tokens
        # For demo: treat POSITIVE as descriptive, NEGATIVE as not
        if result["label"] == "POSITIVE":
            return {"score": float(result["score"]), "label": "descriptive"}
        else:
            return {"score": 1.0 - float(result["score"]), "label": "not_descriptive"}
    except Exception as e:
        return {"score": 0.0, "label": f"error: {e}"} 