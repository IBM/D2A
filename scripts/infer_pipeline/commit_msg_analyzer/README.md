### Install

python -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt 


### Run the analyzer

./msg_analyzer.py

### Analysis results

The results are saved in `result` folder
- `[timestamp]_[project_name]_commit_only.txt`: this is for pipeline. Only commits with positive scores will be saved here
- `[timestamp]_[project_name]_commit_score.cvs`: all commits and their scores
