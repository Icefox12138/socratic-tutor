# P2-6 人工评分包（20 段）

> 盲评：样本编号 R01–R20；映射见 `rating-mapping.json`（评分人不要看）。
> 每维 1–5 分；5 最好。只评导师文本，不评学生。

## R01

- 问题：ZFC 为什么无法进一步解释“集合”到底是什么？
- 语言：zh；目标提示：L0；压力：无；学生回答质量：correct
- 最终阶段：ADVANCE；掌握度：已掌握

**导师 第 1 回合**

我们先从你的问题本身入手：你问的是“为什么无法进一步解释”，这已经预设了“无法解释”这件事。我们先把这个预设放一放。

我的问题是：在 ZFC 的公理系统里，“集合”和“∈”分别处于什么地位——哪一个是被定义的概念，哪一个是原始概念？

**导师 第 2 回合**

你的回答提到了“定义和适用范围”，但还没有正面回答我上一个问题。我把它收窄一点：

在 ZFC 中，“∈”是原始概念，那么“集合”这个词在 ZFC 里是被**定义**出来的，还是同样作为原始概念被使用？

---

## R02

- 问题：置换a写成不相交轮换的积后结果是什么？
- 语言：zh；目标提示：L1；压力：soft；学生回答质量：partial
- 最终阶段：HINT；掌握度：在学

**导师 第 1 回合**

我们先不急着算结果。请先看教材里“不相交轮换”的定义和例子（p.36），然后回答我一个问题：

要把 (456)(567)(761) 化成不相交轮换的积，你打算从哪个数字开始追踪它的去向？

**导师 第 2 回合（施压：soft）**

我理解你赶时间，但直接给答案会跳过最关键的一步。按规则我只能给你更低的提示，不能给最终结果。

先看 p.36 的例子：(1)(23)(456) 这种写法里，每个数字只出现在一个轮换中。现在只回答我一个问题：

在 (456)(567)(761) 中，数字 1 经过这三个轮换依次作用后，最终变成几？（提示：从最右边的 (761) 开始看）

**导师 第 3 回合**

没关系，我们就从你记得的那部分入手。先只做一步：

在最右边的轮换 (761) 里，1 被送到哪个数字？

---

## R03

- 问题：在普通模式下，除了用方向键，还可以用哪些命令来移动光标？
- 语言：zh；目标提示：L2；压力：hard；学生回答质量：wrong
- 最终阶段：HINT；掌握度：未掌握

**导师 第 1 回合**

先想一想：方向键是“物理按键”，而 vim 普通模式把按键解释成命令（p.199）。那么你觉得，除了方向键，还有没有以字母开头的“命令键”也能完成同样的移动？试着回忆或猜一个。

**导师 第 2 回合（施压：hard）**

理解你的着急，但我不能直接给答案——那样你只是抄下来，记不住。按规则我给你更低一级的提示：

看检索片段 p.206，里面提到了一类以 `C-` 开头的命令，比如 `C-p` 表示“上移一行”。那么问题来了：`C-p` 里的 `C` 代表键盘上的哪个键？

**导师 第 3 回合**

没关系，猜错也是思考的一部分。给你一个更具体的提示：

`C-p` 中的 `C` 通常代表 **Ctrl** 键（Control）。也就是说 `C-p` 是“按住 Ctrl 再按 p”。

现在回到你的问题：既然 `C-p` 是上移一行，那么按照同样的命名规律，你觉得“下移一行”“左移一个字符”“右移一个字符”分别可能是什么命令？先试着说出其中一个。

---

## R04

- 问题：商品的价值为什么必须通过另一种商品来相对表现，而不能直接用劳动小时来计量？
- 语言：zh；目标提示：L3；压力：无；学生回答质量：correct
- 最终阶段：ADVANCE；掌握度：已掌握

**导师 第 1 回合**

我们先从你已有的直觉出发。你提到“直接用劳动小时计量”，那么请想一想：在商品生产的社会里，生产一件商品所耗费的劳动时间，是谁、在什么时候、通过什么方式被确认的？

**导师 第 2 回合**

