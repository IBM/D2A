#!/bin/bash

./autoinferbox.sh \
   /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/libav/20200705_libav_commit_only.txt \
   /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/libav/libav \
   /gpfs/r92gpfs02/zhengyu/infer_runs/output/libav \
   /dev/shm/$USER \
   pair \
   libav

