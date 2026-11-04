# D0 preflight 报告

- 时间：2026-10-29 16:39:53
- 根目录：`D:\Guo-Code`

## 1. 根目录与规模

| 根 | 存在 | PDF 数 | GB |
|---|---:|---:|---:|
| library | 是 | 801 | 27.46 |
| steadman | 是 | 100 | 0.75 |
| loeb | 是 | 2 | 0.7 |
| teubner | 是 | 2 | 0.01 |

## 2. 哈希抽样

- 文件数：801；唯一：800；重复组：1；耗时：4.4 s
- 清单：`eval/p0/catalog/hash-manifest.jsonl`
- 重复示例：[['中国文史哲\\新编诸子集成\\32【新编诸子集成】法言义疏（汪荣宝.撰.／陈仲夫.点校） (1).pdf', '中国文史哲\\新编诸子集成\\32【新编诸子集成】法言义疏（汪荣宝.撰.／陈仲夫.点校）.pdf']]

## 3. 磁盘与环境

- D: 可用 468.7 GB（要求 ≥300 GB）：PASS
- Python 3.14.7；uv=uv 0.12.5 (210d1f678 2026-08-14 x86_64-pc-windows-msvc)；DSH=0.2.1-rc.3
- PyMuPDF=2.0；rapidfuzz=3.14.6；SQLite FTS5=True

## 4. 20 本样本可用性

| 样本 | 命中 | 首个文件 |
|---|---:|---|
| A1_princeton | 1 | Princeton calculus Reader (revised edition) - 普林斯顿微积分读本（修订版） -- 阿德里安_班纳 (Adrian Banner) -- 图灵数学·统计学丛书, 修订版, 2016 -- 北京：人民邮电出版社 -- isbn13 9787115435590 -- 9cf6315c3fc942d1088e27865bb325f8 -- Anna’s Archive.pdf |
| A2_lishangzhi | 1 | 线性代数 _ 数学专业用 = Linear algebra -- 李尚志编著; 李尚志 -- 普通高等教育“十五”国家级规划教材, 2006 -- 北京：高等教育出版社 -- isbn13 9787040198706 -- 46290bfe7a1543b3edb553b41139d44f -- Anna’s Archive.pdf |
| A3_cprimer | 1 | Primer C++(第5版).pdf |
| A4_berkeley | 5 | （第1卷）：力学.pdf |
| B1_lenin2 | 1 | 列宁选集第二卷.pdf |
| B2_republic | 1 | A0401理想国.pdf |
| B3_luxun01 | 1 | 鲁迅全集  第01卷 坟 热风 呐喊.pdf |
| B4_capital | 1 | 资本论第一卷（马恩全集中文第一版）.pdf |
| C1_shiji | 1 | 01001.点校本二十四史精装版.史记.一.卷一至卷七.纪[汉]司马迁撰.中华书局2013.pdf |
| C2_shisanjing | 1 | 01.周易正義（全一冊）.pdf |
| C3_tongjian | 20 | 01.资治通鉴.一.卷一威烈王二十三年戊寅起至七秦二世皇帝元年壬辰止[宋]司马光编著[元]胡三省音注.中华书局2013.pdf |
| C4_jinyong | 10 | 金庸作品集01.书剑恩仇录01.明河,1981.pdf |
| K1_apology | 2 | platos-apology__apology.04jan25.pdf |
| K2_vergil | 3 | ap-vergil-usa__collegevergil.04jan25.pdf |
| K3_herodotus | 2 | files-herodotus__her1-transsheets.pdf |
| K4_livy | 2 | livy__Livy.Bk1_.10Oct26.pdf |
| K5_loeb_plato | 1 | greek_L036_plato.pdf |
| K6_loeb_vergil | 1 | latin_L063N_vergil.pdf |
| K7_teubner_conte | 1 | conte_aeneis.pdf |
| K8_teubner_west | 1 | west_ilias1.pdf |

## 5. 页数基线

- 来源：prior probe；文件 801；总页数 361862

## 判定

**PASS**

## 6. 备注与后续

- 页数基线抽检 3 本（史记 358、理想国 459、Princeton 673）与 prior probe 一致；总页数 361,862 可信。
- 重复组：新编诸子集成《法言义疏》两份完全相同；D3 只保留一份，另一份标 `redundant`。
- K3/K4 的 glob 命中包含 worksheet；D3 建 manifest 时必须选 commentary 文件（如 `files-herodotus__hero*.pdf`、`livy__Livy*.pdf`）。
- 20 本样本全部命中；下一步 D1–D2：`capability-probe`（独立 `tutor` profile，测 8 项 API）。
