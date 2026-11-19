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
