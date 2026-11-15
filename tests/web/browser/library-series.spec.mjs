import {test,expect} from '../../../frontend/browser-test.mjs';

// SERIES-LIBRARY-S01 in the browser: the library gathers the books of a series into one group whose cards name the
// series and the book's place in it; the label follows a live language switch (neutral texts).
test.use({locale:'uk-UA'});

test('the library groups the series books and labels their cards',async({page,request})=>{
  const title=`Сага бібліотеки ${test.info().project.name} ${Date.now()}`;
  const item=await(await request.post('/api/series',{data:{title}})).json();
  const join=async(name,data)=>{
    const story=await(await request.post('/api/stories',{data:{title:name}})).json();
    const put=await request.patch(`/api/stories/${story.id}/series`,{data:{series_id:item.id,expected_revision:story.revision,...data}});
    expect(put.ok(),await put.text()).toBeTruthy();
  };
  await join('Друга книга саги',{number:2});
  await join('Перша книга саги',{number:1});
  await join('Світ саги',{bible:true});
  await page.goto('/');
  const group=page.locator(`.library-series[data-series-id="${item.id}"]`);
  await expect(group.locator('h2').first()).toHaveText(`Серія «${title}»`);
  await expect(group.locator('.card h2')).toHaveText(['Світ саги','Перша книга саги','Друга книга саги']);
  await expect(group.locator('.card-series')).toHaveText([`Серія «${title}», біблія світу`,`Серія «${title}», книга 1`,`Серія «${title}», книга 2`]);
  await page.locator('[data-ui-locale="en"]').click();
  await expect(group.locator('h2').first()).toHaveText(`Series «${title}»`);
  await expect(group.locator('.card-series')).toHaveText([`Series «${title}», world bible`,`Series «${title}», book 1`,`Series «${title}», book 2`]);
  await page.locator('[data-ui-locale="uk"]').click();
  await expect(group.locator('.card-series')).toHaveText([`Серія «${title}», біблія світу`,`Серія «${title}», книга 1`,`Серія «${title}», книга 2`]);
  await group.locator('h2 a').first().click();
  await expect(page).toHaveURL(new RegExp(`/series/${item.id}$`));
});
