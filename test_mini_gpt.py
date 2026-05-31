import math
import random
import unittest

from mini_gpt import (
    CausalSelfAttentionHead,
    GPTConfig,
    MiniGPT,
    MultiHeadAttention,
    TransformerBlock,
)


def almost_equal_nested(testcase, left, right, places=7):
    if isinstance(left, list):
        testcase.assertEqual(len(left), len(right))
        for left_item, right_item in zip(left, right):
            almost_equal_nested(testcase, left_item, right_item, places)
    else:
        testcase.assertAlmostEqual(left, right, places=places)


class MiniGPTTests(unittest.TestCase):
    def test_forward_shape(self):
        model = MiniGPT(
            GPTConfig(vocab_size=11, block_size=4, n_embd=6, n_head=2, n_layer=2)
        )

        logits, loss = model.forward([[1, 2, 3], [3, 2, 1]])

        self.assertIsNone(loss)
        self.assertEqual(len(logits), 2)
        self.assertEqual(len(logits[0]), 3)
        self.assertEqual(len(logits[0][0]), 11)

    def test_causal_attention_cannot_see_future_tokens(self):
        head = CausalSelfAttentionHead(n_embd=3, head_size=2, rng=random.Random(1))
        prefix = [[[0.2, -0.1, 0.4], [0.5, 0.3, -0.2]]]
        with_future_a = [prefix[0] + [[9.0, 9.0, 9.0]]]
        with_future_b = [prefix[0] + [[-9.0, -9.0, -9.0]]]

        out_a = head(with_future_a)
        out_b = head(with_future_b)

        almost_equal_nested(self, out_a[0][0], out_b[0][0])
        almost_equal_nested(self, out_a[0][1], out_b[0][1])

    def test_attention_weights_are_probabilities(self):
        head = CausalSelfAttentionHead(n_embd=4, head_size=2, rng=random.Random(2))

        head([[[0.1, 0.2, 0.3, 0.4], [0.4, 0.3, 0.2, 0.1], [0.2, 0.5, 0.1, 0.0]]])

        weights_by_position = head.last_attention_weights[0]
        self.assertEqual([len(row) for row in weights_by_position], [1, 2, 3])
        for row in weights_by_position:
            self.assertAlmostEqual(sum(row), 1.0)
            self.assertTrue(all(weight >= 0.0 for weight in row))

    def test_multi_head_attention_concatenates_heads(self):
        attention = MultiHeadAttention(n_embd=6, n_head=3, rng=random.Random(3))
        batch = [[[0.1, 0.2, 0.3, 0.4, 0.5, 0.6]]]

        output = attention(batch)

        self.assertEqual(len(attention.heads), 3)
        self.assertEqual(attention.head_size, 2)
        self.assertEqual(len(attention.last_concatenated[0][0]), 6)
        self.assertEqual(len(output[0][0]), 6)

    def test_transformer_block_preserves_shape_and_changes_values(self):
        block = TransformerBlock(n_embd=4, n_head=2, rng=random.Random(4))
        batch = [
            [
                [0.1, 0.2, 0.3, 0.4],
                [0.4, 0.3, 0.2, 0.1],
            ]
        ]

        output = block(batch)

        self.assertEqual(len(output), 1)
        self.assertEqual(len(output[0]), 2)
        self.assertEqual(len(output[0][0]), 4)
        self.assertNotEqual(output, batch)

    def test_cross_entropy_loss_uses_next_token_targets(self):
        model = MiniGPT(GPTConfig(vocab_size=3, block_size=2, n_embd=4, n_head=2, n_layer=1))
        logits = [
            [
                [2.0, 1.0, 0.0],
                [0.0, 1.0, 2.0],
            ]
        ]
        targets = [[0, 2]]

        loss = model.cross_entropy_loss(logits, targets)

        expected_one = -math.log(math.exp(2.0) / (math.exp(2.0) + math.exp(1.0) + 1.0))
        expected_two = -math.log(math.exp(2.0) / (1.0 + math.exp(1.0) + math.exp(2.0)))
        self.assertAlmostEqual(loss, (expected_one + expected_two) / 2)

    def test_forward_returns_loss_when_targets_are_given(self):
        model = MiniGPT(GPTConfig(vocab_size=7, block_size=4, n_embd=4, n_head=2, n_layer=1))

        logits, loss = model.forward([[1, 2, 3]], targets=[[2, 3, 4]])

        self.assertEqual(len(logits[0]), 3)
        self.assertIsInstance(loss, float)
        self.assertGreater(loss, 0.0)

    def test_generate_appends_tokens_and_respects_block_size(self):
        model = MiniGPT(GPTConfig(vocab_size=5, block_size=3, n_embd=4, n_head=2, n_layer=1))

        generated = model.generate(
            [[0, 1, 2, 3]],
            max_new_tokens=2,
            choose_token=lambda logits: 4,
        )

        self.assertEqual(generated, [[0, 1, 2, 3, 4, 4]])
        self.assertEqual(model.last_contexts_seen[0], [1, 2, 3])
        self.assertEqual(model.last_contexts_seen[1], [2, 3, 4])

    def test_invalid_inputs_fail_fast(self):
        with self.assertRaises(ValueError):
            MiniGPT(GPTConfig(vocab_size=5, block_size=3, n_embd=5, n_head=2))

        model = MiniGPT(GPTConfig(vocab_size=5, block_size=3, n_embd=4, n_head=2))
        with self.assertRaises(ValueError):
            model.forward([[0, 1, 2, 3]])
        with self.assertRaises(ValueError):
            model.forward([[0, 99]])


if __name__ == "__main__":
    unittest.main()

