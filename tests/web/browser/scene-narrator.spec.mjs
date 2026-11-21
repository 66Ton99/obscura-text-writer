import {test,expect} from '../../../frontend/browser-test.mjs';

// SCENE-NARRATOR-S07 in the browser: the scene card narrator fields, the plan line lock and the not-in-cast note (neutral book).
test.use({locale:'uk-UA'});
const view=async(request,id)=>(await request.get(`/api/stories/${id}`)).json();
const openPanel=async page=>{
  await page.locator('.tool-section[data-section=scene]').evaluate(details=>{details.open=true});
  await expect(page.locator('#scene-settings')).toBeVisible();
};
const selectScene=async(page,index)=>{
  if(test.info().project.name==='mobile'){
    const option=await page.locator('#scene-select-mobile option').nth(index).getAttribute('value');await page.locator('#scene-select-mobile').selectOption(option);
  }else await page.locator('#scene-list .scene-item').nth(index).click();
};

test('the narrator person and character are saved from the scene card',async({page,request})=>{
  const {story_id,scene_ids}=await(await request.post('/test-brief-link')).json();
  const scene_id=scene_ids[1];
  await page.goto(`/stories/${story_id}`);
  await selectScene(page,1);
  await openPanel(page);
  const form=page.locator('#scene-settings');
  await expect(form.locator('input[name="title"]')).toHaveValue('Кав’ярня');
  const person=form.locator('#scene-narrator-person');
  await expect(person).toHaveValue('story');await expect(person).toBeEnabled();
  await expect(form.locator('.scene-narrator-hero')).toBeHidden();
  await person.selectOption('first');
  await expect(form.locator('.scene-narrator-hero')).toBeVisible();
  await form.locator('#scene-narrator-hero').selectOption('nina');
  await form.getByRole('button',{name:'Зберегти параметри'}).click();
  await expect(page.locator('#notice')).toContainText('Параметри сцени збережено');
  const saved=(await view(request,story_id)).scenes.find(s=>s.id===scene_id);
  expect(saved.narrator).toEqual({person:'first',character_id:'nina'});
  expect(saved.narrator_source).toBe('scene');
});

test('a narrator outside the cast shows a warning in the card',async({page,request})=>{
  const {story_id,scene_ids}=await(await request.post('/test-brief-link')).json();
  const scene_id=scene_ids[1];
  await page.goto(`/stories/${story_id}`);
  await selectScene(page,1);
  await openPanel(page);
  const form=page.locator('#scene-settings');
  await expect(form.locator('input[name="title"]')).toHaveValue('Кав’ярня');
  await form.locator('#scene-narrator-person').selectOption('third_limited');
  await form.locator('#scene-narrator-hero').selectOption('marko');
  await form.getByRole('button',{name:'Зберегти параметри'}).click();
  await expect(page.locator('#notice')).toContainText('Параметри сцени збережено');
  await expect(form.locator('#scene-narrator-notes')).toContainText('Оповідача немає серед учасників сцени: Марко.');
});

test('a «Оповідач:» plan line locks the fields and shows its value',async({page,request})=>{
  const {story_id}=await(await request.post('/test-brief-link')).json();
  await request.post(`/api/stories/${story_id}/scenes`,{data:{title:'Вечір',beats:'Хто бере участь: Лєра\nОповідач: Лєра, перша особа\nПрогулянка.',character_ids:['lera']}});
  await page.goto(`/stories/${story_id}`);
  await expect(page.locator('#scene-list .scene-item')).toHaveCount(3);
  await selectScene(page,2);
  await openPanel(page);
  const form=page.locator('#scene-settings');
  await expect(form.locator('input[name="title"]')).toHaveValue('Вечір');
  await expect(form.locator('#scene-narrator-person')).toHaveValue('first');
  await expect(form.locator('#scene-narrator-person')).toBeDisabled();
  await expect(form.locator('#scene-narrator-hero')).toHaveValue('lera');
  await expect(form.locator('#scene-narrator-hero')).toBeDisabled();
  await expect(form.locator('#scene-narrator-notes')).toContainText('Задано рядком «Оповідач:» у плані');
});
