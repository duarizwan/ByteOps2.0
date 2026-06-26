import numpy as np
from app.anomaly.metrics import classification_metrics, partial_auroc, roc_points, confusion


def test_partial_auroc_perfect():
    assert partial_auroc(np.array([0,0,1,1]), np.array([.1,.2,.9,.8])) == 1.0


def test_classification_metrics_perfect():
    m = classification_metrics(np.array([0,0,1,1]), np.array([.1,.2,.9,.8]), threshold=0.5)
    assert m["precision"] == 1.0 and m["recall"] == 1.0 and m["f1"] == 1.0
    assert m["accuracy"] == 1.0


def test_confusion_counts():
    tp, fp, fn, tn = confusion(np.array([1,1,0,0]), np.array([1,0,0,0]))
    assert (tp, fp, fn, tn) == (1, 0, 1, 2)


def test_roc_points_monotone_fpr():
    fpr, tpr = roc_points(np.array([0,1,0,1]), np.array([.2,.8,.3,.9]))
    assert fpr[0] == 0.0 and fpr[-1] == 1.0
    assert all(b >= a for a, b in zip(fpr, fpr[1:]))
