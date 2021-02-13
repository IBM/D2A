#!/usr/bin/env python3

import os
import sys
import json
import gzip

data = []
with gzip.open(sys.argv[1], "rt") as fp:
    data = json.loads(fp.read())

print("keys: " + ", ".join(data.keys()))
print("-----------------------------------------")
print("\n")


print("%d issues. 1st issue:" % len(data["prev_issues"].keys()))
print("-----------------------------------------")
cnt = 0
for key in data["prev_issues"].keys():
    issue = data["prev_issues"][key]
    if issue["commit_touched"]:
        print(json.dumps(issue, indent=2))
        print("")
        cnt += 1
        if cnt == 1:
            break
print("\n")

print("commit info:")
print("-----------------------------------------")
print( json.dumps(data["commit_info"], indent=2 ) )
print("")