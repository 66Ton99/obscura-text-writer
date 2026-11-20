import {test,expect} from '@playwright/test';
test.use({locale:'uk-UA'});

// A brief saved through the same API the workspace uses, then the brief tab opened.
async function openBrief(page,request,brief){
  const fixture=await(await request.post('/test-fixture')).json();
  if(brief){
    const scene=(await(await request.get(`/api/scenes/${fixture.scene_id}/versions`)).json()).scene;
    const response=await request.post(`/api/scenes/${fixture.scene_id}/brief`,{data:{text:JSON.stringify(brief),expected_revision:scene.revision,source_brief_id:null}});
    expect(response.ok()).toBeTruthy();
  }
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=brief`);
  await expect(page.locator('#brief-form')).toBeVisible();
  return fixture;
}
const beats=page=>page.locator('#brief-form [data-list="beats"] textarea');
const beatValues=async page=>beats(page).evaluateAll(areas=>areas.map(area=>area.value));
const numbers=async page=>page.locator('#brief-form [data-list="beats"] .brief-item-number').allTextContents();
const savedBrief=async(request,sceneId)=>{
  const data=await(await request.get(`/api/scenes/${sceneId}/versions`)).json();
  return JSON.parse((await(await request.get(`/api/versions/${data.scene.heads.brief}`)).json()).text);
};
const sample={objective:'Лєра повертається до парку',beats:['Вечір у парку','Зустріч біля фонтана','Прощання'],constraints:['Без флешбеків'],proposed_changes:[],introduced:['c-1']};

test.describe('brief form',()=>{
  test('BRIEF-FORM-S01 a beat with quotes and a line break saves exactly, introduced stays',async({page,request})=>{
    const fixture=await openBrief(page,request,sample);
    await expect(page.locator('#editor')).toBeHidden();
    await expect(page.locator('#brief-form .brief-form-objective textarea')).toHaveValue('Лєра повертається до парку');
    await beats(page).nth(1).fill('Зустріч біля "фонтана"\nі мовчання');
    await expect(page.locator('#save-text')).toBeEnabled();
    await page.locator('#save-text').click();
    await expect.poll(async()=>(await savedBrief(request,fixture.scene_id)).beats[1]).toBe('Зустріч біля "фонтана"\nі мовчання');
    const saved=await savedBrief(request,fixture.scene_id);
    expect(saved.beats).toEqual(['Вечір у парку','Зустріч біля "фонтана"\nі мовчання','Прощання']);
    expect(saved.introduced).toEqual(['c-1']);
    expect(saved.constraints).toEqual(['Без флешбеків']);
  });

  test('BRIEF-FORM-S02 insert, move and remove renumber the labels, not the texts',async({page,request})=>{
    await openBrief(page,request,sample);
    expect(await numbers(page)).toEqual(['1.','2.','3.']);
    await page.locator('#brief-form [data-list="beats"] li').nth(0).getByRole('button',{name:'Вставити перед'}).click();
    await beats(page).nth(0).fill('Пролог');
    await page.locator('#brief-form [data-list="beats"] li').nth(2).getByRole('button',{name:'Вставити перед'}).click();
    await beats(page).nth(2).fill('Середина');
    expect(await beatValues(page)).toEqual(['Пролог','Вечір у парку','Середина','Зустріч біля фонтана','Прощання']);
    expect(await numbers(page)).toEqual(['1.','2.','3.','4.','5.']);
    await page.locator('#brief-form [data-list="beats"] li').nth(4).getByRole('button',{name:'Перемістити вище'}).click();
    await page.locator('#brief-form [data-list="beats"] li').nth(0).getByRole('button',{name:'Видалити'}).click();
    expect(await beatValues(page)).toEqual(['Вечір у парку','Середина','Прощання','Зустріч біля фонтана']);
    expect(await numbers(page)).toEqual(['1.','2.','3.','4.']);
    expect(JSON.parse(await page.locator('#editor').inputValue()).beats).toEqual(['Вечір у парку','Середина','Прощання','Зустріч біля фонтана']);
  });

  test('BRIEF-FORM-S03 advanced JSON keeps unsaved edits; broken JSON keeps the author there',async({page,request})=>{
    await openBrief(page,request,sample);
    await page.locator('#brief-form [data-add="beats"]').click();
    await beats(page).nth(3).fill('Нове');
    await page.locator('#brief-advanced').click();
    await expect(page.locator('#editor')).toBeVisible();
    await expect(page.locator('#brief-advanced')).toHaveText('Звичайний вигляд');
    const brief=JSON.parse(await page.locator('#editor').inputValue());
    expect(brief.beats).toEqual([...sample.beats,'Нове']);
    brief.objective='Нова мета';await page.locator('#editor').fill(JSON.stringify(brief));
    await page.locator('#brief-advanced').click();
    await expect(page.locator('#editor')).toBeHidden();
    await expect(page.locator('#brief-form .brief-form-objective textarea')).toHaveValue('Нова мета');
    expect(await beatValues(page)).toEqual([...sample.beats,'Нове']);
    await page.locator('#brief-advanced').click();
    await page.locator('#editor').fill('{"objective":"зламано",');
    await page.locator('#brief-advanced').click();
    await expect(page.locator('#editor')).toBeVisible();
    await expect(page.locator('#brief-form .brief-form-problem')).toContainText('JSON зіпсовано');
  });

  test('BRIEF-FORM-S04 planner numbers, history and a brief without beats',async({page,request})=>{
    const fixture=await openBrief(page,request,{...sample,beats:['1. Вечір','2. Фонтан']});
    expect(await beatValues(page)).toEqual(['Вечір','Фонтан']);
    expect(JSON.parse(await page.locator('#editor').inputValue()).beats).toEqual(['1. Вечір','2. Фонтан']);
    await page.locator('#brief-form [data-list="beats"] li').nth(1).getByRole('button',{name:'Видалити'}).click();
    await page.locator('#brief-form [data-list="beats"] li').nth(0).getByRole('button',{name:'Видалити'}).click();
    await expect(page.locator('#save-text')).toBeDisabled();
    await expect(page.locator('#save-text')).toHaveAttribute('title','Додайте хоча б один біт');
    await page.locator('#brief-form [data-add="beats"]').click();
    await beats(page).nth(0).fill('Вечір');
    await expect(page.locator('#save-text')).toBeEnabled();
    await page.locator('#save-text').click();
    await expect.poll(async()=>(await savedBrief(request,fixture.scene_id)).beats).toEqual(['Вечір']);
    await expect(page.locator('#save-state')).toHaveText(/Збережено/);
    // The previous version opened from the history is read-only.
    const versions=(await(await request.get(`/api/scenes/${fixture.scene_id}/versions`)).json()).versions.filter(v=>v.kind==='brief');
    await page.locator('#workspace-history summary').click();
    await page.locator('#history-version').selectOption(versions[0].id);
    await page.locator('#version-panel button',{hasText:'Переглянути'}).first().click();
    await expect(beats(page).first()).toHaveJSProperty('readOnly',true);
    await expect(page.locator('#brief-form [data-add="beats"]')).toHaveCount(0);
  });

  test('BRIEF-FORM narrow screen has no horizontal scroll',async({page,request})=>{
    await page.setViewportSize({width:375,height:800});
    await openBrief(page,request,sample);
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
