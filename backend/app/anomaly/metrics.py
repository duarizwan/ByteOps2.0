"""Pure evaluation metrics for anomaly detectors (no torch). Higher score = more anomalous."""
from __future__ import annotations

import numpy as np


def confusion(labels, preds):
    labels, preds = np.asarray(labels), np.asarray(preds)
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    tn = int(((preds == 0) & (labels == 0)).sum())
    return tp, fp, fn, tn


def classification_metrics(labels, scores, threshold) -> dict:
    labels = np.asarray(labels)
    preds = (np.asarray(scores) >= threshold).astype(int)
    tp, fp, fn, tn = confusion(labels, preds)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (tp + tn) / max(1, len(labels))
    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def roc_points(labels, scores):
    labels = np.asarray(labels)
    order = np.argsort(-np.asarray(scores))
    labels = labels[order]
    P, N = labels.sum(), len(labels) - labels.sum()
    tpr = np.concatenate([[0.0], np.cumsum(labels) / (P or 1)])
    fpr = np.concatenate([[0.0], np.cumsum(1 - labels) / (N or 1)])
    return fpr.tolist(), tpr.tolist()


def pr_points(labels, scores):
    labels = np.asarray(labels)
    order = np.argsort(-np.asarray(scores))
    labels = labels[order]
    tp = np.cumsum(labels)
    fp = np.cumsum(1 - labels)
    P = labels.sum() or 1
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / P
    return recall.tolist(), precision.tolist()


def partial_auroc(labels, scores, max_fpr: float = 0.2) -> float:
    labels = np.asarray(labels)
    fpr, tpr = roc_points(labels, scores)
    fpr, tpr = np.array(fpr), np.array(tpr)
    if labels.sum() == 0 or labels.sum() == len(labels):
        return float("nan")
    area = 0.0
    for i in range(1, len(fpr)):
        if fpr[i - 1] >= max_fpr:
            break
        x0, x1 = fpr[i - 1], min(fpr[i], max_fpr)
        if x1 > x0:
            area += (x1 - x0) * (tpr[i] + tpr[i - 1]) / 2.0
    return float(area / max_fpr)


def auroc(labels, scores) -> float:
    fpr, tpr = roc_points(labels, scores)
    _trap = getattr(np, "trapezoid", None) or np.trapz
    return float(_trap(tpr, fpr))
