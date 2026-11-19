import {test,expect} from '../../../frontend/browser-test.mjs';

// EDIT-LOOP-REVIEW-S02: the pass limit is an editor model setting of the story; the workspace has no field for it.
test('editor pass limit is set in the editor settings and drives the call count',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  const url=`/api/stories/${fixture.story_id}/settings`;
  await page.goto(`/stories/${fixture.story_id}/settings`);
  await page.locator('[data-settings-role="editor"]').click();
  const input=page.locator('form[data-role="editor"] [name="edit_pass_limit"]');
  await expect(input).toBeVisible();
  await expect(input).toHaveValue('5');
  await input.fill('3');
  const saved=page.waitForResponse(r=>r.url().endsWith(url)&&r.request().method()==='PUT');
  await page.locator('#settings-save').click();
  expect((await saved).ok()).toBe(true);
  expect((await(await request.get(url)).json()).roles.editor.edit_pass_limit).toBe(3);
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await expect(page.locator('#edit-pass-limit')).toHaveCount(0);
  await expect(page.locator('#workspace-telemetry')).toContainText(/up to 3 calls|до 3 викл\./);
});
