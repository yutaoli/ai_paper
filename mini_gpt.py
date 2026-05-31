"""A tiny, dependency-free GPT for learning the core forward path.

This module intentionally uses plain Python lists instead of a tensor library.
It is slow, but every operation maps directly to a GPT concept.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable, Iterable


Vector = list[float]
Matrix = list[list[float]]
Batch = list[list[Vector]]


def _zeros(rows: int, cols: int) -> Matrix:
    return [[0.0 for _ in range(cols)] for _ in range(rows)]


def _vector_add(a: Vector, b: Vector) -> Vector:
    return [x + y for x, y in zip(a, b)]


def _vector_sub(a: Vector, b: Vector) -> Vector:
    return [x - y for x, y in zip(a, b)]


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b))


def _matvec(vector: Vector, weight: Matrix, bias: Vector | None = None) -> Vector:
    out_features = len(weight[0])
    output = []
    for col in range(out_features):
        value = sum(vector[row] * weight[row][col] for row in range(len(vector)))
        if bias is not None:
            value += bias[col]
        output.append(value)
    return output


def _softmax(values: Vector) -> Vector:
    max_value = max(values)
    exp_values = [math.exp(value - max_value) for value in values]
    total = sum(exp_values)
    return [value / total for value in exp_values]


def _relu(values: Vector) -> Vector:
    return [max(0.0, value) for value in values]


def _mean(values: Vector) -> float:
    return sum(values) / len(values)


def _variance(values: Vector, mean: float) -> float:
    return sum((value - mean) ** 2 for value in values) / len(values)


def _copy_batch(batch: Batch) -> Batch:
    return [[token[:] for token in sequence] for sequence in batch]


class Linear:
    """A tiny linear projection: y = xW + b."""

    def __init__(
        self,
        in_features: int,
        out_features: int,
        rng: random.Random,
        bias: bool = True,
        scale: float = 0.2,
    ) -> None:
        self.weight: Matrix = [
            [rng.uniform(-scale, scale) for _ in range(out_features)]
            for _ in range(in_features)
        ]
        self.bias: Vector | None = (
            [rng.uniform(-scale, scale) for _ in range(out_features)] if bias else None
        )

    def __call__(self, vector: Vector) -> Vector:
        return _matvec(vector, self.weight, self.bias)


class LayerNorm:
    """Layer normalization over a single token vector."""

    def __init__(self, n_embd: int, eps: float = 1e-5) -> None:
        self.gamma = [1.0 for _ in range(n_embd)]
        self.beta = [0.0 for _ in range(n_embd)]
        self.eps = eps

    def __call__(self, vector: Vector) -> Vector:
        mean = _mean(vector)
        variance = _variance(vector, mean)
        denom = math.sqrt(variance + self.eps)
        return [
            ((value - mean) / denom) * self.gamma[index] + self.beta[index]
            for index, value in enumerate(vector)
        ]


class FeedForward:
    """Position-wise MLP used after attention in a transformer block."""

    def __init__(self, n_embd: int, rng: random.Random) -> None:
        self.up = Linear(n_embd, 4 * n_embd, rng)
        self.down = Linear(4 * n_embd, n_embd, rng)

    def __call__(self, vector: Vector) -> Vector:
        return self.down(_relu(self.up(vector)))


class CausalSelfAttentionHead:
    """One causal self-attention head."""

    def __init__(self, n_embd: int, head_size: int, rng: random.Random) -> None:
        self.head_size = head_size
        self.query = Linear(n_embd, head_size, rng, bias=False)
        self.key = Linear(n_embd, head_size, rng, bias=False)
        self.value = Linear(n_embd, head_size, rng, bias=False)
        self.last_attention_weights: list[Matrix] = []

    def __call__(self, batch: Batch) -> Batch:
        outputs: Batch = []
        self.last_attention_weights = []

        for sequence in batch:
            keys = [self.key(token) for token in sequence]
            queries = [self.query(token) for token in sequence]
            values = [self.value(token) for token in sequence]

            sequence_output: Matrix = []
            sequence_weights: Matrix = []
            for position, query in enumerate(queries):
                scores = [
                    _dot(query, keys[past_position]) / math.sqrt(self.head_size)
                    for past_position in range(position + 1)
                ]
                weights = _softmax(scores)
                attended = [0.0 for _ in range(self.head_size)]
                for past_position, weight in enumerate(weights):
                    attended = _vector_add(
                        attended,
                        [weight * item for item in values[past_position]],
                    )
                sequence_output.append(attended)
                sequence_weights.append(weights)

            outputs.append(sequence_output)
            self.last_attention_weights.append(sequence_weights)

        return outputs


class MultiHeadAttention:
    """Multiple causal heads followed by an output projection."""

    def __init__(self, n_embd: int, n_head: int, rng: random.Random) -> None:
        if n_embd % n_head != 0:
            raise ValueError("n_embd must be divisible by n_head")
        self.n_embd = n_embd
        self.n_head = n_head
        self.head_size = n_embd // n_head
        self.heads = [
            CausalSelfAttentionHead(n_embd, self.head_size, rng)
            for _ in range(n_head)
        ]
        self.proj = Linear(n_embd, n_embd, rng)
        self.last_concatenated: Batch = []

    def __call__(self, batch: Batch) -> Batch:
        head_outputs = [head(batch) for head in self.heads]
        concatenated: Batch = []
        projected: Batch = []

        for batch_index, sequence in enumerate(batch):
            sequence_concat: Matrix = []
            sequence_projected: Matrix = []
            for position in range(len(sequence)):
                token = []
                for head_output in head_outputs:
                    token.extend(head_output[batch_index][position])
                sequence_concat.append(token)
                sequence_projected.append(self.proj(token))
            concatenated.append(sequence_concat)
            projected.append(sequence_projected)

        self.last_concatenated = concatenated
        return projected


class TransformerBlock:
    """Pre-norm transformer block: attention then MLP, both with residuals."""

    def __init__(self, n_embd: int, n_head: int, rng: random.Random) -> None:
        self.ln1 = LayerNorm(n_embd)
        self.attn = MultiHeadAttention(n_embd, n_head, rng)
        self.ln2 = LayerNorm(n_embd)
        self.ffwd = FeedForward(n_embd, rng)

    def __call__(self, batch: Batch) -> Batch:
        normalized_for_attention = [
            [self.ln1(token) for token in sequence] for sequence in batch
        ]
        attended = self.attn(normalized_for_attention)
        after_attention: Batch = []
        for sequence, attended_sequence in zip(batch, attended):
            after_attention.append(
                [
                    _vector_add(token, attention_delta)
                    for token, attention_delta in zip(sequence, attended_sequence)
                ]
            )

        normalized_for_mlp = [
            [self.ln2(token) for token in sequence] for sequence in after_attention
        ]
        mlp_out: Batch = []
        for sequence in normalized_for_mlp:
            mlp_out.append([self.ffwd(token) for token in sequence])

        output: Batch = []
        for sequence, mlp_sequence in zip(after_attention, mlp_out):
            output.append(
                [
                    _vector_add(token, mlp_delta)
                    for token, mlp_delta in zip(sequence, mlp_sequence)
                ]
            )
        return output


@dataclass
class GPTConfig:
    vocab_size: int
    block_size: int
    n_embd: int = 8
    n_head: int = 2
    n_layer: int = 2
    seed: int = 1337


class MiniGPT:
    """A minimum GPT-like model with forward, loss, and generation."""

    def __init__(self, config: GPTConfig) -> None:
        if config.vocab_size <= 0:
            raise ValueError("vocab_size must be positive")
        if config.block_size <= 0:
            raise ValueError("block_size must be positive")
        if config.n_embd % config.n_head != 0:
            raise ValueError("n_embd must be divisible by n_head")

        self.config = config
        self.rng = random.Random(config.seed)
        self.token_embedding_table: Matrix = [
            [self.rng.uniform(-0.5, 0.5) for _ in range(config.n_embd)]
            for _ in range(config.vocab_size)
        ]
        self.position_embedding_table: Matrix = [
            [self.rng.uniform(-0.5, 0.5) for _ in range(config.n_embd)]
            for _ in range(config.block_size)
        ]
        self.blocks = [
            TransformerBlock(config.n_embd, config.n_head, self.rng)
            for _ in range(config.n_layer)
        ]
        self.ln_f = LayerNorm(config.n_embd)
        self.lm_head = Linear(config.n_embd, config.vocab_size, self.rng)
        self.last_contexts_seen: list[list[int]] = []

    def embed(self, idx: list[list[int]]) -> Batch:
        self._validate_idx(idx)
        embedded: Batch = []
        for sequence in idx:
            embedded_sequence: Matrix = []
            for position, token_id in enumerate(sequence):
                token_embedding = self.token_embedding_table[token_id]
                position_embedding = self.position_embedding_table[position]
                embedded_sequence.append(_vector_add(token_embedding, position_embedding))
            embedded.append(embedded_sequence)
        return embedded

    def forward(
        self,
        idx: list[list[int]],
        targets: list[list[int]] | None = None,
    ) -> tuple[list[list[Vector]], float | None]:
        x = self.embed(idx)
        for block in self.blocks:
            x = block(x)
        x = [[self.ln_f(token) for token in sequence] for sequence in x]
        logits = [[self.lm_head(token) for token in sequence] for sequence in x]
        loss = self.cross_entropy_loss(logits, targets) if targets is not None else None
        return logits, loss

    def cross_entropy_loss(
        self,
        logits: list[list[Vector]],
        targets: list[list[int]],
    ) -> float:
        if len(logits) != len(targets):
            raise ValueError("targets must have the same batch size as logits")
        total_loss = 0.0
        count = 0
        for batch_index, sequence in enumerate(logits):
            if len(sequence) != len(targets[batch_index]):
                raise ValueError("targets must have the same time dimension as logits")
            for position, token_logits in enumerate(sequence):
                target = targets[batch_index][position]
                if not 0 <= target < self.config.vocab_size:
                    raise ValueError("target token id is outside the vocabulary")
                probs = _softmax(token_logits)
                total_loss += -math.log(probs[target])
                count += 1
        if count == 0:
            raise ValueError("cannot compute loss for empty logits")
        return total_loss / count

    def generate(
        self,
        idx: list[list[int]],
        max_new_tokens: int,
        choose_token: Callable[[Vector], int] | None = None,
    ) -> list[list[int]]:
        if max_new_tokens < 0:
            raise ValueError("max_new_tokens must be non-negative")
        choose = choose_token or _argmax
        generated = [sequence[:] for sequence in idx]
        self.last_contexts_seen = []

        for _ in range(max_new_tokens):
            context = [
                sequence[-self.config.block_size :]
                for sequence in generated
            ]
            self.last_contexts_seen.extend([sequence[:] for sequence in context])
            logits, _ = self.forward(context)
            for batch_index, sequence_logits in enumerate(logits):
                next_token = choose(sequence_logits[-1])
                if not 0 <= next_token < self.config.vocab_size:
                    raise ValueError("generated token id is outside the vocabulary")
                generated[batch_index].append(next_token)
        return generated

    def _validate_idx(self, idx: list[list[int]]) -> None:
        if not idx:
            raise ValueError("idx must contain at least one sequence")
        for sequence in idx:
            if not sequence:
                raise ValueError("sequences must not be empty")
            if len(sequence) > self.config.block_size:
                raise ValueError("sequence length exceeds block_size")
            for token_id in sequence:
                if not 0 <= token_id < self.config.vocab_size:
                    raise ValueError("token id is outside the vocabulary")


def _argmax(values: Iterable[float]) -> int:
    best_index = 0
    best_value = -math.inf
    for index, value in enumerate(values):
        if value > best_value:
            best_index = index
            best_value = value
    return best_index


__all__ = [
    "CausalSelfAttentionHead",
    "FeedForward",
    "GPTConfig",
    "LayerNorm",
    "MiniGPT",
    "MultiHeadAttention",
    "TransformerBlock",
]

