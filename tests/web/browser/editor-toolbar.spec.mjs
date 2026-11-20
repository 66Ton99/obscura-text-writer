import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
const middle=box=>box.y+box.height/2;
const within=(inner,outer,label)=>{
  expect(inner.x,label).toBeGreaterThanOrEqual(outer.x-1);
  expect(inner.x+inner.width,label).toBeLessThanOrEqual(outer.x+outer.width+1);
  expect(inner.y+inner.height,label).toBeLessThanOrEqual(outer.y+outer.height+1);
};
// A model id may be up to 300 characters; the toolbar line must stay inside the panel either way.
// Text and both boxes are taken in one step: a later re-render may put the real model line back.
const longModel=page=>page.locator('#workspace-telemetry').evaluate(node=>{
  node.textContent='venice / '+'very-long-model-name-'.repeat(14)+' · до 5 викл.';
  const box=element=>{const r=element.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}};
  return {line:box(node),toolbar:box(node.closest('.editor-toolbar')),text:node.textContent.length};
});

test('editor buttons share one row with the model line under the primary button',async({page,request})=>{
  test.skip(test.info().project.name==='mobile','the phone layout is checked separately');
  await page.setViewportSize({width:1600,height:900});
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  for(const [tab,second] of [['Чернетка','#workspace-use-draft'],['Проза','#workspace-edit-prose'],['Завдання',null]]){
    await page.locator('#mode-tabs button',{hasText:tab}).first().click();
    const save=await page.locator('#save-text').boundingBox(),primary=await page.locator('#workspace-primary').boundingBox();
    const focus=await page.locator('#workspace-focus').boundingBox();
    expect(Math.abs(middle(primary)-middle(save)),tab).toBeLessThan(4);
    expect(Math.abs(middle(focus)-middle(save)),tab).toBeLessThan(4);
    if(second){await expect(page.locator(second)).toBeVisible();expect(Math.abs(middle(await page.locator(second).boundingBox())-middle(save)),tab).toBeLessThan(4)}
    const telemetry=page.locator('#workspace-telemetry');await expect(telemetry).toBeVisible();
    const line=await telemetry.boundingBox(),toolbar=await page.locator('.workspace-sticky .editor-toolbar').boundingBox();
    expect(line.y,tab).toBeGreaterThanOrEqual(primary.y+primary.height-1);
    within(line,toolbar,tab);
  }
  const long=await longModel(page);expect(long.text).toBeGreaterThan(290);
  within(long.line,long.toolbar,'long model');
});

test('on a phone the primary action takes its own full-width row with the model line inside the panel',async({page,request})=>{
  test.skip(test.info().project.name!=='mobile','desktop layout is checked above');
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await page.locator('#mode-tabs button',{hasText:'Чернетка'}).first().click();
  const toolbar=await page.locator('.workspace-sticky .editor-toolbar').boundingBox(),primary=await page.locator('#workspace-primary').boundingBox();
  const save=await page.locator('#save-text').boundingBox();
  expect(primary.width).toBeGreaterThan(toolbar.width*0.95);
  expect(primary.y).toBeGreaterThan(save.y+save.height-1);
  const line=await page.locator('#workspace-telemetry').boundingBox();
  expect(line.y).toBeGreaterThanOrEqual(primary.y+primary.height-1);
  within(line,toolbar,'phone');
  const long=await longModel(page);expect(long.text).toBeGreaterThan(290);
  within(long.line,long.toolbar,'phone long model');
});
