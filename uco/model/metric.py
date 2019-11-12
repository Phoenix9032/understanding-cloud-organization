from functools import partial

import torch


def dice_mean(output, targets, threshold=0.5):
    d0 = dice_0(output, targets, threshold)
    d1 = dice_1(output, targets, threshold)
    d2 = dice_2(output, targets, threshold)
    d3 = dice_3(output, targets, threshold)
    return (d0 + d1 + d2 + d3) / 4


def dice_0(output, targets, threshold=0.5):
    return dice_c(0, output, targets, threshold)


def dice_1(output, targets, threshold=0.5):
    return dice_c(1, output, targets, threshold)


def dice_2(output, targets, threshold=0.5):
    return dice_c(2, output, targets, threshold)


def dice_3(output, targets, threshold=0.5):
    return dice_c(3, output, targets, threshold)


def dice_c(c, output, targets, threshold=0.5):
    B, C, H, W = targets.size()
    total = 0.0
    for b in range(B):
        total += dice_single_channel(output[b, c, :, :], targets[b, c, :, :], threshold)
    return total / B


def dice_single_channel(probability, truth, threshold, eps=1e-9):
    p = (probability.view(-1) > threshold).float()
    t = (truth.view(-1) > 0.5).float()
    dice = (2.0 * (p * t).sum() + eps) / (p.sum() + t.sum() + eps)
    return dice


def accuracy_0(output, targets, threshold=0.5):
    return accuracy(output, targets, 0, threshold)


def accuracy_1(output, targets, threshold=0.5):
    return accuracy(output, targets, 1, threshold)


def accuracy_2(output, targets, threshold=0.5):
    return accuracy(output, targets, 2, threshold)


def accuracy_3(output, targets, threshold=0.5):
    return accuracy(output, targets, 3, threshold)


def accuracy(output, targets, class_, threshold=0.5):
    preds = (output[:, class_] > threshold).float()
    return (preds == targets[:, class_]).float().mean()


def precision_0(output, targets, threshold=0.5):
    return precision(output, targets, 0, threshold)


def precision_1(output, targets, threshold=0.5):
    return precision(output, targets, 1, threshold)


def precision_2(output, targets, threshold=0.5):
    return precision(output, targets, 2, threshold)


def precision_3(output, targets, threshold=0.5):
    return precision(output, targets, 3, threshold)


def precision(output, targets, class_, threshold):
    preds = (output[:, class_] > threshold).float()
    tp, fp, tn, fn = _confusion(preds, targets[:, class_])
    if tp == 0 and fp == 0:
        return 1
    return tp / (tp + fp)


def recall_0(output, targets, threshold=0.5):
    return recall(output, targets, 0, threshold)


def recall_1(output, targets, threshold=0.5):
    return recall(output, targets, 1, threshold)


def recall_2(output, targets, threshold=0.5):
    return recall(output, targets, 2, threshold)


def recall_3(output, targets, threshold=0.5):
    return recall(output, targets, 3, threshold)


def recall(output, targets, class_, threshold):
    preds = (output[:, class_] > threshold).float()
    tp, fp, tn, fn = _confusion(preds, targets[:, class_])
    if tp == 0 and fn == 0:
        return 1
    return tp / (tp + fn)


def _confusion(prediction, truth):
    """
    https://gist.github.com/the-bass/cae9f3976866776dea17a5049013258d
    Returns the confusion matrix for the values in the `prediction` and `truth`
    tensors, i.e. the amount of positions where the values of `prediction`
    and `truth` are
    - 1 and 1 (True Positive)
    - 1 and 0 (False Positive)
    - 0 and 0 (True Negative)
    - 0 and 1 (False Negative)
    """

    confusion_vector = prediction / truth
    # Element-wise division of the 2 tensors returns a new tensor which holds a
    # unique value for each case:
    #   1     where prediction and truth are 1 (True Positive)
    #   inf   where prediction is 1 and truth is 0 (False Positive)
    #   nan   where prediction and truth are 0 (True Negative)
    #   0     where prediction is 0 and truth is 1 (False Negative)

    true_positives = torch.sum(confusion_vector == 1).item()
    false_positives = torch.sum(confusion_vector == float("inf")).item()
    true_negatives = torch.sum(torch.isnan(confusion_vector)).item()
    false_negatives = torch.sum(confusion_vector == 0).item()

    return true_positives, false_positives, true_negatives, false_negatives


