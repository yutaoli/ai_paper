# AI Paper Notes

这个仓库用于沉淀 LLM 学习笔记、阅读路线和最小 GPT 实现。

## 文档入口

| 文档 | 内容 |
| --- | --- |
| [llm-people-reading-map.md](./llm-people-reading-map.md) | LLM 关键人物、论文、工程项目、Agent 方向和学习路径地图 |
| [mini-gpt.md](./mini-gpt.md) | 用 TDD 实现一个最小 GPT，解释 GPT 核心概念、训练流程、测试设计和 nanoGPT 对照 |

## Mini GPT

`mini_gpt.py` 是一个纯 Python、无第三方依赖的教学版 GPT。它实现了：

- token embedding 与 position embedding
- causal self-attention
- multi-head attention
- residual connection
- layer normalization
- MLP
- logits 与 next-token loss
- autoregressive generation

运行测试：

```bash
python -m unittest discover -v
```

相关文件：

| 文件 | 说明 |
| --- | --- |
| [mini_gpt.py](./mini_gpt.py) | 最小 GPT 实现 |
| [test_mini_gpt.py](./test_mini_gpt.py) | TDD 测试用例 |
| [mini-gpt.md](./mini-gpt.md) | 原理文档和 FAQ |

## 推荐阅读顺序

1. 先读 [mini-gpt.md](./mini-gpt.md)，理解 GPT 的最小工作链路。
2. 再读 [mini_gpt.py](./mini_gpt.py) 和 [test_mini_gpt.py](./test_mini_gpt.py)，把概念对应到代码和测试。
3. 最后读 [llm-people-reading-map.md](./llm-people-reading-map.md)，扩展到 LLM 历史、模型设计、Agent、工程落地和商业化。
4. agent开发，参考：[mini-aiagent] (https://github.com/yutaoli/mini-aiagent)。

