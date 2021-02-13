#
# Copyright (c) IBM, Inc. and its affiliates.
#

# process hash_array_list with specified concurrency parameters and path arguments
# Process single hash or hash pair
# copy selected data to output path
# report start/finish times along with exit status for each hash

#set -x

# enable the extra infer issue types that are disabled by default
# https://github.com/facebook/infer/blob/master/infer/man/man1/infer.txt#L349
function enable_infer_issue_types {
  checker_list_file="$pipeline_path/infer_issue_type_filter.txt"
  infer_extra_args=""
  cat $checker_list_file| { while read checker
    do
      if [[ "$checker" =~ "(disabled by default)" ]]; then
        checker=${checker//" (disabled by default)"/}
        checker=${checker//"."/}
        checker=${checker//","/}
        infer_extra_args="$infer_extra_args --enable-issue-type $checker"
      fi
    done
    echo $infer_extra_args
  }
}

# Function to wrap processing and report exit status
function spawned_process_wrapper {
  hash=$1
  outdir=$2
  workdir=$3
  echo $(date) " Starting " $hash
  process_hash_pair $hash &> $outdir/process_hash_pair.log &
  pid=$!
  wait $pid
  if [ $? -eq 0 ]; then
    echo $(date) " Completed-success " $hash
  else
    echo $(date) " Completed-failure " $hash
  fi
  rm -rf $workdir
}

# Function to process a single hash
function process_single_hash {
  githash=$1
  output_folder=$2
  
  pre_build_script="$pipeline_path/not_exist_script"
  post_build_script="$pipeline_path/not_exist_script"
  if [[ $PROJECT == "qemu" ]]; then
    pre_build_script="$pipeline_path/pre_build_qemu.sh"
    post_build_script="$pipeline_path/post_build_qemu.sh"
  fi

  echo "============================"
  echo "Processing Hash: $githash"
  echo "Output Folder: $output_folder"
  time git reset --hard $githash

  if [ -f $pre_build_script ]; then
    echo ""
    echo "------------------------"
    echo "pre-build actions"
    echo "source from: $pre_build_script"
    echo "------------------------"
    set -x
    source $pre_build_script
    set +x
  fi

  source $pipeline_path/configure_project.sh

  if [ "$MAKE_ONLY" == "true" ]; then
    echo ""
    echo "------------------------"
    echo "make only"
    echo "------------------------"
    set -x
    make
    set +x
  else
    # run infer
    echo ""
    echo "------------------------"
    echo "infer run"
    echo "------------------------"
    set -x
    time infer run $INFER_ARGS --reactive -j $INFER_CONCURRENCY -- make -j $MAKE_CONCURRENCY
    time infer-explore --html 
    # compress the results and clean up
    gzip ./infer-out/logs
    gzip ./infer-out/bugs.txt
    gzip ./infer-out/report.txt # the contents in bugs.txt are moved to report.txt in newer infer
    gzip ./infer-out/report.html/index.html
    tar -zcf ./infer-out/report.html/traces.tar.gz  -C ./infer-out/report.html traces
    rm -rf ./infer-out/report.html/traces
    rm -rf ./infer-out/results.db ./infer-out/results.db-shm ./infer-out/results.db-wal ./infer-out/specs ./infer-out/tmp ./infer-out/lint_issues
    # move results to the output folder
    mkdir $output_folder
    if [ ! "$(ls ./infer-out)" == "" ]; then
      mv ./infer-out/* $output_folder
    fi
    time make clean
    set +x
  fi

  if [ -f $post_build_script ]; then
    echo ""
    echo "------------------------"
    echo "post-build actions"
    echo "source from: $post_build_script"
    echo "------------------------"
    set -x
    source $post_build_script
    set +x
  fi
}


# Usage: process_hash_pair <currhash>
function process_hash_pair {
  #Exit at first error
  set -e

  #Copy base project into working directory
  time cp -fr $project_path $workdir/project

  cd $workdir/project

  #Obtain current and previous hash and define output dirs
  #previous hash obtained with ${currhash}^
  #TODO: handle commit with multiple parents
  currhash=$1
  currdir=$workdir/curr
  if [ "$single_or_pair" == "pair" ]; then
    parents=$(git log -1 --pretty=%P ${currhash})
    parents_number=$(awk -v parents="$parents" '{ print NF, parents }')
    echo "Parent commits ($parent_number): $parents"
    prevhash=$(echo $parents|cut -d' ' -f1)
    prevdir=$workdir/prev
    echo "Current hash: $currhash Previous hash: $prevhash"
  else
    echo "Current hash: $currhash"
  fi

  #Process
  if [ "$single_or_pair" == "pair" ]; then
    #process previous 
    process_single_hash $prevhash $prevdir
    #process current
    process_single_hash $currhash $currdir
    #compute diff
    set -x
    time infer-reportdiff --report-current $currdir/report.json --report-previous $prevdir/report.json
    gzip $prevdir/report.json
    gzip $currdir/report.json
    gzip ./infer-out/differential/preexisting.json
    rm -rf $workdir/differential
    mv ./infer-out/differential $workdir
    rm -rf infer-out
    set +x
  else
    #process current
    process_single_hash $currhash $currdir
    if [ ! "$MAKE_ONLY" == "true" ]; then
      gzip $currdir/report.json
    fi
  fi
  
  set -x
  #Save important data
  rm -rf $workdir/project
  if [ ! "$(ls $workdir)" == "" ]; then
    mv $workdir/* $outdir/
  fi
  rm -rf $workdir
  set +x
  cd -
}


#Main
#Arguments check
if [ "$#" -ne 10 ]; then
  echo "Error: wrong arguments"
  echo "Usage $0 <project_path> <hash_list> <output_path> <work_path> <JOB_CONCURRENCY> <INFER_CONCURRENCY> <MAKE_CONCURRENCY> <pipeline_script_path> <single_or_pair> <target_project>"
  exit
fi

project_path=$1
IFS=',' read -r -a hash_list_array <<< "$2"
output_path=$3
work_path=$4
JOB_CONCURRENCY=$5
INFER_CONCURRENCY=$6
MAKE_CONCURRENCY=$7
pipeline_path=$8
single_or_pair=$9
PROJECT=${10} # [ "openssl" | "ffmpeg"  | "qemu" ]
INFER_ARGS=$(enable_infer_issue_types)
INFER_ARGS="--bufferoverrun --pulse --bo-field-depth-limit 3 --no-linters --no-fragment-retains-view --no-inefficient-keyset-iterator --no-self-in-block $INFER_ARGS"

# uncomment next line to just compile, no use of infer
#MAKE_ONLY=true

echo "==========================================="
echo "Project: $project_path"
echo "Output path: $output_path"
echo "Work path: $work_path"
echo "Job Concurrency: $JOB_CONCURRENCY"
echo "Infer Concurrency: $INFER_CONCURRENCY"
echo "Make Concurrency: $MAKE_CONCURRENCY"
echo "Pipeline Script Path: $pipeline_path"
echo "Target Project: $PROJECT"
echo "Received ${#hash_list_array[@]} hashpairs"

if [ "$MAKE_ONLY" == "true" ]; then
  single_or_pair="single"
  echo "Running in mode: single, compile only"
else
  echo "Running in mode: $single_or_pair"
fi
echo "==========================================="

rm -rf $work_path

for currhash in "${hash_list_array[@]}"
do
  # hangout if max outstanding jobs running
  runningJobs=($(jobs -rp))
  while [ ${#runningJobs[@]} -ge $JOB_CONCURRENCY ] ; do
    sleep 1
    runningJobs=($(jobs -rp))
  done

  #Process current and previous hash
  hashdir=${currhash:0:1}/${currhash:1:1}/$currhash
  workdir=$work_path/workdir/$hashdir #Temporary working directory
  outdir=$output_path/$hashdir #Final directory for this hash pair
  rm -rf $workdir
  mkdir -p $workdir
  mkdir -p $outdir
  # detach hash processing to run in parallel
  spawned_process_wrapper $currhash $outdir $workdir &
done

wait
#cleanup workdir
rm -rf $work_path/workdir
echo "Job completed"
