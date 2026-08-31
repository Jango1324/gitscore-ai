from gitscore.features.activity import extract_activity_features
from gitscore.features.languages import extract_language_features
from gitscore.features.quality import extract_quality_features
from gitscore.features.ml import extract_ml_features
from gitscore.features.readme import extract_readme_features
def extract_profile_features(repositories):
    activity_features = extract_activity_features(repositories)
    language_features = extract_language_features(repositories)
    quality_features = extract_quality_features(repositories)
    ml_features = extract_ml_features(repositories)
    readme_features = extract_readme_features(repositories)
    combined_dict = activity_features | language_features | quality_features | ml_features | readme_features
    return combined_dict


