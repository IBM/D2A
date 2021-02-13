#!/bin/bash


output_path="/gpfs/r92gpfs02/amorari/infer_data/openssl_output"
commit_file="/gpfs/r92gpfs02/amorari/infer_data/commitlist.output"

#echo "=== Hash Per Job ==="
#sum=0
#for j in `bjobs|grep -v JOBID|cut -d' ' -f1`; do 
#  cnt=$(bpeek $j|grep "process_hash_pair /gpfs"|wc -l 2>&1)
#  echo "Job $j: $cnt"
#  sum=$(($sum+ $cnt))
#done

total=$(cat $commit_file|wc -l)
completed=$(ls ${output_path}/*/*/* | grep differential| wc -l)
fixed=$(ls -ls ${output_path}/*/*/*/differential/fixed.json|cut -d' ' -f6|grep -Eo '[0-9]+' |wc -l)
echo "========== Hash Pairs ========"
echo -e "Total (hash pairs in the commit list file):                     \t$total"
echo -e "Completed (differential exists):                                \t$completed"
echo -e "Containing fixes (differnetial exists and fixed.json not empty):\t$fixed"

