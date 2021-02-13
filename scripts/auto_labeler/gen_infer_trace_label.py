#!/usr/bin/env python3


"""
TBD: document output data structure with example in a different file 
"""

import sys
import os
import shutil
import json
import csv
import hashlib
import gzip
import tarfile
import subprocess
import multiprocessing
import time
import base64
import pickle
from datetime import datetime
import configs
import gc


test_mode = False

repo_copies = configs.repo_copy
repo_urls = configs.repo_urls

processed_commit_folder = "issues_by_commit"
cache_folder_name = "cache"
idx_list = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"]


def remove_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

def remove_folder(folder_path):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)        

def compress_and_encode_string(content):
    if isinstance(content, str):
        b_content = content.encode()
    else:
        b_content = content
    compressed_bytes = gzip.compress(b_content)
    encoded_content = base64.b64encode(compressed_bytes).decode('ascii')
    return encoded_content

def decode_and_decompress_string(encoded_content):
    encoded_bytes = encoded_content.encode('ascii')
    compressed_bytes = base64.b64decode(encoded_bytes)
    b_content = gzip.decompress(compressed_bytes)
    content = b_content.decode()
    return content

"""
step 0: prepare output folder. 
"""
def cleanup(output_folder, process_individual_pairs):
    # output folder
    print("preparing output folder @ '%s'\n" % output_folder, flush = True)   
    cache_folder = os.path.join(output_folder, cache_folder_name)
    if not os.path.exists(cache_folder):
        os.makedirs(cache_folder)
    commit_output_folder = os.path.join(output_folder, processed_commit_folder)
    if not os.path.exists(commit_output_folder):
        os.makedirs(commit_output_folder)
    for idx1 in idx_list:
        for idx2 in idx_list:
            folder = os.path.join(output_folder, processed_commit_folder, idx1, idx2)
            if not os.path.exists(folder):
                os.makedirs(folder)


# ---------------------------------------------

"""
Step 1: collect hash pairs with 'differential' folder, 
        which indicates the version pair was processed successfully 
"""
def load_commits_with_differential(infer_output_path):
    commit_folder_list = []
    for f in os.listdir(infer_output_path):  
        f_path = os.path.join(infer_output_path, f)
        if os.path.isdir(f_path):
            # f_path is folder `a`
            for ff in os.listdir(f_path):
                ff_path = os.path.join(f_path, ff)
                if os.path.isdir(ff_path):
                    # ff_path is folder `a/2`
                    for fff in os.listdir(ff_path):
                        fff_path = os.path.join(ff_path, fff)
                        if os.path.isdir(fff_path):
                            # fff_path is folder `a/2/a26e245ecd6a15459202569e0df8b40bc10339a5`
                            diff_folder_path = os.path.join(fff_path, "differential")
                            if os.path.exists(diff_folder_path):
                                commit_folder_list.append( (fff, fff_path) )
                                if test_mode:
                                    if len(commit_folder_list) == 1:
                                        return commit_folder_list
    return commit_folder_list


# ---------------------------------------------

"""
Extract the hashes of the before and after versions in `process_hash_pair.log`
In paricular, look for the line in the following format
  Current hash: 0904e79a6e6109240d5a552f2699408b26cf63ee Previous hash: ff281ee8369350d88e8b57af139614f5683e1e8c
"""
def get_versions_from_log(pairwise_analysis_folder):
    process_hash_pair_log_path = os.path.join(pairwise_analysis_folder, "process_hash_pair.log")
    if not os.path.exists(process_hash_pair_log_path):
        print("Error: '%s' not found. cannot extract version hashes", flush = True)
        return {
            "before": None,
            "after": None
        }
    with open(process_hash_pair_log_path, "r") as fp:
        for l in fp.readlines():
            l = l.strip()
            if l.startswith("Current hash: ") and l.find("Previous hash:") > 0:
                l = l[ len("Current hash: ") : ]
                parts = l.split("Previous hash:")
                return {
                    "before": parts[1].strip(),
                    "after": parts[0].strip()
                }


"""
Helper functions. 
- Compute the sha1sum of the content of bug_txt files.
- the sha1sum of bug_txt is used as the identifier of a unique bug
"""
def gen_hash(data):
    if isinstance(data, str):
        data = data.encode()
    sha1 = hashlib.sha1()
    sha1.update(data)      
    return sha1.hexdigest()


def gen_sha256sum(data):
    if isinstance(data, str):
        data = data.encode()
    sha256 = hashlib.sha256()
    sha256.update(data)      
    return sha256.hexdigest()



"""
filter out the code location in the header/bug info section
    ffmpeg.c:1805: error: INTEGER_OVERFLOW_L2
    ([0, 1] - 1):unsigned32 by call to `avfilter_unref_buffer`.
--> 
    INTEGER_OVERFLOW_L2
    ([0, 1] - 1):unsigned32 by call to `avfilter_unref_buffer`.
"""
def filter_loc_bug_info_block(msg_prefix, bug_txt_name, block, filtered_content_lines):
    lines = block.split("\n")
    if len(lines) < 2:
        print(msg_prefix + "Error: unexpected format in '%s' - 2+ lines expected:\n%s" % (bug_txt_name, block), flush=True) 
        sys.exit(1)
    if lines[0].startswith("#") or lines[0].count(":") == 3:
        i = 0
        if lines[0].startswith("#"):
            i = 1
            filtered_content_lines.append("")
        if lines[i].count(":") < 3:
            print(msg_prefix + "Error: unexpected format in '%s' - 3+ ':' expected:\n%s" % (bug_txt_name, lines[i]), flush=True)
            sys.exit(1)
        s_idx = lines[i].find(":") + 1
        s_idx = lines[i].find(":", s_idx) + 1
        # to_remove = lines[i][ : s_idx]
        loc_removed = lines[i][s_idx : ].strip()
        filtered_content_lines.append(loc_removed)
        i += 1
        while i < len(lines):
            l = lines[i].strip()
            filtered_content_lines.append(l)
            i += 1
    else:
        print(msg_prefix + "Error: unexpected format in the 1st line in '%s'" % bug_txt_name, flush=True)
        sys.exit(1)


"""
filter out the code location in the trace step
    ffmpeg.c:1694:21: Call
    1692.                     picture.pts = ist->pts;
    1693. 
    1694.                     av_vsrc_buffer_add_frame(ost->input_video_filter, &picture);
                              ^
    1695.                 }
    1696.                 frame_available = ist->st->codec->codec_type != AVMEDIA_TYPE_VIDEO ||
-->
    Call
                         picture.pts = ist->pts;
     
                         av_vsrc_buffer_add_frame(ost->input_video_filter, &picture);
                         ^
                     }
                     frame_available = ist->st->codec->codec_type != AVMEDIA_TYPE_VIDEO ||
"""
def filter_loc_trace_step_block(msg_prefix, bug_txt_name, block, filtered_content_lines):
    lines = block.split("\n")
    if len(lines) < 2:
        print(msg_prefix + "Error: unexpected format in '%s' - 2+ lines expected, %d found:\n%s" % (bug_txt_name, len(lines), block), flush=True) 
        sys.exit(1)
    idx = 0
    while lines[idx].strip() == "" and idx < len(lines):
        idx += 1
        filtered_content_lines.append("")
    if lines[idx].count(":") < 3:
        print(msg_prefix + "Error: unexpected format in '%s' - 3+ ':' expected:\n%s" % (bug_txt_name, lines[idx]), flush=True)
        sys.exit(1)
    # first line 
    s_i = lines[idx].find(":") + 1
    s_i = lines[idx].find(":", s_i) + 1
    s_i = lines[idx].find(":", s_i) + 1
    loc_removed = lines[idx][s_i : ].strip()
    filtered_content_lines.append(loc_removed)
    idx += 1
    # 2nd line with the line number
    while idx < len(lines):
        l = lines[idx]
        ln_dot_idx = l.find(".")
        if l.find("^") != -1 and ln_dot_idx == -1:
            filtered_content_lines.append(l[s_i + 1:])
        else:
            s_i = ln_dot_idx
            filtered_content_lines.append(l[s_i + 1:])
        idx += 1



