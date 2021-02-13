#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from os.path import isfile, join
import subprocess
import json
import shutil
import copy
import gzip
import pickle
from datetime import datetime
import shlex
import utils
import shlex
import shutil
import time
import multiprocessing
import pickle
import gzip

import clang.cindex
import clang.enumerations
from clang.cindex import Index
from clang.cindex import Config
from clang.cindex import TranslationUnitLoadError


"""
Global variables
"""
g_index = None
g_clang_default_headers = None
g_labeler_output = None
g_repo_local_path = None
g_repo_url = None
g_tmp_output_folder = None
g_work_folder = "/dev/shm/zhengyu"


# ============================


def init(project, arg_tmp_output_folder = ""):
    global g_labeler_output, g_repo_local_path, g_repo_url, g_tmp_output_folder
    global g_index, g_clang_default_headers
    # load config
    print("\n* init", flush=True)
    config_file = 'config.json'
    if not os.path.exists(config_file):
        print("  - Error: cannot find config file '%s'" % config_file, flush=True)
        sys.exit(1)
    print("  - load config from '%s'" % config_file, flush = True)
    config_json = {}
    with open(config_file, "r") as fp:
        config_json = json.load(fp)
    # auto-labeler output folder
    if project not in config_json["labeler_output"]:
        print("  - Error: cannot find labeler output folder for project '%s' in config.json" % project)
        sys.exit(1)
    g_labeler_output = config_json["labeler_output"][project]
    if not os.path.exists(g_labeler_output):
        print("  - Error: cannot find auto-labeler output folder '%s'" % g_labeler_output)
        sys.exit(1)
    # project repo url
    if project not in config_json["repos"]:
        print("  - Error: cannot find repo url for project '%s' in config.json" % project)
        sys.exit(1)
    g_repo_url = config_json["repos"][project]
    # clang default headers and index
    if not clang.cindex.Config.loaded:
        clang.cindex.Config.set_library_path(config_json["libclang_path"])
    g_index = Index.create()
    g_clang_default_headers = utils.clang_default_include_path()
    # local repo folder
    if project not in config_json["local_repo_path"]:
        print("  - Error: cannot find local repo folder for project '%s'" % project)
        sys.exit(1)
    g_repo_local_path = config_json["local_repo_path"][project]
    if not os.path.exists(g_repo_local_path):
        print("  - Error: repo not found @ %s" % g_repo_local_path)
        sys.exit(1)
    # temp output folder: cached results
    if arg_tmp_output_folder == "":
        time_stamp_str = datetime.now().strftime("%Y%m%d_%H%M")
        g_tmp_output_folder = os.path.join("tmp_outputs", "%s_%s" % (project, time_stamp_str))
    else:
        g_tmp_output_folder = arg_tmp_output_folder
    if not os.path.exists(g_tmp_output_folder):
        os.makedirs(g_tmp_output_folder)
    # g_work_folder = "/dev/shm/zhengyu"
    if os.path.exists(g_work_folder):
        shutil.rmtree(g_work_folder)
    os.makedirs(g_work_folder)
    print("  - remove and create work folder '%s'" % g_work_folder, flush = True)



def get_relative_path(full_path, last_sec):
    cnt = 0
    s_idx = len(full_path)
    while s_idx > 0 and cnt < last_sec:
        s_idx = full_path.rfind("/", 0, s_idx - 1)
        cnt += 1
    return full_path[s_idx + 1 : ]




def process_bug_details(item):
    sample_url = item["sample_url"]
    if sample_url.find("/blob/") < 1:
        print("* Warning: cannot extract before version hash because no 'blob' found in sample url", flush=True)
    s_idx = sample_url.find("/blob/") + len("/blob/")
    e_idx = sample_url.find("/", s_idx + 1)
    report = item["sample_bug"]["report"]
    if "sha1sum_no_loc" in item:
        sha1sum_id = item["sha1sum_no_loc"]
    elif "sha1sum" in item:
        sha1sum_id = item["sha1sum"]
    else:
        print("* Error: no 'sha1sum_no_loc' or 'sha1sum' found in bug details. exit", flush=True)
        sys.exit(1)
    bug_txt_encoded = item["sample_gzipped_bug_txt_file_content"]
    if bug_txt_encoded.find("\n") > 0:
        bug_txt_encoded = utils.convert_2_b64encode(item["sample_gzipped_bug_txt_file_content"])
    res = {
        "sha1sum": sha1sum_id,
        "bug_type": item["bug_type"],
        "versions": {
            "before": sample_url[s_idx: e_idx],
            "after": item["sample_commit"]
        },
        "bug_info": {
            "qualifier": report["qualifier"],
            "file": report["file"],
            "procedure": report["procedure"],
            "line": report["line"],
            "column": report["column"]
        },
        "trace": report["bug_trace"],
        "zipped_bug_report": bug_txt_encoded
    }
    return res



def get_version_pair(item):
    sample_url = item["sample_url"]
    if sample_url.find("/blob/") < 1:
        print("* Warning: cannot extract before version hash because no 'blob' found in sample url", flush=True)
    s_idx = sample_url.find("/blob/") + len("/blob/")
    e_idx = sample_url.find("/", s_idx + 1)
    before_ver = sample_url[s_idx: e_idx]
    after_ver = item["sample_commit"]
    return (before_ver, after_ver)



def load_issues_by_version(msg_prefix, pickle_file, issues, before_hash, after_hash):
    if not os.path.exists(pickle_file):
        print("|- Error: cannot find file " + pickle_file, flush=True)
    cnt = 0
    with gzip.open(pickle_file, mode = 'rb') as fp:
        while True:
            try:
                item = pickle.load(fp)
                bug = process_bug_details(item)
                before_version = bug["versions"]["before"]
                after_version = bug["versions"]["after"]
                if before_version == before_hash:
                    if after_version == after_hash:
                        issues.append(bug)
                        cnt += 1
            except EOFError:
                break
    print("  - %s %d samples loaded from '%s'" % (msg_prefix, cnt, get_relative_path(pickle_file, 2)), flush=True)



def load_pairwise_index(pickle_file, pairwise_index):
    if not os.path.exists(pickle_file):
        print("|- Error: cannot find file " + pickle_file, flush=True)
    cnt = 0
    with gzip.open(pickle_file, mode = 'rb') as fp:
        while True:
            try:
                item = pickle.load(fp)
                (before_version, after_version) = get_version_pair(item)
                if before_version not in pairwise_index:
                    pairwise_index[before_version] = {}
                if after_version not in pairwise_index[before_version]:
                    pairwise_index[before_version][after_version] = 0
                pairwise_index[before_version][after_version] += 1
                cnt += 1
            except EOFError:
                break
    print("  - %d issues found in '%s'" % (cnt, get_relative_path(pickle_file, 2)), flush=True)



def gen_worklist_from_positive_bugs():
    issue_index = {}
    print("\n* generate work list", flush=True)
    src_path = os.path.join(g_labeler_output, "label_1_bug_details.pickle.gz")
    load_pairwise_index(src_path, issue_index)
    src_path = os.path.join(g_labeler_output, "label_2_bug_details.pickle.gz")
    load_pairwise_index(src_path, issue_index)
    # stats
    cnt = 0
    pair_total = 0
    for before_version in issue_index:
        pair_total += len(issue_index[before_version].keys())
        for after_version in issue_index[before_version]:
            cnt += issue_index[before_version][after_version]
    print("  - %d version pairs, %d issues loaded" % (pair_total, cnt), flush = True)
    return (pair_total, issue_index)



def gen_worklist_from_negative_bugs():
    issue_index = {}
    print("\n* generate work list", flush=True)
    src_path = os.path.join(g_labeler_output, "label_0_bug_details.pickle.gz")
    load_pairwise_index(src_path, issue_index)
    # stats
    cnt = 0
    pair_total = 0
    for before_version in issue_index:
        pair_total += len(issue_index[before_version].keys())
        for after_version in issue_index[before_version]:
            cnt += issue_index[before_version][after_version]
    print("  - %d version pairs, %d issues loaded" % (pair_total, cnt), flush = True)
    return (pair_total, issue_index)



def func_map_key(src_file, start_line, start_column, end_line, end_column):
    return "%s@%d:%d-%d:%d" % (src_file, start_line, start_column, end_line, end_column)



def extract_func_from_src(local_repo_path, src_file, start_line, start_column, end_line, end_column):
    src_file = os.path.join(local_repo_path, src_file)
    if not os.path.exists(src_file):
        print("Error: cannot find source file: %s" % src_file, flush=True)
        return None
    if start_line > end_line:
        print("Error: function range start line (%d) is larger than the end line (%d)" % (start_line, end_line), flush=True)
        return None
    res = ""
    line_cnt = 0
    with open(src_file, encoding="iso-8859-1") as f:
        lines = f.readlines()
        for l in lines:
            line_cnt += 1
            if line_cnt == start_line:
                if line_cnt < end_line:
                    res += l[start_column - 1 : ]
                else:
                    res += l[start_column - 1 : end_column - 1]
            elif start_line < line_cnt and line_cnt < end_line:
                res += l
            elif end_line == line_cnt:
                res += l[ : end_column - 1]
    return res




