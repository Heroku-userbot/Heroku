import base64
import html


def _escape(value) -> str:
    return html.escape(str(value), quote=False)


def _attribute(value) -> str:
    return html.escape(str(value), quote=True)


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _escape(value)

    name = type(value).__name__
    if name == "TextEmpty":
        return ""
    if name == "TextPlain":
        return _escape(getattr(value, "text", ""))
    if name == "TextConcat":
        return "".join(_text(item) for item in getattr(value, "texts", []))
    if name == "TextWithEntities":
        return _escape(getattr(value, "text", ""))

    tags = {
        "TextBold": ("<b>", "</b>"),
        "TextItalic": ("<i>", "</i>"),
        "TextUnderline": ("<u>", "</u>"),
        "TextStrike": ("<s>", "</s>"),
        "TextFixed": ("<code>", "</code>"),
        "TextSubscript": ("<sub>", "</sub>"),
        "TextSuperscript": ("<sup>", "</sup>"),
        "TextMarked": ("<mark>", "</mark>"),
        "TextSpoiler": ("<tg-spoiler>", "</tg-spoiler>"),
    }
    if name in tags:
        start, end = tags[name]
        return start + _text(getattr(value, "text", None)) + end

    if name in {"TextUrl", "TextAutoUrl"}:
        url = getattr(value, "url", None) or getattr(value, "text", "")
        return f'<a href="{_attribute(url)}">{_text(getattr(value, "text", None))}</a>'
    if name in {"TextEmail", "TextAutoEmail"}:
        email = getattr(value, "email", None) or getattr(value, "text", "")
        return f'<a href="mailto:{_attribute(email)}">{_text(getattr(value, "text", None))}</a>'
    if name in {"TextPhone", "TextAutoPhone"}:
        phone = getattr(value, "phone", None) or getattr(value, "text", "")
        return f'<a href="tel:{_attribute(phone)}">{_text(getattr(value, "text", None))}</a>'
    if name == "TextMentionName":
        return f'<a href="tg://user?id={_attribute(getattr(value, "user_id", ""))}">{_text(value.text)}</a>'
    if name == "TextMention":
        return _text(getattr(value, "text", None))
    if name in {"TextHashtag", "TextCashtag", "TextBotCommand", "TextBankCard"}:
        return _text(getattr(value, "text", None))
    if name == "TextCustomEmoji":
        return f'<tg-emoji emoji-id={_attribute(getattr(value, "document_id", ""))}>{_escape(getattr(value, "alt", ""))}</tg-emoji>'
    if name == "TextImage":
        return f'<i>[image:{_attribute(getattr(value, "document_id", ""))}]</i>'
    if name == "TextMath":
        return f"<tg-math>{_escape(getattr(value, 'source', ''))}</tg-math>"
    if name == "TextDate":
        date = getattr(value, "date", None)
        unix = int(date.timestamp()) if hasattr(date, "timestamp") else (date or 0)
        fmt = "".join(
            letter
            for field, letter in (
                ("relative", "r"),
                ("day_of_week", "w"),
                ("short_date", "d"),
                ("long_date", "D"),
                ("short_time", "t"),
                ("long_time", "T"),
            )
            if getattr(value, field, False)
        )
        attributes = f' format="{fmt}"' if fmt else ""
        return f'<tg-time unix="{unix}"{attributes}>{_text(getattr(value, "text", None))}</tg-time>'
    if name == "TextAnchor":
        return f'<a name="{_attribute(getattr(value, "name", ""))}">{_text(getattr(value, "text", None))}</a>'
    if name == "TextDiff":
        return _text(getattr(value, "text", None))
    if name == "TextButton":
        return _button(value)

    nested = getattr(value, "text", None)
    if nested is not None:
        return _text(nested)
    return _escape(getattr(value, "source", ""))


