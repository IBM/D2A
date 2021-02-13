#!/usr/bin/env python3

import os
import sys
import json
import pickle
import gzip


def load_unique_bug_history(src_path):
    print("Load unique bugs history @ %s" % src_path, flush=True)
    res = {}
    with gzip.open(src_path, mode = 'rb') as fp:
        res = pickle.load(fp)
    print("|- %d unique issues loaded. done\n" % len(res), flush=True)
    return res


output_folder = sys.argv[1]
unique_bugs_history_file = os.path.join(output_folder, "cache", "unique_bugs_info.pickle.gz")
data = load_unique_bug_history(unique_bugs_history_file)

for sha1sum in data.keys():
    issue = data[sha1sum]
    if issue["fix_type"] == "unfixed_only":
        print("sha1sum = " + sha1sum)
        print( json.dumps(issue, indent=2) )
        break

print("\n\n")

for sha1sum in data.keys():
    issue = data[sha1sum]
    if issue["fix_type"] == "fixed_only":
        print("sha1sum = " + sha1sum)
        print( json.dumps(issue, indent=2) )
        break

print("\n\n")

for sha1sum in data.keys():
    issue = data[sha1sum]
    if issue["fix_type"] == "fixed_and_unfixed":
        print("sha1sum = " + sha1sum)
        print( json.dumps(issue, indent=2) )
        break
