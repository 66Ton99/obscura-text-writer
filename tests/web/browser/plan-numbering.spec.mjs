import {test,expect} from '@playwright/test';

async function openPlan(page,request,text){
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=plan`);
  const editor=page.locator('#editor');
  await expect(editor).toBeVisible();
  await editor.fill(text);
  return {fixture,editor};
}
const caretAtEndOf=async(editor,fragment)=>editor.evaluate((el,f)=>{const at=el.value.indexOf(f)+f.length;el.focus();el.setSelectionRange(at,at);},fragment);

test.describe('plan numbering',()=>{
  test('PLAN-NUMBERING-S01 Enter at the end of an item continues the list and shifts the rest',async({page,request})=>{
    const {editor}=await openPlan(page,request,'Хто бере участь: Анна\n1. Перший\n2. Другий');
    await caretAtEndOf(editor,'1. Перший');
    await page.keyboard.press('Enter');
    await page.keyboard.type('Новий');
    await expect(editor).toHaveValue('Хто бере участь: Анна\n1. Перший\n2. Новий\n3. Другий');
    await page.keyboard.press('Enter');await page.keyboard.press('Enter');
    await expect(editor).toHaveValue('Хто бере участь: Анна\n1. Перший\n2. Новий\n\n1. Другий');
  });

  test('PLAN-NUMBERING-S01 Ctrl+Z after Enter takes back the renumbering, then the new item',async({page,request})=>{
    const {editor}=await openPlan(page,request,'1. Перший\n2. Другий');
    await caretAtEndOf(editor,'1. Перший');
    await page.keyboard.press('Enter');
    await expect(editor).toHaveValue('1. Перший\n2. \n3. Другий');
    await page.keyboard.press('Control+z');
    await expect(editor).toHaveValue('1. Перший\n2. \n2. Другий');
    await page.keyboard.press('Control+z');
    await expect(editor).toHaveValue('1. Перший\n2. Другий');
  });

  test('PLAN-NUMBERING-S02 a new first item renumbers the list and leaves parsed lines alone',async({page,request})=>{
    const {editor}=await openPlan(page,request,'Початок: ранок\n1. А\n2. Б');
    await caretAtEndOf(editor,'Початок: ранок\n');
    await page.keyboard.type('1. Нове\n');
    await expect(editor).toHaveValue('Початок: ранок\n1. Нове\n2. А\n3. Б');
    await expect(page.locator('#save-text')).toBeEnabled();
  });

  test('PLAN-NUMBERING-S03 deleting an item shifts the numbers; the button fixes every list',async({page,request})=>{
    const {editor}=await openPlan(page,request,'1. А\n2. Б\n3. В');
    await editor.evaluate(el=>{const from=el.value.indexOf('2. Б');el.focus();el.setSelectionRange(from,from+5);});
    await page.keyboard.press('Backspace');
    await expect(editor).toHaveValue('1. А\n2. В');
    await editor.evaluate(el=>{el.value='1. А\n5. Б\n\n3. В\n3. Г';el.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.locator('#plan-renumber').click();
    await expect(editor).toHaveValue('1. А\n2. Б\n\n3. В\n4. Г');
    await page.keyboard.press('Control+z');
    await expect(editor).toHaveValue('1. А\n5. Б\n\n3. В\n3. Г');
  });

  test('PLAN-NUMBERING-S04 one Ctrl+Z undoes the renumbering; other tabs keep their numbers',async({page,request})=>{
    const {editor}=await openPlan(page,request,'1. А\n2. Б');
    await caretAtEndOf(editor,'1. А\n');
    await page.keyboard.type('1. Х\n');
    await expect(editor).toHaveValue('1. А\n2. Х\n3. Б');
    await page.keyboard.press('Control+z');
    await expect(editor).toHaveValue('1. А\n1. Х\n2. Б');
    await expect(page.locator('#plan-renumber')).toBeVisible();
    await page.locator('#save-text').click();
    await expect(page.locator('#save-text')).toBeDisabled();
    await expect(page.locator('#plan-renumber')).toBeEnabled(); // the save has finished
    await page.locator('[data-mode="brief"]').click();
    await expect(page.locator('#plan-renumber')).toBeHidden();
    // The brief keeps its numbers: Enter after an item adds a plain line, nothing is renumbered.
    if(await editor.isHidden())await page.locator('#brief-advanced').click();
    await editor.fill('1. А\n1. Б');
    await caretAtEndOf(editor,'1. А');
    await page.keyboard.press('Enter');
    await expect(editor).toHaveValue('1. А\n\n1. Б');
  });
});