def dump_build_args(local_repo_path, build_args_str):
    res = []
    args = build_args_str.split(" ")
    for arg in args:
        arg = arg.strip()
        if arg.startswith("-I"):
            if arg.find("-I" + local_repo_path) != -1:
                header_path = arg.replace(local_repo_path, "<$repo$>")
                res.append(header_path)
            elif arg.find("-I/home/zhengyu/local") != -1:
                header_path = arg.replace("/home/zhengyu/local", "<$sys$>")
                res.append(header_path)
            else:
                res.append(arg)
        else:
            res.append(arg)
    return " ".join(res)



"""
return value: (func_range, dumped_build_args, line_in_ast, parse_exception)
"""
def compute_func_range_by_line(local_repo_path, src_file, line, build_args, parse_cache, status):
    src_file = os.path.join(local_repo_path, src_file)
    dumped_build_args = ""
    if not os.path.exists(src_file):
        status["msg"].append("  - Error: cannot find src file: %s" % src_file)
        return (None, dumped_build_args, None, False)
    cursor_kind = clang.cindex.CursorKind
    if src_file in parse_cache:
        tu = parse_cache[src_file]["tu"]
        dumped_build_args = parse_cache[src_file]["dumped_build_args"]
    else:
        status["msg"].append("      parse: " + src_file)
        if build_args is None:
            if (not src_file.endswith(".h")):
                status["msg"].append("      |- [parsing_warning] build args not found")
            build_args = ""
        clang_args = []
        clang_args += g_clang_default_headers
        clang_args += build_args.split(" ")
        dumped_build_args = dump_build_args(local_repo_path, build_args)
        if build_args.strip() == "":
            status["msg"].append("      |-- [arg] NONE")
        else:
            for l in build_args.split(" "):
                if l.startswith("-I"):
                    status["msg"].append("      |-- [arg] %s" % l)
        try:
            tu = g_index.parse(src_file, args = clang_args, options = 0x01 | 0x200)
        except TranslationUnitLoadError:
            print("* TranslationUnitLoadError: " + src_file)
            return (None, dumped_build_args, None, True)
        parse_cache[src_file] = {
            "tu": tu,
            "dumped_build_args": dumped_build_args
        }
        if not src_file.endswith(".h"):
            for diagnostic in tu.diagnostics:
                msg = diagnostic.format().strip()
                if msg.find(" error:") > 0:
                    status["msg"].append("      |-- [parsing_error] " + msg)
    line_in_ast = False
    for c in tu.cursor.get_children():
        if c.location.file is None:
            continue
        if c.location.file.name != src_file:
            continue
        if c.kind == cursor_kind.CXX_METHOD or c.kind == cursor_kind.FUNCTION_DECL:
            if line >= c.extent.start.line and line <= c.extent.end.line:
                res = {
                    "func_name":    c.spelling,
                    "start_line":   c.extent.start.line,
                    "start_column": c.extent.start.column,
                    "end_line":     c.extent.end.line,
                    "end_column":   c.extent.end.column,
                    "is_func_definition": is_func_defintiion(c) # True if function body presents
                }
                line_in_ast = True
                return (res, dumped_build_args, line_in_ast, False)
    # when there are parsing errors and line was not found in AST, we don't know if it's indeed not in AST
    # return None for such cases
    if len(tu.diagnostics) > 0 and (not line_in_ast):
        line_in_ast = None
    return (None, dumped_build_args, line_in_ast, False)




def is_func_defintiion(func_cursor):
    for child in func_cursor.get_children():
        if child.kind == clang.cindex.CursorKind.COMPOUND_STMT:
            return True
    return False



def compute_func_range_by_func_name(local_repo_path, src_file, func_name, has_func_body, before_func_body, build_args, parse_cache, func_body_search_cache, status):
    relative_path = src_file
    src_file = os.path.join(local_repo_path, src_file)
    if not os.path.exists(src_file):
        status["msg"].append("  - Error: cannot find src file: %s" % src_file)
        return (None, "")
    cursor_kind = clang.cindex.CursorKind
    dumped_build_args = ""
    if src_file in parse_cache:
        tu = parse_cache[src_file]["tu"]
        dumped_build_args = parse_cache[src_file]["dumped_build_args"]
    else:
        status["msg"].append("      parse: " + relative_path)
        if build_args is None:
            if (not src_file.endswith(".h")):
                status["msg"].append("      |- [parsing_warning] build args not found")
            build_args = ""
        clang_args = []
        clang_args += g_clang_default_headers
        clang_args += build_args.split(" ")
        dumped_build_args = dump_build_args(local_repo_path, build_args)
        if build_args.strip() == "":
            status["msg"].append("      |-- [arg] NONE")
        else:
            for l in build_args.split(" "):
                if l.startswith("-I"):
                    status["msg"].append("      |-- [arg] %s" % l)
        
        try:
            tu = g_index.parse(src_file, args = clang_args, options = 0x01 | 0x200)
        except TranslationUnitLoadError:
            print("* TranslationUnitLoadError: " + src_file)
            return (None, dumped_build_args)
        
        parse_cache[src_file] = {
            "tu": tu,
            "dumped_build_args": dumped_build_args
        }
        if not src_file.endswith(".h"):
            for diagnostic in tu.diagnostics:
                msg = diagnostic.format().strip()
                if msg.find(" error:") > 0:
                    status["msg"].append("      |-- [parsing error] " + msg)
    for c in tu.cursor.get_children():
        if c.location.file is None:
            continue
        if c.location.file.name != src_file:
            continue
        if c.kind == cursor_kind.CXX_METHOD or c.kind == cursor_kind.FUNCTION_DECL:
            if (c.spelling == func_name) and (is_func_defintiion(c) == has_func_body):
                res = {
                    "func_name":    c.spelling,
                    "start_line":   c.extent.start.line,
                    "start_column": c.extent.start.column,
                    "end_line":     c.extent.end.line,
                    "end_column":   c.extent.end.column,
                    "is_func_definition": has_func_body
                }
                return (res, dumped_build_args)
    # --------------------------------------------------------------------------------
    # if we are here, matching by function name failed
    # this is possible when function name is a Macro.
    # for example,
    #   line 52 @ https://github.com/libav/libav/commit/19a0729b4cfacfd90b8ee84ab0c093ff7e397e65
    #   static void FUNCC(draw_edges)(uint8_t *_buf, int _wrap, int width, int height, int w, int sides)
    #     [before] #define FUNCC(a) a ## _c
    #     [after ] #define FUNCC(a) a ## _8_c
    # given we match by function name when the function is not changed, we may find the corresponding function if search by function body
    # --------------------------------------------------------------------------------
    # check cache first
    if (src_file in func_body_search_cache) and (before_func_body in func_body_search_cache[src_file]):
        cached_res = func_body_search_cache[src_file][before_func_body]
        return (cached_res, dumped_build_args)
    else:
        with open(src_file, "r", encoding="utf-8", errors="ignore") as fp:
            content = fp.read()
        s_idx = content.find(before_func_body)
        if s_idx != -1:
            prefix_content = content[0:s_idx]
            line_num = prefix_content.count("\n") + 1
            status["msg"].append("      - func_body found. start_line: %d" % line_num)
            for c in tu.cursor.get_children():
                if c.location.file is None:
                    continue
                if c.location.file.name != src_file:
                    continue
                if c.kind == cursor_kind.CXX_METHOD or c.kind == cursor_kind.FUNCTION_DECL:
                    if line_num >= c.extent.start.line and line_num <= c.extent.end.line:
                        res = {
                            "func_name":    c.spelling,
                            "start_line":   c.extent.start.line,
                            "start_column": c.extent.start.column,
                            "end_line":     c.extent.end.line,
                            "end_column":   c.extent.end.column,
                            "is_func_definition": has_func_body
                        }
                        # update cache
                        if src_file not in func_body_search_cache:
                            func_body_search_cache[src_file] = {}
                        func_body_search_cache[src_file][before_func_body] = res
                        return (res, dumped_build_args)
    # no function name or body matches, return None
    return (None, dumped_build_args)




def func_touched_by_commit(commit_info, src_file, func_start, func_end, version):
    version = version.lower().strip()
    matched_file_found = False
    if version not in {"before", "after"}:
        print("* Error: `version` should be 'before' or 'after'", flush=True)
        sys.exit(1)
    for mod in commit_info:
        src_changed = mod[version]
        if src_changed == src_file:
            matched_file_found = True
            for l in mod["changes"]:
                parts = l.strip().split("^^")
                pos = parts[0].strip()
                if version == "after":
                    pos = parts[1].strip()
                items = pos.split(",")
                mod_start = int(items[0])
                mod_range = int(items[1])
                mod_end = mod_start + mod_range
                if mod_range > 0:
                    mod_end -= 1
                if (mod_range > 0 and (func_end < mod_start or mod_end < func_start)) or (mod_range == 0 and (func_end <= mod_start or mod_end <= func_start)):
                    continue
                else:
                    dbg_info = {
                        "src_found_in_commit": matched_file_found,
                        "func_start": func_start,
                        "func_end": func_end,
                        "mod_start": mod_start,
                        "mod_end": mod_end,
                        "mod_range": mod_range
                    }
                    return (True, dbg_info)
    dbg_info = {
        "src_found_in_commit": matched_file_found,
        "func_start": func_start,
        "func_end": func_end
    }
    return (False, dbg_info)




def log_interesting_case(dest_map, bug_type, issue):
    if not bug_type in dest_map:
        dest_map[bug_type] = []
    dest_map[bug_type].append(issue)




