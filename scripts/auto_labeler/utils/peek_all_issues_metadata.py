#!/usr/bin/env python3

import os
import sys
import json
import gzip
import pickle

output_folder = sys.argv[1]
src_path = os.path.join(output_folder, "cache", "issues_metadata.pickle.gz")

res = []
if not os.path.exists(src_path):
    print("|- Error: cannot find file " + src_path, flush=True)
with gzip.open(src_path, mode = 'rb') as fp:
    while True:
        try:
            item = pickle.load(fp)
            res.append(item)
        except EOFError:
            break

print("%d issues loaded\n" % len(res))
print(json.dumps(res[0], indent=2))
