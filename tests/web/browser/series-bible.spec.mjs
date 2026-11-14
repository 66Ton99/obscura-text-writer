import {test,expect} from '../../../frontend/browser-test.mjs';

// SERIES-BIBLE-S08 in the browser: the world bible in the book settings, on the series screen and in a prequel's facts
// (neutral texts).
test.use({locale:'uk-UA'});
const name=title=>`${title} ${test.info().project.name}`;
const view=async(request,id)=>(await request.get(`/api/stories/${id}`)).json();

async function writingSettings(page,storyId){
  await page.goto(`/stories/${storyId}/settings`);
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
  return page.locator('#story-series-form');
}

test('the book settings make a work the world bible of a series',async({page,request})=>{
  const {story_id}=await(await request.post('/test-fixture')).json();
  await request.post('/api/series',{data:{title:name('Сага біблії налаштувань')}});
  const form=await writingSettings(page,story_id);
  await form.locator('select[name="series_id"]').selectOption({label:name('Сага біблії налаштувань')});
  await form.getByLabel('Біблія світу').check();
  await expect(form.locator('input[name="number"]')).toBeHidden();
  await expect(form.locator('input[name="start"]')).toBeHidden();
  await form.getByRole('button',{name:'Зберегти'}).click();
  await expect(page.locator('#notice')).toContainText('Серію збережено');
  const series=(await view(request,story_id)).series;
  expect([series.bible,series.number,series.status.state]).toEqual([true,null,'bible']);
  await expect(form.getByLabel('Біблія світу')).toBeChecked();
  await expect(form.locator('[data-series-refresh]')).toBeHidden();
  await page.goto(`/stories/${story_id}`);
  await expect(page.locator('#story-series')).toContainText(`Серія «${name('Сага біблії налаштувань')}», біблія світу`);
});

test('the series screen creates the world bible and keeps it off the axis',async({page,request})=>{
  const {story_id}=await(await request.post('/test-fixture')).json();
  const item=await(await request.post('/api/series',{data:{title:name('Сага біблії екрана')}})).json();
  const story=(await view(request,story_id)).story;
  await request.patch(`/api/stories/${story_id}/series`,{data:{series_id:item.id,number:1,expected_revision:story.revision}});
  await page.goto(`/series/${item.id}`);
  await expect(page.locator('#series-bible')).toBeHidden();
  await page.locator('#series-new-bible').click();
  await page.locator('dialog input').fill('Світ саги');
  await page.locator('dialog').getByRole('button',{name:'Підтвердити'}).click();
  await expect(page).toHaveURL(/\/stories\//);
  await page.goto(`/series/${item.id}`);
  await expect(page.locator('#series-bible .series-book')).toContainText('Світ саги');
  await expect(page.locator('#series-bible .series-book')).toContainText('біблія світу ще не має підсумку');
  await expect(page.locator('#series-books .series-book')).toHaveCount(1);
  await expect(page.locator('#series-axis li')).toHaveCount(1);
  await expect(page.locator('#series-outside li')).toHaveCount(0);
  await expect(page.locator('#series-new-bible')).toBeHidden();
  await expect(page.locator('#series-delete')).toBeDisabled();
});

test('a prequel cannot mark a fact of the world bible as the future',async({page,request})=>{
  const {prequel_id}=await(await request.post('/test-series-bible-prequel')).json();
  const form=await writingSettings(page,prequel_id);
  await form.getByRole('button',{name:'Переглянути факти пізніших книг'}).click();
  const dialog=page.locator('#series-facts-dialog');
  const bible=dialog.locator('.series-fact',{hasText:'Магія коштує крові'});
  await expect(bible).toContainText('з біблії світу — завжди минуле');
  await expect(bible.locator('input[type="radio"]')).toHaveCount(0);
  await dialog.getByRole('button',{name:'Усе — майбутнє'}).click();
  await expect(dialog.locator('[data-facts-changed]')).toHaveText('Змінено: 0');
  const own=dialog.locator('.series-fact',{hasText:'Халат'});
  await own.getByLabel('Минуле').check();
  await expect(dialog.locator('[data-facts-changed]')).toHaveText('Змінено: 1');
});
