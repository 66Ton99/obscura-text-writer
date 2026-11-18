"""scripts/tokenizers_notices.py (PACKAGING-001-S08): licences of the Rust crates compiled into tokenizers."""
import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('tokenizers_notices', ROOT / 'scripts' / 'tokenizers_notices.py')
tn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tn)

REGISTRY = 'registry+https://github.com/rust-lang/crates.io-index#'


def component(ref, name, version, scope='required', licence='MIT', sha='ab' * 32):
    return {'bom-ref': ref, 'name': name, 'version': version, 'scope': scope,
            'hashes': [{'alg': 'SHA-256', 'content': sha}], 'licenses': [{'expression': licence}]}


def test_crates_from_sbom_take_required_registry_crates_only():
    sbom = {'components': [
        component(REGISTRY + 'ahash@0.8.12', 'ahash', '0.8.12', licence='MIT OR Apache-2.0'),
        component(REGISTRY + 'cc@1.4.4', 'cc', '1.4.4', scope='excluded'),
        component('path+file:///D:/a/tokenizers/tokenizers/tokenizers#0.23.2', 'tokenizers', '0.23.2', licence='Apache-2.0'),
    ]}
    assert tn.crates_from_sbom(sbom) == [tn.Crate('ahash', '0.8.12', 'ab' * 32, 'MIT OR Apache-2.0')]
    assert tn.path_crates(sbom) == [('tokenizers', '0.23.2', 'Apache-2.0')]


def test_sbom_without_crates_is_refused():
    with pytest.raises(ValueError, match='SBOM'):
        tn.crates_from_sbom({})
    with pytest.raises(ValueError, match='SBOM'):
        tn.crates_from_sbom({'components': [component(REGISTRY + 'cc@1.4.4', 'cc', '1.4.4', scope='excluded')]})


def crate_archive(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, text in files.items():
            data = text.encode('utf-8')
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_license_texts_take_root_licence_files_only():
    archive = crate_archive({'demo-1.0/LICENSE-MIT': 'MIT text', 'demo-1.0/COPYRIGHT': 'Copyright text',
                             'demo-1.0/sub/LICENSE': 'nested', 'demo-1.0/src/license.rs': 'code', 'demo-1.0/Cargo.toml': 'x'})
    assert tn.license_texts(archive, 'demo-1.0') == {'COPYRIGHT': 'Copyright text', 'LICENSE-MIT': 'MIT text'}


def test_crate_without_licence_files_needs_a_manual_entry():
    with pytest.raises(ValueError, match='bare 1.0'):
        tn.section_texts('bare', '1.0', {}, manual={})
    assert tn.section_texts('bare', '1.0', {}, manual={'bare': ('MIT text', 'reason')}) == {'manual: reason': 'MIT text'}
    assert tn.section_texts('ok', '1.0', {'LICENSE': 'x'}, manual={}) == {'LICENSE': 'x'}


def test_archive_with_another_hash_is_refused():
    data = b'crate bytes'
    assert tn.verified(data, hashlib.sha256(data).hexdigest(), 'demo 1.0') == data
    with pytest.raises(ValueError, match='demo 1.0'):
        tn.verified(data, '00' * 32, 'demo 1.0')


def test_render_prints_identical_texts_once():
    text = tn.render('APACHE ROOT', [('alpha', '1.0', 'MIT', {'LICENSE': 'identical licence body'}),
                                     ('beta', '2.0', 'MIT', {'LICENSE': 'identical licence body'})])
    assert text.startswith('APACHE ROOT')
    assert text.count('identical licence body') == 1
    assert 'alpha 1.0' in text and 'beta 2.0' in text and 'same text as alpha 1.0' in text
