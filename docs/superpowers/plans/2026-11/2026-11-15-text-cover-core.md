# Текстова обкладинка — план ядра

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Obscura малює текстову PNG-обкладинку (назва, серія з номером, автори, одна з 4 палітр) і реєструє її як звичайний ресурс обкладинки — через HTTP і MCP-інструмент `generate_cover`.

**Architecture:** Чистий модуль `publication/text_cover.py` (Pillow + вбудований Noto Serif) розкладає й малює PNG. Дія сховища `generate_cover` перевіряє текст правилами `PublicationData`, розв'язує підписи й передає PNG у чинну дію `upload_cover` (без рефакторингу). HTTP-маршрут і MCP-інструмент — тонкі обгортки.

**Tech Stack:** Python 3.12, Pillow 12.3, FastAPI, pydantic, `mcp` 2.3, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-15-text-cover-design.md` (затверджено 2026-11-15).

**Межі плану.** Ядро — задачі 1–4 нижче. Кнопка в картці, переклади, браузерний тест, сторінки сайту `publication.md`/`mcp.md` обома мовами й знімок — окремий план периферії після рев'ю ядра (`detent:pr-slicing`). Обидва плани — один PR.

## Global Constraints

- Полотно 1600×2560 RGB, PNG; шрифти лише з `storygen.publication/resources/fonts/NotoSerif-{Regular,Bold}.ttf` через `importlib.resources`.
- Палітри (фон / текст / акцент): `ink` `#1c2433`/`#efe6d2`/`#c9a24a`; `paper` `#f2ece0`/`#1f1f1f`/`#8a2a2a`; `wine` `#5b1a1f`/`#f3e9dc`/`#d9b26a`; `forest` `#1f3a2e`/`#eef0e6`/`#b8c48a`.
- Поля 120 px з боків → ширина рядка ≤ 1360 px.
- Серія: Regular 70 px, акцент, великі літери, центр першого рядка на y=220, ≤ 2 рядки, далі «…». Формат `ЦИКЛ · КНИГА N` / `CYCLE · BOOK N`; без номера — лише цикл; без циклу — рядка немає.
- Назва: Bold від 220 px кроком −10 до 90 px, міжрядкове 1,2, ≤ 6 рядків, при 90 px і переповненні — останній рядок «…»; центр блоку на y=1280. Лінії акценту 360×5 px: на 90 px вище першого рядка і на 60 px нижче останнього.
- Автори: Regular від 90 до 60 px, імена через «, », ≤ 2 рядки, далі «…»; центр блоку на y=2320; без авторів — рядка немає.
- «Книга»/«Book»: мовний тег `uk` або `uk-…` без урахування регістру → «Книга», інакше «Book».
- Порожня назва → `effective_title` твору (`story.title`); порожня мова → мова твору.
- Без Pillow — `ValueError('Для обкладинок установіть storygen[publication] (Pillow)')`, той самий текст, що в `image_info`.
- Генерація не змінює картку; відповідь — `CoverAsset` (HTTP) / `{cover_id, width, height, mime_type}` (MCP).
- Документація українською; маркери OpenSpec англійською; кожен новий Scenario — запис у `docs/verification/traceability.json`; перевірка `python scripts/check_docs.py`.
- Гейт: `python scripts/check_docs.py && python -m pytest -q`.

## Review Focus

1. Назва 300 символів одним словом (без пробілів) — перенос за символами, жоден рядок > 1360 px → тест у задачі 1.
2. 20 авторів по 40 символів і цикл 300 символів — обрізання «…», ширина ≤ 1360 px → тест у задачі 1.
3. Мовні теги `UK`, `uk-UA`, `UK-UA`, `en`, `pl` → «Книга» ×3, «Book» ×2 → тест у задачі 1.
4. Невідомий підпис / чужий твір / неактивний твір → без файлу й без рядка `publication_assets` → тест у задачі 2.
5. Порожня назва картки → на обкладинці назва твору; порожня мова → мова твору («Книга» для українського твору без мови в запиті) → тест у задачі 2 (перехоплення аргументів малювання).

---

### Task 1: Модуль малювання `publication/text_cover.py`

**Files:**
- Create: `src/storygen/publication/text_cover.py`
- Test: `tests/publication/test_text_cover.py` (створити теку `tests/publication/` з порожнім `__init__.py`, якщо інші теки тестів його мають — перевірити `tests/storage/__init__.py`)

