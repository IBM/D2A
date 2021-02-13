#!/usr/bin/env python3

import os
import json
import csv
from datetime import datetime



def get_commits_without_differential(task_name, commit_list_file, infer_output_path):
#    if not os.path.exists(commit_list_file):
#        print("error: cannot find commit list file @ '%s'" % commit_list_file)
#        return
    
    all_commits = []
    unique_all_commits = set()
    duplicated_all_commits = []
    if os.path.exists(commit_list_file):
        with open(commit_list_file, "r") as fp:
            for l in fp.readlines():
                l = l.strip()
                if l != "":
                    if l in unique_all_commits:
                        duplicated_all_commits.append(l)
                    all_commits.append(l)
                    unique_all_commits.add(l)

    processed_commits = set()
    unprocessed_commits = []
    failure_commits = []
    failure_logs = []

    folder_cnt = 0
    log__no_diff = 0
    log__diff = 0
    no_log__no_diff = 0
    no_log__diff = 0
    empty_fixed_json = 0
    non_empty_fixed_json = 0


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
                            processed_commits.add(fff)
                            # fff_path is folder `a/2/a26e245ecd6a15459202569e0df8b40bc10339a5`
                            log_path = os.path.join(fff_path, "process_hash_pair.log")
                            fixed_json_path = os.path.join(fff_path, "differential", "fixed.json")
                            folder_cnt += 1
                            success = False
                            if os.path.exists(log_path):
                                if os.path.exists(fixed_json_path):
                                    log__diff += 1
                                    fixed_json_size = os.path.getsize(fixed_json_path)
                                    if fixed_json_size > 2:
                                        non_empty_fixed_json += 1
                                    else:
                                        empty_fixed_json += 1
                                    success = True
                                else:
                                    log__no_diff += 1
                            else:
                                if os.path.exists(fixed_json_path):
                                    no_log__diff += 1
                                else:
                                    no_log__no_diff += 1
                            if not success:
                                failure_commits.append(fff)
                                failure_logs.append(log_path)
    for c in all_commits:
        if not c in processed_commits:
            unprocessed_commits.append(c)

    msg  = "===================================================\n"
    msg += "%s\n" % task_name
    msg += "* commit: %s\n" % commit_list_file
    msg += "* output: %s\n" % infer_output_path
    msg += "---------------------------------------------------\n"
    msg += "%4d commits (%d unique).\n" % (len(all_commits), len(unique_all_commits))
    msg += "|- %4d processed.\n" % folder_cnt
    msg += "|  |- %4d successes.\n" % log__diff
    msg += "|  |  |- %4d non-empty fixed.json.\n" % non_empty_fixed_json
    msg += "|  |  |- %4d empty fixed.json.\n" % empty_fixed_json
    msg += "|  |- %4d processing or failures.\n" % (folder_cnt - log__diff)
    msg += "|- %4d unprocessed." % len(unprocessed_commits)
    msg += "\n"
    msg += "details:\n"
    msg += "|- [x] process_hash_pair.log, [x] fixed.json | %4d\n" % log__diff
    msg += "|- [x] process_hash_pair.log, [ ] fixed.json | %4d\n" % log__no_diff
    msg += "|- [ ] process_hash_pair.log, [x] fixed.json | %4d\n" % no_log__diff
    msg += "|- [ ] process_hash_pair.log, [ ] fixed.json | %4d\n" % no_log__no_diff
    msg += "===================================================\n"

    print(msg)

    dest_folder = "analysis_status"
    timestamp = datetime.now().strftime("%Y%m%d")
    if not os.path.exists(dest_folder):
        os.mkdir(dest_folder)
    with open(os.path.join(dest_folder, "%s_%s_summary.txt" % (timestamp, task_name)), "w") as fp:
        fp.write(msg)
    if len(failure_commits) > 0:
        # with open(os.path.join(dest_folder, "%s_%s_failure_commits.txt" % (timestamp, task_name)), "w") as fp:
        #     for c in failure_commits:
        #         fp.write("%s\n" % c)
        with open(os.path.join(dest_folder, "%s_%s_failure_logs.txt" % (timestamp, task_name)), "w") as fp:
            for l in failure_logs:
                fp.write("%s\n" % l)
    if len(unprocessed_commits) > 0:
        with open(os.path.join(dest_folder, "%s_%s_unprocessed.txt" % (timestamp, task_name)), "w") as fp:
            for l in unprocessed_commits:
                fp.write("%s\n" % l)
    if len(duplicated_all_commits) > 0:
        with open(os.path.join(dest_folder, "%s_%s_duplicated_commits.txt" % (timestamp, task_name)), "w") as fp:
            for l in duplicated_all_commits:
                fp.write("%s\n" % l)
    

if __name__ == '__main__':
    get_commits_without_differential("openssl", "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/openssl/commitlist.output", "/gpfs/r92gpfs02/zhengyu/infer_runs/output/openssl")
    print("")
    
    get_commits_without_differential("ffmpeg", "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/ffmpeg/devign_ffmpeg_commits.txt", "/gpfs/r92gpfs02/zhengyu/infer_runs/output/ffmpeg")
    print("")
    
    get_commits_without_differential("httpd", "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/httpd/20200422_httpd_commit_only.txt", "/gpfs/r92gpfs02/zhengyu/infer_runs/output/httpd")
    
    get_commits_without_differential("libtiff", "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/libtiff/20200703_libtiff_commit_only.txt", "/gpfs/r92gpfs02/zhengyu/infer_runs/output/libtiff")
   
    get_commits_without_differential("libav", 
      "/gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/libav/20200705_libav_commit_only.txt",
      "/gpfs/r92gpfs02/zhengyu/infer_runs/output/libav"
    )



