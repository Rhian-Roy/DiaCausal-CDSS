"""TF-IDF vector search (split out of retrieve.py in restructure step 6).

A PLACEHOLDER for the medical embedding model chosen in October: it lets the fusion step run end to end today.
The two functions below are exactly the two scikit-learn calls the retriever used to make inline.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def build(texts: list[str]):
    """Fit the vectorizer on the passage texts: (vectorizer, matrix)."""
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    return vectorizer, vectorizer.fit_transform(texts)


def similarities(vectorizer, matrix, question: str):
    """Cosine similarity of the question to every passage."""
    return cosine_similarity(vectorizer.transform([question]), matrix)[0]
