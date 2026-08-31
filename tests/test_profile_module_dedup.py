"""
Regression test for the features/profile.py vs profile_features.py
duplication found in the audit (docs/CHANGELOG_DEV.md), plus the
Milestone 3 `feautures` -> `features` package rename.

Correction: the original audit described profile_features.py as
"byte-identical" to profile.py. Re-verified while implementing the
Milestone 1 fix, profile_features.py was actually empty (0 bytes) on
disk, not a content duplicate — the earlier read that reported matching
content was inaccurate. Regardless of which it was, it was confirmed
unused (no import anywhere in src/ or scripts/ referenced
`gitscore.feautures.profile_features`), so it was deleted as dead code.
This test guards against it reappearing silently, confirms the old
misspelled `feautures/` directory is gone, and confirms the pipeline's
actual import target still works under its corrected package name.
"""
from pathlib import Path

from gitscore.features.profile import extract_profile_features
from conftest import make_repo


def test_old_misspelled_package_directory_is_gone():
    src_dir = Path(__file__).resolve().parents[1] / "src" / "gitscore"
    assert not (src_dir / "feautures").exists()


def test_profile_features_module_file_removed():
    features_dir = Path(__file__).resolve().parents[1] / "src" / "gitscore" / "features"
    assert not (features_dir / "profile_features.py").exists()


def test_extract_profile_features_still_importable_and_works():
    repos = [make_repo(name="ai-project", description="Uses PyTorch")]
    features = extract_profile_features(repos)
    assert features["total_repos"] == 1
    assert features["ml_repository_count"] == 1