**Interfaces:**
- Produces:
  - `PALETTES: dict[str, Palette]`, `Palette = NamedTuple('Palette', [('background', str), ('text', str), ('accent', str)])`, ключі рівно `('ink', 'paper', 'wine', 'forest')` у цьому порядку.
  - `book_word(language: str) -> str`
  - `series_text(cycle_title: str, cycle_number: int | None, language: str) -> str` — `''` без циклу.
  - `@dataclass(frozen=True) class Line: text: str; size: int; bold: bool; y: int` (y — центр рядка).
  - `layout_text_cover(*, title: str, series: str, authors: list[str]) -> list[Line]` — усі рядки обкладинки, крім ліній акценту.
  - `render_text_cover(*, title: str, series: str, authors: list[str], palette: str) -> bytes` — PNG.
  - `font(size: int, bold: bool)` — `ImageFont.FreeTypeFont` (для тестів ширини).
  - Невідома палітра → `ValueError('Невідома палітра обкладинки')`.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from PIL import Image
import io
from storygen.publication.covers import image_info
from storygen.publication import text_cover as tc

LIMIT = 1360

def widths_ok(lines):
    from PIL import ImageDraw
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    return all(draw.textlength(l.text, font=tc.font(l.size, l.bold)) <= LIMIT for l in lines)

def test_palettes_are_the_four_approved():
    assert list(tc.PALETTES) == ['ink', 'paper', 'wine', 'forest']
    assert tc.PALETTES['ink'] == ('#1c2433', '#efe6d2', '#c9a24a')
    assert tc.PALETTES['forest'] == ('#1f3a2e', '#eef0e6', '#b8c48a')

@pytest.mark.parametrize('tag,word', [('uk', 'Книга'), ('UK', 'Книга'), ('uk-UA', 'Книга'), ('UK-UA', 'Книга'), ('en', 'Book'), ('pl', 'Book'), ('ukx', 'Book')])
def test_book_word_ignores_case(tag, word):
    assert tc.book_word(tag) == word

def test_series_text():
    assert tc.series_text('Десяточники', 1, 'uk') == 'ДЕСЯТОЧНИКИ · КНИГА 1'
    assert tc.series_text('Tens', 2, 'en') == 'TENS · BOOK 2'
    assert tc.series_text('Десяточники', None, 'uk') == 'ДЕСЯТОЧНИКИ'
    assert tc.series_text('', 3, 'uk') == ''

@pytest.mark.parametrize('palette', list(tc.PALETTES))
def test_render_is_a_valid_cover(palette):
    png = tc.render_text_cover(title='Десяточка', series='ДЕСЯТОЧНИКИ · КНИГА 1', authors=["Ім'я Автора"], palette=palette)
    assert image_info(png) == ('image/png', 1600, 2560)
    with Image.open(io.BytesIO(png)) as image:
        assert image.getpixel((5, 5)) == Image.new('RGB', (1, 1), tc.PALETTES[palette].background).getpixel((0, 0))

def test_short_title_is_one_line_at_220():
    lines = [l for l in tc.layout_text_cover(title='Десяточка', series='', authors=[]) if l.bold]
    assert [(l.text, l.size) for l in lines] == [('Десяточка', 220)]

def test_empty_series_and_authors_draw_only_the_title():
    lines = tc.layout_text_cover(title='Маяк', series='', authors=[])
    assert all(l.bold for l in lines)

@pytest.mark.parametrize('title', ['а' * 300, ('довгеслово ' * 30).strip()], ids=['no-spaces', 'words'])
def test_huge_title_fits_and_is_cut(title):
    lines = [l for l in tc.layout_text_cover(title=title, series='', authors=[]) if l.bold]
    assert 1 <= len(lines) <= 6 and lines[0].size >= 90 and widths_ok(lines)

def test_huge_title_ends_with_ellipsis():
    lines = [l for l in tc.layout_text_cover(title='а' * 300, series='', authors=[]) if l.bold]
    assert lines[-1].text.endswith('…') and lines[0].size == 90

def test_many_authors_and_long_series_are_cut_within_margins():
    authors = [f'Автор Номер{i:02d} Дуже Довге Прізвище' for i in range(20)]
    lines = tc.layout_text_cover(title='Маяк', series='Ц' * 300, authors=authors)
    series = [l for l in lines if not l.bold and l.y < 1280]
    names = [l for l in lines if not l.bold and l.y > 1280]
    assert len(series) == 2 and series[-1].text.endswith('…')
    assert len(names) == 2 and names[-1].text.endswith('…') and names[0].size >= 60
    assert widths_ok(lines)

