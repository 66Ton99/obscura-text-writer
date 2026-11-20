import {test,expect} from '../../../frontend/browser-test.mjs';

test('characters page saves, previews and returns to the same material',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
  await page.locator('#workspace-characters').click();
  await expect(page.locator('#characters-page')).toBeVisible();
  await page.locator('#characters-add').click();
  await page.locator('[data-ui-locale="uk"]').click();
  const card=page.locator('.character-editor fieldset').last();
  await card.locator('input').fill('Олена');
  await card.getByRole('button',{name:/Додати відомість|Add detail/}).click();
  await card.locator('textarea').fill('Працює у бібліотеці. '.repeat(35));
  await card.locator('select').first().selectOption('timeless');
  await page.locator('[data-ui-locale="en"]').click();
  await expect(card.locator('input')).toHaveValue('Олена');
  await page.locator('#characters-preview').click();
  await expect(page.locator('#characters-preview-text')).toContainText('No information is available');
  await page.locator('#characters-save').click();
  await expect(page.locator('#characters-status')).toHaveText('Details saved');
  await expect(page.locator('#characters-save')).toBeDisabled();
  const saved=await(await request.get(`/api/stories/${f.story_id}/characters`)).json();
  const view=await(await request.get(`/api/stories/${f.story_id}`)).json();
  const scene=view.scenes.find(s=>s.id===f.scene_id);
  const cast=await request.patch(`/api/scenes/${f.scene_id}`,{data:{story_id:f.story_id,expected_revision:scene.revision,character_ids:[saved.cards.at(-1).id]}});
  expect(cast.ok()).toBeTruthy();
  await page.reload();
  await expect(page.locator('#characters-preview')).toBeEnabled();
  await page.locator('#characters-preview').click();
  await expect(page.locator('#characters-preview-text')).toContainText('Працює у бібліотеці.');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:`docs/images/characters-page-${test.info().project.name}.png`,fullPage:true});
  await page.locator('#characters-return').click();
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
});

test('empty story, dirty navigation and failed save preserve edits',async({page,request})=>{
  const story=await(await request.post('/api/stories',{data:{title:'Персонажі без сцен'}})).json();
  await page.goto(`/stories/${story.id}/characters`);
  await expect(page.locator('#characters-preview')).toBeDisabled();
  await page.locator('#characters-add').click();
  await page.locator('.character-editor fieldset input').fill('Марія');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.locator('#characters-return').click();
  await expect(page.locator('#characters-page')).toBeVisible();
  await page.route(`**/api/stories/${story.id}/characters`,async route=>{
    if(route.request().method()==='PUT')await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:'Конфлікт версій'})});else await route.continue();
  });
  await page.locator('#characters-save').click();
  await expect(page.locator('#characters-status')).toContainText('Конфлікт');
  await expect(page.locator('.character-editor fieldset input')).toHaveValue('Марія');
  await expect(page.locator('#characters-save')).toBeEnabled();
});


test('unsaved manuscript is protected before opening characters',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}`);
  await expect(page.locator('#editor')).toBeEditable();
  await page.locator('#editor').fill('Незбережений план.');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.locator('#workspace-characters').click();
  await expect(page.locator('#workspace')).toBeVisible();
  await expect(page.locator('#editor')).toHaveValue('Незбережений план.');
});


test('word target recommendation permits larger values',async({page,request})=>{
  await page.goto('/');
  const target=page.locator('[name="target_words"]');
  await target.fill('25000');
  expect(await target.evaluate(el=>el.checkValidity())).toBeTruthy();
  await expect(page.locator('#word-target-help')).toContainText(/15.?000/);
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}`);
  await page.locator('.tool-section[data-section=scene] > summary').click();
  const scene=page.locator('#scene-settings [name="target_words"]');
  await scene.fill('30000');
  expect(await scene.evaluate(el=>el.checkValidity())).toBeTruthy();
  await expect(page.locator('#scene-target-help')).toContainText(/15.?000/);
});

test('timing warning follows the interface language on load and in preview',async({page,request})=>{
  const UK='Часову доступність опису не перевірено; він може містити відомості з майбутніх сцен.';
  const EN='The timing of this description has not been checked; it may contain details from future scenes.';
  const f=await(await request.post('/test-fixture')).json();
  const imported=await request.post(`/api/stories/${f.story_id}/sources`,{multipart:{characters:{name:'characters.md',mimeType:'text/plain',buffer:Buffer.from('## Anna'+String.fromCharCode(10)+'The lighthouse keeper.'+String.fromCharCode(10))}}});
  expect(imported.ok()).toBeTruthy();
  const cards=(await(await request.get(`/api/stories/${f.story_id}/characters`)).json()).cards;
  const scene=(await(await request.get(`/api/stories/${f.story_id}`)).json()).scenes.find(s=>s.id===f.scene_id);
  expect((await request.patch(`/api/scenes/${f.scene_id}`,{data:{story_id:f.story_id,expected_revision:scene.revision,character_ids:[cards.at(-1).id]}})).ok()).toBeTruthy();
  await page.goto(`/stories/${f.story_id}/characters`);
  await page.locator('[data-ui-locale="en"]').click();
  const status=page.locator('#characters-status');
  await expect(status).toHaveText(EN);
  await page.locator('[data-ui-locale="uk"]').click();
  await expect(status).toHaveText(UK);
  await page.locator('[data-ui-locale="en"]').click();
  await page.locator('#characters-preview').click();
  const info=page.getByRole('status').filter({hasText:EN}).filter({hasNot:status});
  await expect(info).toHaveCount(1);
  await page.locator('[data-ui-locale="uk"]').click();
  await expect(page.getByRole('status').filter({hasText:UK})).toHaveCount(2);
});

