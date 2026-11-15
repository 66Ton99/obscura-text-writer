import {test,expect} from '../../../frontend/browser-test.mjs';

// IMPORT-NUMBER-S03 in the browser: «Додати сцену» inserts right after the open scene, and the plan numbers of the
// following scenes move on by one (neutral text).
test.use({locale:'uk-UA'});

test('a new scene goes right after the open one and later plans are renumbered',async({page,request})=>{
  const story=await(await request.post('/api/stories',{data:{title:'Порядок сцен'}})).json();
  for(const [title,beats] of [['Ранок','## Сцена 1: Ранок\nСвітає.'],['Вечір','## Сцена 2: Вечір\nТемніє.']]){
    const response=await request.post(`/api/stories/${story.id}/scenes`,{data:{title,beats}});
    expect(response.ok(),await response.text()).toBeTruthy();
  }
  const first=(await(await request.get(`/api/stories/${story.id}`)).json()).scenes[0];
  await page.goto(`/stories/${story.id}?scene=${first.id}`);
  await expect(page.locator('main h2').first()).toHaveText('Ранок');
  await page.locator('#add-scene').click();
  await page.locator('dialog[open] input').fill('Полудень');
  await page.locator('dialog[open]').getByRole('button',{name:'Підтвердити'}).click();
  await expect(page.locator('#scene-list .scene-item',{hasText:'Полудень'})).toBeAttached();
  const scenes=(await(await request.get(`/api/stories/${story.id}`)).json()).scenes;
  expect(scenes.map(scene=>scene.title)).toEqual(['Ранок','Полудень','Вечір']);
  expect(scenes.map(scene=>scene.author_scene_number)).toEqual([1,2,3]);
  expect(scenes[1].beats.split('\n')[0]).toBe('## Сцена 2: Полудень');
  expect(scenes[2].beats).toBe('## Сцена 3: Вечір\nТемніє.');
  if(test.info().project.name!=='mobile')
    await expect(page.locator('#scene-list .scene-item').nth(1)).toContainText('2. Полудень');
});
