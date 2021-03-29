# D2A Leaderboard

## Introduction

## Data

All the data is dervied from the original [D2A dataset](https://developer.ibm.com/exchanges/data/all/d2a/).

1. Infer Bug Reports (Trace): This dataset consists of Infer bug reports, which are a combination of English language and C Programming language text.
3. Bug function source code (Function)
4. Bug function source code, trace functions source code and bug function file URL (Code)

## Tasks

1. Code + Trace
2. Trace
3. Code
4. Function

## Metrics

The dataset for the Code + Trace, Trace and Code tasks are quiet unbalanced with a label 0:label 1 ratio of about 40:1 in the training set. The function dataset is much more balanced with a label 0:label 1 ratio of 0.87:1 in the training set. Because of different distributions we require different metrics to measure the performance of models on these tasks.

* Balanced Data: For the balanced dataset we use Accuracy to measure model performance.
* Unbalanced Data: Because the dataset is so heavily unbalanced, we cannot use Accuracy since the model predicting only 0 would have a 98% accuracy. Instead we use the two metrics described below.
  * AUROC: Many opensource project datasets are huge with hundereds of thousands of examples and thousands of 1 label examples. The cost associated with veryfying every label is high. Which is why it is important to rank the models in the order of model confidence in labels. We use AUROC percentage for this purpose.
  * F1 - 5% FPR: The macro-average F1 score is generally considered a good metric for unbalanced datasets. We want the AUROC curve to peak as early as possible so we calculate the macro-average F1-score percentage at 5% FPR.
* Overall: To get the overall model performance, we calculate the simple average percentage of all the scores across all the tasks.

## Baselines

### Augmented Static Analyzer

### C-BERT

## Evaluation

## Submission

## Cite
