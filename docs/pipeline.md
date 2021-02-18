# Running the Dataset Generation Pipeline

Starting from the URL to a git repo, there are four steps to generate labeled samples based on differential analysis.

1. [Commit Message Analysis (CMA)](../scripts/infer_pipeline/commit_msg_analyzer) analyzes the commit messages and identifies the commits that are more likely to refer to vulnerability fixes. 
2. [Pairwise Static Analysis](../scripts/infer_pipeline) runs the standard static program analysis on before-commit and after-commit versions for each selected commit hash obtained in the previous step.
3. [Auto-labeler](scripts/auto_labeler) merges the analysis results for all selected commit versions and label each issue based on differential logic and commit history heuristics. 
4. [Function Extractor](scripts/dataset_generator) extracts the bodies of the functions involved in the trace. 

## Steps

### Step 1 - Commit Message Analysis

CMA scripts can be found in [here](../scripts/infer_pipeline/commit_msg_analyzer). The inputs are 

1) the URL to a git repo such as [line 578 in msg_analyzer.py](../scripts/infer_pipeline/commit_msg_analyzer/msg_analyzer.py#L578) 

2) the commit message score threshold. The script will ask for a float number as the filtering score. The default threshold is `0.4` ([line 317-324 in msg_analyzer.py](../scripts/infer_pipeline/commit_msg_analyzer/msg_analyzer.py#L317-L324)). This is useful when the CMA returns too many commits for the expensive pairwise static analysis

Go to `scripts/infer_pipeline/commit_msg_analyzer`

#### Install CMA

```shell
python -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt 
```

#### Run the analyzer

```shell
./msg_analyzer.py
```

#### Analysis results

The results are saved in `result` folder
- `[timestamp]_[project_name]_commit_only.txt`: this is for pipeline. Only commits with positive scores will be saved here
- `[timestamp]_[project_name]_commit_score.cvs`: all commits and their scores

### Step 2 - Pairwise Static Analysis

We use [Facebook Infer](https://fbinfer.com/) as the static program analyzer.

#### Install the Infer

Please follow the instructions in [How to install Infer from source
](https://github.com/facebook/infer/blob/master/INSTALL.md) 


#### Run pairwise static analysis

The main script is [process_hash_pair.sh](../scripts/infer_pipeline/process_hash_pair.sh). 

We use [autoinferbox.sh](../scripts/infer_pipeline/autoinferbox.sh) to [run LSF jobs](scripts/infer_pipeline/commit_msg_analyzer). Essentially, We divide the selected commits and send `HASH_PER_JOB` ([line 19 in autoinferbox.sh](../scripts/infer_pipeline/autoinferbox.sh)) commits to one work node. 

The wrapper script [run_on_libtiff.sh](../scripts/infer_pipeline/run_on_libtiff.sh) is an example showing how to run the analysis on `libtiff`. 

The inputs are the commit file produced by CMA (`20200703_libtiff_commit_only.txt`) and the local repo of libtiff. Parameters descriptions can be seen [here](../scripts/infer_pipeline/autoinferbox.sh#L26-32).

For each commit, pairwise analysis will generate the following contents
```shell
$ ls libtiff
0/  1/  2/  3/  4/  5/  6/  7/  8/  9/  a/  b/  c/  d/  e/  f/

$ ls libtiff/0
2/  6/  a/  c/
 
$ ls libtiff/0/2
02bb01750fd03cdc4a429a02b26a6bdaa250ab4e/

$ ls libtiff/0/2/02bb01750fd03cdc4a429a02b26a6bdaa250ab4e/
curr/  differential/  prev/  process_hash_pair.log

$ ls libtiff/0/2/02bb01750fd03cdc4a429a02b26a6bdaa250ab4e/curr/bugs.txt.gz  costs-report.json  logs.gz  report.html/  report.json.gz  report.txt.gz

$ ls libtiff/0/2/02bb01750fd03cdc4a429a02b26a6bdaa250ab4e/prev/bugs.txt.gz  costs-report.json  logs.gz  report.html/  report.json.gz  report.txt.gz

$ ls libtiff/0/2/02bb01750fd03cdc4a429a02b26a6bdaa250ab4e/differential/
costs_summary.json  fixed.json  introduced.json  preexisting.json.gz
```

### Step 3 - Auto-labeler

Once we have all pairwise analysis results for all selected commits, we can run [auto-labeler](../scripts/auto_labeler) to merge and label issues.

The main script is [gen_infer_trace_label.py](../scripts/auto_labeler/gen_infer_trace_label.py), which takes the project name as the input [here](../scripts/auto_labeler/gen_infer_trace_label.py#1500) 


### Step 4 - Generating the Dataset Samples

python clang binding is needed
```shell
pip install clang
```


The main script is [dataset_generator.py](../scripts/dataset_generator/dataset_generator.py). Its parameter specifications can be found [here](../scripts/dataset_generator/dataset_generator.py#L1741-L1746). An example could be found in the busb job wrapper [here](../scripts/dataset_generator/bsub_job.sh#L10).