def compute_bug_txt_hash_without_loc(msg_prefix, bug_txt_name, content, ver_hash):
    content = content.decode("utf-8")
    # print("\n===================================")
    # print(content, flush=True)
    # print("===================================\n")
    blocks = content.strip().split("\n\n")
    if len(blocks) < 2:
        print(msg_prefix + "Error: unexpected bug.txt format - at least two blocks are expected.")
        sys.exit(1)
    filtered_content_lines = []
    # bug summary block
    filter_loc_bug_info_block(msg_prefix, bug_txt_name, blocks[0], filtered_content_lines)
    idx = 1
    while idx < len(blocks):
        filtered_content_lines.append("")
        filter_loc_trace_step_block(msg_prefix, bug_txt_name, blocks[idx], filtered_content_lines)
        idx += 1
    filtered_content_lines.append("")
    loc_filtered_content = "\n".join(filtered_content_lines)
    # log the filtered bug_txt if in test mode
    if test_mode:
        log_folder = os.path.join("logs", "loc_filtered", ver_hash)
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        log_file = os.path.join(log_folder, "original.txt")
        no_loc_log_file = os.path.join(log_folder, "no_loc.txt")
        with open(log_file, "a") as fp:
            fp.write("---------------------------------\n")
            fp.write(content)
            fp.write("---------------------------------\n\n\n")
        with open(no_loc_log_file, "a") as fp:
            fp.write("---------------------------------\n")
            fp.write(loc_filtered_content)
            fp.write("---------------------------------\n\n\n")
    sha1sum_without_loc = gen_hash(loc_filtered_content)
    return sha1sum_without_loc



"""
Compute the sha1sum of all trace files (endswith .txt) found in a tar.gz tarball
- the keys of the trace_name_sha1sum_map are in the format of "bug_%d.txt"
"""
def read_hash_traces(msg_prefix, trace_tar_path, ver_hash):
    trace_name_sha1sum_map = {}
    tar = tarfile.open(trace_tar_path, "r:gz")
    cnt = 0
    for filename in tar.getnames():
        if not filename.endswith(".txt"):
            continue
        try:
            cnt += 1
            f = tar.extractfile(filename)
            content = f.read()
            trace_file_name = filename.replace("traces/", "")
            trace_name_sha1sum_map[trace_file_name] = {
                "sha1sum_all": gen_hash(content),
                "sha1sum_no_loc": compute_bug_txt_hash_without_loc(msg_prefix, trace_file_name, content, ver_hash)
            }
        except Exception as e:
            print(e, flush = True)
            continue
    print(msg_prefix + "%d trace txt files loaded" % len(trace_name_sha1sum_map.keys()), flush = True)
    return trace_name_sha1sum_map



def build_github_url(project, commit_hash, file, line):
    if not project in repo_urls:
        return ""
    else:
        return repo_urls[project] + "/blob/" + commit_hash + "/" + file + "/#L%d" % line



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
    


"""
Infer provides bug_trace for each issue. 
The bug_trace contains multiple steps, where each step points to a line in source code
If the commit doesn't touch the files in bug_trace, it's very unlikely to be a fixed issue
This function compares the bug_trace and the changes in the commit to see if there are overlaps. 
"""
def get_commit_trace_overlaps(bug_trace, commit_info):
    overlaps = {}
    if not commit_info is None:     
        for step in bug_trace:
            filename = step["filename"]
            for diff in commit_info["changes"]:
                file_changed = diff["before"]
                if file_changed == filename:
                    if not filename in  overlaps:
                        overlaps[filename] = 0
                    overlaps[filename] += 1
    return overlaps


"""
* prev/report.json format
    [
        {
            "bug_type": "DEAD_STORE",
            "qualifier": "The value written to &iv (type unsigned char const *) is never used.",
            "severity": "ERROR",
            "line": 23,
            "column": 5,
            "procedure": "",
            "procedure_start_line": 12,
            "file": "",
            "bug_trace": [
                {
                    "level": 0,
                    "filename": "",
                    "line_number": 23,
                    "column_number": 5,
                    "description": "Write of unused value"
                }
            ],
            "key": "",
            "hash": "",
            "bug_type_hum": ""
        },
        ...
    ]
"""
def build_issue_key(infer_issue):
    key = "%s:%d:%d:%s" % (infer_issue["hash"], infer_issue["line"], infer_issue["column"], infer_issue["qualifier"]) 
    key = gen_sha256sum(key)
    return key


"""
Step 2.1: read all issues reported for the parent commit
          compute the sha1sum of the bug txt files for deduplicate purpose
"""
def load_issues(msg_prefix, project_name, versions, infer_res_folder, res_dict):
    json_path = os.path.join(infer_res_folder, "prev", "report.json.gz")
    trace_tar_path = os.path.join(infer_res_folder, "prev", "report.html", "traces.tar.gz")
    if not os.path.exists(json_path):
        print(msg_prefix + "Error: no report.json found @ " + json_path, flush = True) 
    if not os.path.exists(trace_tar_path):
        print(msg_prefix + "Error: no trace txt found @ " + trace_tar_path, flush = True)
    res_dict["prev_issues"] = {}
    res_dict["commit_info"] = get_git_commit_info(project_name, versions["before"], versions["after"])
    res_dict["versions"] = {
        "before": versions["before"],
        "after":  versions["after"]
    }
    issues = {}
    # compute the sha1sum of the trace txt files in report.html/traces.tar.gz
    trace_name_sha1sum_map = {}
    print(msg_prefix + "Load 'traces.tar.gz'", flush = True)
    trace_name_sha1sum_map = read_hash_traces(msg_prefix, trace_tar_path, versions["after"])
    # process report.json
    print(msg_prefix + "Load 'prev/report.json.gz'", flush = True)
    with gzip.open(json_path, "rb") as jfp:
        issues = json.load(jfp)
    total_issue_cnt = len(issues)
    cnt = 0
    # traces in older infer start from bug_1.txt
    #        in newer infer start from bug_0.txt
    offset = 0
    if not "bug_0.txt" in trace_name_sha1sum_map:
        offset = 1
    for issue in issues:
        key = build_issue_key(issue)
        if key in res_dict["prev_issues"]:
            print(msg_prefix + "Error: duplicated key found: %s" % (key), flush = True)
        trace_file_name = "bug_%d.txt" % (cnt + offset)
        trace_file_sha1sum = ""
        if trace_file_name in trace_name_sha1sum_map:
            trace_file_sha1sum = trace_name_sha1sum_map[trace_file_name]
        else:
            print(msg_prefix + "Error: key %s not found in trace_name_sha1sum_map" % (trace_file_name), flush = True)
        commit_trace_overlaps = get_commit_trace_overlaps(issue["bug_trace"], res_dict["commit_info"])
        del issue["key"]
        del issue["hash"]
        del issue["bug_type_hum"]
        res_dict["prev_issues"][key] = {
            "report": issue,
            "fixed": 0,
            "src": issue["file"],
            "line": issue["line"],
            "commit_touched": False if 0 == len(commit_trace_overlaps) else True,
            "trace_file": trace_file_name,
            "trace_file_sha1sum_all": trace_file_sha1sum["sha1sum_all"],
            "trace_file_sha1sum_no_loc": trace_file_sha1sum["sha1sum_no_loc"]
        }
        cnt += 1
    print(msg_prefix + "prev/report.json.gz: %d/%d loaded" % (len(res_dict["prev_issues"]), total_issue_cnt) , flush = True)



