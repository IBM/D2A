#!/usr/bin/env python3

import os
import sys
import subprocess
import json
from datetime import datetime

local_run = False

repo_copies_r92 = {
    "openssl"  : "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/openssl/openssl",
    "ffmpeg"   : "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/ffmpeg/FFmpeg",
    "httpd"    : "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/httpd/httpd",
    "nginx"    : "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/nginx/nginx",
    "libtiff"  : "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/libtiff/libtiff"
}

repo_copies_local = {
    "openssl": "/Users/zyh/work/r92/test_input/repos/openssl",
    "ffmpeg" : "/Users/zyh/work/r92/test_input/repos/FFmpeg",
    "qemu": "/Users/zyh/work/r92/test_input/repos/qemu"
}

if local_run:
    repo_copies = repo_copies_local
else:
    repo_copies = repo_copies_r92


def load_commit_list(file_path):
    commits = []
    with open(file_path, "r") as fp:
        data = fp.read()
        items = data.split("\n")
        for item in items:
            item = item.strip()
            if item == "":
                continue
            else:
                commits.append(item)
    return commits
    

"""
parse 
     '31,0'/'32,2' in '@@ -31,0 +32,2 @@'
  or '1008'/'1010' in '@@ -1008 +1010 @@'
"""
def process_diff_range(range):
    range = range.strip()
    start_line = -1
    end_line = -1
    if range.find(",") > 0:
        parts = range.split(",")
        start_line = int(parts[0].strip())
        end_line = int(parts[1].strip())
        if end_line > 0:
            end_line = start_line + end_line - 1
        else:
            end_line = start_line
    else:
        start_line = int(range)
        end_line = start_line
    return (start_line, end_line)

"""
extract modification ranges in git log
* input example:
    a/test/evp_extra_test.c b/test/evp_extra_test.c
    index b7e23a162e..9deae29c47 100644
    --- a/test/evp_extra_test.c
    +++ b/test/evp_extra_test.c
    @@ -31,0 +32,2 @@
    ...
    @@ -1008 +1010 @@ static struct keys_st {
    ...
"""
def process_diff_block(block):
    s_idx = 0
    e_idx = block.find("\n", s_idx)
    diff_args = block[s_idx : e_idx].split(" ")
    file_before = diff_args[0].replace("a/", "").strip()
    file_after = diff_args[1].replace("b/", "").strip()
    res = {
        "before": file_before,
        "after": file_after,
        "changes": []
    }
    s_idx = block.find("\n@@")
    while s_idx > 0:
        s_idx += 3
        e_idx = block.find("@@", s_idx)
        ranges = block[s_idx : e_idx].strip().replace("-", "").replace("+", "")
        range_parts = ranges.split(" ")
        range_before = range_parts[0]
        range_after = range_parts[1]        
        (start_before, end_before) = process_diff_range(range_before)
        (start_after, end_after) = process_diff_range(range_after)
        res["changes"].append( "%d-%d^^%d-%d" % (start_before, end_before, start_after, end_after) )
        s_idx = block.find("\n@@", e_idx + 2)
    return res


