"""WAITLIST-001 on the site: the builder renders the waitlist form (S07), the publish gate (S10)."""
import json

import pytest

from scripts import check_site
from scripts.build_site import TURNSTILE_SCRIPT, build
from tests.test_docs_site import ROOT, make_site

ACTION='https://waitlist.obscurawriter.com/'
TEST_KEY='1x00000000000000000000AA'
PRIVACY={'uk':'# Приватність\n\n## Список очікування\n\nАдреса.\n','en':'# Privacy\n\n## Waitlist\n\nAddress.\n'}


def waitlist_site(root,form='waitlist',section=None,privacy=None):
    """make_site plus a `paid` page with the form and a `privacy` page, pairs confirmed."""
    site=make_site(root)
    for lang in ['uk','en']:
        (site/lang/'paid.md').write_text('# Платна версія\n' if lang=='uk' else '# Paid version\n',encoding='utf-8')
        (site/lang/'privacy.md').write_text((privacy or PRIVACY)[lang],encoding='utf-8')
    manifest=json.loads((site/'site.json').read_text(encoding='utf-8'))
    paid={'slug':'paid','title':{'uk':'Платна версія','en':'Paid version'}}
    if form is not None:paid['form']=form
    manifest['pages']+=[paid,{'slug':'privacy','title':{'uk':'Приватність','en':'Privacy'}}]
    if section!='missing':manifest['waitlist']=section or {'action':ACTION,'sitekey':TEST_KEY}
    (site/'site.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
    for page in manifest['pages']:check_site.rehash(root,page['slug'])
    return site


def read(path):return path.read_text(encoding='utf-8')


@pytest.mark.req('WAITLIST-001')
def test_s07_form_only_on_the_form_page(tmp_path):
    waitlist_site(tmp_path);out=tmp_path/'_site'
    build(tmp_path,out)
    for lang,prefix,anchor in [('uk','','список-очікування'),('en','en/','waitlist')]:
        page=read(out/f'{prefix}paid.html')
        assert f'action="{ACTION}"' in page and f'data-sitekey="{TEST_KEY}"' in page and TURNSTILE_SCRIPT in page
        assert f'name="lang" value="{lang}"' in page
        for state in ['ok','invalid','captcha','error']:assert f'id="waitlist-{state}"' in page
        assert f'href="privacy.html#{anchor}"' in page and 'mailto:privacy@obscurawriter.com' in page and '<noscript>' in page
        other=read(out/f'{prefix}install.html')
        assert 'challenges.cloudflare.com' not in other and 'waitlist-form' not in other


@pytest.mark.req('WAITLIST-001')
def test_s07_other_pages_unchanged_by_the_form(tmp_path):
    waitlist_site(tmp_path/'with');waitlist_site(tmp_path/'without',form=None)
    build(tmp_path/'with',tmp_path/'a');build(tmp_path/'without',tmp_path/'b')
    for name in ['install.html','privacy.html','en/install.html','en/privacy.html']:
        assert (tmp_path/'a'/name).read_bytes()==(tmp_path/'b'/name).read_bytes(),name
    assert 'challenges.cloudflare.com' not in read(tmp_path/'b/paid.html')


@pytest.mark.req('WAITLIST-001')
@pytest.mark.parametrize('form,section',[
    ('waitlist','missing'),
    ('waitlist',{'action':'http://waitlist.obscurawriter.com/','sitekey':TEST_KEY}),
    ('waitlist',{'action':ACTION,'sitekey':'a b'}),
    ('other',None),
])
def test_s07_bad_waitlist_section_stops_the_build(tmp_path,form,section):
    waitlist_site(tmp_path,form=form,section=section)
    with pytest.raises(ValueError,match='site.json'):build(tmp_path,tmp_path/'_site')


@pytest.mark.req('WAITLIST-001')
def test_s07_missing_privacy_anchor_fails_the_check(tmp_path):
    waitlist_site(tmp_path)
    assert check_site.check(tmp_path)==[]
    (tmp_path/'docs/site/en/privacy.md').write_text('# Privacy\n\n## Mailing list\n\nAddress.\n',encoding='utf-8')
    check_site.rehash(tmp_path,'privacy')
    errors=check_site.check(tmp_path)
    assert any('privacy.html#waitlist (en)' in error for error in errors),errors


REAL_KEY='0x4AAAAAAAexampleexample'
DATABASE='01234567-89ab-cdef-0123-456789abcdef'
WRANGLER=(ROOT/'workers/waitlist/wrangler.toml').read_text(encoding='utf-8')


def publishable(root,sitekey=REAL_KEY,database=DATABASE,origins='https://obscurawriter.com'):
    """A waitlist site with base_url and a copy of wrangler.toml carrying the given values."""
    site=waitlist_site(root,section={'action':ACTION,'sitekey':sitekey})
    manifest=json.loads((site/'site.json').read_text(encoding='utf-8'))
    manifest['base_url']='https://obscurawriter.com/'
    (site/'site.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
    text=WRANGLER.replace('database_id = "REPLACE_WITH_DATABASE_ID"',f'database_id = "{database}"')
    text=text.replace('ALLOWED_ORIGINS = "https://obscurawriter.com"',f'ALLOWED_ORIGINS = "{origins}"')
    (root/'workers/waitlist').mkdir(parents=True,exist_ok=True)
    (root/'workers/waitlist/wrangler.toml').write_text(text,encoding='utf-8')


@pytest.mark.req('WAITLIST-001')
def test_s10_placeholders_block_publication(tmp_path):
    publishable(tmp_path,sitekey='REPLACE_WITH_SITEKEY',database='REPLACE_WITH_DATABASE_ID')
    problems=check_site.publication_problems(tmp_path)
    assert len(problems)==2 and any('sitekey' in p for p in problems) and any('database_id' in p for p in problems),problems
    publishable(tmp_path/'test-key',sitekey=TEST_KEY)
    problems=check_site.publication_problems(tmp_path/'test-key')
    assert len(problems)==1 and 'sitekey' in problems[0],problems


@pytest.mark.req('WAITLIST-001')
def test_s10_localhost_origin_blocks_publication(tmp_path):
    publishable(tmp_path,origins='https://obscurawriter.com,http://localhost:8000')
    problems=check_site.publication_problems(tmp_path)
    assert len(problems)==1 and 'ALLOWED_ORIGINS' in problems[0],problems


@pytest.mark.req('WAITLIST-001')
def test_s10_ready_site_publishes(tmp_path,monkeypatch,capsys):
    publishable(tmp_path)
    assert check_site.publication_problems(tmp_path)==[]
    monkeypatch.setattr(check_site,'ROOT',tmp_path)
    assert check_site.main(['--publish'])==0
    assert 'Сайт готовий до публікації.' in capsys.readouterr().out
    publishable(tmp_path/'bad',sitekey='REPLACE_WITH_SITEKEY')
    monkeypatch.setattr(check_site,'ROOT',tmp_path/'bad')
    assert check_site.main(['--publish'])==1