def _caption(value) -> str:
    if value is None:
        return ""
    text = _text(getattr(value, "text", None))
    credit = _text(getattr(value, "credit", None))
    if credit:
        return f"{text}<cite>{credit}</cite>" if text else f"<cite>{credit}</cite>"
    return text


def _media(name: str, value) -> str:
    media_id = getattr(value, f"{name}_id", "")
    caption = _caption(getattr(value, "caption", None))
    marker = f"<i>[{name}:{_attribute(media_id)}]</i>"
    return marker + caption


def _blocks(items) -> str:
    return "\n".join(rendered for rendered in (_block(item) for item in items) if rendered)


def _list_item(value) -> str:
    name = type(value).__name__
    if name in {"PageListItemBlocks", "PageListOrderedItemBlocks"}:
        text = _blocks(getattr(value, "blocks", []))
    else:
        text = _text(getattr(value, "text", None))
    if getattr(value, "checkbox", False):
        text = f'<input type="checkbox"{" checked" if getattr(value, "checked", False) else ""}>' + text
    attributes = []
    if name == "PageListOrderedItemBlocks" or name == "PageListOrderedItemText":
        number = getattr(value, "num", None)
        if number is None:
            number = getattr(value, "value", None)
        if number is not None:
            attributes.append(f' value="{_attribute(number)}"')
        if getattr(value, "type", None):
            attributes.append(f' type="{_attribute(value.type)}"')
    return f"<li{''.join(attributes)}>{text}</li>"


def _table_cell(value) -> str:
    tag = "th" if getattr(value, "header", False) else "td"
    attributes = []
    for field, attribute in (("colspan", "colspan"), ("rowspan", "rowspan")):
        value_ = getattr(value, field, None)
        if value_:
            attributes.append(f' {attribute}="{_attribute(value_)}"')
    if getattr(value, "align_center", False):
        attributes.append(' align="center"')
    elif getattr(value, "align_right", False):
        attributes.append(' align="right"')
    if getattr(value, "valign_middle", False):
        attributes.append(' valign="middle"')
    elif getattr(value, "valign_bottom", False):
        attributes.append(' valign="bottom"')
    return f"<{tag}{''.join(attributes)}>{_text(getattr(value, 'text', None))}</{tag}>"


def _button(value) -> str:
    text = _text(getattr(value, "text", None))
    button_type = getattr(value, "type", None)
    type_name = type(button_type).__name__
    attributes = []
    if type_name == "InlineButtonTypeUrl":
        attributes = ["type=\"url\"", f"url=\"{_attribute(getattr(button_type, 'url', ''))}\""]
    elif type_name == "InlineButtonTypeCallback":
        data = getattr(button_type, "data", b"")
        if isinstance(data, (bytes, bytearray, memoryview)):
            data = base64.urlsafe_b64encode(bytes(data)).decode()
        attributes = ["type=\"callback_data\"", f"data=\"{_attribute(data)}\""]
    elif type_name == "InlineButtonTypeSwitchInline":
        query = _attribute(getattr(button_type, "query", ""))
        tag = "switch_inline_query_current_chat" if getattr(button_type, "same_peer", False) else "switch_inline_query"
        attributes = [f"type=\"{tag}\"", f"query=\"{query}\""]
        chats = {
            "InlineQueryPeerTypePM": "allow-user-chats",
            "InlineQueryPeerTypeBotPM": "allow-bot-chats",
            "InlineQueryPeerTypeChat": "allow-group-chats",
            "InlineQueryPeerTypeMegagroup": "allow-group-chats",
            "InlineQueryPeerTypeBroadcast": "allow-channel-chats",
        }
        allowed = list(dict.fromkeys(
            chats[type(item).__name__]
            for item in getattr(button_type, "peer_types", None) or []
            if type(item).__name__ in chats
        ))
        if allowed:
            attributes[0] = "type=\"switch_inline_query_chosen_chat\""
            attributes += allowed
    elif type_name == "InlineButtonTypeWebView":
        attributes = ["type=\"web_app\"", f"url=\"{_attribute(getattr(button_type, 'url', ''))}\""]
    elif type_name == "InlineButtonTypeCopy":
        attributes = ["type=\"copy_text\"", f"text=\"{_attribute(getattr(button_type, 'copy_text', ''))}\""]
    elif type_name == "InlineButtonTypeUrlAuth":
        attributes = ["type=\"login_url\"", f"url=\"{_attribute(getattr(button_type, 'url', ''))}\""]
        if getattr(button_type, "fwd_text", None):
            attributes.append(f"forward-text=\"{_attribute(button_type.fwd_text)}\"")
    elif type_name == "InlineButtonTypeUserProfile":
        attributes = ["type=\"url\"", f"url=\"tg://user?id={_attribute(getattr(button_type, 'user_id', ''))}\""]
    else:
        attributes = ["type=\"disabled\""]
    style = getattr(getattr(value, "style", None), "__dict__", {})
    for key in ("bg_primary", "bg_danger", "bg_success", "link"):
        if style.get(key):
            attributes.append(f"style=\"{key.removeprefix('bg_')}\"")
            break
    return f"<tg-button {' '.join(attributes)}>{text}</tg-button>"