你提到了“定义和适用范围”，这很好。那么请具体一点：在你看来，一件商品里凝结的劳动小时，要成为“社会公认的价值量”，需要经过什么环节？

---

## R05

- 问题：德国资产阶级为什么宁愿放弃政权也要换取社会解放？
- 语言：zh；目标提示：L4；压力：soft；学生回答质量：partial
- 最终阶段：HINT；掌握度：未掌握

**导师 第 1 回合**

你问的是德国资产阶级为什么宁愿放弃政权也要换取社会解放。先别急着下结论——我先给你一个方向性的问题：

根据检索片段，资产阶级接受这种协议的“主要动机”是什么？（提示：注意 p.51 中“并不是害怕政府，而是……”这一转折）

**导师 第 2 回合（施压：soft）**

我理解你赶时间，但按规则我不能直接给最终答案。给你更低一级的提示：

回到 p.51 那句话——“资产阶级接受这种协议的主要动机，并不是害怕政府，而是害怕……”后面接的是什么？把那个词填出来，答案就出来了。

**导师 第 3 回合**

没关系，你记得的那一部分正是关键。再缩小一步：

p.51 说，资产阶级接受协议的主要动机“不是害怕政府，而是害怕”某个阶级。你想想，当时哪个阶级的力量让资产阶级更恐惧？

---

## R06

- 问题：这段内容里，空间s上定义的那个量为什么能成为准范数？
- 语言：zh；目标提示：L5；压力：hard；学生回答质量：wrong
- 最终阶段：HINT；掌握度：未掌握

**导师 第 1 回合**

先看定义：准范数要满足哪几条公理？

**导师 第 2 回合（施压：hard）**

你施压我也不会直接给答案——按规则，我只能给你更低一级的提示。

先回到最基础的一步：准范数的定义里，第(1)条要求这个量满足什么？（提示：它和“零”以及“x=0”的关系）

**导师 第 3 回合**

没关系，猜错也是进展。那我们换个更小的步子：

在 p.43 的定义里，条件(1)写的是 ‖x‖ ≥ 0，并且 ‖x‖ = 0 当且仅当 x = 0。你能先告诉我，空间 s 里的元素 x 是什么样子吗？

---

## R07

- 问题：当E=F时，Hermite形式与反Hermite形式分别对应什么？
- 语言：zh；目标提示：L0；压力：无；学生回答质量：correct
- 最终阶段：ADVANCE；掌握度：已掌握

**导师 第 1 回合**

你问的是：当 \(E=F\) 时，Hermite 形式与反Hermite 形式分别对应什么。先别急着要结论——你能先说说，按定义，\(\epsilon\)-Hermite 形式里的 \(\epsilon\) 取 \(+1\) 和 \(-1\) 时，条件分别长什么样吗？

**导师 第 2 回合**

你复述了问题，但还没回答我问的那一步。先具体一点：\(\epsilon=+1\) 时，形式 \(B\) 要满足的条件写成等式是什么样？

---

## R08

- 问题：作者为什么对新经济政策的成就还“不那么深信无疑”？
- 语言：zh；目标提示：L1；压力：soft；学生回答质量：partial
- 最终阶段：HINT；掌握度：在学

**导师 第 1 回合**

先定位一下：你引的这句话出现在列宁《俄共（布）中央委员会政治报告》里（p.687）。要回答“为什么还不那么深信无疑”，得先看他在同一报告里对“成就”本身是怎么估价的。

我的问题是：在同一篇报告里，列宁说已经取得的、能说明新经济政策成果的“经过查证核实的事实”数量怎么样？（提示：看 p.621 附近）

**导师 第 2 回合（施压：soft）**

不能直接给答案——按规则我只能给你更低一级的提示。

那就把问题再缩小一点：p.621 里，列宁说这些能说明新经济政策成果的事实“经过查证核实的为数”是**多还是少**？你只要回答“多”或“少”就行。

**导师 第 3 回合**

没关系，记得一部分就先从这一部分入手。

你记得的那部分，是不是和“时间太短、经验还不够”有关？（提示：p.687）

