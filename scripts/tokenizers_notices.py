"""Write the licence notices of tokenizers and the Rust crates compiled into it (PACKAGING-001-S08).

The tokenizers wheel carries no licence file but has a CycloneDX SBOM of what was compiled into it. The script
takes the required crates.io crates from that SBOM, downloads each `.crate` archive from static.crates.io, checks
it against the SBOM SHA-256 and reads the licence files at the archive root in memory: nothing is unpacked to disk
and no crate code runs. The crate built from the tokenizers repository takes its LICENSE from the matching GitHub
tag. A crate without licence files stops the script unless MANUAL names its text and the reason.

Run again whenever tokenizers is updated:
    python scripts/tokenizers_notices.py --out store_build/licenses/tokenizers-<version>.txt
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.request
from importlib.metadata import distribution
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = 'registry+https://github.com/rust-lang/crates.io-index#'
CRATE_URL = 'https://static.crates.io/crates/{name}/{name}-{version}.crate'
TOKENIZERS_LICENSE_URL = 'https://raw.githubusercontent.com/huggingface/tokenizers/v{version}/LICENSE'
_LICENSE_NAME = re.compile(r'^(licen[cs]e|copying|notice|copyright|unlicense)([-_.][^\\/]*)?$', re.IGNORECASE)
_CODE = ('.rs', '.py', '.toml')
TIMEOUT = 60

_DEFMT_MIT = '''Copyright (c) Ferrous Systems

Permission is hereby granted, free of charge, to any
person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the
Software without restriction, including without
limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software
is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice
shall be included in all copies or substantial portions
of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF
ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.'''

# Crates whose archive has no licence file: name -> (licence text, reason).
MANUAL: dict[str, tuple[str, str]] = {
    'defmt-parser': (_DEFMT_MIT, 'MIT OR Apache-2.0 per Cargo.toml; the archive has no licence file, so this is '
                                 'LICENSE-MIT of the same repository (knurling-rs/defmt) from the defmt 1.1.1 crate'),
}


class Crate(NamedTuple):
    name: str
    version: str
    sha256: str
    licence: str


def _licence(component: dict) -> str:
    return ' AND '.join(item.get('expression') or item.get('license', {}).get('id', '') for item in component.get('licenses', []))


def crates_from_sbom(sbom: dict) -> list[Crate]:
    """Required crates.io components (build-only tools are `excluded` in the SBOM)."""
    found = []
    for item in sbom.get('components', []):
        if item.get('scope') == 'required' and item.get('bom-ref', '').startswith(REGISTRY):
            sha = next((h['content'] for h in item.get('hashes', []) if h.get('alg') == 'SHA-256'), '')
            found.append(Crate(item['name'], item['version'], sha, _licence(item)))
    if not found:
        raise ValueError('У SBOM немає жодного crate зі scope=required з crates.io: перелік неповний або SBOM пошкоджений')
    return sorted(found)


def path_crates(sbom: dict) -> list[tuple[str, str, str]]:
    """Required crates built from the tokenizers repository itself (not from crates.io)."""
    return sorted((item['name'], item['version'], _licence(item)) for item in sbom.get('components', [])
                  if item.get('scope') == 'required' and item.get('bom-ref', '').startswith('path+'))


def verified(data: bytes, sha256: str, label: str) -> bytes:
    if hashlib.sha256(data).hexdigest() != sha256.lower():
        raise ValueError(f'Контрольна сума архіву не збігається з SBOM: {label}')
    return data


def license_texts(archive: bytes, top: str) -> dict[str, str]:
    """Licence files directly in the archive's top folder, read in memory."""
    texts = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as crate:
        for member in crate.getmembers():
            parts = member.name.split('/')
            if (member.isfile() and len(parts) == 2 and parts[0] == top and _LICENSE_NAME.match(parts[1])
                    and not parts[1].lower().endswith(_CODE)):
                texts[parts[1]] = crate.extractfile(member).read().decode('utf-8', errors='replace').strip()
    return dict(sorted(texts.items()))


def section_texts(name: str, version: str, texts: dict[str, str], *, manual=MANUAL) -> dict[str, str]:
    if texts:
        return texts
    if name in manual:
        text, reason = manual[name]
        return {f'manual: {reason}': text}
    raise ValueError(f'Немає файлів ліцензії в архіві й запису в MANUAL: {name} {version}')


def render(root_licence: str, sections) -> str:
    """`sections`: (name, version, declared licence, {file: text}); a text met before is referred to, not repeated."""
    parts = [root_licence.strip() + '\n']
    seen: dict[str, str] = {}
    for name, version, licence, texts in sections:
        parts.append(f"\n{'=' * 78}\n{name} {version}\nLicence: {licence}\n")
        for file, text in texts.items():
            if text in seen:
                parts.append(f"{'-' * 78}\n{file}: same text as {seen[text]}\n")
            else:
                seen[text] = f'{name} {version}'
                parts.append(f"{'-' * 78}\n{file}\n\n{text}\n")
    return ''.join(parts)


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={'User-Agent': 'obscura-build-notices'})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def _installed_sbom() -> tuple[str, dict]:
    dist = distribution('tokenizers')
    files = [item for item in dist.files or [] if '/sboms/' in str(item).replace('\\', '/')]
    if len(files) != 1:
        raise ValueError('У встановленому tokenizers немає рівно одного SBOM')
    return dist.version, json.loads(Path(dist.locate_file(files[0])).read_text(encoding='utf-8'))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    version, sbom = _installed_sbom()
    root_licence = _fetch(TOKENIZERS_LICENSE_URL.format(version=version)).decode('utf-8')
    header = (f'tokenizers {version}\nLicence: Apache-2.0 (the tokenizers code, including the crates built from its '
              f'repository: {", ".join(f"{n} {v}" for n, v, _ in path_crates(sbom))})\n\n{root_licence}')
    sections, problems = [], []
    crates = crates_from_sbom(sbom)
    for number, crate in enumerate(crates, 1):
        label = f'{crate.name} {crate.version}'
        print(f'[{number}/{len(crates)}] {label}', file=sys.stderr)
        try:
            data = verified(_fetch(CRATE_URL.format(name=crate.name, version=crate.version)), crate.sha256, label)
            texts = section_texts(crate.name, crate.version, license_texts(data, f'{crate.name}-{crate.version}'))
        except ValueError as error:
            problems.append(str(error))
            continue
        sections.append((crate.name, crate.version, crate.licence, texts))
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(render(header, sections).encode('utf-8'))
    print(f'{args.out}: tokenizers {version}, {len(sections)} crates', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
