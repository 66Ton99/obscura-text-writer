"""Obscura's Claude skills, generated from the one plugin source for every client.

`integrations/claude/obscura/` is the only source. Claude Code reads it as a plugin from a local marketplace;
Claude Desktop gets one ZIP per skill, self-contained, with the shared rules copied in; any other MCP client gets
the same texts through the bridge's `get_guide`. Names coming from a client are checked against the lists read
from disk and are never joined into a path.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

USER_FILES: tuple[str, ...] = ('.claude-plugin/', 'obscura/.claude-plugin/', 'obscura/shared/', 'obscura/skills/')
RULES = 'rules'
_ROOT_REF = re.compile(r'\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`)]+)')
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


class BundleError(ValueError):
    """The plugin cannot be turned into a bundle or guide as asked."""


def user_files(source: Path) -> list[str]:
    """Marketplace files a user gets (no tools, no evals), as sorted POSIX paths relative to `source`."""
    found = []
    for path in source.rglob('*'):
        if path.is_file():
            rel = path.relative_to(source).as_posix()
            if rel.startswith(USER_FILES):
                found.append(rel)
    return sorted(found)


def marketplace_source(*, frozen: bool, executable: Path, checkout: Path) -> Path | None:
    """The marketplace folder: next to the packaged exe, or `integrations/claude` in a source checkout."""
    source = executable.parent/'claude' if frozen else checkout/'integrations'/'claude'
    return source if (source/'.claude-plugin'/'marketplace.json').is_file() else None


def plugin_root(source: Path | None) -> Path | None:
    if source is None:
        return None
    plugin = source/'obscura'
    return plugin if (plugin/'.claude-plugin'/'plugin.json').is_file() else None


def skill_names(plugin: Path) -> list[str]:
    return sorted(p.parent.name for p in (plugin/'skills').glob('*/SKILL.md'))


def _check_skill(plugin: Path, skill: str) -> Path:
    names = skill_names(plugin)
    if skill not in names:
        raise BundleError(f'Невідомий скіл «{skill}». Допустимі: {", ".join(names)}')
    return plugin/'skills'/skill


def _own_references(plugin: Path, skill: str) -> dict[str, Path]:
    folder = _check_skill(plugin, skill)/'references'
    refs = {p.stem: p for p in folder.glob('*.md')} if folder.is_dir() else {}
    refs[RULES] = plugin/'shared'/'rules.md'
    return refs


def _rewrite(plugin: Path, skill: str, source: str, text: str, target) -> str:
    """Replace every `${CLAUDE_PLUGIN_ROOT}/...` with `target(reference_name)`; anything else is an error."""
    own = f'skills/{skill}/references/'

    def replace(match: re.Match) -> str:
        path = match.group(1)
        if path == 'shared/rules.md':
            return target(RULES)
        if path.startswith(own) and path.endswith('.md') and '/' not in path[len(own):]:
            name = path[len(own):-3]
            if (plugin/'skills'/skill/'references'/f'{name}.md').is_file():
                return target(name)
        raise BundleError(f'{source}: посилання {match.group(0)} веде поза скіл; дозволено лише shared/rules.md '
                          f'і skills/{skill}/references/*.md')

    return _ROOT_REF.sub(replace, text)


def bundle_files(plugin: Path, skill: str) -> dict[str, str]:
    """A self-contained skill folder for Claude Desktop: `<skill>/SKILL.md` and `<skill>/references/*.md`."""
    folder = _check_skill(plugin, skill)
    refs = _own_references(plugin, skill)

    def target(name: str) -> str:
        return f'references/{name}.md'

    files = {}
    for path in sorted(folder.rglob('*')):
        if path.is_file():
            rel = path.relative_to(folder).as_posix()
            files[f'{skill}/{rel}'] = _rewrite(plugin, skill, f'{skill}/{rel}', path.read_text(encoding='utf-8'), target)
    files[f'{skill}/references/{RULES}.md'] = refs[RULES].read_text(encoding='utf-8')
    return files


def desktop_zip(plugin: Path, skill: str) -> bytes:
    """The skill's ZIP for Claude Desktop upload; the same plugin gives the same bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, text in sorted(bundle_files(plugin, skill).items()):
            info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, text.encode('utf-8'))
    return buffer.getvalue()


def guide_references(plugin: Path, skill: str) -> list[str]:
    return sorted(_own_references(plugin, skill))


def guide_text(plugin: Path, skill: str) -> str:
    """SKILL.md for a client without the skills: plugin paths point to `get_guide` references instead."""
    path = _check_skill(plugin, skill)/'SKILL.md'

    def target(name: str) -> str:
        return f'get_guide(task="{skill}", reference="{name}")'

    return _rewrite(plugin, skill, f'{skill}/SKILL.md', path.read_text(encoding='utf-8'), target)


def guide_reference(plugin: Path, skill: str, name: str) -> str:
    refs = _own_references(plugin, skill)
    if name not in refs:
        raise BundleError(f'Невідома довідка «{name}» для «{skill}». Допустимі: {", ".join(sorted(refs))}')
    text = refs[name].read_text(encoding='utf-8')

    def target(ref: str) -> str:
        return f'get_guide(task="{skill}", reference="{ref}")'

    return text if name == RULES else _rewrite(plugin, skill, f'{skill}/references/{name}.md', text, target)
