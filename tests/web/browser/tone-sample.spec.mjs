import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
// STYLE-SAMPLE-001: the voice sample field of the writing profile, its counter and saving.
const openWriting=async page=>{
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
};
test('the author saves a voice sample in the writing profile',async({page,request})=>{
  const story=await(await request.post('/api/stories',{data:{title:'Зразок звучання'}})).json();
  await page.goto(`/stories/${story.id}/settings`);
  await openWriting(page);
  const form=page.locator('#profile-form');
  const field=form.getByLabel('Зразок звучання (необов’язково)');
  await expect(form.locator('[data-tone-sample-count]')).toHaveText('0 / 3000');
  await field.fill('Вітер ішов низько.');
  await expect(form.locator('[data-tone-sample-count]')).toHaveText('18 / 3000');
  await page.locator('#settings-save').click();
  await expect(page.locator('#notice')).toContainText('Профіль письма збережено');
  const settings=await(await request.get(`/api/stories/${story.id}/settings`)).json();
  expect(settings.profile.tone_sample).toBe('Вітер ішов низько.');
  await page.reload();
  await openWriting(page);
  await expect(field).toHaveValue('Вітер ішов низько.');
  await expect(form.locator('[data-tone-sample-count]')).toHaveText('18 / 3000');
});