"""
step 2.2: load bugs in fixed.json
"""
def mark_fixed_issues(msg_prefix, infer_res_folder, res_dict):
    fixed_json_path = os.path.join(infer_res_folder, "differential", "fixed.json")
    if not os.path.exists(fixed_json_path):
        return False
    fixed_issues = []
    marked_cnt = 0
    with open(fixed_json_path, "r") as jfp:
        fixed_issues = json.load(jfp)
    for issue in fixed_issues:
        key = build_issue_key(issue)
        if key in res_dict["prev_issues"]:
            res_dict["prev_issues"][key]["fixed"] = 1
            marked_cnt += 1
        else:
            print(msg_prefix + "Error: cannot mark issue as fixed. key not found: %s" % (key), flush = True)
    print(msg_prefix + "%d/%d issues from 'fixed.json' are marked as fixed" % (marked_cnt, len(fixed_issues)), flush = True)
    return True
     

"""
step 2.3: save the local pairwise results
"""
def save_hash_pair_result(output_path, commit_hash, res_dict):
    dest_file = os.path.join(output_path, processed_commit_folder, commit_hash[0], commit_hash[1], "%s.json.gz" % commit_hash)
    with gzip.open(dest_file, mode = 'wt') as fp:
        fp.write(json.dumps(res_dict))


"""
Step 2: process each hash_pair and save the results as a temp json
"""
def process_one_hash_pair(progress_indicator, project_name, output_folder, infer_folder):
    # get before/after version hashes from "process_hash_pair.log"
    versions = get_versions_from_log(infer_folder)
    msg_prefix = "[%s, %s] " % (progress_indicator, versions["after"])
    print(msg_prefix + "START", flush = True)
    res_dict = {}
    load_issues(msg_prefix, project_name, versions, infer_folder, res_dict)
    mark_fixed_issues(msg_prefix, infer_folder, res_dict)
    save_hash_pair_result(output_folder, versions["after"], res_dict)
    print(msg_prefix + "FINISH - %d issues saved." % len(res_dict["prev_issues"].keys()), flush = True)


"""
Step 3: 
"""
def pairwise_result_loader(idx, total, output_folder, json_gz_file, issues_queue, commits_queue):
    commit_hash = json_gz_file.replace(".json.gz", "")
    msg_prefix = "[%d/%d, %s] " % (idx, total, commit_hash)
    json_path = os.path.join(output_folder, processed_commit_folder, json_gz_file[0], json_gz_file[1], json_gz_file)
    print(msg_prefix + "Start" , flush = True)
    if os.path.isfile(json_path):
        with gzip.open(json_path, "rt") as fp:
            data = json.load(fp)
            total_cnt = len( data["prev_issues"].keys())
            cnt = 0
            for key in data["prev_issues"].keys():
                issue_metadata = {
                    "cmt": data["versions"]["after"], 
                    "key": key,
                    "fixed": data["prev_issues"][key]["fixed"],
                    "touched": data["prev_issues"][key]["commit_touched"],
                    "txt": data["prev_issues"][key]["trace_file"].replace("bug_", "").replace(".txt", ""),
                    "sha1sum_all": data["prev_issues"][key]["trace_file_sha1sum_all"],
                    "sha1sum_no_loc": data["prev_issues"][key]["trace_file_sha1sum_no_loc"]
                }
                issue_metadata_encoded = compress_and_encode_string(json.dumps(issue_metadata)) 
                issues_queue.put(issue_metadata_encoded)
                cnt += 1
            print(msg_prefix + "%d/%d loaded. done" % (cnt, total_cnt), flush = True)
            commit_info_encoded = compress_and_encode_string(json.dumps(data["commit_info"])) 
            commits_queue.put( commit_info_encoded ) 
    else:
        print(msg_prefix + "Error: file not found '%s'" % json_path, flush = True)



def gen_issue_index_file(issue_index_cache, issues_queue):
    msg_prefix = "[issues merger] "
    print(msg_prefix + "Ready", flush = True)
    fp = gzip.open(issue_index_cache, "wb")
    ts = time.time()
    ts_window = 10 * 60
    cnt = 0
    while True:
        issue_metadata_encoded = issues_queue.get()
        # issue_metadata_encoded is compressed and base64 encoded after json.dumps
        issue_metadata_str = decode_and_decompress_string(issue_metadata_encoded)
        if issue_metadata_str == "all_done":
            break
        pickle.dump(issue_metadata_encoded, fp)
        cnt += 1
        now_ts = time.time()
        if (now_ts - ts) > ts_window:
            print(msg_prefix + "%d pickled; %d todo." % (cnt, issues_queue.qsize()), flush=True)
            ts = now_ts
    fp.close()
    print(msg_prefix + "%d issues pickled. Done" % cnt, flush=True)



def all_commits_info_merger(commit_info_cache, commits_queue):
    msg_prefix = "[commits merger] "
    print(msg_prefix + "Ready", flush = True)
    fp = gzip.open(commit_info_cache, "wb")
    ts = time.time()
    ts_window = 10 * 60
    cnt = 0
    while True:
        commit_info_encoded = commits_queue.get()
        # commit_info_encoded is compressed and base64 encoded after json.dumps
        commit_info_str = decode_and_decompress_string(commit_info_encoded)
        if commit_info_str == "all_done":
            break
        commit_info = json.loads(commit_info_str)
        pickle.dump(commit_info, fp)
        cnt += 1
        now_ts = time.time()
        if (now_ts - ts) > ts_window:
            print(msg_prefix + "%d/%d commits pickled" % (cnt, commits_queue.qsize()), flush=True)
            ts = now_ts
    fp.close()
    print(msg_prefix + "%d commits pickled. Done" % cnt, flush=True)



