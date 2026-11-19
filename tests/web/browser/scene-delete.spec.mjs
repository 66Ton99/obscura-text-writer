import {test,expect} from '../../../frontend/browser-test.mjs';

// #104 WORKSPACE-TOOLS-S05: the delete action sits next to the selected scene in the list. The test browser runs the English UI.
test('delete icon follows the selected scene and moves it to the scene trash',async({page,request})=>{
  test.skip(test.info().project.name==='mobile','the scene list is replaced by a picker on narrow screens');
  const fixture=await(await request.post('/test-fixture')).json();
  await request.post(`/api/stories/${fixture.story_id}/scenes`,{data:{title:'Друга сцена',beats:'Прогулянка.'}});
  await page.goto(`/stories/${fixture.story_id}`);
  const rows=page.locator('#scene-list .scene-item'),button=page.locator('#scene-list .scene-delete');
  await expect(rows).toHaveCount(2);
  await expect(button).toHaveCount(1);
  await expect(button).toHaveAttribute('aria-label','Delete scene');
  await expect(button).toHaveText('');
  await expect(page.locator('#scene-list .scene-item.active + .scene-row-actions')).toHaveCount(1);
  await expect(rows.nth(0)).toHaveClass(/active/);
  // The icon lies inside the right edge of the active row, not under it.
  const row=await rows.nth(0).boundingBox(),icon=await button.boundingBox();
  expect(icon.y).toBeGreaterThanOrEqual(row.y);expect(icon.y+icon.height).toBeLessThanOrEqual(row.y+row.height+1);
  expect(icon.x+icon.width).toBeLessThanOrEqual(row.x+row.width+1);

  await rows.nth(1).click();
  await expect(rows.nth(1)).toHaveClass(/active/);
  await expect(button).toHaveCount(1);
  await expect(page.locator('#scene-list .scene-item').nth(1).locator('+ .scene-row-actions')).toHaveCount(1);
  await expect(rows).toHaveCount(2);

  await button.click();
  await expect(page.locator('dialog[open]')).toContainText('scene trash');
  await page.locator('dialog[open] .app-dialog-actions button:not(.secondary)').click();
  await expect(rows).toHaveCount(1);
  await expect(page.locator('#notice')).toContainText('Scene deleted');
  await page.locator('.scene-panel details summary').filter({hasText:'Scene trash'}).click();
  await expect(page.locator('.scene-panel')).toContainText('Друга сцена');
});

test('unsaved text keeps the scene: the icon explains instead of deleting',async({page,request})=>{
  test.skip(test.info().project.name==='mobile','the scene list is replaced by a picker on narrow screens');
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await expect(page.locator('#scene-list .scene-item')).toHaveCount(1);
  await page.locator('#workspace-material .ProseMirror, #editor').first().click();
  await page.keyboard.type('Нове речення. ');
  await page.locator('#scene-list .scene-delete').click();
  await expect(page.locator('#notice')).toContainText('Save your changes first');
  await expect(page.locator('dialog[open]')).toHaveCount(0);
  await expect(page.locator('#scene-list .scene-item')).toHaveCount(1);
});

// STORE-FOOTER: the footer has no delete action; a narrow screen gets the named button under the scene picker.
test('narrow screen shows the named button under the scene picker, not in the footer',async({page,request})=>{
  test.skip(test.info().project.name!=='mobile','desktop uses the list icon');
  const fixture=await(await request.post('/test-fixture')).json();
  await request.post(`/api/stories/${fixture.story_id}/scenes`,{data:{title:'Друга сцена',beats:'Прогулянка.'}});
  await page.goto(`/stories/${fixture.story_id}`);
  await expect(page.locator('.workspace-extra button').filter({hasText:'Delete scene'})).toHaveCount(0);
  await expect(page.locator('#scene-list .scene-delete')).toBeHidden();
  const named=page.locator('#scene-list-section .scene-delete-mobile');
  await expect(named).toBeVisible();await expect(named).toHaveText('Delete scene');
  await named.click();
  await page.locator('dialog[open] .app-dialog-actions button:not(.secondary)').click();
  await expect(page.locator('#notice')).toContainText('Scene deleted');
  await expect(page.locator('#scene-select-mobile option')).toHaveCount(1);
});

test('desktop footer has no delete action',async({page,request})=>{
  test.skip(test.info().project.name==='mobile','the mobile case is above');
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await expect(page.locator('#scene-list .scene-delete')).toHaveCount(1);
  await expect(page.locator('.workspace-extra button').filter({hasText:'Delete scene'})).toHaveCount(0);
  await expect(page.locator('#scene-list-section .scene-delete-mobile')).toBeHidden();
});
