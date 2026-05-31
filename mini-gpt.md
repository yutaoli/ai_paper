# Mini GPT：用 TDD 搞懂 GPT 原理

## 目标

写一个最小但完整的 GPT 教学实现。它不追求训练速度，也不依赖 PyTorch，只用 Python 标准库把 GPT 的关键路径跑通：

- 输入 token id 序列。
- 叠加 token embedding 与 position embedding。
- 经过 causal self-attention、multi-head、residual、layer normalization、MLP。
- 输出每个位置对下一个 token 的 logits。
- 计算 next-token 交叉熵 loss。
- 用自回归方式生成新 token。

完成标准是：测试用例全部通过，并且每个测试都能对应一个 GPT 核心概念。

## TDD 计划

1. 先写测试，固定行为边界。
   - 张量形状：forward 返回 `batch x time x vocab_size`。
   - 因果掩码：当前位置不能看到未来 token。
   - self-attention 权重：每行概率和为 1。
   - multi-head：每个 head 独立注意并拼接。
   - residual + layer norm + MLP：block 输出形状不变，但内容被转换。
   - next-token loss：targets 与 logits 对齐。
   - generate：只使用 block size 范围内的上下文逐 token 生成。
2. 再写最小实现，只实现让测试变绿的功能。
3. 每次失败都先理解失败代表的概念，再改实现。
4. 最后补充文档，把测试、代码结构和 GPT 概念对应起来。

## 核心概念

### 1. Token 与词表

GPT 不直接处理文本，而是处理 token id。教学版直接用整数表示 token：

```text
"hello" -> tokenizer -> [3, 8, 2, 2, 5]
```

本项目聚焦 GPT 结构本身，所以不实现复杂 tokenizer，只假设输入已经是 token id。

### 2. Embedding

token id 只是离散编号，模型需要把它映射成向量。

- `token_embedding[token_id]` 表示这个 token 的语义向量。
- `position_embedding[position]` 表示这个位置的顺序信息。
- 两者相加得到每个位置的输入表示。

没有 position embedding 时，纯 attention 本身不知道 token 的顺序。

### 3. Causal Self-Attention

self-attention 会让序列中的每个位置读取其他位置的信息。GPT 是生成模型，预测第 `t` 个位置的下一个 token 时不能偷看未来，因此要使用 causal mask：

```text
position 0 can attend: 0
position 1 can attend: 0, 1
position 2 can attend: 0, 1, 2
```

每个位置会产生 query、key、value：

- query：我正在找什么信息。
- key：我提供什么索引。
- value：真正被汇总的信息。

注意力分数是 `query dot key / sqrt(head_size)`，再经过 softmax 变成概率，用来加权汇总 value。

### 4. Multi-Head Attention

一个 head 只能从一种投影空间看上下文。multi-head attention 用多个 head 并行观察：

- 有的 head 可以关注近邻 token。
- 有的 head 可以关注更早的主题 token。
- 有的 head 可以学习语法或结构线索。

教学版会把多个 head 的结果拼接，再通过输出投影混合。

### 5. Residual Connection

Transformer block 中每个子层都包在残差连接里：

```text
x = x + attention(layer_norm(x))
x = x + mlp(layer_norm(x))
```

残差让模型可以在原表示上做增量修改，训练深层网络时更稳定。

### 6. Layer Normalization

LayerNorm 对每个 token 向量内部做归一化，使均值接近 0、方差接近 1，然后再乘以可学习缩放参数、加偏置参数。它可以稳定不同层之间的数值分布。

### 7. MLP

attention 负责混合不同位置的信息，MLP 负责对每个位置的向量做非线性变换。典型结构是：

```text
Linear -> activation -> Linear
```

教学版使用 ReLU，保持实现直观。

### 8. Logits 与 Next-Token Loss

GPT 的输出不是一个 token，而是每个位置上的词表 logits：

```text
batch x time x vocab_size
```

训练时，第 `t` 个位置的 logits 用来预测 `target[t]`。交叉熵会鼓励正确 token 的 logit 变大。

### 9. 自回归生成

生成时从已有上下文开始：

1. 截断到最近 `block_size` 个 token。
2. forward 得到最后一个位置的 logits。
3. 选择下一个 token。
4. 把新 token 追加到上下文。
5. 重复直到生成指定长度。