def adjust_bug_location(project, issue, status):
    bug_type = issue["bug_type"]
    search_needed = True
    res = None
    match_idx = -1
    if bug_type == "NULLPTR_DEREFERENCE" or bug_type == "USE_AFTER_FREE":
        bug_qualifier = "invalid access occurs here"
    elif bug_type == "DEAD_STORE":
        bug_qualifier = "Write of unused value"
    elif bug_type == "UNINITIALIZED_VALUE" or bug_type == "NULL_DEREFERENCE" or bug_type == "PULSE_MEMORY_LEAK":
        search_needed = False
    else:
        bug_qualifier = issue["bug_info"]["qualifier"].strip()
        if bug_qualifier.endswith("."):
            bug_qualifier = bug_qualifier[ :-1] # remove '.' at the end
        bug_qualifier = bug_qualifier.replace("`", "")
    if search_needed:
        idx = 0
        for step in issue["trace"]:
            description = step["description"].strip().replace("`", "")
            if description.endswith(bug_qualifier) > 0:
                res = {
                    "file": step["filename"],
                    "line": step["line_number"],
                    "column": step["column_number"],
                    "url": g_repo_url + "/blob/" + issue["versions"]["before"] + "/" + step["filename"] + "/#L%d" % step["line_number"]
                }
                match_idx = idx
            idx += 1
    bug_loc_file = issue["bug_info"]["file"]
    bug_loc_line = issue["bug_info"]["line"]
    bug_loc_column = issue["bug_info"]["column"]
    # if the buggy loc is the same as the loc specified by infer; no adjustment is needed 
    if (res is not None) and bug_loc_file == res["file"] and bug_loc_line == res["line"] and bug_loc_column == res["column"]:
        res = None
    # update adjusted bug loc counters
    if res is not None:
        if bug_type not in status["adjusted_bug_loc_stats"]:
            status["adjusted_bug_loc_stats"][bug_type] = 0
        status["adjusted_bug_loc_stats"][bug_type] += 1
    if res is None:
        match_idx = len(issue["trace"]) - 1
        last_step = issue["trace"][match_idx]
        if last_step["filename"] != bug_loc_file or last_step["line_number"] != bug_loc_line or last_step["column_number"] != bug_loc_column:
            log_interesting_case(status["bug_loc_trace_mismatches"], bug_type, issue)
            match_idx = -1
    return (res, match_idx)




def run_cmd_in_repo(cmd_str, local_repo_path, status, my_env=None):
    status["msg"].append( "  - %s" % cmd_str )
    proc = subprocess.run(shlex.split(cmd_str), 
                        cwd = local_repo_path, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        env=my_env)
    return (proc.stdout, proc.stderr)




def process_diff_range(pos):
    pos = pos.strip()
    start_line = -1
    line_range = 1
    if pos.find(",") > 0:
        parts = pos.split(",")
        start_line = int(parts[0].strip())
        line_range = int(parts[1].strip())
    else:
        start_line = int(pos)
        line_range = 1
    return (start_line, line_range)




def process_diff_block(block):
    s_idx = 0
    e_idx = block.find("\n", s_idx)
    diff_args = block[s_idx : e_idx].split(" ")
    file_before = diff_args[0].strip()[2:].strip() 
    file_after  = diff_args[1].strip()[2:].strip()
    res = {
        "before": file_before,
        "after": file_after,
        "changes": []
    }
    s_idx = block.find("\n@@")
    while s_idx > 0:
        s_idx += 3
        e_idx = block.find("@@", s_idx)
        line_diffs = block[s_idx : e_idx].strip().replace("-", "").replace("+", "")
        line_diff_parts = line_diffs.split(" ")
        line_diff_before = line_diff_parts[0]
        line_diff_after = line_diff_parts[1]        
        (line_before, range_before) = process_diff_range(line_diff_before)
        (line_after, range_after) = process_diff_range(line_diff_after)
        res["changes"].append( "%d,%d^^%d,%d" % (line_before, range_before, line_after, range_after) )
        s_idx = block.find("\n@@", e_idx + 2)
    return res

"""
format:
[
    {
        "before": "file_name",
        "after": "file_name",
        "changes": [
            "line_before,range^^line_after,range",
            ...
        ]
    }
]
"""
def get_git_commit_info(local_repo_path, before_version_hash, after_version_hash, status):
    # get changed lines
    line_diffs = []
    cmd = "git diff --unified=0 %s %s" % (before_version_hash, after_version_hash)
    (my_std_out, _) = run_cmd_in_repo(cmd, local_repo_path, status)
    raw_data = my_std_out.decode('iso-8859-1')
    parts = raw_data.split("diff --git ")
    idx = 1
    while idx < len(parts):
        block_info = process_diff_block(parts[idx])
        line_diffs.append(block_info)
        idx += 1
    return line_diffs


"""
range_str: format "%s@%d:%d-%d:%d"
"""
def get_func_lines(func_key):
    pieces = func_key.split("@")
    locs = pieces[1].split("-")
    items = locs[0].split(":")
    start_line = int(items[0])
    items = locs[1].split(":")
    end_line = int(items[0])
    return (start_line, end_line)



def get_loc_line(loc):
    loc = loc.strip()
    if loc.find(":") == -1:
        print("  - ERROR: unexpected loc '%s'" % loc, flush=True)
    parts = loc.split(":")
    return int(parts[0])


def get_changed_lines_info(changed_area):
    changed_area = changed_area.strip()
    ranges = changed_area.split("^^")
    # before
    pos = ranges[0].strip()
    parts = pos.split(",")
    start_line_before = int(parts[0])
    line_cnt_before = int(parts[1])
    end_line_before = start_line_before + line_cnt_before
    if line_cnt_before > 0:
        end_line_before -= 1
    # after
    pos = ranges[1].strip()
    parts = pos.split(",")
    start_line_after = int(parts[0])
    line_cnt_after = int(parts[1])
    end_line_after = start_line_after + line_cnt_after
    if line_cnt_after > 0:
        end_line_after -= 1
    return {
        "before": {
            "start": start_line_before,
            "end": end_line_before,
            "cnt": line_cnt_before
        },
        "after": {
            "start": start_line_after,
            "end": end_line_after,
            "cnt": line_cnt_after
        }
    }



def get_renamed_src(src_file, commit_info):
    for changed_item in commit_info:
        if (changed_item["before"] == src_file) and (changed_item["before"].strip() != changed_item["after"].strip()):
            return (True, changed_item["after"].strip())
    return (False, src_file)
                


def get_after_fix_line(src_file, before_line, func_key, commit_info, status):
    file_removed = False
    func_removed = False
    (func_start, func_end) = get_func_lines(func_key)
    # if the file/function removed by the commit
    for changed_item in commit_info:
        if changed_item["before"] == src_file: 
            for block in changed_item["changes"]:
                line_info = get_changed_lines_info(block)
                if line_info["before"]["start"] <= func_start and func_end <= line_info["before"]["end"]:
                    if line_info["after"]["start"] == 0:
                        file_removed = True
                    if line_info["after"]["cnt"] == 0:
                        func_removed = True
    if file_removed or func_removed:
        return (0, func_removed, file_removed, -1)
    # locate the file in commit changes
    changes_in_file = []
    for changed_item in commit_info:
        if changed_item["before"] == src_file: 
            changes_in_file = changed_item["changes"]
    # collect changed blocks that overlap with the range of the function
    overlap_blocks = []
    idx = 0
    while idx < len(changes_in_file):
        block = changes_in_file[idx]
        line_info = get_changed_lines_info(block)
        if line_info["before"]["cnt"] > 0:
            if not (func_start > line_info["before"]["end"] or func_end < line_info["before"]["start"]):
                overlap_blocks.append(line_info)
        else:
            if not (func_start >= line_info["before"]["end"] or func_end <= line_info["before"]["start"]):
                overlap_blocks.append(line_info)
        idx += 1

    after_line = -1
    overlap_block_cnt = len(overlap_blocks)
    if overlap_block_cnt == 0:
       after_line = -1
    elif overlap_block_cnt == 1:
        block = overlap_blocks[0]
        after_line = -1
        if block["before"]["start"] < func_start and func_end < block["before"]["end"]:
            status["msg"].append("  - WARNING: change block covers the function")
            after_line = (block["after"]["start"] + block["after"]["end"]) / 2
        elif block["before"]["start"] <= func_start:
            after_line = block["after"]["end"]
        else:
            after_line = block["after"]["start"]
    elif overlap_block_cnt == 2:
        block = overlap_blocks[1]
        after_line = block["after"]["start"]
    else:
        block = overlap_blocks[2]
        after_line = block["after"]["start"]
    return (after_line, func_removed, file_removed, overlap_block_cnt)



def get_git_version(local_repo_path, status):
    (raw_output, _) = run_cmd_in_repo("git rev-parse HEAD", local_repo_path, status)
    return raw_output.decode('iso-8859-1').strip()
        

