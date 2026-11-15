"""Build the bilingual user-guide site from docs/site into a static directory (#29, DOCS-SITE).

No network and no model calls. Ukrainian pages go to the root, English ones to en/.
Links between pages are relative, so the built tree works from any folder. With `base_url` in the manifest
the pages also carry canonical, hreflang and Open Graph tags, and robots.txt, sitemap.xml and 404.html are written.
The output directory is written over, not emptied: build into a fresh directory (CI does) for an exact tree.
"""
import argparse
import html
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.site_common import IMAGES, LABELS, SITE, heading_id, heading_text, load_manifest, page_path, page_slug

ROOT=Path(__file__).resolve().parents[1]


def is_external(href):return bool(urlsplit(href).scheme) or href.startswith('//')


def rewrite_href(href,slugs):
    """`<slug>.md[#anchor]` inside the manifest becomes `<slug>.html[#anchor]`; everything else is unchanged."""
    if is_external(href) or href.startswith('#'):return href
    path,_,fragment=href.partition("#");path,fragment=unquote(path),unquote(fragment)
    slug=page_slug(path,slugs)
    if slug:return slug+'.html'+(f'#{fragment}' if fragment else '')
    return href


def image_target(root,source,src,lang):
    """Map an image path relative to the markdown file onto the copied images/ directory."""
    if is_external(src):return src
    resolved=(source.parent/src).resolve()
    images=(Path(root)/IMAGES).resolve()
    if not resolved.is_relative_to(images):return src
    prefix='' if lang=='uk' else '../'
    return prefix+'images/'+resolved.relative_to(images).as_posix()


def markdown():
    """CommonMark + tables; raw HTML is escaped, so every link goes through the checker."""
    return MarkdownIt('commonmark',{'html':False}).enable('table')


def render(root,lang,slug,slugs):
    md=markdown()
    source=page_path(root,lang,slug)
    tokens=md.parse(source.read_text(encoding='utf-8'))
    seen={}
    for index,token in enumerate(tokens):
        if token.type=='heading_open':token.attrSet('id',heading_id(heading_text(tokens[index+1]),seen))
        for child in token.children or []:
            if child.type=='link_open':child.attrSet('href',rewrite_href(child.attrGet('href') or '',slugs))
            elif child.type=='image':child.attrSet('src',image_target(root,source,child.attrGet('src') or '',lang))
    return md.renderer.render(tokens,md.options,{})


LOCALES={'uk':'uk_UA','en':'en_US'}


def site_base_url(manifest):
    """The public address of the site (`base_url`), or None for a build without one (tests, local previews)."""
    url=manifest.get('base_url')
    if url is None:return None
    if not isinstance(url,str) or not url.startswith('https://') or not url.endswith('/') or any(ch.isspace() for ch in url) or not urlsplit(url).hostname:
        raise ValueError('site.json: base_url має бути адресою https://<хост>/ зі скісною рискою в кінці')
    return url


def public_url(base,lang,slug):
    """Absolute address of a page; the index of each language is its folder."""
    return base+('' if lang=='uk' else 'en/')+('' if slug=='index' else f'{slug}.html')


def head_meta(manifest,lang,slug,title):
    """Description, canonical, hreflang alternates (x-default: English) and Open Graph tags, one per line."""
    esc=lambda value:html.escape(value,quote=True)
    description=(manifest.get('description') or {}).get(lang)
    base=site_base_url(manifest);lines=[]
    if description:lines.append(f'<meta name="description" content="{esc(description)}">')
    if base:
        other='en' if lang=='uk' else 'uk'
        lines+=[f'<link rel="canonical" href="{esc(public_url(base,lang,slug))}">',
                *(f'<link rel="alternate" hreflang="{code}" href="{esc(public_url(base,code,slug))}">' for code in ('uk','en')),
                f'<link rel="alternate" hreflang="x-default" href="{esc(public_url(base,"en",slug))}">',
                '<meta property="og:type" content="website">','<meta property="og:site_name" content="Obscura Text Writer">',
                f'<meta property="og:title" content="{esc(title)}">',f'<meta property="og:url" content="{esc(public_url(base,lang,slug))}">',
                f'<meta property="og:locale" content="{LOCALES[lang]}">',f'<meta property="og:locale:alternate" content="{LOCALES[other]}">']
        if description:lines.append(f'<meta property="og:description" content="{esc(description)}">')
    return ''.join(line+'\n' for line in lines)