test('find a character filters cards, jumps and never loses edits',async({page,request})=>{
  // CHARACTER-TIME-S04 (#75)
  const story=await(await request.post('/api/stories',{data:{title:'Пошук персонажів'}})).json();
  expect((await request.post(`/api/stories/${story.id}/scenes`,{data:{title:'Зустріч'}})).ok()).toBeTruthy();
  const url=`/api/stories/${story.id}/characters`;
  const entry=text=>({id:null,text,origin:'author',sources:[],availability:'timeless',available_from_scene_id:null});
  const cards=[{id:null,name:'Маріанна',entries:[entry('Сусідка')]},{id:null,name:'Анна',entries:[entry('Лікарка')]},
    {id:null,name:'Хазяїн',entries:[entry("Інше ім'я: Джон")]}];
  const loaded=await(await request.get(url)).json();
  expect((await request.put(url,{data:{expected_revision:loaded.revision,cards}})).ok()).toBeTruthy();
  await page.goto(`/stories/${story.id}/characters`);
  await page.locator('[data-ui-locale="uk"]').click();
  const find=page.locator('#characters-find'),groups=page.locator('.character-editor fieldset'),count=page.locator('#characters-find-count');
  await expect(groups).toHaveCount(3);
  // Typing filters by the other name and never moves the cursor.
  await find.pressSequentially('джон');
  await expect(groups.filter({visible:true})).toHaveCount(1);
  await expect(count).toHaveText('Показано 1 з 3');
  await expect(find).toBeFocused();
  await find.press('Enter');
  await expect(groups.nth(2).locator('input').first()).toBeFocused();
  // A suggestion picks the exact name, not the first card containing it.
  await find.evaluate(el=>{el.value='Анна';el.dispatchEvent(new InputEvent('input',{inputType:'insertReplacementText',bubbles:true}))});
  await expect(groups.nth(1).locator('input').first()).toBeFocused();
  await expect(groups.filter({visible:true})).toHaveCount(2);
  // An edit under the filter is kept, and Save stores every card.
  await groups.nth(1).locator('input').first().fill('Анна К');
  // Removing the found name hides the card only after the cursor leaves it.
  await find.fill('джон');
  const host=groups.nth(2).locator('textarea');
  await host.fill("Інше ім'я: Петро");
  await expect(groups.nth(2)).toBeVisible();
  await find.click();
  await expect(groups.filter({visible:true})).toHaveCount(0);
  await expect(count).toHaveText('Немає персонажів за запитом');
  // A hidden card with an empty required field clears the filter on Save and on preview.
  await find.fill('');
  await groups.nth(0).locator('textarea').fill('');
  await find.fill('хаз');
  await expect(groups.nth(0)).toBeHidden();
  await page.locator('#characters-save').click();
  await expect(find).toHaveValue('');
  await expect(groups.nth(0)).toBeVisible();
  expect((await(await request.get(url)).json()).cards[1].name).toBe('Анна');
  let previews=0;page.on('request',req=>{if(req.url().endsWith('/characters/preview'))previews++});
  await find.fill('хаз');
  await expect(groups.nth(0)).toBeHidden();
  await expect(page.locator('#characters-preview')).toBeEnabled();
  await page.locator('#characters-preview').click();
  await expect(find).toHaveValue('');
  await expect(groups.nth(0)).toBeVisible();
  expect(await groups.nth(0).locator('textarea').evaluate(el=>el.matches(':invalid'))).toBeTruthy();
  expect(previews).toBe(0);
  await groups.nth(0).locator('textarea').fill('Сусідка');
  await find.fill('хаз');
  await page.locator('#characters-save').click();
  await expect(page.locator('#characters-status')).toHaveText('Відомості збережено');
  const saved=(await(await request.get(url)).json()).cards;
  expect(saved.map(card=>card.name)).toEqual(['Маріанна','Анна К','Хазяїн']);
  expect(saved[2].entries[0].text).toBe("Інше ім'я: Петро");
  // Adding a character clears the filter and focuses the new card.
  await find.fill('маріанна');
  await page.locator('#characters-add').click();
  await expect(find).toHaveValue('');
  await expect(groups).toHaveCount(4);
  await expect(groups.nth(3).locator('input').first()).toBeFocused();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