"""
some project has an odd way to compile the `.c` file. for example, in libav
  @ libavcodec/ac3enc_float.c
    #define CONFIG_AC3ENC_FLOAT 1
    #include "ac3enc.c"
    #include "kbdwin.h"
we have build argument for `libavcodec/ac3enc_float.c` but not `libavcodec/ac3enc.c`
"""
def get_parent_build_arg(local_repo_path, build_args_map, src_full_path, status):
    status["msg"].append("  - NO build args for '%s'. check parent c/cpp files." % src_full_path)
    parent_src_files = []
    for root, _, files in os.walk(local_repo_path):
        for name in files:
            if name.endswith((".c", ".cpp")):
                parent_src_files.append(os.path.join(root, name))
    status["msg"].append("    - %d c/cpp files found" % len(parent_src_files))
    candidates = []
    for parent_src in parent_src_files:
        # check if the parent src file include the target c/cpp file
        if not os.path.exists(parent_src):
            continue
        with open(parent_src, "r", encoding="utf-8", errors="ignore") as fp:
            lines = fp.readlines()
            for l in lines:
                l = l.strip()
                if not l.startswith("#include"):
                    continue
                s_idx = l.find("\"") + 1
                if s_idx == -1:
                    continue
                e_idx = l.find("\"", s_idx)
                included_src = l[s_idx:e_idx]
                if src_full_path.endswith(included_src):
                    if parent_src in build_args_map:
                        candidates.append(parent_src)
                    break
    status["msg"].append("    - %d parent c/cpp files with build args:" % len(candidates))
    cnt = 0
    for parent_src in candidates:
        cnt += 1
        status["msg"].append("      |-- parent: " +  parent_src)
        if cnt == 3:
            status["msg"].append("      |-- ... ")
            break
    if len(candidates) > 0:
        parent_src = candidates[0]
        status["msg"].append("    - use build arg for parent '%s'" % parent_src)
        build_args_map[src_full_path] = build_args_map[parent_src]
        return build_args_map[parent_src]
    else:
        build_args_map[src_full_path] = ""
        return ""



def process_before_fix(project, local_repo_path, pair_cnt, issue, label, commit_info, build_args, parse_cache, status):
    sha1sum = issue["sha1sum"]
    id = "%s_%s_%d" % (project, sha1sum, label)
    # save messages to status["msg"]
    status["msg"].append("")
    status["msg"].append("* prcess issue: " + id)
    commit_url = g_repo_url + "/commit/" + issue["versions"]["after"]
    status["msg"].append("  pair_cnt: %d, commit_url: %s" % (pair_cnt, commit_url))
    status["msg"].append("  -----------------------------------------")
    # adjusted bug locations:
    # for some error types, infer provides incorrect bug location.
    # by comparing the bug description and the step qualifier, identify the correct bug location
    # if infer already returns correct bug location, adjusted location is None
    (adjusted_bug_loc, bug_loc_adjusted_idx) = adjust_bug_location(project, issue, status)
    res = {
        "id": id,
        "label": label,
        "label_source": "auto_labeler",
        "bug_type": issue["bug_type"],
        "project": project,
        "bug_info": {
            "qualifier": issue["bug_info"]["qualifier"],
            "file": issue["bug_info"]["file"],
            "procedure": issue["bug_info"]["procedure"],
            "line": issue["bug_info"]["line"],
            "column": issue["bug_info"]["column"],
            "url": g_repo_url + "/blob/" + issue["versions"]["before"] + "/" + issue["bug_info"]["file"] + "/#L%d" % issue["bug_info"]["line"],
        },
        "adjusted_bug_loc": adjusted_bug_loc,
        "bug_loc_trace_index": bug_loc_adjusted_idx,
        "versions": {
            "before": issue["versions"]["before"], 
            "after": issue["versions"]["after"],
        },
        "sample_type": "before_fix",
        "trace": [],
        "functions": {},
        "commit": {
            "url": commit_url,
            "changes": commit_info
        },
        "compiler_args": {},
        "zipped_bug_report": issue["zipped_bug_report"]
    }
    step_idx = 0
    touched_func_map = {}
    for step in issue["trace"]:
        src = step["filename"]
        line = step["line_number"]
        column = step["column_number"]
        step_info = {
            "idx": step_idx,
            "level": step["level"],
            "description": step["description"],
            "func_removed": None,
            "file_removed": None,
            "file": src,
            "loc": "%d:%d" % (line, column),
            "func_name": None,
            "func_key": None,
            "is_func_definition": None,
            "url": g_repo_url + "/blob/" + issue["versions"]["before"] + "/" + src + "/#L%d" % line
        }
        # get compiler argument
        src_full_path = os.path.abspath(os.path.join(local_repo_path, src))
        if os.path.islink(src_full_path):
            src_full_path = os.path.abspath( os.path.realpath(src_full_path) )
        build_arg_str = None
        if src_full_path in build_args:
            build_arg_str = build_args[src_full_path]
        else:
            build_arg_str = get_parent_build_arg(local_repo_path, build_args, src_full_path, status)
        if build_arg_str == "":
            # default: include the root folder of the project
            status["msg"].append("    - NO_BUILD_ARGS for " + src_full_path + ". use default values.")
            build_arg_str = "-I" + local_repo_path


        (func_range, dumped_compiler_args, _, _) = compute_func_range_by_line(local_repo_path, src, line, build_arg_str, parse_cache, status)
        if (src not in res["compiler_args"]) or res["compiler_args"][src] == "":
            res["compiler_args"][src] = dumped_compiler_args
        if func_range is not None:
            s_line = func_range["start_line"]
            s_column = func_range["start_column"]
            e_line = func_range["end_line"]
            e_column = func_range["end_column"]
            func_key = func_map_key(src, s_line, s_column, e_line, e_column)
            step_info["func_key"] = func_key
            step_info["func_name"] = func_range["func_name"]
            step_info["is_func_definition"] = func_range["is_func_definition"]
            if not func_key in res["functions"]:
                code = extract_func_from_src(local_repo_path, src, s_line, s_column, e_line, e_column)
                (touched_by_commit, touched_dbg_info) = func_touched_by_commit(commit_info, src, s_line, e_line, "before")
                if not func_key in touched_func_map:
                    touched_func_map[func_key] = touched_by_commit
                res["functions"][func_key] = {
                    "file": src,
                    "loc": "%d:%d-%d:%d" % (s_line, s_column, e_line, e_column),
                    "name": func_range["func_name"],
                    "touched_by_commit": touched_by_commit,
                    "code": code
                }
                msg =  "  - [step %d, L%d, %s] %s" % (step_idx, line, ("Y" if touched_by_commit else "N"), func_key)
                msg += " | file %s commit diff" % ("in" if touched_dbg_info["src_found_in_commit"] else "NOT in")
                msg += ", func %d-%d" % (touched_dbg_info["func_start"], touched_dbg_info["func_end"] )
                if "mod_start" in touched_dbg_info:
                    msg += ", mod %d-%d(%d)" % (touched_dbg_info["mod_start"], touched_dbg_info["mod_end"], touched_dbg_info["mod_range"])
                status["msg"].append(msg)
            else:
                msg =  "  - [step %d, L%d, %s] %s | func info processed" % (step_idx, line, ("Y" if touched_func_map[func_key] else "N"), func_key)
                status["msg"].append(msg)
        else:
            status["msg"].append("  - [step %d, L%d] NONE" % (step_idx, line))
        res["trace"].append(step_info)
        step_idx += 1
    return res