def merge_pairwise_result(output_folder, issue_index_cache, commit_info_cache):
    print("\n", flush = True)
    print("Merge pairwise analysis results.", flush = True)
    print("------------------------------------------------------------", flush = True)
    json_folder = os.path.join(output_folder, processed_commit_folder)
    files = []
    for f in os.listdir(json_folder):  
        f_path = os.path.join(json_folder, f)
        if os.path.isdir(f_path):
            for ff in os.listdir(f_path):
                ff_path = os.path.join(f_path, ff)
                if os.path.isdir(ff_path):
                    for fff in os.listdir(ff_path):
                        fff_path = os.path.join(ff_path, fff)
                        if os.path.isfile(fff_path) and fff.endswith(".json.gz"):
                            files.append(fff)
    total_cnt = len(files)
    # load per-commit results using multiple workers
    manager = multiprocessing.Manager()
    pool = multiprocessing.Pool( multiprocessing.cpu_count() - 2)
    issues_queue = manager.Queue()
    commits_queue = manager.Queue()
    cnt = 0
    jobs = []
    merger_list = []
    # set up the merger workers
    merger = pool.apply_async(gen_issue_index_file, (issue_index_cache, issues_queue))
    merger_list.append(merger)
    merger = pool.apply_async(all_commits_info_merger, (commit_info_cache, commits_queue))
    merger_list.append(merger)
    time.sleep(5)
    # set up the pairwise result loader
    for f in files:
        cnt += 1
        args = (cnt, total_cnt, output_folder, f, issues_queue, commits_queue)
        loader = pool.apply_async(pairwise_result_loader, args)
        jobs.append(loader)
    # wait until loaders finish    
    for job in jobs:
        job.get()

    issues_queue.put( compress_and_encode_string("all_done") )
    commits_queue.put( compress_and_encode_string("all_done") )
    for merger in merger_list:
        merger.get()
    pool.close()
    pool.join()
    print("------------------------------------------------------------\n", flush = True)
    time.sleep(10)
    

def load_issues_index_cache(src_path):
    print("Load all issue index cache @ %s" % src_path, flush=True)
    res = []
    if not os.path.exists(src_path):
        print("|- Error: cannot find file " + src_path, flush=True)
        return res
    cnt = 0
    ts = time.time()
    ts_window = 10 * 60
    with gzip.open(src_path, mode = 'rb') as fp:
        while True:
            try:
                res.append(pickle.load(fp))
                cnt += 1
                now_ts = time.time()
                if (now_ts - ts) > ts_window:
                    print("|- %d issue indices loaded." % cnt, flush=True)
                    ts = now_ts
            except EOFError:
                break
    print("|- %d issue indices loaded. done\n" % cnt, flush=True)
    return res


def load_commit_info(src_path):
    print("Load all commit info @ %s" % src_path, flush=True)
    res = {}
    if not os.path.exists(src_path):
        print("|- Error: cannot find file " + src_path, flush=True)
        return res
    with gzip.open(src_path, mode = 'rb') as fp:
        while True:
            try:
                l = pickle.load(fp)
                commit_hash = l["commit_hash"]
                res[commit_hash] = l
            except EOFError:
                break
    print("|- %d commits loaded. done\n" % len(res.keys()), flush=True)
    return res


def load_unique_bug_history(src_path):
    print("Load unique bugs history @ %s" % src_path, flush=True)
    res = {}
    cnt = 0
    ts = time.time()
    ts_window = 10 * 60
    with gzip.open(src_path, mode = 'rb') as fp:
        while True:
            try:
                l = pickle.load(fp)
                sha1sum_no_loc = l["sha1sum_no_loc"]
                del l["sha1sum_no_loc"]
                res[sha1sum_no_loc] = l
                cnt += 1
                now_ts = time.time()
                if (now_ts - ts) > ts_window:
                    print("|- %d unique issues loaded." % cnt, flush=True)
                    ts = now_ts
            except EOFError:
                break
    print("|- %d unique issues loaded. done.\n" % cnt, flush=True)
    return res


"""
global label algorithm:
    ---------------------------------------
    samples_type:  "fixed_and_unfixed", "fixed_only", "unfixed_only", or "invalid"

    if samples_type == "fixed_and_unfixed":
        if fixed_then_unfixed:
            global_label = 0                 # case 1
        else:
            if exist_commit_touched_fixed:
                global_label = 1             # case 2
            else:
                global_label = 0             # case 3

    else:
        if fixed_only:
            if exist_commit_touched_fixed:
                global_label = 1             # case 4
            else:
                global_label = 0             # case 5
        else: # unfixed_only
            global_label = 0                 # case 6
    ---------------------------------------
set the following fields:
    - fixed_cnt, unfixed_cnt, fix_type, fixed_then_unfixed, exists_commit_touched_fixed, label
"""
def label_one_bug(bug_info):
    local_fixed_cnt = 0
    local_unfixed_cnt = 0
    fixed_found = False
    unfixed_after_fixed_found = False
    exists_commit_touched_fixed = False 
    for commit_info in bug_info["history"]:
        if commit_info["fixed"] == 0:
            local_unfixed_cnt += 1
            if (not unfixed_after_fixed_found) and fixed_found:
                unfixed_after_fixed_found = True
        else:
            local_fixed_cnt += 1
            if (not exists_commit_touched_fixed) and commit_info["touched"] == True:
                exists_commit_touched_fixed = True
            if not fixed_found:
                fixed_found = True
    # ---
    bug_info["fixed_cnt"] = local_fixed_cnt
    bug_info["unfixed_cnt"] = local_unfixed_cnt
    # ---
    if   local_fixed_cnt == 0 and local_unfixed_cnt >  0:
        bug_info["fix_type"] = "unfixed_only"
    elif local_fixed_cnt > 0  and local_unfixed_cnt == 0:
        bug_info["fix_type"] = "fixed_only"
    elif local_fixed_cnt > 0  and local_unfixed_cnt >  0:
        bug_info["fix_type"] = "fixed_and_unfixed"
    else:
        bug_info["fix_type"] = "invalid"
    # ---
    bug_info["fixed_then_unfixed"] = unfixed_after_fixed_found
    # ---
    bug_info["commit_touched_fixed"] = exists_commit_touched_fixed
    # we have everything for the global label
    if bug_info["fix_type"] == "fixed_and_unfixed":
        if bug_info["fixed_then_unfixed"]:
            bug_info["label"] = 0
        else:
            if bug_info["commit_touched_fixed"]:
                bug_info["label"] = 2
            else:
                bug_info["label"] = 0
    elif bug_info["fix_type"] == "fixed_only":
        if bug_info["commit_touched_fixed"]:
            bug_info["label"] = 1
        else:
            bug_info["label"] = 0
    elif bug_info["fix_type"] == "unfixed_only":
        bug_info["label"] = 0
    else:
        bug_info["label"] = 0



