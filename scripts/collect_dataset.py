from gitscore.pipeline.analyze import analyze_user
import time
batch_start = time.perf_counter()
usernames = [
    "Jango1324",
    "this-user-definitely-does-not-exist-123xyz",
    "torvalds",
    "karpathy",

]
successful = 0
failed = 0
for username in usernames:
    try:
        result = analyze_user(username)
        successful += 1
        print(f"{username}: {result['score']['total_score']}/100")
    except Exception as error:
            failed += 1
            print(f"{username}: FAILED - {error}")
total  = len(usernames)
batch_elapsed = time.perf_counter() - batch_start
print (f"Collection Complete successful {successful}: Failed:{failed}, Total attempts : {total}, In {result["time"]}")
