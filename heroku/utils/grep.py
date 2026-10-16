import html
from html.parser import HTMLParser


class _RichGrepParser(HTMLParser):
    _blocks = {
        "p", "div", "section", "article", "header", "footer", "aside",
        "h1", "h2", "h3", "h4", "h5", "h6", "details", "summary",
        "blockquote", "pre", "ul", "ol", "li", "table", "tr",
        "figure", "figcaption", "tg-math-block",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = [[]]
        self.emoji_id = None
        self.hidden = 0

    def _break(self):
        if self.lines[-1]:
            self.lines.append([])

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if self.hidden:
            return
        attrs = dict(attrs)
        if tag in self._blocks or tag in {"br", "hr"}:
            self._break()
        elif tag in {"td", "th"} and self.lines[-1]:
            self.lines[-1].append(("\t", None))
        elif tag in {"emoji", "tg-emoji"}:
            self.emoji_id = attrs.get("emoji-id") or attrs.get("id")
        elif tag == "img":
            src = attrs.get("src", "")
            if src.startswith("tg://emoji?id="):
                emoji_id = src.removeprefix("tg://emoji?id=").split("&", 1)[0]
                self.lines[-1].append((attrs.get("alt", ""), emoji_id))

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag in self._blocks:
            self._break()
        elif tag in {"emoji", "tg-emoji"}:
            self.emoji_id = None

    def handle_data(self, data):
        if self.hidden:
            return
        for index, part in enumerate(data.splitlines(keepends=True)):
            text = part.rstrip("\r\n")
            if text:
                self.lines[-1].append((text, self.emoji_id))
            if part.endswith(("\r", "\n")):
                self._break()


def filter_rich_lines(source: str, include: str, exclude: str) -> list[str]:
    parser = _RichGrepParser()
    parser.feed(source)
    parser.close()
    result = []
    for chunks in parser.lines:
        visible = "".join(text for text, _ in chunks)
        if not visible.strip():
            continue
        if include and include not in visible:
            continue
        if exclude and exclude in visible:
            continue

        matches = []
        start = 0
        while include and (start := visible.find(include, start)) >= 0:
            matches.append((start, start + len(include)))
            start += len(include)
        rendered = []
        offset = 0
        for text, emoji_id in chunks:
            pieces = []
            cursor = 0
            for start, end in matches:
                left, right = max(0, start - offset), min(len(text), end - offset)
                if left < right:
                    pieces.append(html.escape(text[cursor:left], quote=False))
                    pieces.append("<u>" + html.escape(text[left:right], quote=False) + "</u>")
                    cursor = right
            pieces.append(html.escape(text[cursor:], quote=False))
            body = "".join(pieces)
            if emoji_id and emoji_id.isdecimal():
                body = f'<tg-emoji emoji-id="{emoji_id}">{body}</tg-emoji>'
            rendered.append(body)
            offset += len(text)
        result.append("".join(rendered))
    return result