precision_0_20 = partial(precision_0, threshold=0.20)
precision_0_30 = partial(precision_0, threshold=0.30)
precision_0_40 = partial(precision_0, threshold=0.40)
precision_0_50 = partial(precision_0, threshold=0.50)
precision_0_60 = partial(precision_0, threshold=0.60)
precision_0_70 = partial(precision_0, threshold=0.70)
precision_0_80 = partial(precision_0, threshold=0.80)

precision_1_20 = partial(precision_1, threshold=0.20)
precision_1_30 = partial(precision_1, threshold=0.30)
precision_1_40 = partial(precision_1, threshold=0.40)
precision_1_50 = partial(precision_1, threshold=0.50)
precision_1_60 = partial(precision_1, threshold=0.60)
precision_1_70 = partial(precision_1, threshold=0.70)
precision_1_80 = partial(precision_1, threshold=0.80)

precision_2_20 = partial(precision_2, threshold=0.20)
precision_2_30 = partial(precision_2, threshold=0.30)
precision_2_40 = partial(precision_2, threshold=0.40)
precision_2_50 = partial(precision_2, threshold=0.50)
precision_2_60 = partial(precision_2, threshold=0.60)
precision_2_70 = partial(precision_2, threshold=0.70)
precision_2_80 = partial(precision_2, threshold=0.80)

precision_3_20 = partial(precision_3, threshold=0.20)
precision_3_30 = partial(precision_3, threshold=0.30)
precision_3_40 = partial(precision_3, threshold=0.40)
precision_3_50 = partial(precision_3, threshold=0.50)
precision_3_60 = partial(precision_3, threshold=0.60)
precision_3_70 = partial(precision_3, threshold=0.70)
precision_3_80 = partial(precision_3, threshold=0.80)

recall_0_20 = partial(recall_0, threshold=0.20)
recall_0_30 = partial(recall_0, threshold=0.30)
recall_0_40 = partial(recall_0, threshold=0.40)
recall_0_50 = partial(recall_0, threshold=0.50)
recall_0_60 = partial(recall_0, threshold=0.60)
recall_0_70 = partial(recall_0, threshold=0.70)
recall_0_80 = partial(recall_0, threshold=0.80)

recall_1_20 = partial(recall_1, threshold=0.20)
recall_1_30 = partial(recall_1, threshold=0.30)
recall_1_40 = partial(recall_1, threshold=0.40)
recall_1_50 = partial(recall_1, threshold=0.50)
recall_1_60 = partial(recall_1, threshold=0.60)
recall_1_70 = partial(recall_1, threshold=0.70)
recall_1_80 = partial(recall_1, threshold=0.80)

recall_2_20 = partial(recall_2, threshold=0.20)
recall_2_30 = partial(recall_2, threshold=0.30)
recall_2_40 = partial(recall_2, threshold=0.40)
recall_2_50 = partial(recall_2, threshold=0.50)
recall_2_60 = partial(recall_2, threshold=0.60)
recall_2_70 = partial(recall_2, threshold=0.70)
recall_2_80 = partial(recall_2, threshold=0.80)

recall_3_20 = partial(recall_3, threshold=0.20)
recall_3_30 = partial(recall_3, threshold=0.30)
recall_3_40 = partial(recall_3, threshold=0.40)
recall_3_50 = partial(recall_3, threshold=0.50)
recall_3_60 = partial(recall_3, threshold=0.60)
recall_3_70 = partial(recall_3, threshold=0.70)
recall_3_80 = partial(recall_3, threshold=0.80)