def process_after_fix(local_repo_path, pair_cnt, before_fix_example, commit_info, build_args_after, parse_cache, func_body_search_cache, status):
    bfs_id = before_fix_example["id"]
    items = bfs_id.split("_")
    project = items[0]
    sha1sum = items[1]
    id = "%s_%s_0" % (project, sha1sum)
    
    commit_url = g_repo_url + "/commit/" + before_fix_example["versions"]["after"]
    status["msg"].append("")
    status["msg"].append("* prcess issue: " + id)
    status["msg"].append("  pair_cnt: %d, commit_url: %s" % (pair_cnt, commit_url))
    status["msg"].append("  -----------------------------------------")

    res = {
        "id": id,
        "label": 0,
        "label_source": "after_fix_extractor",
        "bug_type": before_fix_example["bug_type"],
        "project": project,
        "bug_info": None,
        "adjusted_bug_loc": None,
        "bug_loc_trace_index": None,
        "version_pair": {
            "before": before_fix_example["versions"]["before"], 
            "after": before_fix_example["versions"]["after"]
        },
        "sample_type": "after_fix",
        "trace": [],
        "functions": {},
        "commit": {
            "url": commit_url,
            "changes": commit_info
        },
        "compiler_args": {},
        "zipped_bug_report": None
    }
    step_idx = 0
    touched_func_map = {}
    for step in before_fix_example["trace"]:
        src = step["file"]
        if step["func_key"] is None:
            step_info = {
                "idx": step_idx,
                "level": step["level"],
                "description": None,
                "func_removed": None,
                "file_removed": None,
                "file": src,
                "loc": None, 
                "func_name": None,
                "func_key": None,
                "is_func_definition": None,
                "url": None
            }
            status["msg"].append("  - before-fix func_key is NONE")
        else:
            step_line_before = get_loc_line(step["loc"])
            (line_after, func_removed, file_removed, overlap_change_block_cnt) = get_after_fix_line(src, step_line_before, step["func_key"], commit_info, status)
            step_info = {
                "idx": step_idx,
                "level": step["level"],
                "description": None,
                "func_removed": func_removed,
                "file_removed": file_removed,
                "file": src,
                "loc": None, 
                "func_name": None,
                "func_key": None,
                "is_func_definition": None,
                "url": None
            } 
            if not file_removed:
                if not func_removed:
                    # if the src is renamed, get the renamed name
                    (is_renamed, renamed_src) = get_renamed_src(src, commit_info)
                    if is_renamed:
                        status["msg"].append("      renamed: %s --> %s" % (src, renamed_src))
                        src = renamed_src
                        step_info["file"] = renamed_src
                    # get compiler arguments
                    src_full_path = os.path.join(local_repo_path, src)
                    if os.path.islink(src_full_path):
                        src_full_path = os.path.abspath( os.path.realpath(src_full_path) )

                    build_arg_str = None
                    if src_full_path in build_args_after:
                        build_arg_str = build_args_after[src_full_path]
                    else:
                        build_arg_str = get_parent_build_arg(local_repo_path, build_args_after, src_full_path, status)
                    if build_arg_str == "":
                        # default: include the root folder of the project
                        status["msg"].append("    - NO_BUILD_ARGS for " + src_full_path + ". use default values.")
                        build_arg_str = "-I" + local_repo_path

                    dumped_compiler_args = ""
                    before_func_body = before_fix_example["functions"][step["func_key"]]["code"]
                    if line_after == -1:
                        (func_range, dumped_compiler_args) = compute_func_range_by_func_name(local_repo_path, src, step["func_name"], step["is_func_definition"], before_func_body, build_arg_str, parse_cache, func_body_search_cache, status)
                    else:
                        (func_range, dumped_compiler_args, line_in_ast, parse_exception) = compute_func_range_by_line(local_repo_path, src, line_after, build_arg_str, parse_cache, status)
                        # functions can be excluded from the AST by inserting "#ifdef 0" before the function
                        # e.g. 
                        #   https://github.com/libav/libav/commit/ac4b32df71bd932838043a4838b86d11e169707f
                        #   [0, BEF_L210, AFT_L342, OV#1] libavcodec/vp8dsp.c: NONE
                        if line_in_ast is not None:
                            # if there are parsing errors and line was not found in AST, line_in_ast will be None
                            if (not step_info["func_removed"]) and (not line_in_ast):
                                step_info["func_removed"] = True
                        # if cannot find any function using after-fix line number, default to search by name
                        # an example: https://github.com/openssl/openssl/commit/5c98b2caf5ce545fbf77611431c7084979da8177#diff-cd83b656938741d60d872e962b4a5b4f
                        #             before-fx: Line 165 @ crypto/bn/bn_ctx.c
                        if (parse_exception == False) and (func_range is None):
                            (func_range, dumped_compiler_args) = compute_func_range_by_func_name(local_repo_path, src, step["func_name"], step["is_func_definition"], before_func_body, build_arg_str, parse_cache, func_body_search_cache, status)
                    if (src not in res["compiler_args"]) or res["compiler_args"][src] == "":
                        res["compiler_args"][src] = dumped_compiler_args
                    if func_range is not None:
                        s_line = func_range["start_line"]
                        s_column = func_range["start_column"]
                        e_line = func_range["end_line"]
                        e_column = func_range["end_column"]
                        func_key = func_map_key(src, s_line, s_column, e_line, e_column)
                        step_info["func_key"] = func_key
                        step_info["func_name"] = func_range["func_name"]
                        step_info["is_func_definition"] = func_range["is_func_definition"]
                        step_info["loc"] = "%d:%d-%d:%d" % (s_line, s_column, e_line, e_column)
                        step_info["url"] = g_repo_url + "/blob/" + before_fix_example["versions"]["after"] + "/" + src + "/#L%d-L%d" % (s_line, e_line)
                        if not func_key in res["functions"]:
                            code = extract_func_from_src(local_repo_path, src, s_line, s_column, e_line, e_column)
                            (touched_by_commit, touched_dbg_info) = func_touched_by_commit(commit_info, src, s_line, e_line, "after")
                            if not func_key in touched_func_map:
                                touched_func_map[func_key] = touched_by_commit
                            res["functions"][func_key] = {
                                "file": src,
                                "loc": "%d:%d-%d:%d" % (s_line, s_column, e_line, e_column),
                                "name": func_range["func_name"],
                                "touched_by_commit": touched_by_commit,
                                "code": code
                            }
                            msg =  "  - [step %d, BEF_L%d, AFT_L%d, OVC#%d, %s] %s" % (step_idx, step_line_before, line_after, overlap_change_block_cnt, ("Y" if touched_by_commit else "N"), func_key)
                            msg += " | file %s commit diff" % ("in" if touched_dbg_info["src_found_in_commit"] else "NOT in")
                            msg += ", func %d-%d" % (touched_dbg_info["func_start"], touched_dbg_info["func_end"] )
                            if "mod_start" in touched_dbg_info:
                                msg += ", mod %d-%d(%d)" % (touched_dbg_info["mod_start"], touched_dbg_info["mod_end"], touched_dbg_info["mod_range"])
                            status["msg"].append(msg)
                        else:
                            msg =  "  - [step %d, BEF_L%d, AFT_L%d, OVC#%d, %s] %s | func info processed" % (step_idx, step_line_before, line_after, overlap_change_block_cnt, ("Y" if touched_func_map[func_key] else "N"), func_key)
                            status["msg"].append(msg)
                    else:
                        status["msg"].append("  - [step %d, BEF_L%d, AFT_L%d, OVC#%d] %s: NONE" % (step_idx, step_line_before, line_after, overlap_change_block_cnt, src))
                else:
                    status["msg"].append("  - [step %d, BEF_L%d, AFT_L%d, OVC#%d] %s: %s - function removed" % (step_idx, step_line_before, line_after, overlap_change_block_cnt, src, step["func_name"]))
            else:
                status["msg"].append("  - [step %d, BEF_L%d, AFT_L%d, OVC#%d] %s: %s - file removed" % (step_idx, step_line_before, line_after, overlap_change_block_cnt, src, step["func_name"]))
        res["trace"].append(step_info)
        step_idx += 1
    return res



def sanity_check(sample_before, sample_after, status):
    id = sample_before["id"].replace("_1", "")
    trace_before = sample_before["trace"]
    functions_before = sample_before["functions"]
    trace_after = sample_after["trace"]
    functions_after = sample_after["functions"]
    step_cnt = len(trace_before)
    i = 0
    while i < step_cnt:
        func_key_before = trace_before[i]["func_key"]
        func_key_after = trace_after[i]["func_key"]
        func_removed_after = trace_after[i]["func_removed"]
        if (func_key_before is not None) and (func_key_after is None) and (func_removed_after == False):
            if id not in status["after_fix_miss_func_key"]:
                status["after_fix_miss_func_key"][id] ={
                    "steps": [],
                    "after": sample_after,
                    "before": sample_before
                }
            if i not in status["after_fix_miss_func_key"][id]["steps"]:
                status["after_fix_miss_func_key"][id]["steps"].append(i)
        if (func_key_before is not None) and (func_key_after is not None):
            func_touched_before = functions_before[func_key_before]["touched_by_commit"]
            func_touched_after = functions_after[func_key_after]["touched_by_commit"]
            if func_touched_before != func_touched_after:
                if id not in status["before_after_inconsistent_touch_by_commit"]:
                    status["before_after_inconsistent_touch_by_commit"][id] = {
                        "steps": [],
                        "after": sample_after,
                        "before": sample_before
                    }
                if i not in status["before_after_inconsistent_touch_by_commit"][id]["steps"]:
                    status["before_after_inconsistent_touch_by_commit"][id]["steps"].append(i)
        i += 1
    return 



def prepare_code_base(project, version_hash, tmp_folder_suffix, status):
    # copy the fresh repo to work folder
    local_repo_path = os.path.join(g_work_folder, "%s_%s" % (project, tmp_folder_suffix))
    status["msg"].append("  - copy repo to '%s'" % (local_repo_path))
    shutil.copytree(g_repo_local_path, local_repo_path)
    status["msg"].append("  - set repo folder to " + local_repo_path)
    run_cmd_in_repo("git reset --hard %s" % version_hash, local_repo_path, status)
    current_ver_hash = get_git_version(local_repo_path, status)
    status["msg"].append("  - current version: " + current_ver_hash)
    return local_repo_path



def remove_code_base(project, tmp_folder_suffix, status):
    repo_folder = os.path.join(g_work_folder, "%s_%s" % (project, tmp_folder_suffix))
    if os.path.exists(repo_folder):
        shutil.rmtree(repo_folder)
        status["msg"].append("  - [cleanup] remove repo: %s" % repo_folder)
        


def remove_build_arg_folder(build_arg_folder, status):
    args_folder = build_arg_folder
    if os.path.exists(args_folder):
        shutil.rmtree(args_folder)
        status["msg"].append("  - [cleanup] remove compiler args logs: %s" % build_arg_folder)



def clean_build(project, version_hash, status):
    to_be_removed_repo = os.path.join(g_work_folder, "%s_%s" % (project, version_hash))
    if os.path.exists(to_be_removed_repo):
        status["msg"].append( "  - [cleanup] remove repo: %s" % to_be_removed_repo )
        shutil.rmtree(to_be_removed_repo)
    compile_arg_folder = os.path.join(g_work_folder, "%s_args_%s" % (project, version_hash))
    if os.path.exists(compile_arg_folder):
        status["msg"].append( "  - [cleanup] remove arg folder: %s" % compile_arg_folder )
        shutil.rmtree(compile_arg_folder)



