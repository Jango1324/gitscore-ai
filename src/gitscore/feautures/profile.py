from gitscore.feautures.activity import extract_activity_features
from gitscore.feautures.languages import extract_language_features
from gitscore.feautures.quality import extract_quality_features
from gitscore.feautures.ml import extract_ml_features 
def extract_profile_features(repositories):
    activity_features = extract_activity_features(repositories)
    language_features = extract_language_features(repositories)
    quality_feautures = extract_quality_features(repositories)
    ml_feautures = extract_ml_features(repositories)
    combined_dict = activity_features | language_features | quality_feautures | ml_feautures
    return combined_dict


