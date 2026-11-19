import {test,expect} from '../../../frontend/browser-test.mjs';

// R20-WORKSPACE: «Use as prose» sits on the main panel of the Draft tab, left of the primary action.
test('use as prose sits left of the primary action on the draft tab',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const take=page.locator('#workspace-use-draft'),primary=page.locator('#workspace-primary');
  await expect(take).toBeVisible();
  await expect(take).toHaveText(/Use as prose|Взяти як прозу/);
  expect(await take.evaluate(el=>!!(el.compareDocumentPosition(document.querySelector('#workspace-primary'))&Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true);
  expect(await take.evaluate(el=>el.closest('.editor-toolbar')!==null)).toBe(true);
  await page.locator('[data-mode="plan"]').click();
  await expect(take).toBeHidden();
  await page.locator('[data-mode="draft"]').click();
  await take.click();
  await page.locator('dialog[open] .app-dialog-actions button:not(.secondary)').click();
  await expect(page.locator('#current-kind')).toHaveText(/PROSE|ПРОЗА/);
  const scene=(await(await request.get(`/api/stories/${fixture.story_id}`)).json()).scenes.find(s=>s.id===fixture.scene_id);
  const prose=await(await request.get(`/api/versions/${scene.heads.prose}`)).json();
  expect(prose.text).toContain('Лєра побачила **зорі**.');
  expect(prose.version.content_format).toBe('markdown');
  await expect(primary).toBeVisible();
});

// STORE-FOOTER-S01: the Store footer keeps the statistics materials, the history and the run controls only.
test.describe('Store edition footer',()=>{
  test.afterEach(async({request})=>{await request.post('/test-build-edition',{data:{edition:'full'}})});
  test('Store footer keeps only what an author needs',async({page,request})=>{
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await request.post('/test-build-edition',{data:{edition:'store'}});
    const fixture=await(await request.post('/test-fixture')).json();
    await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
    await expect(page.locator('#workspace-primary')).toBeVisible();
    for(const selector of ['#run-options','.workspace-extra','#generation-controls','#pause-each'])await expect(page.locator(selector)).toHaveCount(0);
    await expect(page.locator('#workspace-history')).toHaveCount(1);
    const stats=page.locator('#scene-statistics details');
    await stats.locator('summary').click();
    await expect(stats).toContainText(/Current prose: .* whole story\)|Поточна проза: .* весь твір\)/);
    await expect(stats.locator('select')).toHaveCount(0);
    await expect(stats.locator('h3')).toHaveCount(1);
    expect(errors).toEqual([]);
  });
  // STORE-FOOTER-S02: text versions only, three actions; restore saves a new author version in the version's format.
  test('Store history views, compares and restores text versions',async({page,request})=>{
    await request.post('/test-build-edition',{data:{edition:'store'}});
    const fixture=await(await request.post('/test-fixture')).json(),scene=fixture.scene_id;
    const history=async()=>(await(await request.get(`/api/scenes/${scene}/versions`)).json());
    const save=async(text,content_format)=>{const {scene:current}=await history();expect((await request.post(`/api/scenes/${scene}/prose`,{data:{text,expected_revision:current.revision,content_format}})).ok()).toBe(true)};
    await save('Нова **проза**.','markdown');await save('Третя проза.','plain');
    let data=await history();
    const markdown=data.versions.find(v=>v.kind==='manual'&&v.content_format==='markdown'),plain=data.versions.find(v=>v.kind==='manual'&&v.id!==data.scene.heads.prose&&v.content_format==='plain');
    await page.goto(`/stories/${fixture.story_id}?scene=${scene}&material=prose`);
    await page.locator('#workspace-history summary').click();
    const list=page.locator('#history-version');
    const labels=await list.locator('option').allTextContents();
    expect(labels.length).toBe(data.versions.filter(v=>['draft','edited','manual'].includes(v.kind)).length);
    for(const label of labels)expect(label).toMatch(/^(Draft|Prose|Edited) · /);
    const buttons=page.locator('#version-panel > button');
    await expect(buttons).toHaveText(['View version','Compare with the current text','Restore this version']);
    const restore=buttons.nth(2);
    await list.selectOption(data.scene.heads.prose);await expect(restore).toBeDisabled();
    await list.selectOption(plain.id);await buttons.nth(1).click();
    await expect(page.locator('#version-panel .comparison')).toBeVisible();
    await list.selectOption(markdown.id);await restore.click();
    await page.locator('dialog[open] .app-dialog-actions button:not(.secondary)').click();
    await expect.poll(async()=>(await history()).scene.heads.prose).not.toBe(data.scene.heads.prose);
    data=await history();
    const head=await(await request.get(`/api/versions/${data.scene.heads.prose}`)).json();
    expect(head.text).toBe('Нова **проза**.');expect(head.version.content_format).toBe('markdown');expect(head.version.kind).toBe('manual');
    const count=data.versions.length;
    await page.locator('#workspace-history summary').scrollIntoViewIfNeeded();
    if(!await list.isVisible())await page.locator('#workspace-history summary').click();
    await list.selectOption(markdown.id);await restore.click();
    await page.locator('dialog[open] .app-dialog-actions button:not(.secondary)').click();
    await expect(page.locator('#notice')).toContainText('The text is already the same');
    expect((await history()).versions.length).toBe(count);
  });
  test('full edition keeps run options and extra actions',async({page,request})=>{
    const fixture=await(await request.post('/test-fixture')).json();
    await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
    await expect(page.locator('#run-options')).toHaveCount(1);
    await expect(page.locator('.workspace-extra #generation-controls')).toHaveCount(1);
    const stats=page.locator('#scene-statistics details');
    await stats.locator('summary').click();
    await expect(stats.locator('select')).toHaveCount(1);
  });
});
