#!/usr/bin/env python2

import os
import sys
import time
import tarfile

def get_trace(tar_file, bug_id):
    bug_file = "bug_%s.txt" % bug_id
    if not os.path.exists(tar_file):
        print("Error: cannot find tar file @ %s" % tar_file)
        return
    tar = tarfile.open(tar_file, "r:gz")
    for filename in tar.getnames():
        if filename.endswith(bug_file):
            try:
                f = tar.extractfile(filename)
                content = f.read()
                print("tar: %s" % tar_file)
                print("bug: %s" % filename)
                print("-------------------------------")
                print(content)
                return
            except :
                print 'ERROR: Did not find %s in tar archive' % filename
                return
    print("Error: cannot find %s in %s" % (bug_file, tar_file))


def get_direct_trace(bug_id):
    bug_file = "/gpfs/r92gpfs02/zhengyu/infer_runs/output/openssl_test/b/d/bdcd660e33710079b495cf5cc6a1aaa5d2dcd317/prev/report.html/traces/bug_%s.txt" % bug_id
    with open(bug_file, "r") as fp:
        content = fp.read()
        print(content)
    
    
            


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: %s <path_to_trace.tar.gz> <bug_id>" % sys.argv[0])
        print("     : e.g. '%s traces.tar.gz 5' will open bug_5.txt in traces.tar.gz" % sys.argv[0])
        sys.exit(1)
    tar_file = sys.argv[1]
    bug_id = sys.argv[2]

    s1 = time.time()
    get_trace(tar_file, bug_id)
    e1 = time.time()
    print(e1 - s1)

    # s2 = time.time()
    # get_direct_trace(bug_id)
    # e2 = time.time()
    # print(e2 - s2)




    
    