def gen_stats(project_name, all_commit_info, unique_bug_info, output_folder):
    print("Generate stats...", flush=True)
    # individual issues stats
    cnt_local_fixed = 0
    cnt_local_fixed_and_touched_by_commit = 0
    cnt_local_fixed_and_not_touched_by_commit = 0
    cnt_local_unfixed = 0
    cnt_local_unfixed_and_touched_by_commit = 0
    cnt_local_unfixed_and_not_touched_by_commit = 0

    tmp_cnt = 0
    ts = time.time()
    ts_window = 10 * 60
    for sha1sum_no_loc in unique_bug_info:
        for issue in unique_bug_info[sha1sum_no_loc]["history"]:
            fixed = issue["fixed"]
            touched_by_commit = issue["touched"]
            if fixed == 0:
                cnt_local_unfixed += 1
                if touched_by_commit:
                    cnt_local_unfixed_and_touched_by_commit += 1
                else:
                    cnt_local_unfixed_and_not_touched_by_commit += 1
            else:
                cnt_local_fixed += 1
                if touched_by_commit:
                    cnt_local_fixed_and_touched_by_commit += 1
                else:
                    cnt_local_fixed_and_not_touched_by_commit += 1
            tmp_cnt += 1
            now_ts = time.time()
            if (now_ts - ts) > ts_window:
                print("|- %d all bugs processed" % tmp_cnt, flush=True)
                ts = now_ts
    print("|- %d all bugs processed. done" % tmp_cnt, flush=True)

    msg  = "=============================================\n"
    msg += "%s status\n" % project_name
    msg += "---------------------------------------------\n"
    msg += "%d commit pairs with differential results.\n" % len(all_commit_info)
    msg += "\n"
    msg += "%d bugs found (duplications possible).\n" % tmp_cnt
    msg += "|- %d bugs appear in 'fixed.json'.\n" % cnt_local_fixed
    msg += "|  |- %d share common files with corresponding commits.\n" % cnt_local_fixed_and_touched_by_commit
    msg += "|  |- %d do NOT.\n" % cnt_local_fixed_and_not_touched_by_commit
    msg += "|- %d bugs do NOT appear in 'fixed.json'.\n" % cnt_local_unfixed
    msg += "|  |- %d share common files with corresponding commits.\n" % cnt_local_unfixed_and_touched_by_commit
    msg += "|  |- %d do not.\n" % cnt_local_unfixed_and_not_touched_by_commit
    # -----
    # global stats
    label_0_cnt = 0
    label_1_cnt = 0
    label_2_cnt = 0
    label_0_case_0 = 0
    label_0_case_1 = 0
    label_0_case_2 = 0
    label_0_case_3 = 0
    label_0_case_4 = 0
    label_1_case_0 = 0
    label_2_case_0 = 0
    fixed_only_cnt = 0
    unfixed_only_cnt = 0
    fixed_and_unfixed_cnt = 0
    invalid_cnt = 0

    tmp_cnt = 0
    ts = time.time()
    ts_window = 10 * 60
    unique_bug_info_len = len(unique_bug_info)
    for sha1sum in unique_bug_info.keys():
        bug_info = unique_bug_info[sha1sum]
        if bug_info["label"] == 0:
            label_0_cnt += 1
        elif bug_info["label"] == 1:
            label_1_cnt += 1
        else:
            label_2_cnt += 1
        
        if bug_info["fix_type"] == "fixed_and_unfixed":
            fixed_and_unfixed_cnt += 1
            if bug_info["fixed_then_unfixed"]:
                # bug_info["label"] = 0
                label_0_case_0 += 1
            else:
                if bug_info["commit_touched_fixed"]:
                    # bug_info["label"] = 2
                    label_2_case_0 += 1
                else:
                    # bug_info["label"] = 0
                    label_0_case_1 += 1
        elif bug_info["fix_type"] == "fixed_only":
            fixed_only_cnt += 1
            if bug_info["commit_touched_fixed"]:
                # bug_info["label"] = 1
                label_1_case_0 += 1
            else:
                # bug_info["label"] = 0
                label_0_case_2 += 1
        elif bug_info["fix_type"] == "unfixed_only":
            unfixed_only_cnt += 1
            # bug_info["label"] = 0
            label_0_case_3 += 1
        else:
            invalid_cnt += 1
            # bug_info["label"] = 0
            label_0_case_4 += 1
        tmp_cnt += 1
        now_ts = time.time()
        if (now_ts - ts) > ts_window:
            print("|- %d/%d unique bug processed" % (tmp_cnt, unique_bug_info_len), flush=True)
            ts = now_ts
    print("|- %d/%d unique bug processed. done" % (tmp_cnt, unique_bug_info_len), flush=True)

    msg += "\n"
    msg += "%d unique bugs.\n" % len(unique_bug_info)
    msg += "|- %d unfixed_only\n" % unfixed_only_cnt
    msg += "|  |- [label 0] %d unfixed\n" % unfixed_only_cnt    
    msg += "|- %d fixed_only.\n" % fixed_only_cnt
    msg += "|  |- [label 0] %d NONE fixed bugs share common files with commits\n" % label_0_case_2   
    msg += "|  |- [label 1] %d exists fixed bugs share common files with commits\n" % label_1_case_0
    msg += "|- %d fixed_and_unfixed.\n" % fixed_and_unfixed_cnt
    msg += "|  |- [label 0] %d unfixed after fixed\n" % label_0_case_0
    msg += "|  |- [label 0] %d NONE fixed bugs share common files with commits\n" % label_0_case_1
    msg += "|  |- [label 2] %d exists fixed bugs share common files with commits\n" % label_2_case_0
    msg += "|- %d invalid (neither fixed nor unfixed).\n" % invalid_cnt
    msg += "\n"
    msg += "%d unique bugs\n" % len(unique_bug_info)
    msg += "|- [label 0] %d\n" % label_0_cnt
    msg += "|  |- %d fixed_and_unfixed - unfixed AFTER fixed.\n" % label_0_case_0
    msg += "|  |- %d fixed_and_unfixed - fixed bugs do NOT share common files with commits.\n" % label_0_case_1
    msg += "|  |- %d fixed_only - fixed do NOT share common files with commits.\n" % label_0_case_2
    msg += "|  |- %d unfixed_only\n" % label_0_case_3
    msg += "|  |- %d invalid - neither fixed nor unfixed.\n" % label_0_case_4
    msg += "|- [label 1] %d\n" % label_1_cnt
    msg += "|  |- %d fixed_only - exists fixed bugs share common files with commits.\n" % label_1_case_0
    msg += "|- [label 2] %d\n" % label_2_cnt
    msg += "|  |- %d fixed_and_unfixed - exists fixed bugs share common files with commits.\n" % label_2_case_0
    msg += "=============================================\n"
    print("\n\n", flush = True)
    print(msg, flush = True)
    print("\n", flush = True)
    # write stats summary
    with open(os.path.join(output_folder, "summary.txt"), "w") as fp:
        fp.write(msg)



def select_bug_sample_for_output(sha1sum, bug_info):
    if bug_info["label"] == 1 or bug_info["label"] == 2:
        for bug in bug_info["history"]:
            if bug["fixed"] == 1 and bug["touched"] == True:
                return (bug["cmt"], bug["key"], bug["txt"])
        # when we are here, there is no fixed case with commit_touched == True
        for bug in bug_info["history"]:
            if bug["fixed"] == 1:
                print("Warning: no bug (label 1 or 2) satisfying 'fixed = 1' and 'commit_touched = True' found for unique bug %s" % sha1sum, flush = True)
                return (bug["cmt"], bug["key"], bug["txt"])
        print("Error: no bug (label 1 or 2) satisfying 'fixed = 1' found for unique bug %s" % sha1sum, flush = True)
    else:
        for bug in bug_info["history"]:
            if bug["fixed"] == 0:
                return (bug["cmt"], bug["key"], bug["txt"])
        # when an issue is fixed but not touched by commit
        for bug in bug_info["history"]:
            return (bug["cmt"], bug["key"], bug["txt"])
    


