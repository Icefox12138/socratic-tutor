"""TEDS (Tree-Edit-Distance-based Similarity) for table extraction.

Two variants:
  teds        text-aware; a cell relabel costs 1 - normalized Levenshtein similarity
  teds_struct structure-only; every cell label is the same, text ignored

Trees follow the usual TEDS shape: table -> row -> cell, cells are leaves.
colspan/rowspan are NOT part of the tree (both parsers only agree on them
partly, and TEDS as published scores the row/cell structure).
"""
import re
import unicodedata
from html.parser import HTMLParser


class Node:
    __slots__ = ("kind", "text", "children")

    def __init__(self, kind, text="", children=None):
        self.kind = kind
        self.text = text
        self.children = children or []

    def __repr__(self):
        return "Node(%s,%r,%d)" % (self.kind, self.text[:12], len(self.children))


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = None
        self.stack = []
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            node = Node("table")
            self.root = node
            self.stack = [node]
        elif tag == "tr" and self.stack:
            node = Node("row")
            self.stack[-1].children.append(node)
            self.stack.append(node)
        elif tag in ("td", "th") and self.stack:
            node = Node("cell")
            self.stack[-1].children.append(node)
            self.stack.append(node)
            self._cell = node

    def handle_endtag(self, tag):
        if tag in ("td", "th", "tr", "table"):
            if len(self.stack) > 1:
                self.stack.pop()
            if tag in ("td", "th"):
                self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.text += data


def parse_html(html):
    parser = _TableParser()
    parser.feed(html or "")
    return parser.root or Node("table")


def grid_to_tree(rows):
    """Rows of strings -> tree with no spans."""
    root = Node("table")
    for row in rows:
        r = Node("row")
        root.children.append(r)
        for cell in row:
            r.children.append(Node("cell", "" if cell is None else str(cell)))
    return root


def odl_to_tree(table):
    """ODL table dict (rows of cells with row/column/spans) -> tree."""
    root = Node("table")
    for row in table.get("rows") or []:
        r = Node("row")
        root.children.append(r)
        for cell in row:
            r.children.append(Node("cell", str(cell.get("text") or "")))
    return root


def postorder(root):
    nodes = []

    def walk(n):
        for c in n.children:
            walk(c)
        nodes.append(n)

    walk(root)
    return nodes


def lmd_map(nodes):
    """Leftmost leaf descendant, as an index into the postorder list."""
    index = {id(n): i for i, n in enumerate(nodes)}
    lmd = []
    for n in nodes:
        cur = n
        while cur.children:
            cur = cur.children[0]
        lmd.append(index[id(cur)])
    return lmd, index


def _zs(nodes_a, nodes_b, relabel):
    lmd_a, _ = lmd_map(nodes_a)
    lmd_b, _ = lmd_map(nodes_b)
    n, m = len(nodes_a), len(nodes_b)
    tree = {}
    INF = float("inf")

    def keyroots(lmd):
        # A keyroot is the highest postorder node carrying a given leftmost
        # leaf: a parent's lmd equals its leftmost child's, so the LAST node
        # with that lmd is the subtree root, not the leaf itself.
        last = {}
        for idx, leaf in enumerate(lmd):
            last[leaf] = idx
        return sorted(last.values())

    keyroots_a = keyroots(lmd_a)
    keyroots_b = keyroots(lmd_b)

    def forest(i, j):
        li, lj = lmd_a[i], lmd_b[j]
        fd = {}
        fd[(li - 1, lj - 1)] = 0
        for x in range(li, i + 1):
            fd[(x, lj - 1)] = fd[(x - 1, lj - 1)] + 1
        for y in range(lj, j + 1):
            fd[(li - 1, y)] = fd[(li - 1, y - 1)] + 1
        for x in range(li, i + 1):
            for y in range(lj, j + 1):
                if lmd_a[x] == li and lmd_b[y] == lj:
                    cost = min(
                        fd[(x - 1, y - 1)] + relabel(nodes_a[x], nodes_b[y]),
                        fd[(x - 1, y)] + 1,
                        fd[(x, y - 1)] + 1,
                    )
                    fd[(x, y)] = cost
                    tree[(x, y)] = cost
                else:
                    fd[(x, y)] = min(
                        fd[(x - 1, y)] + 1,
                        fd[(x, y - 1)] + 1,
                        fd[(lmd_a[x] - 1, lmd_b[y] - 1)] + tree[(x, y)],
                    )

    for i in keyroots_a:
        for j in keyroots_b:
            forest(i, j)
    return tree.get((n - 1, m - 1), INF)


def _norm(text):
    t = unicodedata.normalize("NFKC", text or "")
    t = re.sub(r"[^0-9A-Za-z\u3400-\u9fff\u0370-\u03ff\u1f00-\u1fff]", "", t)
    return t.lower()


def _lev(a, b):
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _sim(a, b):
    a, b = _norm(a), _norm(b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return 1.0 - _lev(a, b) / max(len(a), len(b))


def similarity(gold_root, pred_root, struct=False):
    """TEDS in [0, 1]; 1.0 means identical trees."""
    ga, pa = postorder(gold_root), postorder(pred_root)
    if not ga or not pa:
        return 0.0
    if not pred_root.children:  # no rows at all: nothing matched
        return 0.0

    if struct:
        def relabel(a, b):
            return 0.0 if a.kind == b.kind else 1.0
    else:
        def relabel(a, b):
            if a.kind != b.kind:
                return 1.0
            if a.kind == "cell":
                return 1.0 - _sim(a.text, b.text)
            return 0.0

    dist = _zs(ga, pa, relabel)
    return max(0.0, 1.0 - dist / max(len(ga), len(pa)))


def tree_size(root):
    return len(postorder(root))
