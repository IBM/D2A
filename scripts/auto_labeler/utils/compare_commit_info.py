#!/usr/bin/env python3

import os
import sys
import json
import gzip
import pickle

def load_commit_info_from_pipeline(src_path):
    res = {}
    none_cnt = 0
    no_commit_hash_cnt = 0
    if not os.path.exists(src_path):
        print("|- Error: cannot find file " + src_path, flush=True)
    with gzip.open(src_path, mode = 'rb') as fp:
        while True:
            try:
                item = pickle.load(fp)
                if item is None:
                    none_cnt += 1
                    continue
                if "commit_hash" not in item:
                    no_commit_hash_cnt += 1
                    continue
                commit_hash = item["commit_hash"]
                res[commit_hash] = item
            except EOFError:
                break
    print("* %s" % src_path)
    print("  - %d valid items loaded." % len(res))
    print("  - %d 'NONE' objects found." % none_cnt)
    print("  - %d not NONE items without 'commit_hash' found." % no_commit_hash_cnt)
    return res


def load_all_commit_info(src_path):
    res = {}
    if not os.path.exists(src_path):
        print("|- Error: cannot find file " + src_path, flush=True)
    with open(src_path) as json_file:
        res = json.load(json_file)
    print("* %s" % src_path)
    print("  - %d items loaded" % len(res))
    return res


def find_change(changes, before_file, after_file):
    for item in changes:
        if item["before"] == before_file and item["after"] == after_file:
            return item
    return None



def compare(pipeline_commit_info, all_commit_info):
    same_cnt = 0
    different_cnt = 0
    cmt_not_found_cnt = 0
    timestamp_diff_cnt = 0
    changed_file_total_diff_cnt = 0
    changed_file_diff_cnt = 0
    changed_line_total_diff_cnt = 0
    changed_line_diff_cnt = 0
    for cmt in pipeline_commit_info.keys():
        if cmt not in all_commit_info:
            print("* commit %s not found in all_commit_info" % cmt)
            cmt_not_found_cnt += 1
            different_cnt += 1
            continue

        pp_info = pipeline_commit_info[cmt]
        all_info = all_commit_info[cmt]
        if pp_info["timestamp"] != all_info["timestamp"]:
            timestamp_diff_cnt += 1
            different_cnt += 1
            continue
        
        pp_changes = pp_info["changes"]
        all_changes = all_info["changes"]
        if len(pp_changes) != len(all_changes):
            changed_file_total_diff_cnt += 1
            different_cnt += 1
            continue

        same_file_changes = True
        for pp in pp_changes:
            before_file = pp["before"]
            after_file = pp["after"]
            item_in_all = find_change(all_changes, before_file, after_file)
            if item_in_all is None:
                same_file_changes = False
                changed_file_diff_cnt += 1
                break

            if len(pp["changes"]) != len(item_in_all["changes"]):
                same_file_changes = False
                changed_line_total_diff_cnt += 1
                break

            same_line_changes = True
            for changed_line in pp["changes"]:
                if changed_line not in item_in_all["changes"]:
                    same_line_changes = False
                    changed_line_diff_cnt += 1
                    break
            if not same_line_changes:
                same_file_changes = False
                break
        if not same_file_changes:
            different_cnt += 1
            continue

        same_cnt += 1

    print("* %d items found in pipeline_commit_info" % len(pipeline_commit_info))
    print("  - %d same" % same_cnt)
    print("  - %d different" % different_cnt)
    print("    - %d commit not found in all commit info" % cmt_not_found_cnt)
    print("    - %d different timestamp" % timestamp_diff_cnt)
    print("    - %d different total changed files" % changed_file_total_diff_cnt)
    print("    - %d different changed before-after file pairs" % changed_file_diff_cnt)
    print("    - %d different total changed lines" % changed_line_total_diff_cnt)
    print("    - %d different changed lines" % changed_line_diff_cnt)


def compare_commit_info(pipeline_commit_info_file, all_commit_info_file):
    pipeline_commit_info = load_commit_info_from_pipeline(pipeline_commit_info_file)
    all_commit_info = load_all_commit_info(all_commit_info_file)
    compare(pipeline_commit_info, all_commit_info)



def compare_openssl():
    print("openssl")
    print("=================================================")
    pipeline_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/auto_labeler/2020-06-25_openssl/cache/commits_info.pickle.gz"
    all_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/auto_labeler/utils/openssl.json"
    compare_commit_info(pipeline_path, all_path)
    print("=================================================\n")


def compare_ffmpeg():
    print("ffmpeg")
    print("=================================================")
    pipeline_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/auto_labeler/2020-06-25_ffmpeg/cache/commits_info.pickle.gz"
    all_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/auto_labeler/utils/ffmpeg.json"
    compare_commit_info(pipeline_path, all_path)
    print("=================================================\n")


def compare_httpd():
    print("httpd")
    print("=================================================")
    pipeline_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/auto_labeler/2020-06-25_httpd/cache/commits_info.pickle.gz"
    all_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/auto_labeler/utils/httpd.json"
    compare_commit_info(pipeline_path, all_path)
    print("=================================================\n")

def compare_nginx():
    print("nginx")
    print("=================================================")
    pipeline_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/auto_labeler/2020-06-25_nginx/cache/commits_info.pickle.gz"
    all_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/auto_labeler/utils/nginx.json"
    compare_commit_info(pipeline_path, all_path)
    print("=================================================\n")


if __name__ == "__main__":
    compare_openssl()
    print("")
    compare_ffmpeg()
    print("")
    compare_httpd()