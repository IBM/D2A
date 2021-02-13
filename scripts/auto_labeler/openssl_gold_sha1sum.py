#!/usr/bin/env python3


import os
import json
import csv
import hashlib
from datetime import datetime


def gen_goldtrace_sha1sum(file_path):
    sha1 = hashlib.sha1()
    with open(file_path, 'r') as f:
        data = f.read()
        data = data.replace("/gpfs/automountdir/r92gpfs02/zhengyu/work/ai4code/benchmarks/openssl/src/", "").encode('ascii')
        sha1.update(data)
    return sha1.hexdigest()


def gen_gold_sha1sum(gold_trace_folder):
    gold_trace_sha_map = {}
    for f in os.listdir(gold_trace_folder): 
        f_path = os.path.join(gold_trace_folder, f)
        gold_trace_sha_map[f] = gen_goldtrace_sha1sum(f_path)
    return gold_trace_sha_map


def gold_silver_duplications(gold_trace_folder):
    duplication_cnt = 0
    unique_cnt = 0
    dt_string = datetime.now().strftime("%Y-%m-%d")
    dest_file =  "openssl_gold_trace_sha1sum.csv"
    gold = gen_gold_sha1sum(gold_trace_folder)
    with open(dest_file, mode='w') as csv_fp:
        writer = csv.writer(csv_fp, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        field_names = ['gold_trace', 'sha1sum']
        writer.writerow(field_names)
        for t in gold.keys():
            sha1sum = gold[t]
            writer.writerow([t, sha1sum])





if __name__ == '__main__':
    # gold_silver_duplications("/gpfs/r92gpfs02/zhengyu/infer_runs/goldset/openssl/traces")
    gold_silver_duplications("/Users/zyh/work/r92/test_input/traces")
    
