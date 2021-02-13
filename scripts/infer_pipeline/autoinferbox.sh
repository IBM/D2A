#!/bin/bash
#set -x
# Copyright (c) IBM, Inc. and its affiliates.
# 

# LLVM and Infer instances
# -------------------------------------------------------------------------------------------------
#export PATH="$ZHENGYU_PREFIX/bin:/home/amorari/anaconda3/bin:$PATH"
#export LD_LIBRARY_PATH="$ZHENGYU_PREFIX/lib:$ZHENGYU_PREFIX/lib64:$LD_LIBRARY_PATH"
# --------------------------------------------------------------------------------------------------


if [ $# -ne 6 ]; then
  echo "Error: wrong arguments"
  echo "Usage: $0 <commit_file> <git_project_path> <output_path> <work_path> <single|pair> <target_project>"
  exit
fi

HASH_PER_JOB=100 #Number of hash pairs sent to each remote machine
JOB_CONCURRENCY=33 #Number of concurrent hash pairs in each remote machine
INFER_CONCURRENCY=1 #Number of concurrent infer processes for analyzing each hash
MAKE_CONCURRENCY=1 #Number of concurrent processes to use for compiling each hash
#Comment wrapper to run locally (then the "remote" machine is this machine
BSUB_WRAPPER="./bsub_wrapper.sh"

commit_file=$1
project_path=$2
output_path=$3
work_path=$4
pipeline_path=$(pwd)
single_or_pair=$5
target_project=$6 # [ "openssl" | "ffmpeg"  | "qemu" | etc... ]

if [ ! "$single_or_pair" == "single" ]; then
  single_or_pair="pair"
fi

echo "Commit file: $commit_file"
echo "Project path: $project_path"
echo "Output path: $output_path"
echo "Work path: $work_path"
echo "Pipeline path: $pipeline_path"
echo "Processing mode: $single_or_pair"
echo "Target project: $target_project"

mkdir -p $output_path

./cleanup_output_path.sh $output_path $single_or_pair

#set -x

total_hash=$(cat $commit_file | wc -l)
echo "total hash in commit_file: $total_hash"
hash_list=""
list_cnt=0
# while loop runs in a subshell. make sure $hash_list after the loop holds the modification inside the loop body
cat $commit_file| { while read hashpair
do

  #Skip if outdir exists
  outdir=$output_path/${hashpair:0:1}/${hashpair:1:1}/$hashpair
  if [ ! -d "$outdir" ]; then 
    if [ ! "$hash_list" == "" ]; then
      hash_list="$hash_list,$hashpair"
    else
      hash_list=$hashpair
    fi
    list_cnt=$(($list_cnt+1))
  fi

  if  (( $list_cnt == $HASH_PER_JOB )); then
    lenhashlist=$(echo "${hash_list}" | awk -F"," '{print NF}')
    echo "autoinferbox sending $lenhashlist hashpairs to job"
    $BSUB_WRAPPER ./process_hash_pair.sh $project_path $hash_list $output_path $work_path $JOB_CONCURRENCY $INFER_CONCURRENCY $MAKE_CONCURRENCY $pipeline_path $single_or_pair $target_project
    hash_list=""
    list_cnt=0
  fi
done

if [ "$hash_list" != "" ]; then 
  lenhashlist=$(echo "${hash_list}" | awk -F"," '{print NF}')
  echo "autoinferbox sending $lenhashlist hashpairs to job"
  $BSUB_WRAPPER ./process_hash_pair.sh $project_path $hash_list $output_path $work_path $JOB_CONCURRENCY $INFER_CONCURRENCY $MAKE_CONCURRENCY $pipeline_path $single_or_pair $target_project
fi
}

