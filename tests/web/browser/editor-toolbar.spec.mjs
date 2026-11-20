import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
const middle=box=>box.y+box.height/2;

test('editor buttons share one row with the model line under the primary button',async({page,request})=>{
  test.skip(test.info().project.name==='mobile','a phone keeps the primary button on its own full-width row');
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
    const line=await telemetry.boundingBox();
    expect(line.y,tab).toBeGreaterThanOrEqual(primary.y+primary.height-1);
    // The model line is not drawn over what follows the toolbar.
    const toolbar=await page.locator('.workspace-sticky .editor-toolbar').boundingBox();
    expect(line.y+line.height,tab).toBeLessThanOrEqual(toolbar.y+toolbar.height+1);
  }
});