def test_unknown_palette():
    with pytest.raises(ValueError, match='палітра'):
        tc.render_text_cover(title='Маяк', series='', authors=[], palette='neon')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/publication/test_text_cover.py -q`
Expected: FAIL — `ModuleNotFoundError: storygen.publication.text_cover`.

- [ ] **Step 3: Implement `src/storygen/publication/text_cover.py`**

Імпорт Pillow — усередині функцій (`font`, `layout_text_cover`, `render_text_cover`); `ImportError` → `ValueError` з текстом із Global Constraints. Шрифти читати один раз (`functools.lru_cache` на `(size, bold)`), `ImageFont.truetype(io.BytesIO(blob), size)`. Вимірювання — `ImageDraw.Draw(Image.new('RGB',(1,1))).textlength`.

Алгоритм переносу (спільний для всіх блоків):

```python
def wrap(text, size, bold, max_lines):
    """Greedy word wrap; a word wider than LIMIT is split by characters; overflow -> last line ends with '…'."""
    # 1. tokens = text.split(); build lines greedily by words
    # 2. a token wider than LIMIT: split it into the longest char prefixes that fit
    # 3. if len(lines) > max_lines: keep max_lines, last = lines[max_lines-1];
    #    trim chars from last until last + '…' fits LIMIT; return (lines, truncated=True)
```

- Назва: для `size` у `range(220, 89, -10)` взяти перший, де `wrap(...)` дає ≤ 6 рядків без обрізання; якщо такого немає — `size=90` з обрізанням.
- Серія: `wrap(series, 70, False, 2)`; автори: `', '.join(authors)`, для `size` у `range(90, 59, -10)` перший без обрізання, інакше 60 з обрізанням.
- `y`: серія — `220 + i*84`; назва — центр блоку 1280, рядок `lh=int(size*1.2)`; автори — центр блоку 2320, `lh=int(size*1.2)`.
- `render_text_cover`: фон, текст (`anchor='mm'`, колір серії — акцент, решта — текст), лінії акценту `(800±180, top-90)` і `(800±180, bottom+60)` товщиною 5, `save(format='PNG', optimize=True)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/publication/test_text_cover.py -q`
Expected: PASS (усі).

- [ ] **Step 5: Commit**

```bash
git add src/storygen/publication/text_cover.py tests/publication/
git commit -m "feat(publication): text cover layout and renderer"
```

---

### Task 2: Дія сховища й HTTP-маршрут

**Files:**
- Modify: `src/storygen/storage/publication_store.py` (`operation`, гілка перед `upload_cover`)
- Modify: `src/storygen/web/routes_publication.py` (модель `CoverGenerate`, маршрут)
- Test: `tests/storage/test_publication.py`, `tests/web/test_publication_api.py`

**Interfaces:**
- Consumes: `render_text_cover`, `series_text`, `PALETTES` (задача 1).
- Produces:
  - `repo.publication('generate_cover', story_id=str, palette=str, title=str, cycle_title=str, cycle_number=int|None, author_ids=list[str], language=str) -> CoverAsset`
  - `POST /api/stories/{story_id}/publication/cover/generate`, тіло `CoverGenerate{palette: Literal['ink','paper','wine','forest'], title: str='', cycle_title: str='', cycle_number: int|None=None, author_ids: list[Identifier]=[], language: str=''}` → `CoverAsset`.

- [ ] **Step 1: Write the failing tests**

У `tests/storage/test_publication.py`:

```python
def test_generate_cover_registers_asset_without_touching_card(tmp_path):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Маяк'))
    author=repo.publication('create_signature',display_name='А. Маяківна')
    before=repo.publication('get_card',story_id=story.id).card.revision
    asset=repo.publication('generate_cover',story_id=story.id,palette='wine',title='',cycle_title='Світло',
        cycle_number=2,author_ids=[author.id],language='')
    assert (asset.mime_type,asset.width,asset.height)==('image/png',1600,2560)
    assert repo.publication('read_cover',story_id=story.id,id=asset.id)[0]
    view=repo.publication('get_card',story_id=story.id)
    assert view.card.revision==before and view.card.cover_id is None
    assert check_integrity(tmp_path).ok

