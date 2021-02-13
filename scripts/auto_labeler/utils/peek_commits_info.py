#!/usr/bin/env python3

import os
import sys
import json
import gzip
import pickle

output_folder = sys.argv[1]
src_path = os.path.join(output_folder, "cache", "commits_info.pickle.gz")

res = []
if not os.path.exists(src_path):
    print("|- Error: cannot find file " + src_path, flush=True)
with gzip.open(src_path, mode = 'rb') as fp:
    while True:
        try:
            item = pickle.load(fp)
            print(json.dumps(item, indent=2))
            res.append(item)
            if "commit_hash" not in item:
                print("========================")
                
                print("========================")
        except EOFError:
            break

print("%d commits loaded\n" % len(res))
print(json.dumps(res[0], indent=2))
