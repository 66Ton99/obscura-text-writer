import {test,expect} from '../../../frontend/browser-test.mjs';

// Spec 2026-11-17-broken-letters-guard: the editor counts letters a provider lost (U+FFFD) and selects them one by one.
test.use({locale:'uk-UA'});

test('the editor banner counts broken letters and disappears once they are fixed',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  const view=await(await request.get(`/api/stories/${f.story_id}`)).json();
  const scene=view.scenes.find(s=>s.id===f.scene_id);
  const saved=await request.post(`/api/scenes/${f.scene_id}/draft`,{data:{text:'Вона п��шла додому. Вечір був тихий.',content_format:'plain',expected_revision:scene.revision}});
  expect(saved.ok(),await saved.text()).toBeTruthy();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=draft`);
  const banner=page.locator('.broken-text-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('У тексті пошкоджених символів «�»: 2.');
  await banner.getByRole('button',{name:'До наступного'}).click();
  expect(await page.evaluate(()=>getSelection().toString())).toBe('�');
  await page.locator('.ProseMirror').fill('Вона пішла додому. Вечір був тихий.');
  await expect(banner).toBeHidden();
});
