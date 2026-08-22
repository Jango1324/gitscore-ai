import sys
from gitscore.pipeline.analyze import analyze_user
if len(sys.argv)<2:
      print("Usage: python scripts/collect_user.py <github_username>")
      sys.exit(1)
username = sys.argv[1]
result = analyze_user(username)
print(result)