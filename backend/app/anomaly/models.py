"""Sequence classifiers over rich per-step features (torch; offline training)."""
from __future__ import annotations

import torch
import torch.nn as nn

CAT_FIELDS = ["step_type", "tool_name", "action_category"]


class StepFeatureEmbedder(nn.Module):
    """Embed categorical fields + project numeric block -> per-step vector [B,T,D]."""
    def __init__(self, vocab_sizes: dict, n_numeric: int, emb: int = 16):
        super().__init__()
        self.embs = nn.ModuleDict({f: nn.Embedding(vocab_sizes[f], emb, padding_idx=0) for f in CAT_FIELDS})
        self.num_proj = nn.Linear(n_numeric, emb)
        self.out_dim = emb * (len(CAT_FIELDS) + 1)

    def forward(self, cat: dict, num: torch.Tensor) -> torch.Tensor:
        parts = [self.embs[f](cat[f]) for f in CAT_FIELDS]
        parts.append(torch.relu(self.num_proj(num)))
        return torch.cat(parts, dim=-1)


class BiLSTMAttention(nn.Module):
    def __init__(self, vocab_sizes, n_numeric, emb=16, hidden=48, dropout=0.3):
        super().__init__()
        self.embed = StepFeatureEmbedder(vocab_sizes, n_numeric, emb)
        self.lstm = nn.LSTM(self.embed.out_dim, hidden, batch_first=True, bidirectional=True)
        self.attn = nn.Linear(hidden * 2, 1)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden * 2, 1)

    def forward(self, cat, num, mask):
        x = self.embed(cat, num)
        out, _ = self.lstm(x)                       # [B,T,2H]
        scores = self.attn(out).squeeze(-1)         # [B,T]
        scores = scores.masked_fill(mask == 0, -1e9)
        attn = torch.softmax(scores, dim=1)         # [B,T]
        context = (out * attn.unsqueeze(-1)).sum(dim=1)  # [B,2H]
        logit = self.head(self.drop(context)).squeeze(-1)
        return logit, attn


class TransformerEncoderClassifier(nn.Module):
    def __init__(self, vocab_sizes, n_numeric, emb=16, hidden=64, layers=2, heads=4, dropout=0.3, max_len=20):
        super().__init__()
        self.embed = StepFeatureEmbedder(vocab_sizes, n_numeric, emb)
        self.proj = nn.Linear(self.embed.out_dim, hidden)
        self.pos = nn.Parameter(torch.randn(1, max_len, hidden) * 0.02)
        layer = nn.TransformerEncoderLayer(hidden, heads, hidden * 2, dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, layers)
        self.head = nn.Linear(hidden, 1)

    def forward(self, cat, num, mask):
        x = self.proj(self.embed(cat, num))
        x = x + self.pos[:, : x.shape[1], :]
        pad_mask = mask == 0
        h = self.encoder(x, src_key_padding_mask=pad_mask)  # [B,T,H]
        m = mask.unsqueeze(-1)
        pooled = (h * m).sum(dim=1) / m.sum(dim=1).clamp(min=1)  # masked mean
        return self.head(pooled).squeeze(-1), None
