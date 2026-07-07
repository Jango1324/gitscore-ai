from gitscore.feautures.activity import extract_activity_features
from gitscore.feautures.languages import extract_language_features
def extract_profile_features(repositories):
    activity_features = extract_activity_features(repositories)
    language_features = extract_language_features(repositories)
    combined_dict = activity_features | language_features
    return combined_dict