@pytest.mark.parametrize('case',['unknown_signature','foreign_story','trashed_story'])
def test_generate_cover_refusals_leave_no_asset(tmp_path,case):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Маяк'))
    args=dict(story_id=story.id,palette='ink',title='',cycle_title='',cycle_number=None,author_ids=[],language='')
    if case=='unknown_signature':args['author_ids']=['f'*32]
    if case=='foreign_story':args['story_id']='e'*32
    if case=='trashed_story':repo.set_story_trashed(story.id,0,False)
    with pytest.raises(KeyError):repo.publication('generate_cover',**args)
    with repo.db.connection() as db:assert db.execute('SELECT COUNT(*) FROM publication_assets').fetchone()[0]==0

def test_generate_cover_falls_back_to_story_title_and_language(tmp_path,monkeypatch):
    from storygen.publication import text_cover
    seen={}
    real=text_cover.render_text_cover
    def spy(**kwargs):
        seen.update(kwargs); return real(**kwargs)
    monkeypatch.setattr(text_cover,'render_text_cover',spy)
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Маяк'))
    repo.publication('generate_cover',story_id=story.id,palette='ink',title='',cycle_title='Світло',
        cycle_number=3,author_ids=[],language='')
    assert seen['title']=='Маяк' and seen['series']=='СВІТЛО · КНИГА 3' and seen['authors']==[]

def test_generate_cover_rejects_unknown_palette_and_long_title(tmp_path):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Маяк'))
    base=dict(story_id=story.id,title='',cycle_title='',cycle_number=None,author_ids=[],language='')
    with pytest.raises(ValueError):repo.publication('generate_cover',**{**base,'palette':'neon'})
    with pytest.raises(ValueError):repo.publication('generate_cover',**{**base,'palette':'ink','title':'x'*301})
```

У `tests/web/test_publication_api.py`:

```python
def test_generate_cover_http(client):
    story=client.post('/api/stories',json={'title':'Маяк'}).json()
    url=f"/api/stories/{story['id']}/publication/cover/generate"
    asset=client.post(url,json={'palette':'paper','title':'Незбережена назва'}).json()
    assert (asset['width'],asset['height'],asset['mime_type'])==(1600,2560,'image/png')
    assert client.get(f"/api/stories/{story['id']}/publication/covers/{asset['id']}").status_code==200
    assert client.get(f"/api/stories/{story['id']}/publication").json()['card']['cover_id'] is None
    assert client.post(url,json={'palette':'neon'}).status_code==422
    assert client.post(url,json={'palette':'ink','author_ids':['f'*32]}).status_code==404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/storage/test_publication.py tests/web/test_publication_api.py -q -k generate`
Expected: FAIL — `ValueError: Невідома операція публікації` / 404 маршруту.

- [ ] **Step 3: Implement**

`operation(repo,'generate_cover',…)` — нова гілка на початку `operation`:
1. `text=PublicationData(title=data['title'],cycle_title=data['cycle_title'],cycle_number=data['cycle_number'],author_ids=data['author_ids'],language=data['language'] or 'uk')` — перевірка меж (pydantic `ValidationError` є `ValueError`). Якщо `data['palette'] not in PALETTES` → `ValueError('Невідома палітра обкладинки')` до будь-якого читання.
2. У read-транзакції (`BEGIN`): `story=repo._active_story(db,story_id)` (KeyError для чужого/неактивного), `names=[signature(db,id).display_name for id in text.author_ids]` (KeyError для невідомого).
3. `language=data['language'] or story.language`; імпортувати модулем (`from ..publication import text_cover`) і викликати `text_cover.render_text_cover(...)`, щоб тест міг підмінити функцію; `png=render_text_cover(title=text.title or story.title, series=series_text(text.cycle_title,text.cycle_number,language), authors=names, palette=data['palette'])` — поза транзакцією.
4. `return operation(repo,'upload_cover',story_id=story_id,content=png)`.

`routes_publication.py`: клас `CoverGenerate(DomainModel)` з полями з Interfaces (`title`/`cycle_title` `max_length=300`, `cycle_number` `ge=1, le=1000000`, `author_ids` `max_length=20`, `language` `max_length=63`); маршрут `@router.post('/api/stories/{story_id}/publication/cover/generate')` → `repo.publication('generate_cover',story_id=story_id,**body.model_dump())`. `Identifier` імпортувати з `publication_models`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/storage/test_publication.py tests/web/test_publication_api.py -q`
Expected: PASS (нові й наявні).

- [ ] **Step 5: Commit**