def page_html(template,manifest,lang,slug,content):
    pages=manifest['pages'];base='' if lang=='uk' else '../'
    titles={page['slug']:page['title'][lang] for page in pages}
    nav='\n'.join(f'<li><a href="{page["slug"]}.html"'+(' aria-current="page"' if page['slug']==slug else '')+f'>{html.escape(titles[page["slug"]])}</a></li>' for page in pages)
    other='en' if lang=='uk' else 'uk'
    switch_href=f'en/{slug}.html' if lang=='uk' else f'../{slug}.html'
    # data-lang: site.js remembers a language picked here, so it wins over the browser languages.
    switch=f'<span>{LABELS[lang]["name"]}</span><a href="{switch_href}" hreflang="{other}" lang="{other}" data-lang="{other}">{LABELS[other]["name"]}</a>'
    home='index.html' if 'index' in titles else f'{pages[0]["slug"]}.html'
    values={'lang':lang,'title':html.escape(titles[slug]),'base':base,'home':home,'switch':switch,'nav':nav,'alt':switch_href,
            'meta':head_meta(manifest,lang,slug,f'{titles[slug]} · Obscura Text Writer'),
            'content':content,'nav_label':LABELS[lang]['nav'],'lang_label':LABELS[lang]['lang']}
    content=values.pop('content');out=template
    for key,value in values.items():out=out.replace('{'+key+'}',value)
    return out.replace('{content}',content)  # last: page text may contain literal {placeholders}


def build(root=ROOT,out=None):
    root=Path(root);out=Path(out) if out else root/'_site'
    if out.resolve()==root.resolve() or (out/'.git').exists():raise ValueError(f'не той каталог виходу: {out}')
    manifest=load_manifest(root);slugs={page['slug'] for page in manifest['pages']}
    template=(root/SITE/'template.html').read_text(encoding='utf-8')
    written=[]
    for lang in manifest['languages']:
        folder=out if lang=='uk' else out/lang
        folder.mkdir(parents=True,exist_ok=True)
        for page in manifest['pages']:
            target=folder/f'{page["slug"]}.html'
            target.write_text(page_html(template,manifest,lang,page['slug'],render(root,lang,page['slug'],slugs)),encoding='utf-8',newline='\n')
            written.append(target)
    for name in ('site.css','site.js'):shutil.copyfile(root/SITE/name,out/name);written.append(out/name)
    images=root/IMAGES
    if images.is_dir():
        for image in sorted(p for p in images.rglob('*') if p.is_file()):
            target=out/'images'/image.relative_to(images);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(image,target);written.append(target)
    (out/'.nojekyll').write_text('',encoding='utf-8')
    base=site_base_url(manifest)
    if base:
        for name,text in (('robots.txt',robots_txt(base)),('sitemap.xml',sitemap_xml(manifest,base)),('404.html',not_found_html(base))):
            (out/name).write_text(text,encoding='utf-8',newline='\n');written.append(out/name)
    return written


def robots_txt(base):return f'User-agent: *\nAllow: /\n\nSitemap: {base}sitemap.xml\n'


def sitemap_xml(manifest,base):
    """Every page in both languages with its hreflang alternates; no dates, so equal sources give equal bytes."""
    esc=lambda value:html.escape(value,quote=True);rows=[]
    for page in manifest['pages']:
        alternates=''.join(f'<xhtml:link rel="alternate" hreflang="{code}" href="{esc(public_url(base,code,page["slug"]))}"/>' for code in ('uk','en'))
        for lang in manifest['languages']:rows.append(f'<url><loc>{esc(public_url(base,lang,page["slug"]))}</loc>{alternates}</url>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            +'\n'.join(rows)+'\n</urlset>\n')


def not_found_html(base):
    """Bilingual page for any missing address. Pages serves it at that address, so every link is absolute."""
    esc=html.escape(base,quote=True)
    return f'''<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Сторінку не знайдено · Page not found · Obscura Text Writer</title>
<link rel="stylesheet" href="{esc}site.css">
</head>
<body>
<header class="site-header"><a class="site-brand" href="{esc}">Obscura Text Writer</a></header>
<main class="site-main">
<h1>Сторінку не знайдено</h1>
<p>Такої сторінки немає. Перейдіть на <a href="{esc}">головну сторінку інструкцій</a>.</p>
<h2 lang="en">Page not found</h2>
<p lang="en">This page does not exist. Go to the <a href="{esc}en/">user guide home page</a>.</p>
</main>
</body>
</html>
'''


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')  # Windows consoles default to a legacy code page
    parser=argparse.ArgumentParser(description='Зібрати сайт інструкцій із docs/site.')
    parser.add_argument('--out',default='_site')
    args=parser.parse_args(argv)
    written=build(ROOT,ROOT/args.out)
    print(f'Сайт зібрано: {len(written)} файлів у {args.out}/')
    return 0


if __name__=='__main__':sys.exit(main())
