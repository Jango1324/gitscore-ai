def score_ml_experience(features):
    ml_repos = features["ml_repository_count"]
    ml_keywords = features["ml_keyword_total"]

    repo_score = 0
    keyword_score = 0
    if(ml_repos == 1):
        repo_score += 10
    elif(ml_repos == 2):
            repo_score += 16
    elif(ml_repos == 3):
            repo_score += 20
    elif(ml_repos == 4):
            repo_score += 23
    elif(ml_repos >= 5):
            repo_score += 25
    if(ml_keywords == 1):
           keyword_score += 3
    elif(ml_keywords == 2):
               keyword_score += 5
    elif(ml_keywords == 3):
               keyword_score += 7
    elif(ml_keywords == 4):
               keyword_score += 8
    elif(ml_keywords >= 5):
               keyword_score += 10

    return repo_score + keyword_score

def  score_project_originality(features):
        original_repos = features["original_repos"]
        total_repos = features["total_repos"]
        original_count_score = 0
        original_ratio_score = 0

        if total_repos ==0:
                original_ratio = 0
        else:
            original_ratio = original_repos / total_repos

        if original_ratio < 0.25:
                original_ratio_score = 0
        elif original_ratio < 0.5:
                        original_ratio_score += 3
        elif original_ratio < 0.75:
                        original_ratio_score += 6
        elif original_ratio < 0.9:
                        original_ratio_score += 8
        else:
                        original_ratio_score += 10

        if original_repos == 1:
                original_count_score += 3
        elif original_repos == 2:
                original_count_score += 5
        elif original_repos == 3:
                original_count_score +=7
        elif original_repos == 4:
                original_count_score += 8
        elif original_repos >= 5:
                original_count_score +=10

        return original_count_score + original_ratio_score

def score_documentation_quality(features):
        coverage_score = 0
        coverage_ratio = features["readme_coverage_ratio"]
        
        usefulness_score = 0
        installation = features["repositories_with_installation"]
        usage = features["repositories_with_usage"]
        demo = features["repositories_with_demo"]

        professional_score = 0
        badges = features["repositories_with_badges"]
        license_count = features["repositories_with_license"]
        contributing = features["repositories_with_contributing"]


        if coverage_ratio < 0.25:
                coverage_score =0
        elif coverage_ratio < 0.5:
                coverage_score =2
        elif coverage_ratio < 0.75:
                coverage_score = 3
        elif coverage_ratio < 0.9:
                coverage_score = 4
        else:
                coverage_score = 5


        if installation > 0:
            usefulness_score += 2
        if usage > 0:
            usefulness_score += 2
        if demo > 0:
            usefulness_score += 2 


        if badges > 0:
                professional_score +=1
        if license_count > 0:
                professional_score += 2
        if contributing > 0:
                professional_score += 1

        return coverage_score + usefulness_score + professional_score

def score_language_tool_relevance(features):
        python_repos = features["python_repository_count"]
        has_pytorch = features["has_pytorch"]
        has_huggingface = features["has_huggingface"]
        has_pandas = features["has_pandas"]
        has_catboost = features["has_catboost"]
        python_score = 0
        tool_score = 0

        if python_repos == 1:
                python_score = 3
        elif python_repos == 2:
                python_score = 5
        elif python_repos == 3:
                python_score = 6
        elif python_repos >= 4:
                python_score = 8

        if has_pytorch:
                tool_score += 4
        if has_huggingface:
                tool_score +=3
        if has_pandas:
                tool_score += 2
        if has_catboost:
                tool_score += 3


        return python_score + tool_score

def score_community_signal(features):
        total_stars = features["total_stars"]
        total_forks = features["total_forks"]

        star_score = 0
        fork_score = 0

        if total_stars ==0:
                star_score = 0
        elif total_stars <= 2:
                star_score = 2
        elif total_stars <= 9:
                star_score = 3
        elif total_stars <= 49:
                star_score = 4
        elif total_stars <= 99 :
                star_score = 5
        else:
                star_score = 6

        if total_forks == 0:
                fork_score = 0
        elif total_forks == 1:
                fork_score = 2
        elif total_forks == 2:
                fork_score = 3
        else: fork_score = 4

        return star_score + fork_score

def calculate_readiness_score(features):
    ml_score = score_ml_experience(features)
    originality_score = score_project_originality(features)
    documentation_score = score_documentation_quality(features)
    language_tool_score = score_language_tool_relevance(features)
    community_score = score_community_signal(features)

    total_score = (
        ml_score
        + originality_score
        + documentation_score
        + language_tool_score
        + community_score
    )

    return {
            'total_score': total_score,
            'ml_experience': ml_score,
            'project_originality' : originality_score,
            'documentation_quality':documentation_score,
            'language_tool_relevance':language_tool_score,
            'community_signal': community_score
    }