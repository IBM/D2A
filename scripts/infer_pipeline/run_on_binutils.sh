#!/bin/bash

./autoinferbox.sh \
   /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/binutils/commits_only_2017_2020.txt \
   /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/binutils/binutils-gdb \
   /gpfs/r92gpfs02/zhengyu/infer_runs/output/binutils \
   /dev/shm/$USER \
   pair \
   binutils

