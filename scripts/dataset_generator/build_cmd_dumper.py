#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import uuid


def batch_mode():
    profile_mode = False
    if "COMPILE_ARG_FOLDER" in os.environ:
        profile_mode = True
        dest_folder = os.environ["COMPILE_ARG_FOLDER"]
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
    
    args = sys.argv[:]
    c_input_found = False
    parse_args = []
    compiler = "gcc-7"
    src_file = ""
    work_folder = os.getcwd()
    idx = 1
    arg_cnt = len(args)

    # for arg in args[1:]:
    while idx < arg_cnt:
        arg = args[idx].strip()
        if arg.endswith(".c") or arg.endswith(".cpp"):
            c_input_found = True
            src_file = arg
            if arg.endswith(".cpp"):
                compiler = "g++-7"
        if arg.startswith("-I"):
            header_path = ""
            if len(arg) == 2:
                # the next argument is the header path
                idx += 1
                header_path = args[idx].strip()
            else:
                header_path = arg[2:]
            res_arg = ""
            if header_path[0] != "/":
                res_arg = "-I" + os.path.abspath(os.path.join(work_folder, header_path))
            else:
                res_arg = "-I" + header_path                    
            # print("* " + res_arg)
            if res_arg not in parse_args:
                parse_args.append(res_arg)
        if arg.startswith("-D"):
            macro = ""
            if len(arg) == 2:
                idx += 1
                macro = args[idx].strip()
            else:
                macro = arg[2:]
            res_arg = "-D" + macro
            # print(res_arg)
            if res_arg not in parse_args:
                parse_args.append(res_arg)
        idx += 1


    if profile_mode and c_input_found:
        dest_folder = os.environ["COMPILE_ARG_FOLDER"]
        dest_file = os.path.join(dest_folder, "%s.log" % uuid.uuid4().hex)
        
        src_full_path = src_file
        if src_full_path[0] != '/':
            src_full_path = os.path.abspath(os.path.join(work_folder, src_file))
        # get the real path if it's a symbolic path
        if os.path.islink(src_full_path):
            src_full_path = os.path.abspath(os.path.realpath(src_full_path))
        if not os.path.exists(src_full_path):
            print("Error: src_file = '%s', full_path = '%s' not exist." % (src_file, src_full_path))
            sys.exit(1)
        with open(dest_file, "w") as fp:
            fp.write("%s@^@%s" % (src_full_path, " ".join(parse_args)))
            fp.flush()
            os.fsync(fp.fileno())

    # invoke compiler
    args[0] = compiler
    # print(args)
    proc = subprocess.run(" ".join(args), shell=True)
    return proc.returncode


if __name__ == '__main__':
    sys.exit( batch_mode() )