def organize_unique_bugs_by_commits(output_folder, unique_bug_info, use_cached):
    print("organizing unique bugs by commits.", flush = True)
    unique_bugs_by_commit = {}
    total_unique_bugs = len(unique_bug_info.keys())
    cnt = 0
    ts = time.time()
    ts_window = 10 * 60
    for sha1sum_no_loc in unique_bug_info:
        (sample_commit, sample_issue_key, sample_trace_file) = select_bug_sample_for_output(sha1sum_no_loc, unique_bug_info[sha1sum_no_loc])
        sample_trace_file = "bug_" + sample_trace_file + ".txt"
        if sample_commit not in unique_bugs_by_commit:
            unique_bugs_by_commit[sample_commit] = {}
        unique_bugs_by_commit[sample_commit][sample_trace_file] =  {
            "sha1sum_no_loc": sha1sum_no_loc,
            "sha1sum_all": unique_bug_info[sha1sum_no_loc]["sha1sum_all"],
            "sample_issue_key": sample_issue_key,
            "fixed_cnt":    unique_bug_info[sha1sum_no_loc]["fixed_cnt"],
            "unfixed_cnt":  unique_bug_info[sha1sum_no_loc]["unfixed_cnt"],
            "fix_type":     unique_bug_info[sha1sum_no_loc]["fix_type"],
            "fixed_then_unfixed":    unique_bug_info[sha1sum_no_loc]["fixed_then_unfixed"],
            "commit_touched_fixed":  unique_bug_info[sha1sum_no_loc]["commit_touched_fixed"],
            "label":        unique_bug_info[sha1sum_no_loc]["label"]
        }
        cnt += 1
        now_ts = time.time()
        if (now_ts - ts) > ts_window:
            print("|- %d/%d bugs grouped" % (cnt, total_unique_bugs), flush=True)
            ts = now_ts
    print("|- %d bugs grouped. done\n" % cnt, flush=True)
    bug_info_by_commit_folder = os.path.join(output_folder, "bug_info_by_commit")
    if (not use_cached) or (not os.path.exists(bug_info_by_commit_folder)):
        print("save bugs by commit hash", flush=True)
        w_cnt = 0
        for commit in unique_bugs_by_commit:
            dest_folder = os.path.join(output_folder, "bug_info_by_commit", commit[0], commit[1])
            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder)
            dest_file =  os.path.join(dest_folder, "%s.pickle.gz" % commit )
            pkl_fp = gzip.open(dest_file, "wb")
            pickle.dump(unique_bugs_by_commit[commit], pkl_fp)
            pkl_fp.close()
            w_cnt += 1
            if w_cnt % 1000 == 0:
                print("|- %d commit groups saved" % w_cnt, flush=True)
        print("|- %d commit groups saved. done\n" % w_cnt, flush=True)
    else:
        print("SKIP bug_info_by_commit generation. Use the cache from %s\n" % bug_info_by_commit_folder, flush=True)
    return list(unique_bugs_by_commit.keys())
    



def get_bug_metadata(msg_prefix, project_name, output_folder, infer_output_path, bug_info_by_commit, commit):
    total_issues = len(bug_info_by_commit.keys())
    bug_metadata = {}
    for trace_file in bug_info_by_commit:
        bug_metadata[trace_file] = {
            "bug_type": "",
            "steps_in_trace": -1,
            "url": "",
            "bug_detail": {},
            "trace_file_content": ""
        }
    # per commit json file
    src_file = os.path.join(output_folder, processed_commit_folder, commit[0], commit[1], "%s.json.gz" % commit)
    cnt = 0
    if os.path.exists(src_file):
        data = {}
        with gzip.open(src_file, "rt") as fp:
            data = json.load(fp)
        for trace_file in bug_info_by_commit:
            issue_key = bug_info_by_commit[trace_file]["sample_issue_key"]
            if issue_key in data["prev_issues"]:
                issue = data["prev_issues"][issue_key]
                bug_metadata[trace_file]["bug_type"] = issue["report"]["bug_type"]
                bug_metadata[trace_file]["steps_in_trace"] = len(issue["report"]["bug_trace"])
                bug_metadata[trace_file]["url"] = build_github_url(project_name, data["versions"]["before"], issue["src"], issue["line"])
                bug_metadata[trace_file]["bug_detail"] = issue
                cnt += 1
    else:
        print(msg_prefix + "Error: cannot find per commit json file '%s'" % src_file, flush = True)
    # print(msg_prefix + "%d bug metadata loaded" % (cnt), flush=True)
    if cnt != total_issues:
        print(msg_prefix + "Error: missing metadata. %d out of %d found." % (cnt, total_issues), flush=True)
    # trace txt tar ball
    cnt = 0 
    trace_tar_path = os.path.join(infer_output_path, commit[0], commit[1], commit, "prev", "report.html", "traces.tar.gz")
    tar = tarfile.open(trace_tar_path, "r:gz")
    for filename in tar.getnames():
        trace_file = filename.replace("traces/", "")
        if trace_file in bug_metadata.keys():
            f = tar.extractfile(filename)
            content = f.read()
            bug_metadata[trace_file]["trace_file_content"] = compress_and_encode_string(content) 
            cnt += 1
    # print(msg_prefix + "%d bug_txt files loaded" % (cnt), flush=True)
    if cnt != total_issues:
        print(msg_prefix + "Error: missing bug_txt. %d out of %d found." % (cnt, total_issues), flush=True)
    return bug_metadata