教学版默认用 argmax，保证测试可复现。

## 文件结构

```text
mini-gpt.md       # 计划、概念和实现说明
mini_gpt.py       # 纯 Python 最小 GPT
test_mini_gpt.py  # unittest 测试
```

## 运行测试

```bash
python -m unittest -v test_mini_gpt.py
```

## 测试与概念映射

| 测试 | 覆盖概念 |
| --- | --- |
| `test_forward_shape` | embedding、block、logits 形状 |
| `test_causal_attention_cannot_see_future_tokens` | causal mask |
| `test_attention_weights_are_probabilities` | softmax 注意力概率 |
| `test_multi_head_attention_concatenates_heads` | multi-head attention |
| `test_transformer_block_preserves_shape_and_changes_values` | layer norm、residual、MLP |
| `test_cross_entropy_loss_uses_next_token_targets` | next-token loss |
| `test_generate_appends_tokens_and_respects_block_size` | 自回归生成与上下文窗口 |

## 实现取舍

- 不实现反向传播和参数更新，因为目标是理解 GPT 前向路径。
- 不依赖第三方库，方便在当前环境直接运行。
- 参数初始化固定 seed，保证测试稳定。
- 数学操作使用 Python list，牺牲性能换可读性。

## FAQ

### 1. 这些测试用例想测试什么概念或流程？

这些测试不是为了证明模型“聪明”，而是为了证明最小 GPT 的关键流程没有走错。设计原则是：一个测试尽量只锁定一个核心概念。

| 测试 | 想测试的概念/流程 | 设计方式 | 重要性 |
| --- | --- | --- | --- |
| `test_forward_shape` | 前向输出形状 | 输入 `batch x time`，检查输出是 `batch x time x vocab_size` | GPT 每个位置都要预测下一个 token，因此每个位置都必须输出词表 logits |
| `test_causal_attention_cannot_see_future_tokens` | 因果注意力 | 构造前缀相同、未来 token 不同的两个序列，检查前面位置输出一致 | GPT 生成时不能看到未来，训练时也不能作弊 |
| `test_attention_weights_are_probabilities` | softmax 注意力概率 | 检查每行权重和为 1、非负，并且只能覆盖可见历史 | attention 本质是对历史 value 做概率加权平均 |
| `test_multi_head_attention_concatenates_heads` | 多头注意力 | 设定 `n_embd=6, n_head=3`，检查每个 head 为 2 维，拼接后回到 6 维 | 多个 head 并行从不同角度读取上下文 |
| `test_transformer_block_preserves_shape_and_changes_values` | Transformer block | 检查 block 输出形状不变，但数值被转换 | block 是可堆叠的同形变换：改变表示，不改变接口 |
| `test_cross_entropy_loss_uses_next_token_targets` | next-token loss | 手写 logits 与 targets，人工计算交叉熵并比对 | 训练目标就是提高真实下一个 token 的概率 |
| `test_forward_returns_loss_when_targets_are_given` | 训练入口 | 给 `idx` 和 `targets`，检查 forward 同时返回 logits 与 loss | 同一个模型前向既服务推理，也服务训练 |
| `test_generate_appends_tokens_and_respects_block_size` | 自回归生成 | 固定选 token 函数，检查生成追加 token 且只看最近 `block_size` | GPT 是逐 token 生成，且上下文窗口有限 |
| `test_invalid_inputs_fail_fast` | 输入约束 | 检查 head 维度不可整除、序列太长、token 越界 | 提前暴露结构错误，避免隐藏 bug |

测试整体跟随 GPT 的主链路：

```text
token ids
-> embedding
-> causal self-attention
-> multi-head attention
-> transformer block
-> logits
-> loss / generate
```

其中最重要的两个测试是因果注意力和自回归生成：前者证明模型不能看未来，后者证明模型会按 GPT 的方式逐 token 续写。

### 2. 这些核心概念的目的是什么？

所有概念都服务于同一个目标：根据前文预测下一个 token。