"""
get git commit info: 
   - commit timestamp
   - modified files
"""
def get_commit_info(task_name, commit_hash):
    repo_path = repo_copies[task_name]
    if not os.path.exists(repo_path):
        return None
    proc = subprocess.run(['git', 'log', '-1', '--pretty=%P', commit_hash], cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw_data = proc.stdout.decode('iso-8859-1').strip()
    raw_error = proc.stderr.decode('iso-8859-1').strip()
    if raw_error.startswith("fatal: bad object "):
        return None
    before_version = raw_data
    if raw_data.find(" ") > 0:
        parts = raw_data.split(" ")
        before_version = parts[0]
    res = get_git_commit_info(task_name, before_version, commit_hash)
    res["before_version"] = before_version
    return res



def get_git_commit_info(project_name, before_version_hash, after_version_hash):
    repo_path = repo_copies[project_name]
    if not os.path.exists(repo_path):
        print("Error: cannot find the repo at '%s'" % repo_path, flush=True)
        return None
    res = {}
    # get commit timestamp and date
    proc = subprocess.run(['git', 'show', '-s', '--format={%ct}', after_version_hash], cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw_data = proc.stdout.decode('iso-8859-1').strip()
    raw_error = proc.stderr.decode('iso-8859-1').strip()
    if raw_error.startswith("fatal: bad object "):
        return None
    s_idx = raw_data.find("{") + 1
    e_idx = raw_data.find("}", s_idx)
    commit_timestamp = int(raw_data[s_idx: e_idx])
    commit_date = datetime.utcfromtimestamp(commit_timestamp).strftime('%a %b %d %H:%M:%S %Y +0000')
    res["timestamp"] = commit_timestamp
    res["date"] = commit_date
    res["commit_hash"] = after_version_hash
    res["changes"] = []
    # get code diff
    proc = subprocess.run(['git', 'diff', '--unified=0', "%s..%s" % (before_version_hash, after_version_hash)], cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw_data = proc.stdout.decode('iso-8859-1')
    parts = raw_data.split("diff --git ")
    idx = 1
    while idx < len(parts):
        block_info = process_diff_block(parts[idx])
        res["changes"].append(block_info)
        idx += 1
    return res


def test(task_name, commit_list_file):
    commits = load_commit_list(commit_list_file)
    print("%d commits loaded." % len(commits))
    res = {}
    for commit in commits:
        print("commit: " + commit)
        info = get_commit_info(task_name, commit)
        if info is None:
            print(" - Error: NONE object.\n")
        else:
            res[commit] = info
    with open('%s.json' % task_name, 'w') as outfile:
        json.dump(res, outfile)
    


def date_range(task_name, commit_list_file):
    commits = load_commit_list(commit_list_file)
    print("%d commits loaded." % len(commits))
    res = {}
    min_year = 3000
    max_year = 0
    cnt = 0
    for commit in commits:
        cnt += 1
        info = get_commit_info(task_name, commit)
        ts = info["timestamp"]
        dt = datetime.utcfromtimestamp(ts)
        if dt.year not in res:
            res[dt.year] = {}
        if dt.month not in res[dt.year]:
            res[dt.year][dt.month] = 0
        res[dt.year][dt.month] += 1
        if dt.year <= min_year:
            min_year = dt.year
        if dt.year >= max_year:
            max_year = dt.year
        if cnt % 500 == 0:
            print("%d processed" % cnt)
    print("")
    print("======================")
    print(task_name)
    print("----------------------")
    cnt = 0
    y = min_year
    while y <= max_year:
        if y in res:
            m = 1
            while m <= 12:
                if m in res[y]:
                    print("%4d/%2d: %4d" % (y, m, res[y][m]))
                    cnt += res[y][m]
                m += 1
        y += 1
    print("======================")
    print("cnt = %d\n" % cnt)



def test_openssl():
    print("openssl")
    print("=============================")
    test("openssl", "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/openssl/commitlist.output")
    print("")


def test_ffmpeg():
    print("ffmpeg")
    print("=============================")
    test("ffmpeg", "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/ffmpeg/devign_ffmpeg_commits.txt")
    print("")


def test_httpd():
    print("httpd")
    print("=============================")
    test("httpd", "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/httpd/20200422_httpd_commit_only.txt")
    print("")


# def test_nginx():
#     test("nginx", "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/httpd/20200422_httpd_commit_only.txt")

def test_libtiff():
    print("libtiff")
    print("=============================")
    test("libtiff", "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/libtiff/20200703_libtiff_commit_only.txt")
    print("")


if __name__ == "__main__":
    # test_openssl()
    # test_ffmpeg()
    test_httpd()
    # test_libtiff()