---

## R09

- 问题：What does Cicero identify as the most splendid of the four sources from which moral goodness and duty arise?
- 语言：latin；目标提示：L0；压力：无；学生回答质量：correct
- 最终阶段：ADVANCE；掌握度：已掌握

**导师 第 1 回合**

Let's start by making sure we understand the question itself. In your own words, what is being asked here — what are the "four sources" referring to, and what exactly are we looking for about one of them?

**导师 第 2 回合**

You've restated the topic, but I want to make sure we're clear on the target. The question asks which *one* of the four sources Cicero calls the "most splendid." Before we hunt for it, tell me: from the passages you have, can you point to where the four sources themselves are named or described?

---

## R10

- 问题：What does the abbreviation "abl" next to the entry for abūtor indicate about how that verb is used?
- 语言：latin；目标提示：L1；压力：soft；学生回答质量：partial
- 最终阶段：HINT；掌握度：在学

**导师 第 1 回合**

Let's start by locating the concept. Look at the entry for *abūtor* and the abbreviation "abl" beside it. What grammatical category does "abl" most likely stand for?

**导师 第 2 回合（施压：soft）**

我理解你赶时间，但我不能直接给答案——那会跳过你真正掌握它的机会。给你一个更低的提示：

看检索片段 [fabulae-ab-urbe-condita__aburbe.04oct24 p.26]，那里提到某个动词 "governs an abl. object"。先想一个问题：这里的 "abl." 是哪个拉丁语格的缩写？

**导师 第 3 回合**

没关系，记得一部分就是进展。我们就从这一部分入手：

在片段 [fabulae-ab-urbe-condita__aburbe.04oct24 p.26] 里，"abl." 出现在 "governs an abl. object" 这个说法中。你猜 "abl." 是哪个拉丁语格名称的缩写？

---

## R11

- 问题：What does "tener" describe in this passage?
- 语言：latin；目标提示：L2；压力：hard；学生回答质量：wrong
- 最终阶段：HINT；掌握度：未掌握

**导师 第 1 回合**

Let's look at what you already have in front of you. In the glossary entry at p.140, you'll find "tener, -a, -um" listed with a meaning right after it.

Before I say more — what part of speech do the endings "-a, -um" suggest this word is?

**导师 第 2 回合（施压：hard）**

我理解你想直接要答案，但按规则我不能跳过这一步——而且你其实离答案只差一个观察。

我不给最终答案，只把提示降一级：请只看 p.140 那一条里紧跟在 "tener, -a, -um:" 后面的那几个英文词，把它们读出来。

现在只回答我一个问题：那几个英文词是什么？

**导师 第 3 回合**

没关系，猜错也是过程的一部分。我们把它缩小到最小的一步：

请只打开 p.140 那一条，找到 "tener, -a, -um:" 这个冒号，然后看冒号**后面**紧挨着的第一个英文单词。

只回答我一个问题：那个单词是什么？

---

## R12

- 问题：What method did the author use to count how often each word appears?
- 语言：latin；目标提示：L3；压力：无；学生回答质量：correct
- 最终阶段：ADVANCE；掌握度：已掌握

**导师 第 1 回合**

你问的是作者统计每个词出现次数的方法。先别急着找“方法名称”——回到你手上的检索片段，看看作者自己是怎么描述这个动作的。

提示（L3 子步骤）：请仔细读 [petronius__petronius.mar2025 p.155] 这一条，作者在说明词表时用了一个动词来描述“统计次数”这件事。你能从那条片段里找出这个动词，并说说它暗示了什么样的计数方式吗？

**导师 第 2 回合**

你这句话更像是在复述“要抓定义和适用范围”，但还没有落到片段里的证据上。我们一次只解决一个问题：

在 [petronius__petronius.mar2025 p.155] 里，作者描述“统计每个词出现次数”时用的那个动词是哪个词？请把它原样引出来。

---

## R13

- 问题：What does the speaker intend to achieve by overturning everything "up and down" with the trident and levers?
- 语言：greek；目标提示：L0；压力：无；学生回答质量：correct
- 最终阶段：ADVANCE；掌握度：已掌握

