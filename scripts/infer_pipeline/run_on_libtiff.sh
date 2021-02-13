#!/bin/bash


./autoinferbox.sh \
   /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/libtiff/20200703_libtiff_commit_only.txt \
   /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/libtiff/libtiff \
   /gpfs/r92gpfs02/zhengyu/infer_runs/output/libtiff \
   /dev/shm/$USER \
   pair \
   libtiff
