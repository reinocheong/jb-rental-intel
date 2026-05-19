"""FB UI noise cleaning utilities."""
import re

def clean_post_text(text):
    """Remove Facebook UI noise from raw textContent."""
    if not text:
        return ""

    # ── 1. Cut at reaction summary ──
    m = re.search(r'所有心情[：:]\s*\d+', text)
    if m and m.start() > 40:
        text = text[:m.start()]
    if len(text) > 150:
        m = re.search(r'\d+条评论', text)
        if m and m.start() > 40:
            text = text[:m.start()]

    # ── 2. Strip header noise (agent name + FB metadata prefix) ──
    text = re.sub(r'火速回复\s*', '', text)
    text = re.sub(r'·\s*关注\s*', '', text)
    text = re.sub(r'·\s*\d+\s*分钟\s*', '', text)
    text = re.sub(r'·\s*\d+\s*小时\s*', '', text)
    text = re.sub(r'·\s*\d+\s*天\s*', '', text)
    text = re.sub(r'·\s*分享对象[：:]\s*公开小组\s*', '', text)
    text = re.sub(r'·\s*分享对象[：:]\s*所有朋友\s*', '', text)
    # Strip time attached to agent name (no leading ·): "Fion Foo34分钟" → "Fion Foo"
    text = re.sub(r'([\u4e00-\u9fffA-Za-z])\d+\s*(?:分钟|小时|天|周|月)\s*', r'\1 ', text)
    # Clean standalone time/datestamp after agent name
    text = re.sub(r'^\s*\d+[月天周]\d+[日号]?\s*', '', text)
    text = re.sub(r'^\s*\d+\s*分钟\s*', '', text)
    text = re.sub(r'^\s*\d+\s*小时\s*', '', text)

    # ── 3. Strip footer noise (trailing UI fragments) ──
    # Identity: "以 Reino Cheong 的身份评论" — support names with spaces
    text = re.sub(r'\s*以\s+[\s\S]+?\s+的身份\s*(?:评论|回答)\s*$', '', text)
    # Interaction bar: "发消息531赞评论分享" / "发消息赞评论分享"
    text = re.sub(r'\s*发消息\s*\d*\s*赞\s*(?:评论|回复)\s*分享\s*\d*\s*$', '', text)
    text = re.sub(r'\s*赞\s*(?:评论|回复)\s*分享\s*\d*\s*$', '', text)
    text = re.sub(r'\s*赞回复分享\s*\d*\s*$', '', text)
    # "全部N条回复"
    text = re.sub(r'\s*全部\s*\d+\s*条回复\s*$', '', text)
    # "展开+NMYR 815,000 · Location" / "收起+NMYR ..." (mid-text, not just end)
    text = re.sub(r'\s*…?\s*展开\s*\+?\d*\s*(?:MYR|RM|US\$)\s*[\d,]+\s*·\s*[^·]+', '', text)
    text = re.sub(r'\s*…?\s*收起\s*\+?\d*\s*(?:MYR|RM|US\$)\s*[\d,]+\s*·\s*[^·]+', '', text)
    # Also catch bare "展开+N" / "收起+N" without location
    text = re.sub(r'\s*…?\s*展开\s*\+?\d*\s*(?:MYR|RM|US\$)?\s*[\d,]+', '', text)
    text = re.sub(r'\s*…?\s*收起\s*\+?\d*\s*(?:MYR|RM|US\$)?\s*[\d,]+', '', text)
    # Lone "展开" / "收起" at end
    text = re.sub(r'\s*展开\s*$', '', text)
    text = re.sub(r'\s*收起\s*$', '', text)
    # Time suffixes: "25周" / "12周赞回复分享已编辑"
    text = re.sub(r'\s*\d+\s*[周天月年]\s*(?:赞回复分享已编辑)?\s*$', '', text)
    text = re.sub(r'\s*\d+\s*(?:分钟|小时|秒)\s*$', '', text)

    # ── 4. Mid-text noise ──
    # "· 分享对象： 公开小组" appearing mid-text (after header already stripped)
    text = re.sub(r'·\s*分享对象[：:]\s*公开小组\s*', '', text)
    text = re.sub(r'·\s*分享对象[：:]\s*所有朋友\s*', '', text)

    # Collapse multiple spaces
    text = re.sub(r'\s{2,}', ' ', text)

    return text.strip()