def build_project(project, local_repo_path, build_arg_folder, status):
    my_env = os.environ.copy()
    my_env["CC"] = "build_cmd_dumper.py"
    my_env["CXX"] = "build_cmd_dumper.py"
    my_env["COMPILE_ARG_FOLDER"] = build_arg_folder

    config_cmd = ""
    if project == "openssl":
        config_cmd = "./config -v"
    elif project == "ffmpeg":
        config_cmd = "./configure --disable-altivec --disable-doc"
    elif project == "httpd":
        run_cmd_in_repo("cp -r /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/httpd/httpd/srclib .", local_repo_path, status)
        run_cmd_in_repo("./buildconf", local_repo_path, status)
        config_cmd = "./configure --disable-ssl --disable-setenvif"
    elif project == "nginx":
        run_cmd_in_repo("cp /gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/dataset_generator/patches/nginx/cc_clang auto/cc/clang", local_repo_path, status)
        config_cmd = "./auto/configure"
    elif project == "libtiff":
        if os.path.exists(os.path.join(local_repo_path, "autogen.sh")):
            run_cmd_in_repo("./autogen.sh", local_repo_path, status)
            config_cmd = "./configure"
        else:
            config_cmd = "./configure --noninteractive"
    elif project == "libav":
        config_cmd = "./configure --disable-altivec --disable-protocol=rtmp --disable-protocol=rtmpt"
    elif project == "binutils":
        config_cmd = "./configure", "--disable-werror"
    
    (my_stdout, muy_stderr) = run_cmd_in_repo(config_cmd, local_repo_path, status, my_env = my_env)
    proc_out = my_stdout.decode("utf-8") + "\n" + muy_stderr.decode("utf-8")

    if project == "openssl":
        if proc_out.find("Configuring for linux-elf") >= 0 or proc_out.find("Configured for linux-generic32") >= 0:
            run_cmd_in_repo("/bin/bash ./Configure cc", local_repo_path, status, my_env = my_env)
    elif project == "ffmpeg":
        if proc_out.find("Unknown option \"--disable-doc\"") >= 0:
            run_cmd_in_repo("./configure", local_repo_path, status, my_env = my_env)
        elif proc_out.find("WARNING: unknown architecture ppc64le") >= 0:
            run_cmd_in_repo("./configure --disable-doc", local_repo_path, status, my_env = my_env)
    elif project == "libtiff":
        if proc_out.find("cannot guess build type;") >= 0:
            run_cmd_in_repo("mv config/config.guess config/config.guess.old", local_repo_path, status)
            run_cmd_in_repo("cp /gpfs/r92gpfs02/zhengyu/infer_runs/infer_pipeline_labeler/dataset_generator/patches/libtiff/my_config.guess config/config.guess", local_repo_path, status)
            run_cmd_in_repo("./configure", local_repo_path, status, my_env = my_env)
    remove_build_arg_folder(build_arg_folder, status)
    os.makedirs(build_arg_folder)
    run_cmd_in_repo("make -k", local_repo_path, status, my_env = my_env)



def load_compile_args(build_arg_folder, status):
    args_folder = build_arg_folder
    if not os.path.exists(args_folder):
        print("  - Error: compile argument folder not found '%s'" % args_folder, flush=True)
        sys.exit(1)
    compile_arg_map = {}
    log_files = [f for f in os.listdir(args_folder) if isfile(os.path.join(args_folder, f))]
    status["msg"].append("  - [build_arg] %d files in '%s'" % (len(log_files), args_folder))
    for log_file in log_files:
        if not log_file.endswith(".log"):
            continue
        with open(os.path.join(args_folder, log_file)) as fp:
            data = fp.read().strip()
            items = data.split("@^@")
            src_file = items[0]
            args = items[1]
            compile_arg_map[src_file] = args
    status["msg"].append("  - [build_arg] extracted for %d src files" % len(compile_arg_map.keys()))
    return compile_arg_map

   

def collect_build_args(project, local_repo_path, version,  status):
    # compiler argument folder
    build_arg_folder = os.path.join(g_work_folder, "%s_%s_args" % (project, version))
    if not os.path.exists(build_arg_folder):
        os.makedirs(build_arg_folder)
    # build project and write compiler argument to `build_arg_folder`
    build_project(project, local_repo_path, build_arg_folder, status)
    build_args = load_compile_args(build_arg_folder, status)
    remove_build_arg_folder(build_arg_folder, status)
    return build_args




def process_auto_labeler_negative_samples(project, pair_cnt, pair_total, before_version, after_version, load_from_cache):
    # tmp_dest_folder has been created
    msg_prefix = "[%3d/%3d, %s-%s]" % (pair_cnt, pair_total, before_version[:7], after_version[:7])
    tmp_output_json = os.path.join(g_tmp_output_folder, "%s_%s_labeler_0.json.gz" % (before_version[:15], after_version[:15]))
    if load_from_cache and os.path.exists(tmp_output_json):
        print("  - %s cache found. SKIP" % msg_prefix, flush = True)
        return
    status = {
        "msg": [],
        "bug_loc_trace_mismatches": {},
        # count how many issues have adjusted bug locations
        "adjusted_bug_loc_stats": {},
        # for a step, before-fix has a function key but after-fix does not
        "after_fix_miss_func_key": {},
        "before_after_inconsistent_touch_by_commit": {},
        "sample_cnt": 0,
        "auto_labeler_1_cnt": 0,
        "auto_labeler_0_cnt": 0,
        "after_commit_extractor_0_cnt": 0
    }

    negative_issues = []
    label_0_bug_details_file = os.path.join(g_labeler_output, "label_0_bug_details.pickle.gz")
    load_issues_by_version(msg_prefix, label_0_bug_details_file, negative_issues, before_version, after_version)
    issue_cnt = len(negative_issues)

    print("  - %s %d negative issues loaded" % (msg_prefix, issue_cnt), flush = True)
    status["msg"].append("-----------------------------------------------------------------------------------")
    status["msg"].append("%s %d labeler negatives issues" % (msg_prefix, issue_cnt))
    status["msg"].append("-----------------------------------------------------------------------------------")
    
    # start processing
    res = []
    tmp_folder_suffix = "%s_%s" % (before_version[:15], after_version[:15])
    # before-fix samples
    before_tmp_folder_suffix = tmp_folder_suffix + "_labeler_0"
    status["msg"].append("* process before-fix [%s]:" % before_version[:7])
    local_repo_path = prepare_code_base(project, before_version, before_tmp_folder_suffix, status)
    print("  - %s %s" % (msg_prefix, local_repo_path), flush = True)
    commit_info = get_git_commit_info(local_repo_path, before_version, after_version, status)
    # collect build args/header path
    build_args_before = collect_build_args(project, local_repo_path, before_tmp_folder_suffix, status)
    print("  - %s %d compile args" % (msg_prefix, len(build_args_before.keys())), flush = True)
    cnt = 0
    parse_cache = {}
    for issue in negative_issues:
        sample = process_before_fix(project, local_repo_path, pair_cnt, issue, 0, commit_info, build_args_before, parse_cache, status)
        res.append(sample)
        status["sample_cnt"] += 1
        status["auto_labeler_1_cnt"] += 1
        cnt += 1
        if cnt % 100 == 0:
            print("  - %s %d samples processed" % (msg_prefix, cnt), flush = True)

    remove_code_base(project, before_tmp_folder_suffix, status)
    print("  - %s %d samples processed. Done." % (msg_prefix, issue_cnt), flush = True)

    status["msg"].append("")
    status["msg"].append("* done. %d/%d issues processed" % (cnt, issue_cnt))
    # save the results as cache
    status["msg"].append("  - save %d samples to '%s'" % (len(res), tmp_output_json))
    with gzip.open(tmp_output_json, mode = 'wt') as fp:
        fp.write(json.dumps(res))
    tmp_status_json = os.path.join(g_tmp_output_folder, "%s_%s_status_labeler_0.json.gz" % (before_version[:15], after_version[:15]))
    with gzip.open(tmp_status_json, mode = 'wt') as fp:
        fp.write(json.dumps(status))
    print("  - %s DONE" % msg_prefix, flush = True)





