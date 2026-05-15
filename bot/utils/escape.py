import re


def escape_mdv2(text) -> str | None:
    """ Escape str in MarkdownV2 syntax or return None if None is provided """
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text)) if text is not None else None