| 概念 | 目的 |
| --- | --- |
| Token | 把文本变成模型能处理的离散编号 |
| Embedding | 把离散 token id 变成连续向量，便于计算语义关系 |
| Position Embedding | 给模型顺序感，否则 attention 不知道谁在前谁在后 |
| Causal Mask | 防止模型看到未来 token，保证自回归训练和生成一致 |
| Query / Key / Value | 让每个 token 学会从上下文中查找、匹配和读取信息 |
| Self-Attention | 让当前位置动态汇总上下文信息 |
| Multi-Head Attention | 让模型从多个角度同时观察上下文 |
| LayerNorm | 稳定每层输入的数值分布 |
| Residual Connection | 保留原表示，只学习增量变化，帮助深层网络训练 |
| MLP | 对每个位置的表示做非线性加工 |
| Transformer Block | 把上下文交互和局部非线性加工组合成可堆叠模块 |
| Logits | 把隐藏向量转换成词表中每个 token 的分数 |
| Cross Entropy Loss | 提供训练信号，让正确 token 的概率变高 |
| Autoregressive Generate | 通过“预测一个、追加一个、再预测一个”生成文本 |
| Block Size | 限制一次能看的上下文长度，控制计算量 |

一句话概括：

```text
Embedding 负责表示输入；
Position 负责顺序；
Attention 负责看上下文；
Causal Mask 负责不作弊；
Multi-Head 负责多角度理解；
LayerNorm + Residual 负责稳定深层计算；
MLP 负责增强表达；
Logits + Loss 负责学习预测；
Generate 负责把预测过程变成文本生成。
```

### 3. mini-gpt 的训练流程是怎样的？

当前 `mini_gpt.py` 只实现了训练流程里的前向计算和 loss 计算，没有实现反向传播和参数更新。完整训练流程应该是：

```text
文本
-> tokenizer 变成 token ids
-> 切 batch
-> 构造 idx / targets
-> forward 得到 logits
-> cross entropy loss
-> backward 计算梯度
-> optimizer 更新参数
-> 重复很多轮
-> generate 验证效果
```

最关键的是 `idx` 和 `targets` 的错位设计：

```text
tokens  = [4, 7, 2, 9, 1]
idx     = [4, 7, 2, 9]
targets = [7, 2, 9, 1]
```

含义是：

```text
看到 4        -> 预测 7
看到 4,7      -> 预测 2
看到 4,7,2    -> 预测 9
看到 4,7,2,9  -> 预测 1
```

代码入口是：

```python
logits, loss = model.forward(idx, targets)
```

这里的 `loss` 会告诉模型：真实下一个 token 的概率是否足够高。完整训练框架还需要 `loss.backward()` 和 `optimizer.step()`。

### 4. 训练循环的目标是什么？

训练循环的目标是不断调整模型参数，让模型预测下一个 token 的概率越来越准。

每一轮训练都在做：

```text
取一批文本 token
-> 构造 idx 和 targets
-> forward 得到 logits
-> cross entropy 得到 loss
-> backward 计算每个参数该怎么改
-> optimizer.step() 更新参数
-> 重复
```

数学目标是最小化 cross entropy loss，也可以理解为最大化真实下一个 token 的概率：

```text
P(target token | previous tokens)
```

训练循环本身不是在手写语言规则，而是让模型从大量样本中统计学习：什么上下文后面更可能出现什么 token。

### 5. 训练模型时输入什么，产出什么？

训练时的输入是文本 token 序列，输出是下一个 token 的概率分布和 loss。

从张量形状看：

```text
输入 idx:       batch x time
输出 logits:    batch x time x vocab_size
目标 targets:   batch x time
loss:           scalar
```

例如：

```text
文本:    我 喜 欢 你
idx:     我 喜 欢
targets: 喜 欢 你
```

模型会在每个位置产出一组词表概率：

```text
看到「我」       -> 预测下一个 token 的概率分布
看到「我 喜」    -> 预测下一个 token 的概率分布
看到「我 喜 欢」 -> 预测下一个 token 的概率分布
```

训练完成后的使用方式是：

```text
输入 prompt
-> 预测下一个 token
-> 把 token 接回上下文
-> 继续预测
-> 输出连续生成的新 token / 文本
```

### 6. OpenAI 训练时，输入 token 序列来自什么数据？产出什么？

OpenAI 没有公开每个模型完整的数据清单、比例和清洗细节。根据 OpenAI 公开说明，基础模型训练数据大致来自这些类别：

