#!/bin/bash

# ./autoinferbox.sh /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/httpd/20200422_httpd_commit_only.txt  /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/httpd/httpd  /gpfs/r92gpfs02/zhengyu/infer_runs/output/httpd  /dev/shm/$USER  pair  httpd

./autoinferbox.sh /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/httpd/latest_commit.txt  /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/httpd/httpd  /gpfs/r92gpfs02/zhengyu/infer_runs/output/httpd  /dev/shm/$USER  pair  httpd