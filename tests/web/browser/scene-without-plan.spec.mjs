import {test,expect} from '../../../frontend/browser-test.mjs';

// SERIES-BIBLE-S06 in the browser: a new scene gets prose straight away, without plan, brief or draft, in an ordinary
// book and in a world bible; the save makes the prose head and shows no error (neutral text).
test.use({locale:'uk-UA'});

async function proseWithoutPlan(page,request,storyId,title){
  await page.goto(`/stories/${storyId}`);
  await page.locator('#add-scene').click();
  await page.locator('dialog[open] input').fill(title);
  await page.locator('dialog[open]').getByRole('button',{name:'Підтвердити'}).click();
  await expect(page.locator('#scene-list .scene-item',{hasText:title})).toBeAttached();
  const added=(await(await request.get(`/api/stories/${storyId}`)).json()).scenes.find(scene=>scene.title===title);
  if(test.info().project.name==='mobile')await page.locator('#scene-select-mobile').selectOption(added.id);
  else await page.locator('#scene-list .scene-item',{hasText:title}).click();
  await expect(page.locator('main h2').first()).toHaveText(title);
  await page.locator('#mode-tabs [data-mode="prose"]').click();
  const editor=page.locator('.rich-text-surface .ProseMirror');
  await editor.click();
  await editor.pressSequentially('Місто стоїть на трьох річках.');
  await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toHaveText(/Збережено/);
  const view=await(await request.get(`/api/stories/${storyId}`)).json();
  const scene=view.scenes.find(item=>item.title===title);
  expect(scene?.heads?.prose,'the prose head').toBeTruthy();
  const prose=(await(await request.get(`/api/scenes/${scene.id}/statistics`)).json()).materials.prose;
  expect([prose.version_id,prose.stale,prose.complete]).toEqual([scene.heads.prose,false,true]);
}

test('an ordinary book writes prose in a new scene without a plan',async({page,request})=>{
  const {story_id}=await(await request.post('/test-fixture')).json();
  await proseWithoutPlan(page,request,story_id,'Нова сцена книги');
});

test('a world bible writes prose in a new scene without a plan',async({page,request})=>{
  const {story_id}=await(await request.post('/test-fixture')).json();
  const item=await(await request.post('/api/series',{data:{title:`Сага сцени ${test.info().project.name} ${Date.now()}`}})).json();
  const story=(await(await request.get(`/api/stories/${story_id}`)).json()).story;
  const put=await request.patch(`/api/stories/${story_id}/series`,{data:{series_id:item.id,bible:true,expected_revision:story.revision}});
  expect(put.ok(),await put.text()).toBeTruthy();
  await proseWithoutPlan(page,request,story_id,'Нова сцена біблії');
});
