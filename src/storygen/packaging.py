"""PACKAGING-001: the pure parts of building the Microsoft Store package; scripts/build_store.py drives them."""
import ast
import hashlib
import json
import os
import re
import shutil
import tomllib
from importlib.metadata import PackageNotFoundError, distribution, distributions
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from . import skill_bundles
from .build_edition import parse_build_edition
from .self_check import CHECK_NAMES

EXTRAS = ('web', 'publication', 'local-tokens', 'desktop', 'mcp')
# Distributions whose wheel carries no licence file: SPDX id and where the text lives. A new one stops the build.
# Licence texts for distributions whose wheel carries none (tokenizers: its own licence and the Rust crates compiled
# into it), as <normalised name>-<version>.txt relative to the checkout; scripts/tokenizers_notices.py writes them.
BUNDLED_LICENSES = Path('store_build/licenses')
# Always named in the notices: the freezer's bootloader is part of the executable.
ALWAYS_NOTICED = ('pyinstaller',)
# GPL-family distributions accepted only with exactly these declared licence texts (PACKAGING-001-S06).
_GPL2_CLASSIFIER = 'License :: OSI Approved :: GNU General Public License v2 (GPLv2)'
COPYLEFT_EXCEPTIONS: dict[str, tuple[frozenset[str], str]] = {
    'pyinstaller': (
        frozenset({'GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute '
                   'non-free programs (including commercial ones)', _GPL2_CLASSIFIER}),
        'Bootloader Exception (COPYING.txt): only the bootloader and related files are included in the build'),
    'pyinstaller-hooks-contrib': (
        frozenset({'License :: OSI Approved :: Apache Software License', _GPL2_CLASSIFIER}),
        'runtime hooks included in the build are under Apache-2.0 (LICENSE, section Runtime hooks)'),
}
# Files the standard library of some interpreters reads at run time and the freezer does not collect.
VENDOR_RUNTIME_FILES = ('codex-rejected-cas.pem',)
# Not part of the main executable: the MCP bridge (frozen separately, STORE-MCP) and anything only tests use.
EXCLUDED_MODULES = ('storygen.mcp', 'mcp', 'pytest', '_pytest')
TEST_MODULES = ('pytest', '_pytest')
# STORE-MCP: the console bridge next to Obscura.exe, with its own contents folder so the two never share `_internal`.
BRIDGE_NAME = 'obscura-mcp'
BRIDGE_CONTENTS = '_mcp'
BRIDGE_ENTRY = 'from storygen.mcp.bridge import main\n\nmain()\n'
_LICENSE_NAME = re.compile(r'^(licen[cs]e|copying|notice|copyright|unlicense|authors)([-_.][^\\/]*)?$', re.IGNORECASE)
ASSETS = {'StoreLogo.png': 50, 'Square44x44Logo.png': 44, 'Square150x150Logo.png': 150}
PACKAGE_DIR = 'src/storygen'
MAX_VERSION_PART = 65535


