import {test,expect} from '../../../frontend/browser-test.mjs';

// DESKTOP-001-S08: in the Obscura window, links to other sites go to the default browser, own links stay in the window.
test.beforeEach(async({request})=>{expect((await(await request.post('/test-app-window',{data:{on:true}})).json()).on).toBe(true)});
test.afterEach(async({request})=>{expect((await(await request.post('/test-app-window',{data:{on:false}})).json()).on).toBe(false)});
const asked=async request=>(await(await request.post('/test-app-window',{data:{}})).json()).external;

test('a link to another site goes to the browser and the window stays on Obscura',async({page,request})=>{
  await page.goto('/');
  await page.evaluate(()=>{for(const [id,href] of [['ext','https://obscurawriter.com/report.html'],['own','/?own=1'],['mail','mailto:a@example.test']]){const a=document.createElement('a');a.id=id;a.href=href;a.textContent=id;document.body.append(a)}});
  const before=page.url();
  await page.locator('#ext').click();
  await expect.poll(()=>asked(request)).toEqual(['https://obscurawriter.com/report.html']);
  expect(page.url()).toBe(before);
  await page.locator('#mail').evaluate(a=>{a.addEventListener('click',e=>{window.mailSeen=!e.defaultPrevented;e.preventDefault()})});
  await page.locator('#mail').click();
  expect(await page.evaluate(()=>window.mailSeen)).toBe(true);
  await page.locator('#own').click();
  await expect(page).toHaveURL(/\?own=1$/);
  expect(await asked(request)).toEqual(['https://obscurawriter.com/report.html']);
});

test('window.open of another site goes to the browser, of Obscura opens as before',async({page,request,context})=>{
  await page.goto('/');
  expect(await page.evaluate(()=>window.open('https://example.test/paid','_blank','noopener'))).toBeNull();
  await expect.poll(()=>asked(request)).toEqual(['https://example.test/paid']);
  const popup=context.waitForEvent('page');
  await page.evaluate(()=>{window.open('/?scene=1','_blank')});
  await expect((await popup)).toHaveURL(/\?scene=1$/);
  expect(await asked(request)).toEqual(['https://example.test/paid']);
});

test('without the window the page links behave as in a browser',async({page,request})=>{
  await request.post('/test-app-window',{data:{on:false}});
  await page.goto('/');
  expect(await page.locator('script[src="/static/app-window.js"]').count()).toBe(0);
  await request.post('/test-app-window',{data:{on:true}});
});