"""
"""
def csv_writer(csv_file, output_folder, row_queue):
    msg_prefix = "[csv %s] " % csv_file.replace("_bugs", "")
    print(msg_prefix + "Ready", flush = True)
    dest_path = os.path.join(output_folder, "%s.csv" % csv_file)
    csv_fp = open(dest_path, "w")
    writer = csv.writer(csv_fp, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    field_names = [
        'sha1sum_no_loc', 'sha1sum_all', 'bug_type', 
        'samples_type', 'sample_cnt', 'fixed_cnt', 'unfixed_cnt', 
        'fixed_then_unfixed', 'commit_touch_fixed', 'trace_steps',
        'sample_commit', 'sample_bug_txt_file', 'sample_url', 'encoded_bug_txt'
    ]    
    writer.writerow(field_names)
    cnt = 0
    while True:
        row_encoded = row_queue.get()
        row_str = decode_and_decompress_string(row_encoded)
        if row_str == "all_done":
            break
        row = json.loads(row_str)
        writer.writerow(row)
        cnt += 1
        if cnt % 200000 == 0:
            print(msg_prefix + "%d/%d issues saved" % (cnt, row_queue.qsize()), flush=True)
    csv_fp.close()
    print(msg_prefix + "%d issues saved. done" % (cnt), flush=True)



def bug_details_writer(file_name, output_folder, row_queue):
    msg_prefix = "[pkl %s] " % file_name.replace("_bug_details", "")
    print(msg_prefix + "Ready", flush = True)
    pkl_dest = os.path.join(output_folder, "%s.pickle.gz" % file_name)
    pkl_fp = gzip.open(pkl_dest, "wb")
    cnt = 0
    while True:
        bug_detail_encoded = row_queue.get()
        bug_detail_str = decode_and_decompress_string(bug_detail_encoded)
        if bug_detail_str == "all_done":
            break
        bug_detail = json.loads(bug_detail_str)
        pickle.dump(bug_detail, pkl_fp)
        cnt += 1
        if cnt % 200000 == 0:
            print(msg_prefix + "%d/%d records saved" % (cnt, row_queue.qsize()), flush=True)
    pkl_fp.close()
    print(msg_prefix + "%d records saved. done" % (cnt), flush=True)




def label_loader(project_name, infer_output_path, output_folder, 
                commit_idx, commit_total, commit, 
                lb0_queue, lb1_queue, lb2_queue, 
                detail_0_queue, detail_1_queue, detail_2_queue):
    digit = 0
    tmp = commit_total
    while tmp > 0:
        digit += 1
        tmp = int(tmp / 10)
    format_str = "[%%%dd/%%%dd, %%s] " % (digit, digit)
    msg_prefix = format_str % (commit_idx, commit_total, commit)
    print(msg_prefix + "Start", flush = True)
    # load bug_info_by_commit
    src_file = os.path.join(output_folder, "bug_info_by_commit", commit[0], commit[1], "%s.pickle.gz" % commit)
    if not os.path.exists(src_file):
        print(msg_prefix + "Error: cannot find " + src_file)
    bug_info_by_commit = {}
    with gzip.open(src_file, mode = 'rb') as fp:
        bug_info_by_commit = pickle.load(fp)
    bug_metadata = get_bug_metadata(msg_prefix, project_name, output_folder, infer_output_path, bug_info_by_commit, commit)
    cnt = 0
    ts = time.time()
    ts_window = 10 * 60
    # bug_info_total = len(bug_info_by_commit)
    for sample_trace_file in bug_info_by_commit:
        bug_info = bug_info_by_commit[sample_trace_file]
        bug = bug_metadata[sample_trace_file]
        # bug details
        per_bug_res = {
            "sha1sum_no_loc":     bug_info["sha1sum_no_loc"],
            "sha1sum_all":        bug_info["sha1sum_all"],
            "bug_type":           bug["bug_type"], 
            "label" :             bug_info["label"],
            "status_type":        bug_info["fix_type"], 
            "sample_cnt":        (bug_info["fixed_cnt"] + bug_info["unfixed_cnt"]), 
            "fixed_cnt":          bug_info["fixed_cnt"], 
            "unfixed_cnt":        bug_info["unfixed_cnt"],
            "fixed_then_unfixed": bug_info["fixed_then_unfixed"],
            "commit_touch_fixed": bug_info["commit_touched_fixed"], 
            "trace_steps":        bug["steps_in_trace"],
            "sample_commit":      commit,
            "sample_bug_txt_file":sample_trace_file, 
            "sample_url":         bug["url"],
            "sample_bug":         bug["bug_detail"],
            "sample_gzipped_bug_txt_file_content": bug["trace_file_content"]
        }
        bug_detail_encoded = compress_and_encode_string(json.dumps(per_bug_res))
        # csv records
        record = [
            bug_info["sha1sum_no_loc"], ",".join(bug_info["sha1sum_all"]), bug["bug_type"],
            bug_info["fix_type"], (bug_info["fixed_cnt"] + bug_info["unfixed_cnt"]), bug_info["fixed_cnt"], bug_info["unfixed_cnt"],
            bug_info["fixed_then_unfixed"], bug_info["commit_touched_fixed"], bug["steps_in_trace"],
            commit, sample_trace_file, bug["url"], bug["trace_file_content"]
        ]
        csv_row_encoded = compress_and_encode_string(json.dumps(record))
        if bug_info["label"] == 0:
            detail_0_queue.put(bug_detail_encoded)
            lb0_queue.put(csv_row_encoded)
        elif bug_info["label"] == 1:
            detail_1_queue.put(bug_detail_encoded)
            lb1_queue.put(csv_row_encoded)
        elif bug_info["label"] == 2:
            detail_2_queue.put(bug_detail_encoded)
            lb2_queue.put(csv_row_encoded)
        else:
            print("Warning: labels other than 0/1/2 found. no csv files prepared for this label", flush = True)
        cnt += 1
        now_ts = time.time()
        if (now_ts - ts) > ts_window:
            print(msg_prefix + "%d unique bugs processed." % cnt, flush = True)
            ts = now_ts
    print(msg_prefix + "%d unique bugs processed. done." % cnt, flush = True)




def gen_unique_bug_info(unique_bugs_history_file, issue_index, commit_info):
    unique_bug_info = {}
    print("Generate unique_bug_info", flush = True)
    cnt = 0
    ts = time.time()
    ts_window = 10 * 60
    total_issue_cnt = len(issue_index)
    for issue_encoded in issue_index:
        issue = json.loads( decode_and_decompress_string(issue_encoded) )
        # sha1sum_all: sha1sum of the all content in bug.txt
        sha1sum_all = issue["sha1sum_all"]
        sha1sum_no_loc = issue["sha1sum_no_loc"]

        commit_hash = issue["cmt"]
        timestamp = -1
        if commit_hash in commit_info:
            timestamp = commit_info[commit_hash]["timestamp"]
        if sha1sum_no_loc not in unique_bug_info:
            unique_bug_info[sha1sum_no_loc] = {
                "history": [], 
                "sha1sum_all": []
            }
        # keep track of bug id used in the 1st version
        # sha1sum_all: is the sha1sum of all content in bug_txt
        # sha1sum_no_loc: remove code location info/
        if sha1sum_all not in unique_bug_info[sha1sum_no_loc]["sha1sum_all"]:
            unique_bug_info[sha1sum_no_loc]["sha1sum_all"].append(sha1sum_all)
        unique_bug_info[sha1sum_no_loc]["history"].append({
            "ts": timestamp,
            "cmt": issue["cmt"],
            "key": issue["key"],
            "txt": issue["txt"],
            "fixed": issue["fixed"],
            "touched": issue["touched"]
        })
        cnt += 1
        now_ts = time.time()
        if (now_ts - ts) > ts_window:
            print("|- %d/%d issues grouped." % (cnt, total_issue_cnt), flush = True)
            ts = now_ts
    print("|- %d/%d issues grouped. done.\n" % (cnt, total_issue_cnt), flush = True)

    print("Label and save issues.", flush = True)
    unique_bug_count = len(unique_bug_info.keys())
    cnt = 0
    ts = time.time()
    ts_window = 10 * 60
    fp = gzip.open(unique_bugs_history_file, "wb")
    for sha1sum_no_loc in unique_bug_info.keys():
        unique_bug_info[sha1sum_no_loc]["history"].sort(key = lambda x : x["ts"])
        bug_info = unique_bug_info[sha1sum_no_loc]
        # assign global label for the issues
        label_one_bug(bug_info)
        record = {"sha1sum_no_loc": sha1sum_no_loc}
        for k in bug_info:
            record[k] = bug_info[k]
        pickle.dump(record, fp)
        cnt += 1
        now_ts = time.time()
        if (now_ts - ts) > ts_window:
            print("|- %d/%d unique bugs labeled" % (cnt, unique_bug_count), flush = True)
            ts = now_ts
    fp.close()
    print("|- %d/%d unique bugs labeled. done.\n" % (cnt, unique_bug_count), flush = True)
    return unique_bug_info



def deduplicate_label_issues(project_name, output_folder, use_cached, issue_index_cache, commit_info_cache, sample_commits_path):
    unique_bug_info = {}
    unique_bugs_history_file = os.path.join(output_folder, cache_folder_name, "unique_bugs_info.pickle.gz")
    commit_info = load_commit_info(commit_info_cache)
    if (not use_cached) or (not os.path.exists(unique_bugs_history_file)):
        issue_index = load_issues_index_cache(issue_index_cache)
        unique_bug_info = gen_unique_bug_info(unique_bugs_history_file, issue_index, commit_info) 
    else:
        unique_bug_info = load_unique_bug_history(unique_bugs_history_file)
    # -----
    # generate dataset stats
    gen_stats(project_name, commit_info, unique_bug_info, output_folder)
    # -----
    # identify samples for each unique bug
    # group unique bugs by sample commits so that we can split the loads for multi-processing purpose
    commit_list = organize_unique_bugs_by_commits(output_folder, unique_bug_info, use_cached)
    fp = gzip.open(sample_commits_path, "wb")
    pickle.dump(commit_list, fp)
    fp.close()
    # print("Sample commit list saved to %s\n" % sample_commits_path, flush=True)
    return commit_list


def load_sample_commits(sample_commits_path):
    print("Load sample commit from %s" % sample_commits_path, flush=True)
    res = []
    with gzip.open(sample_commits_path, mode = 'rb') as fp:
        res = pickle.load(fp)
    print("|- %d commits loaded. done.\n" % len(res), flush=True)
    return res



def generate_label_csv(project_name, infer_output_path, commit_list, output_folder):
    print("generating csv label file and detailed json for unique bugs.", flush = True)
    print("------------------------------------------------------------", flush = True)

    # multi-processing
    manager = multiprocessing.Manager()
    pool = multiprocessing.Pool(multiprocessing.cpu_count() - 2)
    label_0_queue = manager.Queue()
    label_1_queue = manager.Queue()
    label_2_queue = manager.Queue()
    detail_0_queue = manager.Queue()
    detail_1_queue = manager.Queue()
    detail_2_queue = manager.Queue()
    jobs = []
    writer_list = []
    # set up writer workers
    writer_list.append(pool.apply_async(csv_writer, ("label_0_bugs", output_folder, label_0_queue)))
    writer_list.append(pool.apply_async(csv_writer, ("label_1_bugs", output_folder, label_1_queue)))
    writer_list.append(pool.apply_async(csv_writer, ("label_2_bugs", output_folder, label_2_queue)))
    writer_list.append(pool.apply_async(bug_details_writer, ("label_0_bug_details", output_folder, detail_0_queue)))
    writer_list.append(pool.apply_async(bug_details_writer, ("label_1_bug_details", output_folder, detail_1_queue)))
    writer_list.append(pool.apply_async(bug_details_writer, ("label_2_bug_details", output_folder, detail_2_queue)))
    time.sleep(5)
    # set up the pairwise result loader
    commit_cnt = 0
    commit_total = len(commit_list)
    for sample_commit in commit_list:
        commit_cnt += 1
        args = (project_name, infer_output_path, output_folder, 
                commit_cnt, commit_total, sample_commit,  
                label_0_queue, label_1_queue, label_2_queue, 
                detail_0_queue, detail_1_queue, detail_2_queue)
        jobs.append(pool.apply_async(label_loader, args))
    # wait until loaders finish
    for job in jobs:
        job.get()
    exit_request_msg = compress_and_encode_string("all_done")
    label_0_queue.put(exit_request_msg)
    label_1_queue.put(exit_request_msg)
    label_2_queue.put(exit_request_msg)
    detail_0_queue.put(exit_request_msg)
    detail_1_queue.put(exit_request_msg)
    detail_2_queue.put(exit_request_msg)
    for writer in writer_list:
        writer.get()
    pool.close()
    pool.join()
    print("------------------------------------------------------------", flush = True)
    print("csv files and dug detail pickle file generated. done.\n", flush=True)




"""
Put everything together
"""
def process_hash_pairs(project_name, infer_output_path, output_folder = None, process_individual_pairs = True, use_cached = False):
    global idx_list
    if output_folder is None:
        output_folder = datetime.now().strftime("%Y-%m-%d") + "_" + project_name
    cleanup(output_folder, process_individual_pairs)
    # Step 1: 
    # - load pairwise analysis results 
    # - save the output as 'issues_by_commit/a/f/after_commit.json.gz
    # - this is done using multiple processes in parallel
    if process_individual_pairs:
        commit_folder_list = load_commits_with_differential(infer_output_path)
        total_commit = len(commit_folder_list)
        print("%d commit pairs with differential folder.\n" % total_commit, flush = True)
        # multi-processing: one work per version pair 
        pool = multiprocessing.Pool( multiprocessing.cpu_count() - 2 )
        jobs = []
        item_idx = 0
        for item in commit_folder_list:
            item_idx += 1
            (_, infer_commit_folder) = item
            progress_indicator = "%d/%d" % (item_idx, total_commit)
            args = (progress_indicator, project_name, output_folder, infer_commit_folder)
            job = pool.apply_async(process_one_hash_pair, args)
            jobs.append(job)
        for job in jobs:
            job.get()
        pool.close()
        pool.join()
    else:
        print("SKIP processing infer pairwise outputs. Reuse '%s'.\n" % output_folder, flush = True)
    gc.collect()
    
    # Step 2:
    # - load pairwise analysis results
    # - get a few fields that are useful to identify and deduplicate the bugs 
    #   --> save @ "cache/issue_index.pickle.gz"
    # - load commit info (changes) and deduplicate by commit hash 
    #   --> save @ "cache/commit_info.pickle.gz"
    issue_index_cache = os.path.join(output_folder, cache_folder_name, "issue_index.pickle.gz")
    commit_info_cache = os.path.join(output_folder, cache_folder_name, "commit_info.pickle.gz")
    if (not use_cached) or (not os.path.exists(issue_index_cache)) or (not os.path.exists(commit_info_cache)):
        merge_pairwise_result(output_folder, issue_index_cache, commit_info_cache)
    else:
        print("SKIP merging pairwise analysis results. Use cache instead.\n", flush=True)
    gc.collect()

    # Step 3:
    # - load issue index cache "cache/issue_index.pickle.gz"
    # - load commit info cache "cache/commit_info.pickle.gz"
    commit_list = []
    sample_commits_path = os.path.join(output_folder, cache_folder_name, "sample_commits.pickle.gz")
    if (not use_cached) or (not os.path.exists(sample_commits_path)):
        commit_list = deduplicate_label_issues(project_name, output_folder, use_cached, issue_index_cache, commit_info_cache, sample_commits_path)
    else:
        commit_list = load_sample_commits(sample_commits_path)
    gc.collect()
    
    # generate label csv
    generate_label_csv(project_name, infer_output_path, commit_list, output_folder)
    print("\nall finished.\n", flush = True)

    

def process_openssl():
    output_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/output/openssl"
    process_hash_pairs(project_name = "openssl", infer_output_path = output_path, process_individual_pairs = True, use_cached = False)

def process_ffmpeg():
    output_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/output/ffmpeg"
    process_hash_pairs(project_name = "ffmpeg", infer_output_path = output_path, process_individual_pairs = True, use_cached = False)

def process_httpd():
    output_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/output/httpd"
    process_hash_pairs(project_name = "httpd", infer_output_path = output_path, process_individual_pairs = True, use_cached = False)

def process_nginx():
    output_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/output/nginx"
    process_hash_pairs(project_name = "nginx", infer_output_path = output_path, process_individual_pairs = True, use_cached = False)

def process_libtiff():
    output_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/output/libtiff"
    process_hash_pairs(project_name = "libtiff", infer_output_path = output_path, process_individual_pairs = True, use_cached = False)

def process_libav():
    output_path = "/gpfs/r92gpfs02/zhengyu/infer_runs/output/libav"
    process_hash_pairs(project_name = "libav", infer_output_path = output_path, process_individual_pairs = True, use_cached = False)


if __name__ == '__main__':
    if len(sys.argv) < 1:
        print("Error: %s project" % sys.argv[0])
        sys.exit(1)
    project = sys.argv[1]
    if project == "openssl":
        process_openssl()
    elif project == "ffmpeg":
        process_ffmpeg()
    elif project == "httpd":
        process_httpd()
    elif project == "nginx":
        process_nginx()
    elif project == "libtiff":
        process_libtiff()
    elif project == "libav":
        process_libav()
    else:
        print("Unknown project. Exit.")