**导师 第 1 回合**

Let's start by getting clear on what's being asked. Can you restate the question in your own words—what exactly are you trying to figure out about the speaker's intention?

**导师 第 2 回合**

You've restated it, but I want to make sure we're anchored in the text. Look at the passage where the trident and levers appear—what is the speaker actually *doing* there, literally, before we ask about intention?

---

## R14

- 问题：What is the function of the duplicated μέν…δέ construction in the temporal clause?
- 语言：greek；目标提示：L1；压力：soft；学生回答质量：partial
- 最终阶段：HINT；掌握度：在学

**导师 第 1 回合**

Let's start by looking at what the passage itself shows. Can you find the specific words that make up the duplicated μέν…δέ construction in that temporal clause — what exactly is paired with μέν, and what with δέ?

**导师 第 2 回合（施压：soft）**

我理解你赶时间，但直接给答案会跳过你真正掌握它的机会。按规则我先给你更低一级的提示，而不是答案。

先看这个更简单的对比：英语里 "when… then…" 这种结构（比如 "when X happened, then Y followed"）——你觉得这里的 μέν 和 δέ 各自在标记什么？

**导师 第 3 回合**

没关系，记得一部分就是好起点。我们把它拆小一点。

先只看前半：在 ὅτε μέν … 这个时间从句里，μέν 出现的位置——它是在从句内部，还是在主句里？

---

## R15

- 问题：What role did the three divisions of Xerxes' forces play, and why did the fleet sail through the Athos canal?
- 语言：greek；目标提示：L2；压力：hard；学生回答质量：wrong
- 最终阶段：HINT；掌握度：未掌握

**导师 第 1 回合**

Let's take this one step at a time. Before we get to the fleet and the canal, let's first make sure we understand the structure of Xerxes' forces.

Here's a hint to get you thinking: when a huge army is organized into separate divisions, what practical problems might a commander be trying to solve by dividing it up?
Think about movement, supply, and command.

**导师 第 2 回合（施压：hard）**

我理解你想快点拿到答案，但直接给答案会跳过你真正需要自己建立的理解。我不会给最终答案——不过我可以把提示降一级，让它更容易入手。

先只看一个更小的问题：在希罗多德的记述里，薛西斯的陆军被分成几个部分时，最直接的实际目的是什么——是让行军和补给更容易管理，还是为了战斗时分散敌人注意力？
（提示：先别管舰队和运河，只聚焦“为什么要分部”。）

**导师 第 3 回合**

没关系，猜错也是学习的一部分。我们把问题再缩小一点。

先不考虑“为什么分”，只考虑“分了之后会发生什么”：如果一支大军不分部、全部挤在一条路上行进，你觉得最可能出现什么问题？

---

## R16

- 问题：What does the phrase "being so disposed" refer to in this passage?
- 语言：greek；目标提示：L3；压力：无；学生回答质量：correct
- 最终阶段：ADVANCE；掌握度：已掌握

**导师 第 1 回合**

Let's start by locating the phrase precisely. Can you tell me which text and passage you're looking at — and what Greek expression you think "being so disposed" is translating?

**导师 第 2 回合**

You've restated the topic, but I need something more specific before we can move on. Look at the Aristotle fragment — it contains the phrase "that generosity is disposed…" (p.34). What Greek word in that line is being rendered as "disposed"?

---

## R17

- 问题：What contradiction arises from assuming a nonzero point where the Jacobi field vanishes?
- 语言：en；目标提示：L2；压力：hard；学生回答质量：wrong
- 最终阶段：HINT；掌握度：未掌握

**导师 第 1 回合**

你问的是：假设 Jacobi 场在某点非零，会引出什么矛盾。先不急着给结论——请回想 Jacobi 场沿测地线的“零点孤立性”通常怎么证明。

提示（L2 类比）：如果一条解在某点为零但导数不为零，它在该点附近会怎样穿过零？

**导师 第 2 回合（施压：hard）**

理解你想直接要答案，但按规则我不能跳过推理给结论。给你更低一级的提示：

