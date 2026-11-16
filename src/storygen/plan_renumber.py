"""SCENE-RENUMBER: the scene number in the first non-empty plan line, rewritten digits only."""
import re

_NUMBER = re.compile(r'(?i)^([ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?(?:Сцена|Scene)[ \t]+)(\d+)([.:][ \t]*.+)$')


def renumber_plan(text: str, number: int) -> str:
    """The plan with the number of its first non-empty line set to `number`; any other text is returned unchanged."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        body = line.rstrip('\r\n')
        match = _NUMBER.match(body)
        if not match or int(match[2]) == number:
            return text
        lines[index] = match[1] + str(number) + match[3] + line[len(body):]
        return ''.join(lines)
    return text