| 来源 | 说明 |
| --- | --- |
| 公开可获得的信息 | 公开网页、文本等公开内容，经过过滤、清洗、去重等处理 |
| 第三方合作或授权数据 | 与数据提供方合作或授权获得的数据 |
| 用户、人类训练师、研究人员提供或生成的数据 | 包括人工示范、标注、偏好反馈等 |
| 合成数据 | 由模型或系统生成，再用于训练、评估或改进的数据 |

商业产品的数据使用需要区分场景：OpenAI 公开说明中，API、ChatGPT Business、Enterprise、Edu 等商业服务默认不会把客户内容用于训练，除非用户显式选择加入；个人服务可能按数据控制设置用于改进模型。

训练时的即时产出是：

```text
idx -> logits -> loss -> gradients -> updated weights
```

最终产出是训练好的模型参数，而不是一份原文数据库。模型参数压缩了训练数据中的语言模式、知识关联和生成能力。对用户来说，最终表现是：

```text
输入 prompt / 图片 / 音频 / 文件等
-> 输出文本、代码、结构化内容或多模态响应
```

但语言模型底层仍然可以理解为：

```text
输入 token 序列，产出下一个 token 的概率分布。
```

### 7. nanoGPT 最核心的概念有哪些？为了解决什么问题？

nanoGPT 可以看作 mini-gpt 的 PyTorch 训练版。它的核心概念和目的如下：

| 概念 | 解决的问题 |
| --- | --- |
| Next Token Prediction | 把语言建模变成“给定前文预测下一个 token”的监督学习问题 |
| Tokenization | 把文本变成整数 token 序列 |
| Block Size / Context Window | 限制上下文长度，控制 attention 的计算成本 |
| Token + Position Embedding | 同时表示 token 内容和位置信息 |
| Causal Self-Attention | 让当前位置读取历史上下文，同时不能偷看未来 |
| Query / Key / Value | 实现可学习的上下文检索机制 |
| Multi-Head Attention | 让模型从多个角度理解上下文 |
| Transformer Block | 把 attention、MLP、LayerNorm、Residual 组合成可堆叠结构 |
| Logits + Cross Entropy | 把预测目标变成可优化的 loss |
| AdamW Optimizer | 根据梯度更新参数 |
| Training Loop | 持续取 batch、算 loss、反传、更新、评估、保存 |
| Generation / Sampling | 把 next-token prediction 变成连续文本生成 |

一句话总结：

```text
nanoGPT 用 Transformer Decoder 结构，在大量文本上做 next-token prediction，
通过 causal attention 学上下文关系，通过 cross entropy + AdamW 训练参数，
最后用自回归采样生成文本。
```

### 8. mini-gpt 和 nanoGPT 的关系是什么？

两者的主线是同构的：

```text
token ids
-> token embedding + position embedding
-> Transformer blocks
-> final LayerNorm
-> lm_head
-> logits
-> loss / generate
```

差异在于目标和工程程度：

| 模块 | mini-gpt | nanoGPT |
| --- | --- | --- |
| 张量库 | Python list | PyTorch Tensor |
| 目标 | 看懂原理 | 真实训练和生成 |
| attention | 手写循环 | 矩阵乘法 / Flash Attention |
| loss | 手写 cross entropy | `F.cross_entropy` |
| backward | 未实现 | PyTorch autograd |
| optimizer | 未实现 | AdamW |
| 工程能力 | 单元测试驱动教学 | checkpoint、评估、混合精度、分布式等 |

mini-gpt 负责把结构讲清楚；nanoGPT 负责展示同一套结构如何高效训练成真实可用的语言模型。

### 9. 能不能用一个例子说明 mini-gpt 每个流程是怎么算的？

可以用一个极小配置来手算：

```text
vocab_size = 3
block_size = 3
n_embd = 2
n_head = 1
```

假设一段 token 是：

```text
tokens = [0, 1, 2, 1]
```

训练样本会切成：

```text
idx     = [0, 1, 2]
targets = [1, 2, 1]
```

含义是：

```text
看到 0      -> 预测 1
看到 0,1    -> 预测 2
看到 0,1,2  -> 预测 1
```

#### Embedding

假设 token embedding 是：

```text
token 0 -> [1.0, 0.0]
token 1 -> [0.0, 1.0]
token 2 -> [1.0, 1.0]
```