def _normal(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def edition_marker(edition: str, report_url: str = '', support_url: str = '', waitlist_url: str = '') -> str:
    """JSON of the build edition marker, validated in memory by the same rules the application applies."""
    data = {'edition': edition, 'report_url': report_url, 'support_url': support_url, 'waitlist_url': waitlist_url}
    text = json.dumps({key: value for key, value in data.items() if value or key == 'edition'}, ensure_ascii=False)
    parse_build_edition(text)
    return text


def root_requirements(pyproject: Path, extras=EXTRAS) -> list[str]:
    """Requirements of the project itself, read from the checkout (an installed copy may be older)."""
    project = tomllib.loads(Path(pyproject).read_text(encoding='utf-8'))['project']
    optional = project.get('optional-dependencies', {})
    return list(project.get('dependencies', [])) + [item for extra in extras for item in optional[extra]]


def dependency_closure(requirements, *, lookup=None) -> list[str]:
    """Normalised names of every installed distribution the requirements pull in, markers evaluated for this system."""
    from packaging.requirements import Requirement
    lookup = lookup or (lambda name: distribution(name).requires or [])
    seen, todo = {}, [(Requirement(text), frozenset()) for text in requirements]
    while todo:
        requirement, parent_extras = todo.pop()
        environments = [{'extra': extra} for extra in parent_extras] or [{'extra': ''}]
        if requirement.marker and not any(requirement.marker.evaluate(environment) for environment in environments):
            continue
        name, extras = _normal(requirement.name), frozenset(requirement.extras)
        if name in seen and extras <= seen[name]:
            continue
        seen[name] = seen.get(name, frozenset()) | extras
        try:
            children = lookup(requirement.name)
        except PackageNotFoundError:
            raise ValueError(f'Dependency is not installed: {requirement.name}') from None
        todo += [(Requirement(text), seen[name]) for text in children]
    return sorted(seen)


def toc_sources(work: Path) -> list[Path]:
    """Source paths of everything the freezer put into the build, read from its own records (*.toc)."""
    found = set()

    def walk(node):
        if isinstance(node, tuple) and len(node) == 3 and all(isinstance(part, str) for part in node):
            found.add(node[1])
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
    records = sorted(Path(work).rglob('*.toc'))
    if not records:
        raise ValueError(f'No PyInstaller records (*.toc) in {work}')
    for record in records:
        walk(ast.literal_eval(record.read_text(encoding='utf-8')))
    return [Path(item) for item in sorted(found) if item]


def bundled_distributions(sources, *, installed=None) -> list[str]:
    """Names of the installed distributions that own the bundled files; files of no distribution are skipped
    (the interpreter itself, the checkout)."""
    owners = {}
    for dist in (installed if installed is not None else distributions()):
        for item in dist.files or []:
            owners[os.path.normcase(os.path.abspath(dist.locate_file(item)))] = _normal(dist.metadata['Name'])
    names = {owners[key] for key in (os.path.normcase(os.path.abspath(path)) for path in sources) if key in owners}
    return sorted(names - {'storygen'})


def _license_files(dist) -> list:
    """Licence files of a distribution: what lies under *.dist-info/licenses/, or carries a licence name there."""
    found = []
    for item in dist.files or []:
        parts = Path(str(item)).parts
        if not parts or not parts[0].endswith('.dist-info'):
            continue
        if (len(parts) > 2 and parts[1] == 'licenses') or (len(parts) == 2 and _LICENSE_NAME.match(parts[1]) and not parts[1].endswith('.py')):
            found.append(item)
    return found


def _bundled_license(name: str, dist, licenses_dir: Path | None) -> Path | None:
    if licenses_dir is None:
        return None
    path = Path(licenses_dir) / f'{_normal(name)}-{dist.version}.txt'
    return path if path.is_file() else None


def missing_licenses(names, *, lookup=distribution, licenses_dir: Path | None = None) -> list[str]:
    missing = []
    for name in names:
        dist = lookup(name)
        if not _license_files(dist) and _bundled_license(name, dist, licenses_dir) is None:
            missing.append(name)
    return missing


def copyleft_distributions(names, *, lookup=distribution) -> list[str]:
    """Distributions under a GPL-family licence (GPL, LGPL, AGPL): the build must not contain them (PACKAGING-001-S03).

    A COPYLEFT_EXCEPTIONS entry passes only while its declared licence texts match exactly."""
    found = []
    for name in names:
        metadata = lookup(name).metadata
        classifiers = metadata.get_all('Classifier') if hasattr(metadata, 'get_all') else metadata.get('Classifier', [])
        declared = [metadata.get('License-Expression') or '', metadata.get('License') or '']
        declared += [item for item in classifiers or [] if item.startswith('License ::')]
        declared = frozenset(text for text in declared if text)
        exception = COPYLEFT_EXCEPTIONS.get(_normal(name))
        if exception is not None:
            # A listed distribution passes only with the reviewed declaration; any change needs a new review.
            if declared != exception[0]:
                found.append(name)
            continue
        if any('GPL' in text.upper() for text in declared):
            found.append(name)
    return found


def third_party_notices(names, *, lookup=distribution, runtime_license: str = '', licenses_dir: Path | None = None) -> str:
    """A distribution without licence files takes `<licenses_dir>/<name>-<version>.txt`; without that file the build stops."""
    copyleft = copyleft_distributions(names, lookup=lookup)
    if copyleft:
        raise ValueError('Library with a GPL-family licence in the build: ' + ', '.join(copyleft))
    missing = missing_licenses(names, lookup=lookup, licenses_dir=licenses_dir)
    if missing:
        raise ValueError('No licence text for: ' + ', '.join(f'{name} {lookup(name).version}' for name in missing))
    parts = ['Obscura Text Writer — third-party notices\n',
             'This build includes the following components. Each is distributed under its own licence, reproduced below.\n']
    if runtime_license:
        parts.append(f"\n{'=' * 78}\nPython runtime and the libraries distributed with it\n{'-' * 78}\n{runtime_license.strip()}\n")
    for name in names:
        dist = lookup(name)
        declared = dist.metadata.get('License-Expression') or ((dist.metadata.get('License') or '').strip().splitlines() or [''])[0]
        header = f"\n{'=' * 78}\n{dist.metadata['Name']} {dist.version}\nLicence: {declared or 'see the text below'}\n"
        files = _license_files(dist)
        if not files:
            bundled = _bundled_license(name, dist, licenses_dir)
            parts.append(header + f"{'-' * 78}\n{bundled.read_text(encoding='utf-8').strip()}\n")
            continue
        parts.append(header)
        for item in files:
            text = Path(dist.locate_file(item)).read_text(encoding='utf-8', errors='replace').strip()
            parts.append(f"{'-' * 78}\n{Path(str(item)).name}\n\n{text}\n")
    return ''.join(parts)


def plugin_files(root: Path, tracked) -> list[str]:
    """STORE-MCP: the Claude plugin files shipped in `claude\\` next to Obscura.exe — tracked files under the user part
    of the marketplace only (no evals, no stray drafts), as sorted POSIX paths relative to `root` (`integrations/claude`).

    Raises ValueError when the plugin manifest is missing or a skill cannot become a self-contained bundle."""
    files = sorted({rel for rel in tracked if rel.startswith(skill_bundles.USER_FILES) and (root / rel).is_file()})
    if 'obscura/.claude-plugin/plugin.json' not in files:
        raise ValueError('the Claude plugin has no obscura/.claude-plugin/plugin.json')
    # Check the skills as they will ship: on a copy of the tracked files only, so an untracked reference fails here and an
    # untracked draft skill does not.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='obscura-plugin-') as staging:
        for rel in files:
            target = Path(staging) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / rel, target)
        plugin = Path(staging) / 'obscura'
        for skill in skill_bundles.skill_names(plugin):
            skill_bundles.bundle_files(plugin, skill)
    return files


