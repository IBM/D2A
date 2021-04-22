import logging
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score, roc_curve, accuracy_score

# Find the point with the best fpr and the same tpr as the point closest to fpr=0.05
def get_best_closest_at95(fpr, tpr):
    fpr_value = 0.05
    for ix in range(len(fpr)):
        if fpr[ix] >= fpr_value:
            break
    if ix > 0:
        over = fpr[ix] - fpr_value
        under = fpr_value - fpr[ix-1]
        if under < over:
            ix -= 1
    tprval = tpr[ix]
    while ix > 0 and tpr[ix-1] == tprval:
        ix -= 1
    return ix


def read_model_output(filename, single_function=False):
    idxs, preds = [], []
    with open(filename) as f:
        for line in f:
            idx, pred = line.strip().split()
            idxs.append(int(idx))
            if single_function:
                preds.append(int(pred))
            else:
                preds.append(float(pred))
    return idxs, preds


def read_labels(filename, ids, test_set=False, mapping_file=None):
    test_set = mapping_file != None
    df = pd.read_csv(filename)
    expected_predictions = df.shape[0]
    if test_set:
        mapping_df = pd.read_csv(mapping_file)
    labels = []
    for i in ids: 
        try:
            if test_set:
                labels.append(int(mapping_df[mapping_df["new_id"] == i]["old_id"].values[0][-1]))
            else:
                labels.append(int(df[df["id"] == i]['label'].values[0]))
        except: 
            logging.error("Error with id: %s", i)
            sys.exit()
    if len(labels) == expected_predictions:
        return labels
    else:
        logging.error("Not enough predictions. Expected %d, got %d", expected_predictions, len(labels))
        sys.exit()    


def compute_scores(labels, preds, single_function=False):
    if single_function: 
        accuracy = accuracy_score(labels, preds)*100
        scores = {"ACCURACY": accuracy}
    else:
        rounded_predictions = []
        fpr, tpr, thresholds = roc_curve(labels, preds)
        idx = get_best_closest_at95(fpr, tpr)
        max_thresh = thresholds[idx]
        rounded_predictions = []
        for pred in preds:
            if pred >= max_thresh:
                rounded_predictions.append(1)
            else:
                rounded_predictions.append(0)    
        auc_score = roc_auc_score(labels, preds)*100
        f1 = f1_score(labels, rounded_predictions, average='macro')*100
        scores = {"AUC_SCORE": auc_score, "F1_SCORE": f1}
    return scores


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Evaluation for D2A leaderboard')
    parser.add_argument('split_file', help="File holding the dev split")
    parser.add_argument('predictions', help="Model probabilities (or binary predictions if single function)")
    parser.add_argument('--single_function', '-sf', default=False, action="store_true", help="Binary predictions provided")
    parser.add_argument('--mapping_file', '-mf', default=None,  help="Mapping file required when evaluating the test set")

    

    args = parser.parse_args()
    idxs, model_output = read_model_output(args.predictions, single_function=args.single_function)
    labels = read_labels(args.split_file, idxs, mapping_file=args.mapping_file)
    scores = compute_scores(labels, model_output, single_function=args.single_function)
    print(scores)

if __name__ == '__main__':
    main()
