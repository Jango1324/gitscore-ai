import re

ML_KEYWORDS = [
    "ai", "ml", "machine learning", "deep learning", "pytorch", "tensorflow",
    "huggingface", "transformers", "pandas", "numpy", "catboost", "sklearn",
    "opencv", "llm", "ollama",
]

# Each keyword must appear as a standalone token: not glued to another
# letter/digit on either side. This avoids false positives like "ai"
# inside "container"/"explain" or "ml" inside "html", while still
# matching keywords separated by spaces, hyphens, underscores, or other
# punctuation (e.g. "my-ai-project", "llm_app", "AI-powered").
_KEYWORD_PATTERNS = {
    keyword: re.compile(r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])")
    for keyword in ML_KEYWORDS
}


def extract_ml_features(repositories):
    ml_repository_count = 0
    found_keywords = set()

    for repo in repositories:
        name = repo["name"] or ""
        description = repo["description"] or ""
        text = f"{name} {description}".lower()

        repo_keywords = {
            keyword
            for keyword, pattern in _KEYWORD_PATTERNS.items()
            if pattern.search(text)
        }
        if repo_keywords:
            ml_repository_count += 1
            found_keywords |= repo_keywords

    has_pytorch = "pytorch" in found_keywords
    has_huggingface = "huggingface" in found_keywords
    has_pandas = "pandas" in found_keywords
    has_catboost = "catboost" in found_keywords

    return {
        "ml_repository_count": ml_repository_count,
        "has_pytorch": has_pytorch,
        "has_huggingface": has_huggingface,
        "has_pandas": has_pandas,
        "has_catboost": has_catboost,
        "ml_keyword_total": len(found_keywords)
    }