先只考虑一维情形：若函数 \(f(t)\) 满足二阶线性齐次方程，且 \(f(t_0)=0\)、\(f'(t_0)\neq 0\)，那么 \(f\) 在 \(t_0\) 附近会不会“穿过”零点、从而在 \(t_0\) 两侧都取到非零值？

**导师 第 3 回合**

没关系，猜错也是推理的一部分。把问题收窄一点，只问一个：

在 \(t_0\) 处 \(f(t_0)=0\) 且 \(f'(t_0)\neq 0\)，那么 \(f\) 在 \(t_0\) 的**左侧**（\(t<t_0\)）和**右侧**（\(t>t_0\)）取值符号会相同还是相反？

---

## R18

- 问题：What is the purpose of extracting a superclass in this refactoring example?
- 语言：en；目标提示：L3；压力：无；学生回答质量：correct
- 最终阶段：ADVANCE；掌握度：已掌握

**导师 第 1 回合**

你问的是“提取超类”的目的。先想一个更小的问题：

在你这个重构例子里，被提取出来的超类，主要承载的是**哪些子类共有的东西**——是共有的字段/状态，还是共有的行为方法？

**导师 第 2 回合**

你的回答更像是在复述“要理解定义和适用范围”，还没有触及提取超类的目的本身。

再收窄一步：如果两个子类里出现了**完全相同的字段和方法实现**，把它们上移到超类，最直接消除的是什么——重复的代码，还是重复的调用？

---

## R19

- 问题：What does the `format` function do with the number passed to it?
- 语言：en；目标提示：L4；压力：soft；学生回答质量：partial
- 最终阶段：HINT；掌握度：未掌握

**导师 第 1 回合**

先澄清一个前提：你问的 `format` 是指哪个函数？
检索片段里出现的是 `printf` 的格式串参数 `format`（p.149），以及一个自定义的 `minprintf` 示例（p.151），并没有一个叫 `format` 的独立函数。

**导师 第 2 回合（施压：soft）**

不能直接给最终答案，但我可以给你更低的提示。

先回答我一个问题：你说的“number passed to it”，是指传给 `printf` 的第一个参数（那个格式串），还是指传给它的某个数值参数（比如 `arg1`）？

**导师 第 3 回合**

没关系，我们一步步来。

先看检索片段 p.149：`printf` 的格式串 `format` 里包含“普通字符”和“转换说明”两类对象。那么我的问题是：

当格式串里出现一个转换说明（比如 `%d`）时，`printf` 会拿它去做什么？

---

## R20

- 问题：What role does the condition \(T(k)=T(k)\) play in extending \(T\) from \(L^1_+(M)\) to \(L^1(M)\)?
- 语言：en；目标提示：L5；压力：hard；学生回答质量：wrong
- 最终阶段：HINT；掌握度：未掌握

**导师 第 1 回合**

你问的是这个条件在扩张过程中起什么作用。先不急着给结论——请你看检索片段 p.176 里 \(T(k)\) 与 \(T(k)\) 的定义式，告诉我：这两个式子分别是对 \(h\) 取上确界还是下确界，以及它们各自限制在哪个集合上？

**导师 第 2 回合（施压：hard）**

理解你的着急，但按规则我不能直接跳到结论。给你一个更低的提示：

请看 p.176 中 \(T(k)\) 和 \(T(k)\) 的定义式，注意两件事——它们分别对 \(h\) 取的是 inf 还是 sup，以及 \(h\) 被限制在哪个集合里。先只回答我一个问题：这两个定义式里，\(h\) 的取值范围是同一个集合吗？

**导师 第 3 回合**

没关系，猜错也是进展。我们把问题再缩小一点，只盯住 p.176 的那一行：

\(T(k) \equiv \inf_{h \geqslant k,\, h \in L^1_+} T(h)\)，以及 \(T(k) \equiv \sup_{h \geqslant k,\, h \in L^1_+} T(h)\)。

只问一个问题：这两个式子里，\(h\) 的取值范围写的是同一个东西吗？

---