def vendor_runtime_files(python_lib: Path) -> list[Path]:
    """Files next to ssl.py that this interpreter's standard library needs when frozen; empty for stock CPython."""
    return [Path(python_lib) / name for name in VENDOR_RUNTIME_FILES if (Path(python_lib) / name).is_file()]


def package_data_manifest(root: Path, version: str, tracked) -> dict:
    """Version and SHA-256 of every tracked data file of the package, keyed by its path inside the package."""
    package = Path(root) / PACKAGE_DIR
    files = {}
    for item in sorted(tracked):
        path = Path(root) / item
        if path.suffix == '.py' or not path.is_file():
            continue
        files[path.relative_to(package).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not files:
        raise ValueError('No package data files found in the working copy')
    return {'version': version, 'files': files}


def stray_data_files(frozen_package: Path, manifest: dict, allowed=()) -> list[str]:
    """Files in the frozen package folder that are not tracked data of the checkout: they must not be published."""
    known = set(manifest['files']) | set(allowed)
    return sorted(path.relative_to(frozen_package).as_posix() for path in Path(frozen_package).rglob('*')
                  if path.is_file() and path.relative_to(frozen_package).as_posix() not in known)


def pyinstaller_args(entry: Path, name: str, dist: Path, work: Path, source: Path) -> list[str]:
    arguments = ['--noconfirm', '--onedir', '--noconsole', '--noupx', '--name', name, '--distpath', str(dist),
                 '--workpath', str(work), '--specpath', str(work), '--paths', str(source),
                 '--collect-data', 'storygen', '--collect-submodules', 'storygen',
                 '--hidden-import', 'keyring.backends.Windows']
    for module in EXCLUDED_MODULES:
        arguments += ['--exclude-module', module]
    return arguments + [str(entry)]


def bridge_pyinstaller_args(entry: Path, dist: Path, work: Path, source: Path) -> list[str]:
    """STORE-MCP: a console onedir build of the stdio bridge (a windowed executable has no stdin/stdout)."""
    arguments = ['--noconfirm', '--onedir', '--noupx', '--name', BRIDGE_NAME, '--contents-directory', BRIDGE_CONTENTS,
                 '--distpath', str(dist), '--workpath', str(work), '--specpath', str(work), '--paths', str(source),
                 '--hidden-import', 'storygen.mcp.bridge']
    for module in TEST_MODULES:
        arguments += ['--exclude-module', module]
    return arguments + [str(entry)]


def check_report(report, edition: str, version: str) -> list[str]:
    """Reasons why the built application is not fit to package; empty when it is."""
    if not isinstance(report, dict) or not isinstance(report.get('checks'), list) or \
            not all(isinstance(check, dict) and isinstance(check.get('name'), str) for check in report['checks']):
        return ['the self-check report is missing or damaged']
    reasons = [f"check {check['name']}: {check.get('detail')}" for check in report['checks'] if check.get('ok') is not True]
    ran = [check['name'] for check in report['checks']]
    if ran != CHECK_NAMES:
        reasons.append('the report has the wrong set of checks: missing ' + (', '.join(name for name in CHECK_NAMES if name not in ran) or 'nothing')
                       + '; extra or repeated: ' + (', '.join(name for name in ran if name not in CHECK_NAMES or ran.count(name) > 1) or 'none'))
    if report.get('frozen') is not True:
        reasons.append('the self-check did not run in a frozen build')
    if report.get('edition') != edition:
        reasons.append(f"the edition mark did not reach the build: expected {edition}, the app reports {report.get('edition')}")
    if report.get('version') != version:
        reasons.append(f"the app version does not match the project version: expected {version}, the app reports {report.get('version')}")
    if report.get('ok') is not True and not reasons:
        reasons.append('the self-check failed')
    return reasons


def package_version(project_version: str) -> str:
    """Version of the MSIX package: three numeric parts of the project plus the fourth, which the Store reserves as 0."""
    parts = project_version.split('.') if project_version else []
    valid = 1 <= len(parts) <= 4 and all(part.isascii() and part.isdigit() and (part == '0' or not part.startswith('0'))
                                         and int(part) <= MAX_VERSION_PART for part in parts)
    if not valid or (len(parts) == 4 and parts[3] != '0'):
        raise ValueError(f'The MSIX package version must consist of numbers 0–65535, and the fourth part must be 0: {project_version!r}')
    return '.'.join((parts + ['0', '0', '0'])[:4])


def appx_manifest(*, identity_name: str, publisher: str, publisher_display_name: str, version: str,
                  description: str, display_name: str = 'Obscura Text Writer', executable: str = 'Obscura.exe',
                  bridge_executable: str | None = BRIDGE_NAME + '.exe') -> str:
    q = quoteattr
    # STORE-MCP: an execution alias gives chat clients a path that survives updates (the package folder does not).
    extensions = '' if bridge_executable is None else f'''
      <Extensions>
        <uap3:Extension Category="windows.appExecutionAlias" Executable={q(bridge_executable)} EntryPoint="Windows.FullTrustApplication">
          <uap3:AppExecutionAlias>
            <desktop:ExecutionAlias Alias={q(bridge_executable)} />
          </uap3:AppExecutionAlias>
        </uap3:Extension>
      </Extensions>'''
    return f'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:uap3="http://schemas.microsoft.com/appx/manifest/uap/windows10/3"
         xmlns:desktop="http://schemas.microsoft.com/appx/manifest/desktop/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap uap3 desktop rescap">
  <Identity Name={q(identity_name)} Publisher={q(publisher)} Version={q(version)} ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>{escape(display_name)}</DisplayName>
    <PublisherDisplayName>{escape(publisher_display_name)}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Resources>
    <Resource Language="uk-UA" />
    <Resource Language="en-US" />
  </Resources>
  <Applications>
    <Application Id="Obscura" Executable={q(executable)} EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName={q(display_name)} Description={q(description)} BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png" />{extensions}
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
'''


def find_makeappx(explicit: str | None = None) -> Path:
    if explicit:
        # A path given on purpose is never silently replaced by another tool found elsewhere.
        if not Path(explicit).is_file():
            raise ValueError(f'makeappx.exe not found at the given path: {explicit}')
        return Path(explicit)
    for candidate in (os.environ.get('MAKEAPPX'), shutil.which('makeappx')):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise ValueError('makeappx.exe not found. It ships in the Microsoft.Windows.SDK.BuildTools package (nuget.org) and in the Windows SDK; '
                     'give its path with the --makeappx argument or the MAKEAPPX variable.')
