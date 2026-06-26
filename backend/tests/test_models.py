import pytest

torch = pytest.importorskip("torch")
from app.anomaly.models import StepFeatureEmbedder, BiLSTMAttention, TransformerEncoderClassifier

VOCAB = {"step_type": 6, "tool_name": 8, "action_category": 7}
N_NUM = 9


def _batch(B=4, T=6):
    cat = {f: torch.randint(0, n, (B, T)) for f, n in VOCAB.items()}
    num = torch.randn(B, T, N_NUM)
    mask = torch.ones(B, T)
    return cat, num, mask


def test_bilstm_attention_shapes_and_attention_sums_to_one():
    m = BiLSTMAttention(VOCAB, N_NUM, hidden=32)
    cat, num, mask = _batch()
    logit, attn = m(cat, num, mask)
    assert logit.shape == (4,)
    assert attn.shape == (4, 6)
    assert torch.allclose(attn.sum(dim=1), torch.ones(4), atol=1e-4)


def test_transformer_classifier_shapes():
    m = TransformerEncoderClassifier(VOCAB, N_NUM, hidden=64, layers=2, heads=4)
    cat, num, mask = _batch()
    logit, _ = m(cat, num, mask)
    assert logit.shape == (4,)
