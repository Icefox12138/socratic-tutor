from html.parser import HTMLParser
import re

path = r"D:\Guo-Code\socratic-tutor\docs\visual\project.html"
s = open(path, encoding="utf-8").read()


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.err = []

    def handle_starttag(self, tag, attrs):
        if tag not in ("meta", "br", "hr", "img", "link", "input"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.err.append((tag, self.stack[-1] if self.stack else None))
        else:
            self.stack.pop()


p = P()
p.feed(s)
print("chars", len(s))
print("open_left", p.stack[:8])
print("errors", p.err[:8])
print("sections", len(re.findall(r'<section id="', s)))
print("nav_links", len(re.findall(r'<a href="#', s)))
print("has_charset", 'charset="utf-8"' in s)