def _block(value) -> str:
    if value is None:
        return ""

    name = type(value).__name__
    text = _text(getattr(value, "text", None))
    simple = {
        "PageBlockTitle": "h1",
        "PageBlockSubtitle": "h2",
        "PageBlockHeading1": "h1",
        "PageBlockHeading2": "h2",
        "PageBlockHeading3": "h3",
        "PageBlockHeading4": "h4",
        "PageBlockHeading5": "h5",
        "PageBlockHeading6": "h6",
        "PageBlockHeader": "h3",
        "PageBlockSubheader": "h4",
        "PageBlockKicker": None,
        "PageBlockParagraph": "p",
        "PageBlockFooter": "footer",
    }
    if name in simple:
        tag = simple[name]
        return text if tag is None else f"<{tag}>{text}</{tag}>"
    if name == "PageBlockPreformatted":
        language = _attribute(getattr(value, "language", ""))
        return f'<pre><code class="language-{language}">{text}</code></pre>'
    if name == "PageBlockDivider":
        return "<hr>"
    if name == "PageBlockAnchor":
        return f'<a name="{_attribute(getattr(value, "name", ""))}"></a>'
    if name in {"PageBlockBlockquote", "PageBlockPullquote"}:
        caption = _caption(getattr(value, "caption", None))
        tag = "aside" if name == "PageBlockPullquote" else "blockquote"
        expandable = " expandable" if getattr(value, "collapsed", False) else ""
        return f"<{tag}{expandable}>{text}{f'<cite>{caption}</cite>' if caption else ''}</{tag}>"
    if name == "PageBlockBlockquoteBlocks":
        blocks = _blocks(getattr(value, "blocks", []))
        return f"<blockquote>{blocks}{_caption(getattr(value, 'caption', None))}</blockquote>"
    if name in {"PageBlockPhoto", "PageBlockVideo", "PageBlockAudio", "PageBlockDocument"}:
        return _media(name.removeprefix("PageBlock").lower(), value)
    if name == "PageBlockMap":
        geo = getattr(value, "geo", None)
        caption = _caption(getattr(value, "caption", None))
        if geo is None:
            return caption
        zoom = f' zoom="{_attribute(value.zoom)}"' if getattr(value, "zoom", None) else ""
        map_tag = f'<tg-map lat="{_attribute(geo.lat)}" long="{_attribute(geo.long)}"{zoom}/>'
        return f"<figure>{map_tag}<figcaption>{caption}</figcaption></figure>" if caption else map_tag
    if name == "PageBlockButtonRow":
        buttons = "".join(_button(item) for item in getattr(value, "buttons", []))
        align = next((a for a in ("left", "center", "right") if getattr(value, f"align_{a}", False)), None)
        align = f' align="{align}"' if align else ""
        return f"<tg-button-row{align}>{buttons}</tg-button-row>"
    if name in {"PageBlockCollage", "PageBlockSlideshow"}:
        return "".join(_block(item) for item in getattr(value, "items", [])) + _caption(getattr(value, "caption", None))
    if name == "PageBlockTable":
        title = _text(getattr(value, "title", None)) if getattr(value, "title", None) else ""
        flags = "".join(f" {flag}" for flag in ("bordered", "striped", "compact") if getattr(value, flag, False))
        rows = "".join(
            "<tr>" + "".join(_table_cell(cell) for cell in getattr(row, "cells", [])) + "</tr>"
            for row in getattr(value, "rows", [])
        )
        caption = f"<caption>{title}</caption>" if title else ""
        return f"<table{flags}>{caption}{rows}</table>"
    if name in {"PageBlockList", "PageBlockOrderedList"}:
        tag = "ol" if name.endswith("OrderedList") else "ul"
        attributes = ""
        if tag == "ol":
            if getattr(value, "reversed", False):
                attributes += " reversed"
            if getattr(value, "start", None) is not None:
                attributes += f' start="{_attribute(value.start)}"'
            if getattr(value, "type", None):
                attributes += f' type="{_attribute(value.type)}"'
        items = "".join(_list_item(item) for item in getattr(value, "items", []))
        return f"<{tag}{attributes}>{items}</{tag}>"
    if name == "PageBlockDetails":
        title = _text(getattr(value, "title", None))
        blocks = _blocks(getattr(value, "blocks", []))
        return f"<details{' open' if getattr(value, 'open', False) else ''}><summary>{title}</summary>{blocks}</details>"
    if name == "PageBlockMath":
        return f"<tg-math-block>{_escape(getattr(value, 'source', ''))}</tg-math-block>"
    if name == "PageBlockThinking":
        return f"<tg-thinking>{text}</tg-thinking>"
    if name == "PageBlockEmbed":
        url = getattr(value, "url", None)
        return f'<a href="{_attribute(url)}">{_escape(getattr(value, "html", "") or url or "[embed]")}</a>' if url else _escape(getattr(value, "html", "[embed]"))
    if name == "PageBlockEmbedPost":
        return _blocks(getattr(value, "blocks", [])) + _caption(getattr(value, "caption", None))
    if name == "PageBlockRelatedArticles":
        return _text(getattr(value, "title", None))
    if name == "PageBlockAuthorDate":
        return _text(getattr(value, "author", None))
    if name in {"PageBlockChannel", "PageBlockCover", "PageBlockUnsupported"}:
        return f"<i>[{_escape(name)}]</i>"
    nested = getattr(value, "blocks", None)
    if nested is not None:
        return _blocks(nested)
    return text if text else f"<i>[{_escape(name)}]</i>"


def rich_message_to_html(rich_message) -> str:
    if rich_message is None:
        return ""
    return "\n".join(
        rendered
        for rendered in (_block(item) for item in getattr(rich_message, "blocks", []))
        if rendered
    )


def install_rich_message_support():
    from herokutl.tl.custom.message import Message

    if getattr(Message, "_heroku_rich_message_support", False):
        return

    original_text = Message.text
    original_raw_text = Message.raw_text

    def get_rich(self):
        native = getattr(self, "rich_message", None)
        return rich_message_to_html(native) if native is not None else None

    def get_text(self):
        rich = get_rich(self)
        return rich if rich is not None else original_text.fget(self)

    def get_raw_text(self):
        rich = get_rich(self)
        return rich if rich is not None else original_raw_text.fget(self)

    Message.rich = property(get_rich)
    Message.text = property(get_text, original_text.fset)
    Message.raw_text = property(get_raw_text, original_raw_text.fset)
    Message._heroku_rich_message_support = True


install_rich_message_support()