```bash
git add src/storygen/storage/publication_store.py src/storygen/web/routes_publication.py tests/storage/test_publication.py tests/web/test_publication_api.py
git commit -m "feat(publication): generate a text cover as a regular cover asset"
```

---

### Task 3: MCP-інструмент `generate_cover`

**Files:**
- Modify: `src/storygen/mcp/bridge.py` (`TOOLS`, `COVER_PALETTES`, інструмент після `upload_cover`)
- Test: `tests/mcp/test_bridge_publication.py`, `tests/mcp/test_bridge.py`

**Interfaces:**
- Consumes: маршрут задачі 2; `read_publication`, `request`, `identifier` у `bridge.py`.
- Produces: `generate_cover(story_id: str, palette: str = 'ink') -> {'cover_id', 'width', 'height', 'mime_type'}`; `COVER_PALETTES = ('ink', 'paper', 'wine', 'forest')` у `bridge.py` (без імпорту Pillow).

- [ ] **Step 1: Write the failing tests**

У `tests/mcp/test_bridge_publication.py`:

```python
@pytest.mark.req('MCP-BRIDGE')
def test_generate_cover_from_the_saved_card_and_bound_through_it(tmp_path):
    app, http = obscura(tmp_path)
    story = written_story(app, http)
    server = build_server(http)
    author = ok(call(server, 'add_signature', {'display_name': 'А. Маяківна'}))
    ok(call(server, 'update_publication', {'story_id': story.id, 'expected_revision': 0,
        'fields': {'author_ids': [author['id']], 'cycle_title': 'Світло', 'cycle_number': 1}}))
    data = ok(call(server, 'generate_cover', {'story_id': story.id, 'palette': 'forest'}))
    assert set(data) == {'cover_id', 'width', 'height', 'mime_type'} and (data['width'], data['height']) == (1600, 2560)
    assert ok(call(server, 'get_publication', {'story_id': story.id}))['card']['cover_id'] is None
    card = ok(call(server, 'update_publication', {'story_id': story.id, 'expected_revision': 1, 'fields': {'cover_id': data['cover_id']}}))
    assert card['cover']['id'] == data['cover_id']

@pytest.mark.req('MCP-BRIDGE')
def test_generate_cover_refuses_unknown_palette_without_request():
    seen = []
    result = call(_recording_server(seen), 'generate_cover', {'story_id': 'a' * 32, 'palette': 'neon'})
    assert result.is_error and 'palette' in text(result) and seen == []

def test_bridge_palettes_match_the_renderer():
    from storygen.mcp.bridge import COVER_PALETTES
    from storygen.publication.text_cover import PALETTES
    assert COVER_PALETTES == tuple(PALETTES)
```

У `tests/mcp/test_bridge.py`: перейменувати `test_tool_list_is_exactly_the_twenty_five_tools` → `test_tool_list_is_exactly_the_twenty_six_tools` і додати `'generate_cover'` у список після `'upload_cover'`. Оновити посилання на старе ім'я тесту в `docs/verification/traceability.json` (MCP-BRIDGE-S06) — це робиться в задачі 4.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/mcp -q -k "generate_cover or palettes or tool_list"`
Expected: FAIL — немає інструмента / `COVER_PALETTES`.

- [ ] **Step 3: Implement in `bridge.py`**

- `COVER_PALETTES` поруч із `COVER_MAX_BYTES`; `'generate_cover'` у `TOOLS` після `'upload_cover'`.
- Інструмент: `identifier(story_id)`; `palette not in COVER_PALETTES` → `ToolError(f'palette: одне з {", ".join(COVER_PALETTES)}')` до запиту; `card = request('GET', f'/api/stories/{story_id}/publication')['card']`; `data = request('POST', f'/api/stories/{story_id}/publication/cover/generate', json={'palette': palette, **{k: card[k] for k in ('title', 'cycle_title', 'cycle_number', 'author_ids', 'language')}})`; повернути `{'cover_id': data['id'], 'width': …, 'height': …, 'mime_type': …}`.
- Docstring: «Малює текстову обкладинку (назва, серія з номером, автори) зі збереженої картки публікації в одній із палітр ink, paper, wine, forest. Картку не змінює: щоб поставити обкладинку, передайте cover_id в update_publication.»

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/mcp -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storygen/mcp/bridge.py tests/mcp/test_bridge.py tests/mcp/test_bridge_publication.py
git commit -m "feat(mcp): generate_cover tool"
```

---

### Task 4: SPEC.MD, traceability, журнал

**Files:**
- Modify: `SPEC.MD` (R16-COVER: вимога, новий Scenario R16-COVER-S03, технічний опис; MCP-BRIDGE: S06 «двадцять шість», новий Scenario MCP-BRIDGE-S52 з якорем `<a id="mcp-bridge-s52"></a>` за зразком сусідів)
- Modify: `docs/verification/traceability.json`
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` (запис про пакет; номер задачі беклогу перевірити в `2026-10-20-remediation-backlog.md` — якщо окремого пункту немає, записати як «поза беклогом, рішення власника 15.11.2026»)