def process_pair(project, pair_cnt, pair_total, before_version, after_version, load_from_cache):
    # tmp_dest_folder has been created
    msg_prefix = "[%3d/%3d, %s-%s]" % (pair_cnt, pair_total, before_version[:7], after_version[:7])
    tmp_output_json = os.path.join(g_tmp_output_folder, "%s_%s_before_after_fix.json.gz" % (before_version[:15], after_version[:15]))
    if load_from_cache and os.path.exists(tmp_output_json):
        print("  - %s cache found. SKIP" % msg_prefix, flush = True)
        return
    status = {
        "msg": [],
        "bug_loc_trace_mismatches": {},
        # count how many issues have adjusted bug locations
        "adjusted_bug_loc_stats": {},
        # for a step, before-fix has a function key but after-fix does not
        "after_fix_miss_func_key": {},
        "before_after_inconsistent_touch_by_commit": {},
        "sample_cnt": 0,
        "auto_labeler_1_cnt": 0,
        "auto_labeler_0_cnt": 0,
        "after_commit_extractor_0_cnt": 0
    }

    positive_issues = []
    label_1_bug_details_file = os.path.join(g_labeler_output, "label_1_bug_details.pickle.gz")
    label_2_bug_details_file = os.path.join(g_labeler_output, "label_2_bug_details.pickle.gz")
    load_issues_by_version(msg_prefix, label_1_bug_details_file, positive_issues, before_version, after_version)
    load_issues_by_version(msg_prefix, label_2_bug_details_file, positive_issues, before_version, after_version)

    issue_cnt = len(positive_issues)
    print("  - %s %d positive issues loaded" % (msg_prefix, issue_cnt), flush = True)
    status["msg"].append("-----------------------------------------------------------------------------------")
    status["msg"].append("%s %d positive issues" % (msg_prefix, issue_cnt))
    status["msg"].append("-----------------------------------------------------------------------------------")
    
    # start processing
    res = []
    before_fix_examples = []
    tmp_folder_suffix = "%s_%s" % (before_version[:15], after_version[:15])
    # before-fix samples
    before_tmp_folder_suffix = tmp_folder_suffix + "_before"
    status["msg"].append("* process before-fix [%s]:" % before_version[:7])
    local_repo_path = prepare_code_base(project, before_version, before_tmp_folder_suffix, status)
    print("  - %s BEFORE: %s" % (msg_prefix, local_repo_path), flush = True)
    commit_info = get_git_commit_info(local_repo_path, before_version, after_version, status)
    # collect build args/header path
    build_args_before = collect_build_args(project, local_repo_path, before_tmp_folder_suffix, status)
    print("  - %s BEFORE: %d compile args" % (msg_prefix, len(build_args_before.keys())), flush = True)
    cnt = 0
    parse_cache = {}
    for issue in positive_issues:
        sample = process_before_fix(project, local_repo_path, pair_cnt, issue, 1, commit_info, build_args_before, parse_cache, status)
        before_fix_examples.append(sample)
        status["sample_cnt"] += 1
        status["auto_labeler_1_cnt"] += 1
        cnt += 1
    remove_code_base(project, before_tmp_folder_suffix, status)
    print("  - %s BEFORE: %d samples processed" % (msg_prefix, issue_cnt), flush = True)

    status["msg"].append("")
    status["msg"].append("* done. %d/%d issues processed" % (cnt, issue_cnt))
    status["msg"].append("")
    status["msg"].append("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    status["msg"].append("")
    status["msg"].append("* process after-fix [%s]:" % after_version[:7])

    after_tmp_folder_suffix = tmp_folder_suffix + "_after"
    local_repo_path = prepare_code_base(project, after_version, after_tmp_folder_suffix, status)
    print("  - %s AFTER : %s" % (msg_prefix, local_repo_path), flush = True)
    # collect build args/header path
    build_args_after = collect_build_args(project, local_repo_path, after_tmp_folder_suffix, status)
    print("  - %s AFTER : compile args found for %d files" % (msg_prefix, len(build_args_after.keys())), flush = True)
    cnt = 0
    parse_cache = {}
    func_body_search_cache = {}
    issue_cnt = len(before_fix_examples)
    for before_fix_sample in before_fix_examples:
        res.append(before_fix_sample)
        after_fix_sample = process_after_fix(local_repo_path, pair_cnt, before_fix_sample, commit_info, build_args_after, parse_cache, func_body_search_cache, status)
        res.append(after_fix_sample)
        status["sample_cnt"] += 1
        status["after_commit_extractor_0_cnt"] += 1
        # sanity check
        sanity_check(before_fix_sample, after_fix_sample, status)
        cnt += 1
    remove_code_base(project, after_tmp_folder_suffix, status)
    print("  - %s AFTER : %d samples processed" % (msg_prefix, issue_cnt), flush = True)

    status["msg"].append("")
    status["msg"].append("* done. %d/%d issues processed" % (cnt, issue_cnt))
    # save the results as cache
    status["msg"].append("  - save %d samples to '%s'" % (len(res), tmp_output_json))
    with gzip.open(tmp_output_json, mode = 'wt') as fp:
        fp.write(json.dumps(res))
    tmp_status_json = os.path.join(g_tmp_output_folder, "%s_%s_status_before_after_fix.json.gz" % (before_version[:15], after_version[:15]))
    with gzip.open(tmp_status_json, mode = 'wt') as fp:
        fp.write(json.dumps(status))
    print("  - %s DONE" % msg_prefix, flush = True)



def save_labeler_0_result(project, issues):
    if not os.path.exists("result"):
        os.mkdir("result")
    print("\n* load pairwise outputs from '%s'" % g_tmp_output_folder, flush=True)
    total_pairs = 0
    for bv in issues:
        total_pairs += len(issues[bv].keys())
    # load per pair output
    time_stamp_str = datetime.now().strftime("%Y-%m-%d")
    pkl_0_labeler_file = os.path.join("result", "%s_%s_labeler_0.pickle.gz" % (time_stamp_str, project) )
    pkl_0_labeler_fp = gzip.open(pkl_0_labeler_file, "wb")
    pkl_0_labeler_cnt = 0
    cnt = 0
    for before_version in issues:
        for after_version in issues[before_version]:
            tmp_output_json = os.path.join(g_tmp_output_folder, "%s_%s_labeler_0.json.gz" % (before_version[:15], after_version[:15]))
            sample_cnt = 0
            if os.path.exists(tmp_output_json):
                with gzip.open(tmp_output_json, "rt") as fp:
                    samples = json.load(fp)
                    sample_cnt = len(samples)
                    cnt += sample_cnt
                    for s in samples:
                        if s["label"] == 0 and s["label_source"] == "auto_labeler":
                            pickle.dump(s, pkl_0_labeler_fp)
                            pkl_0_labeler_cnt += 1
                        else:
                            print("  - Error: unhandled sample [label = %d, label_source = %s]" % (s["label"], s["label_source"]))
            if sample_cnt > 0:
                print("  - [%3d/%3d, %s-%s] %3d samples saved" % (cnt, total_pairs, before_version[:7], after_version[:7], sample_cnt), flush=True)

    pkl_0_labeler_fp.close()
    print("  - %d/%d samples saved in %s" % (pkl_0_labeler_cnt, cnt, pkl_0_labeler_file), flush=True)    
    if pkl_0_labeler_cnt == 0 and os.path.exists(pkl_0_labeler_file):
        print("  - no record. remove " + pkl_0_labeler_file, flush=True)
        os.remove(pkl_0_labeler_file)





def save_before_after_fix_result(project, issues, json_output=True):
    if not os.path.exists("result"):
        os.mkdir("result")
    print("\n* load pairwise outputs from '%s'" % g_tmp_output_folder, flush=True)
    total_pairs = 0
    for bv in issues:
        total_pairs += len(issues[bv].keys())
    # load per pair output
    time_stamp_str = datetime.now().strftime("%Y-%m-%d")
    json_file = os.path.join("result", "%s_%s_before_after_fix.json" % (time_stamp_str, project) )
    pkl_1_labeler_file = os.path.join("result", "%s_%s_labeler_1.pickle.gz" % (time_stamp_str, project) )
    pkl_0_after_fix_file = os.path.join("result", "%s_%s_after_fix_extractor_0.pickle.gz" % (time_stamp_str, project) )
    pkl_1_labeler_fp = gzip.open(pkl_1_labeler_file, "wb")
    pkl_0_after_fix_fp = gzip.open(pkl_0_after_fix_file, "wb")

    if json_output:
        json_fp = open(json_file, "w")
        json_fp.write("[")

    json_cnt = 0
    pkl_1_labeler_cnt = 0
    pkl_0_after_fix_cnt = 0

    cnt = 0
    for before_version in issues:
        for after_version in issues[before_version]:
            tmp_output_json = os.path.join(g_tmp_output_folder, "%s_%s_before_after_fix.json.gz" % (before_version[:15], after_version[:15]))
            sample_cnt = 0
            if os.path.exists(tmp_output_json):
                with gzip.open(tmp_output_json, "rt") as fp:
                    samples = json.load(fp)
                    sample_cnt = len(samples)
                    cnt += sample_cnt
                    for s in samples:
                        if json_output:
                            if json_cnt == 0:
                                json_fp.write("\n")
                            else:
                                json_fp.write(",\n")
                            json_fp.write(json.dumps(s, indent=2))
                            json_cnt += 1
                        # pickle files
                        if s["label"] == 1 and s["label_source"] == "auto_labeler":
                            pickle.dump(s, pkl_1_labeler_fp)
                            pkl_1_labeler_cnt += 1
                        elif s["label"] == 0 and s["label_source"] == "after_fix_extractor":
                            pickle.dump(s, pkl_0_after_fix_fp)
                            pkl_0_after_fix_cnt += 1
                        else:
                            print("  - Error: unhandled sample [label = %d, label_source = %s]" % (s["label"], s["label_source"]))
            if sample_cnt > 0:
                print("  - [%3d/%3d, %s-%s] %3d samples saved" % (cnt, total_pairs, before_version[:7], after_version[:7], sample_cnt), flush=True)

    pkl_1_labeler_fp.close()
    pkl_0_after_fix_fp.close()
    if json_output:
        json_fp.write("]\n")

    print("  - %d samples saved" % (cnt), flush=True)
    print("    - %d samples saved in %s" % (pkl_1_labeler_cnt, pkl_1_labeler_file), flush=True)
    print("    - %d samples saved in %s" % (pkl_0_after_fix_cnt, pkl_0_after_fix_file), flush=True)
    if json_output:
        print("  - %d samples in %s" % (json_cnt, json_file), flush=True)

    if pkl_1_labeler_cnt == 0 and os.path.exists(pkl_1_labeler_file):
        print("  - no record. remove " + pkl_1_labeler_file, flush=True)
        os.remove(pkl_1_labeler_file)
    if pkl_0_after_fix_cnt == 0 and os.path.exists(pkl_0_after_fix_file):
        print("  - no record. remove " + pkl_0_after_fix_file, flush=True)
        os.remove(pkl_0_after_fix_file)
    if json_output:
        if json_cnt == 0 and os.path.exists(json_file):
            print("  - no record. remove " + json_file, flush=True)
            os.remove(json_file)



def save_status(project, issue_index, is_before_after_fix_task):
    time_stamp_str = datetime.now().strftime("%Y-%m-%d")
    print("\n* load pairwise status info from '%s'" % g_tmp_output_folder, flush=True)
    sample_cnt = 0
    auto_labeler_1_cnt = 0
    auto_labeler_0_cnt = 0
    after_commit_extractor_0_cnt = 0
    adjusted_bug_loc_stats = {}
    bug_loc_trace_mismatches = {}
    after_fix_miss_func_key = {}
    before_after_inconsistent_touch_by_commit = {}

    if not os.path.exists("logs"):
        os.mkdir("logs")
    log_file = ""
    if is_before_after_fix_task:
        log_file = os.path.join("logs", "%s_%s_details_before_after_fix.log" % (time_stamp_str, project))
    else:
        log_file = os.path.join("logs", "%s_%s_details_labeler_0.log" % (time_stamp_str, project))
    if os.path.exists(log_file):
        os.remove(log_file)
    for before_version in issue_index:
        for after_version in issue_index[before_version]:
            tmp_output_json = ""
            if is_before_after_fix_task:
                tmp_output_json = os.path.join(g_tmp_output_folder, "%s_%s_status_before_after_fix.json.gz" % (before_version[:15], after_version[:15]))
            else:
                tmp_output_json = os.path.join(g_tmp_output_folder, "%s_%s_status_labeler_0.json.gz" % (before_version[:15], after_version[:15]))
            if os.path.exists(tmp_output_json):
                status = None
                with gzip.open(tmp_output_json, "rt") as fp:
                    status = json.load(fp)
                with open(log_file, "a") as fp:
                    fp.write("\n".join(status["msg"]))
                    fp.write("\n\n\n\n\n")
                sample_cnt += status["sample_cnt"]
                auto_labeler_1_cnt += status["auto_labeler_1_cnt"]
                auto_labeler_0_cnt += status["auto_labeler_0_cnt"]
                after_commit_extractor_0_cnt += status["after_commit_extractor_0_cnt"]
                for et in status["adjusted_bug_loc_stats"]:
                    if et not in adjusted_bug_loc_stats:
                        adjusted_bug_loc_stats[et] = 0
                    adjusted_bug_loc_stats[et] += status["adjusted_bug_loc_stats"][et]
                for k in status["bug_loc_trace_mismatches"]:
                    if k not in bug_loc_trace_mismatches:
                        bug_loc_trace_mismatches[k] = []
                    bug_loc_trace_mismatches[k] += status["bug_loc_trace_mismatches"][k]
                after_fix_miss_func_key.update( status["after_fix_miss_func_key"] )
                before_after_inconsistent_touch_by_commit.update( status["before_after_inconsistent_touch_by_commit"] )
    print("  - processing log details saved in '%s'" % log_file, flush=True)

    print("\n\n\n")
    msg = "Pairwise Extraction Summary:\n"
    msg += "---------------------------------------------------\n"
    msg += "* %d samples generated.\n" % sample_cnt
    msg += "  - [label-1] %4d samples (auto-labeler)\n" % auto_labeler_1_cnt
    msg += "  - [label-0] %4d samples (auto-labeler)\n" % auto_labeler_0_cnt
    msg += "  - [label-0] %4d samples (after-commit extractor)\n" % after_commit_extractor_0_cnt
    msg += "\n\n"
    if len(adjusted_bug_loc_stats) > 0:
        msg += "* adjusted bug locations for:\n"
        cnt = 0
        for bug_type in adjusted_bug_loc_stats:
            msg += "  - %3d %s\n" % (adjusted_bug_loc_stats[bug_type], bug_type)
            cnt += adjusted_bug_loc_stats[bug_type]
        msg += "  - %3d samples in total\n" % cnt
        msg += "\n\n"
    # bug location not found in trace
    if len(bug_loc_trace_mismatches) > 0:
        msg += "* bug location not found in trace\n"
        cnt = 0
        for bug_type in bug_loc_trace_mismatches:
            msg += "  - %3d %s\n" % (len(bug_loc_trace_mismatches[bug_type]), bug_type)
            cnt += len(bug_loc_trace_mismatches[bug_type])
        msg += "  - %d samples in total" % cnt
        bug_loc_trace_file = ""
        if is_before_after_fix_task:
            bug_loc_trace_file = os.path.join("logs", "%s_%s_bug_not_in_trace_before_after_fix.json" % (time_stamp_str, project))
        else:
            bug_loc_trace_file = os.path.join("logs", "%s_%s_bug_not_in_trace_labeler_0.json" % (time_stamp_str, project))
        with open(bug_loc_trace_file, "w") as fp:
            fp.write(json.dumps(bug_loc_trace_mismatches, indent = 2))
        msg += "\n\n"
    if is_before_after_fix_task:
        if len(after_fix_miss_func_key) > 0:
            msg += "* possible incorrect None func-key in after-fix sample\n"
            for id in after_fix_miss_func_key:
                msg += "  - step [%s] in %s\n" % (",".join("'{0}'".format(n) for n in  after_fix_miss_func_key[id]["steps"]), id)
            msg += "  - %3d samples in total\n" % len(after_fix_miss_func_key)
            with open(os.path.join("logs", "%s_%s_after_fix_none_func_key.json" % (time_stamp_str, project)), "w") as fp:
                fp.write(json.dumps(after_fix_miss_func_key, indent = 2))
            msg += "\n\n"
        if len(before_after_inconsistent_touch_by_commit) > 0:
            msg += "* inconsistent touched_by_commit:\n"
            for id in before_after_inconsistent_touch_by_commit:
                msg += "  - step [%s] in %s\n" % (",".join("'{0}'".format(n) for n in  before_after_inconsistent_touch_by_commit[id]["steps"]), id)
            msg += "  - %3d samples in total\n" % len(before_after_inconsistent_touch_by_commit)
            with open(os.path.join("logs", "%s_%s_inconsistent_touched_by_commit.json" % (time_stamp_str, project)), "w") as fp:
                fp.write(json.dumps(before_after_inconsistent_touch_by_commit, indent = 2))
            msg += "\n\n"
    # summary log
    summary_file = ""
    if is_before_after_fix_task:
        summary_file = os.path.join("logs", "%s_%s_summary_before_after_fix.log" % (time_stamp_str, project))
    else:
        summary_file = os.path.join("logs", "%s_%s_summary_labeler_0.log" % (time_stamp_str, project))
    with open(summary_file, "w") as fp:
        fp.write(msg)
    print(msg, flush=True)



def gen_before_after_fix_dataset(project, load_from_cache = False):
    (pair_total, positive_issues) = gen_worklist_from_positive_bugs()
    print("\n* start processing...", flush=True)
    pair_cnt = 0
    pool = multiprocessing.Pool( int(multiprocessing.cpu_count() * 0.75) )
    jobs = []
    for before_version in positive_issues:
        for after_version in positive_issues[before_version]:
            pair_cnt += 1
            # if pair_cnt != 1:
            #     continue
            job = pool.apply_async(process_pair, (project, pair_cnt, pair_total, before_version, after_version, load_from_cache))
            jobs.append(job)
    for job in jobs:
        job.get()
    pool.close()
    pool.join()
    print("\n* all workers done", flush=True)
    # merge results
    save_before_after_fix_result(project, positive_issues)
    save_status(project, positive_issues, True)



def gen_labeler_0_samples_dataset(project, load_from_cache = False):
    (pair_total, negative_issues) = gen_worklist_from_negative_bugs()
    print("\n* start processing...", flush=True)
    pair_cnt = 0
    pool = multiprocessing.Pool( int(multiprocessing.cpu_count() * 0.75) )
    jobs = []
    for before_version in negative_issues:
        for after_version in negative_issues[before_version]:
            pair_cnt += 1
            # if pair_cnt != 1:
            #     continue
            job = pool.apply_async(process_auto_labeler_negative_samples, (project, pair_cnt, pair_total, before_version, after_version, load_from_cache))
            jobs.append(job)
    for job in jobs:
        job.get()
    pool.close()
    pool.join()
    print("\n* all workers done", flush=True)
    # merge results
    save_labeler_0_result(project, negative_issues)
    save_status(project, negative_issues, False)



if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Error: %s project task_type" % sys.argv[0])
        sys.exit(1)
    project = sys.argv[1]
    task = sys.argv[2]
    tmp_output_folder = ""
    if len(sys.argv) > 3:
        if os.path.exists(sys.argv[3]):
            tmp_output_folder = sys.argv[3]
    if task not in ["before_after_fix", "labeler_0"]:
        print("task_type should be `before_after_fix` or `labeler_0`")
        sys.exit(1)
    print("* project: " + project, flush = True)
    init(project, arg_tmp_output_folder = tmp_output_folder)
    print("* cache folder: " + g_tmp_output_folder)
    load_from_cache = True
    if task == "before_after_fix":
        gen_before_after_fix_dataset(project, load_from_cache = load_from_cache)
    else:
        gen_labeler_0_samples_dataset(project, load_from_cache = load_from_cache)
    # clean up
    print("")
    print("* clean up. remove '%s'" % g_tmp_output_folder)
    if os.path.exists(g_tmp_output_folder):
        shutil.rmtree(g_tmp_output_folder)
    
    