position embedding 是：

```text
pos 0 -> [0.0, 0.0]
pos 1 -> [0.1, 0.0]
pos 2 -> [0.0, 0.1]
```

那么：

```text
x0 = token_emb[0] + pos_emb[0] = [1.0, 0.0]
x1 = token_emb[1] + pos_emb[1] = [0.1, 1.0]
x2 = token_emb[2] + pos_emb[2] = [1.0, 1.1]
```

#### Causal Self-Attention

为了手算简单，假设：

```text
Q = x
K = x
V = x
```

真实代码里 `Q/K/V` 会由三个不同的线性层投影得到。

看位置 2，也就是 `x2 = [1.0, 1.1]`。它能看 `x0, x1, x2`，不能看未来位置。注意力分数是：

```text
score = query dot key / sqrt(head_size)
```

这里 `head_size = 2`：

```text
score(x2, x0) = (1.0*1.0 + 1.1*0.0) / sqrt(2) = 0.707
score(x2, x1) = (1.0*0.1 + 1.1*1.0) / sqrt(2) = 0.849
score(x2, x2) = (1.0*1.0 + 1.1*1.1) / sqrt(2) = 1.563
```

softmax 后大约是：

```text
weights = [0.225, 0.259, 0.516]
```

再加权求和 value：

```text
attn_out2
= 0.225*x0 + 0.259*x1 + 0.516*x2
= 0.225*[1.0,0.0] + 0.259*[0.1,1.0] + 0.516*[1.0,1.1]
= [0.767, 0.827]
```

这表示位置 2 从历史上下文中读到的信息。

#### Causal Mask

位置 1 只能看：

```text
x0, x1
```

不能看：

```text
x2
```

否则位置 1 在预测 target `2` 时就等于偷看了答案。

#### Multi-Head

如果：

```text
n_embd = 4
n_head = 2
head_size = 2
```

两个 head 可能输出：

```text
head1_out = [0.2, 0.8]
head2_out = [0.5, 0.1]
```

拼接后：

```text
concat = [0.2, 0.8, 0.5, 0.1]
```

再经过输出投影 `proj`，混合不同 head 的信息。

#### Transformer Block

一个 block 做两次残差更新：

```text
x = x + attention(layer_norm(x))
x = x + mlp(layer_norm(x))
```

假设某个位置原本是：

```text
x = [1.0, 1.1]
```

attention 输出增量：

```text
attention_delta = [0.7, 0.8]
```

残差后：

```text
x = [1.0, 1.1] + [0.7, 0.8] = [1.7, 1.9]
```

MLP 输出增量：

```text
mlp_delta = [0.2, -0.1]
```

再次残差：

```text
x = [1.7, 1.9] + [0.2, -0.1] = [1.9, 1.8]
```

所以 block 的作用是改变表示，但保持形状不变。

#### Logits 与 Loss

假设最后一个位置的 hidden state 是：

```text
h2 = [1.9, 1.8]
```

`lm_head` 把它映射到词表大小：

```text
logits = [0.2, 2.0, 0.5]
```

softmax 后可能是：

```text
P(token 0) = 0.12
P(token 1) = 0.73
P(token 2) = 0.15
```

如果当前位置 target 是 `1`，交叉熵 loss 是：

```text
loss = -log(0.73) = 0.315
```

如果正确 token 的概率越高，loss 越小；如果正确 token 的概率越低，loss 越大。

#### Generate

假设 prompt 是：

```text
[0, 1]
```

模型输出最后一个位置的 logits：

```text
logits = [0.2, 2.0, 0.5]
```

如果用 argmax：

```text
next_token = 1
```

追加回上下文：

```text
[0, 1] -> [0, 1, 1]
```

如果超过 `block_size`，只保留最近窗口：

```text
block_size = 3
当前上下文 [0, 1, 1, 2]
实际输入   [1, 1, 2]
```

整体流程就是：

```text
idx
-> token embedding + position embedding
-> causal self-attention
-> multi-head 拼接和投影
-> residual + layer norm + MLP
-> lm_head 得到 logits
-> 和 targets 算 loss
-> 生成时取最后一个位置 logits 选 next token
```

### 10. 如果要训练参数，要怎么做？原理是什么？

