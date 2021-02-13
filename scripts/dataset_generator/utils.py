#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shlex
import subprocess
import base64
import gzip


def clang_default_include_path():
    res = []
    cmd = shlex.split("clang -Wp,-v -x c - -fsyntax-only")
    proc = subprocess.run(cmd, stdin = subprocess.DEVNULL, stderr = subprocess.STDOUT, stdout = subprocess.PIPE)
    output = proc.stdout.decode('ascii')
    local_include_str = '#include "..." search starts here:'
    global_include_str = '#include <...> search starts here:'
    s_idx = output.find(local_include_str) + len(local_include_str)
    e_idx = output.find(global_include_str)
    for l in output[s_idx : e_idx].split("\n"):
        l = l.strip()
        if not l == "":
            res.append("-I" + l)
    s_idx = output.find(global_include_str) + len(global_include_str)
    e_idx = output.find("End of search list.")
    for l in output[s_idx : e_idx].split("\n"):
        l = l.strip()
        if not l == "":
            if l.find("(framework directory)") > 0:
                l = l.replace("(framework directory)", "").strip()
            res.append("-I" + l)
    return res


def decode_bug_trace(bug_trace):
    zipped = base64.b64decode(bug_trace)
    trace_plain_text = gzip.decompress(zipped).decode()
    return trace_plain_text
    

def convert_2_b64encode(bug_trace):
    zipped = base64.decodebytes(bug_trace.encode('ascii'))
    encoded_content = base64.b64encode(zipped).decode('ascii')
    return encoded_content

