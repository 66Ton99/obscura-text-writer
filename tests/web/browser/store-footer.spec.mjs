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