当前 mini-gpt 只实现：

```text
idx -> forward -> logits -> loss
```

如果要真正训练参数，还需要：

```text
loss -> backward -> gradients -> update weights
```

也就是给模型增加三件事：

```text
1. 每个参数都要有 grad
2. loss.backward() 能把梯度传回所有参数
3. optimizer.step() 用梯度更新参数
```

#### 哪些东西是参数？

这些都应该被训练：

```text
token_embedding_table
position_embedding_table

每个 Linear 的 weight / bias
  query.weight
  key.weight
  value.weight
  proj.weight
  ffwd.up.weight
  ffwd.down.weight
  lm_head.weight

LayerNorm 的 gamma / beta
```

它们一开始是随机数。训练的目标是不断调整这些数，让正确下一个 token 的概率变高。

#### 训练循环

完整训练循环大概是：

```text
for step in range(num_steps):
    idx, targets = get_batch()

    logits, loss = model.forward(idx, targets)

    zero_grad()
    backward(loss)
    optimizer.step()
```

每一步都在解决同一个问题：

```text
每个参数应该往哪个方向改，才能让 loss 变小？
```

这个方向由梯度给出：

```text
grad = d(loss) / d(parameter)
```

最简单的 SGD 更新公式是：

```text
parameter = parameter - learning_rate * grad
```

例如：

```text
w = 0.30
grad = 0.50
learning_rate = 0.01

new_w = 0.30 - 0.01 * 0.50 = 0.295
```

如果梯度是负的：

```text
w = 0.30
grad = -0.50
learning_rate = 0.01

new_w = 0.30 - 0.01 * (-0.50) = 0.305
```

梯度决定方向，学习率决定步子大小。

#### 梯度怎么从 loss 传回去？

前向路径是：

```text
idx
-> embedding
-> attention
-> MLP
-> logits
-> loss
```

反向传播沿着计算图反着走：

```text
loss
-> logits
-> lm_head
-> final LayerNorm
-> Transformer blocks
-> attention / MLP
-> embeddings
```

cross entropy + softmax 有一个重要结论：

```text
dLoss / dLogits = predicted_probs - one_hot(target)
```

比如：

```text
probs  = [0.1, 0.7, 0.2]
target = token 2
one_hot = [0, 0, 1]
```

那么：

```text
grad_logits = [0.1, 0.7, -0.8]
```

含义是：

```text
token 0 概率偏高一点，压低
token 1 概率太高，压低
token 2 是正确答案，拉高
```

然后这个梯度继续传回 `lm_head`、Transformer block、attention 和 embedding。

#### attention 参数怎么学？

attention 里有：

```text
Q = x @ Wq
K = x @ Wk
V = x @ Wv
```

训练会调整 `Wq/Wk/Wv`，让模型学会：

```text
什么 token 应该关注什么历史 token；
关注之后应该取回什么信息。
```

如果关注错了位置，loss 变大；如果关注对了上下文，loss 变小。反向传播会把这种误差信号传回 `Wq/Wk/Wv`。

#### MLP 参数怎么学？

attention 负责从上下文拿信息，MLP 负责加工当前位置的表示：

```text
x -> Linear -> ReLU -> Linear
```

训练会让 MLP 学到更复杂的非线性特征，例如搭配、语法、局部模式等。

#### 在 mini-gpt 中实现训练有几种路线？

| 方案 | 做法 | 适合什么 |
| --- | --- | --- |
| 用 PyTorch 重写 | 把 list 换成 tensor，继承 `nn.Module`，使用 autograd | 最实用，最接近 nanoGPT |
| 写 tiny autograd | 每个数记录计算图，实现 `backward()` | 最适合理解反向传播原理 |
| 手推每个模块梯度 | 给 attention、LayerNorm、MLP 全部手写 backward | 最底层，但工作量最大，容易错 |

如果目标是继续理解 GPT，下一步推荐写一个 `mini_gpt_torch.py`：保留 GPT 结构，但把反向传播交给 PyTorch autograd。

一句话总结：

```text
训练参数 = forward 得到 loss
        + backward 计算每个参数对 loss 的影响
        + optimizer 根据梯度微调参数
        + 重复很多次，让正确下一个 token 的概率越来越高。
```
