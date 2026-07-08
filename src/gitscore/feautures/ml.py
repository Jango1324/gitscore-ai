def extract_ml_features(repositories):
    ml_repository_count = 0
    ml_keywords_total = 0
    found_keywords = set()
    description = {}
    name = {}
    text = ""
    words_to_check = ["ai", "ml", "machine learning", "deep learning", "pytorch", "tensorflow", "huggingface",
                      "transformers", "pandas", "numpy", "catboost", "sklearn", "opencv", "llm", "ollama"]
    for repo in repositories:
        repo_contains_ml = False
        name = repo["name"] or ""
        description = repo["description"] or ""
        text = f"{name} {description}".lower()
        for word in words_to_check:
            if word in text:
                repo_contains_ml = True
                found_keywords.add(word)
        if repo_contains_ml:
            ml_repository_count += 1
    ml_keywords_total = len(found_keywords)
    has_pytorch = "pytorch" in found_keywords
    has_huggingface = "huggingface" in found_keywords
    has_pandas = "pandas" in found_keywords
    has_catboost =  "catboost" in found_keywords
    
    return{
        "ml_repository_count": ml_repository_count,
        "has_pytorch": has_pytorch,
        "has_huggingface": has_huggingface,
        "has_pandas": has_pandas,
        "has_catboost": has_catboost,
        "ml_keyword_total": ml_keywords_total
    }
    

