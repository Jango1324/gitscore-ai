from gitscore.feautures.activity import extract_activity_features
def extract_profile_features(repositories):
    activity_features = extract_activity_features(repositories)
    return activity_features
