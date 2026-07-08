from gitscore.feautures.activity import extract_activity_features
from gitscore.feautures.languages import extract_language_features
from gitscore.feautures.quality import extract_quality_features
def extract_profile_features(repositories):
    activity_features = extract_activity_features(repositories)
    language_features = extract_language_features(repositories)
    quality_feautures = extract_quality_features(repositories)
    combined_dict = activity_features | language_features | quality_feautures
    return combined_dict