**Interfaces:**
- Consumes: імена тестів із задач 1–3.

- [ ] **Step 1: SPEC.MD.**
  - R16-COVER, після першого абзацу вимоги: «Генерація SHALL малювати текстову PNG-обкладинку 1600×2560 з переданих назви, циклу з номером і підписів авторів в одній із палітр `ink`, `paper`, `wine`, `forest` вбудованим Noto Serif і реєструвати її тим самим шляхом, що й upload; картка змінюється лише явним Save.»
  - `#### Scenario: R16-COVER-S03 — Текстова обкладинка з форми картки`: GIVEN твір із підписом і незбереженою назвою у формі / WHEN запитано генерацію з палітрою / THEN ресурс 1600×2560 PNG зареєстровано, картка й revision незмінні; порожня назва — назва твору, порожні цикл і автори — без рядків; надто довгі назва, цикл чи автори обрізаються «…» в межах полів; «Книга»/«Book» за мовним тегом без урахування регістру; невідома палітра, невідомий підпис, чужий чи неактивний твір — без ресурсу.
  - Технічний опис: модуль `publication/text_cover.py`, маршрут `POST /api/stories/{id}/publication/cover/generate`, обмеження розкладки з Global Constraints (коротко), символи поза шрифтом малюються квадратами, згенерована обкладинка не перемальовується після перейменування.
  - MCP-BRIDGE-S06: «двадцять п’ять» → «двадцять шість».
  - `#### Scenario: MCP-BRIDGE-S52 — Текстова обкладинка з чату`: GIVEN збережена картка / WHEN клієнт викликає `generate_cover` з палітрою / THEN повертаються `cover_id`, `width`, `height`, `mime_type`, картка не змінюється, а невідома палітра відхиляється без запиту; обкладинка прив'язується через `update_publication`.

- [ ] **Step 2: traceability.json** — записи за зразком сусідів:
  - `R16-COVER-S03` → `tests/publication/test_text_cover.py::*` (перелічити всі тести задачі 1 поіменно), `tests/storage/test_publication.py::test_generate_cover_registers_asset_without_touching_card`, `::test_generate_cover_refusals_leave_no_asset`, `::test_generate_cover_falls_back_to_story_title_and_language`, `::test_generate_cover_rejects_unknown_palette_and_long_title`, `tests/web/test_publication_api.py::test_generate_cover_http`; `scope`: «Ядро генерації; кнопку в картці підтверджує план периферії.»
  - `MCP-BRIDGE-S52` → три тести задачі 3.
  - `MCP-BRIDGE-S06` → нове ім'я `test_tool_list_is_exactly_the_twenty_six_tools`.

- [ ] **Step 3: Журнал виконання** — запис: дата, спека, план ядра, коміти, результат гейту.

- [ ] **Step 4: Run the gate**

Run: `python scripts/check_docs.py && python -m pytest -q`
Expected: обидва без помилок.

- [ ] **Step 5: Commit**

```bash
git add SPEC.MD docs/verification/traceability.json docs/superpowers/plans/2026-10-20-remediation-progress.md
git commit -m "docs(spec): text cover scenarios R16-COVER-S03 and MCP-BRIDGE-S52"
```

---

## Після ядра

1. Фінальне рев'ю всієї гілки ядра (end-to-end, `detent:pr-slicing`), знахідки записати.
2. Окремий план периферії: кнопка й вибір палітри в `publication.html`/`publication.js`, `i18n.json`, браузерний тест (незбережена назва потрапляє на обкладинку, картка незмінна до Save), `docs/site/{uk,en}/publication.md` і `mcp.md` + `check_site.py --rehash`, новий знімок картки з нейтральним прикладом, `scripts/verify.py` → `docs/STATUS.md`, PR на `main` з крос-рев'ю.
