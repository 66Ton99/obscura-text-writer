import {test,expect} from '../../../frontend/browser-test.mjs';

// STORE-MCP-001 S08–S10 in the browser: the library block connects Claude Desktop (never called «connected»), offers the
// two restart choices, the .mcpb fallback and the Claude Code command. Routes are intercepted: no real Claude is touched.
test.use({locale:'uk-UA'});

const reply=(status,body)=>route=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});

test('Claude Desktop entry, restart choices and the fallback',async({page})=>{
  const restarts=[];
  await page.route('**/api/connect/claude-desktop',reply(200,{result:'added',path:'C:/Users/u/claude_desktop_config.json',variant:'store'}));
  await page.route('**/api/connect/claude-desktop/restart',route=>{restarts.push(1);return reply(200,{started:true})(route)});
  await page.goto('/');
  const block=page.locator('#claude-connect');
  if(!await block.evaluate(node=>node.open))await block.locator('summary').click();
  await block.getByRole('button',{name:'Підключити Claude Desktop'}).click();
  await expect(block.locator('.connect-result')).toContainText('Запис додано у C:/Users/u/claude_desktop_config.json');
  await expect(block.locator('.connect-result')).not.toContainText('підключено');
  await block.getByRole('button',{name:'Перезапущу сам'}).click();
  await expect(block.locator('.connect-self-help')).toContainText('«Quit»');
  await block.getByRole('button',{name:'Перезапустити Claude зараз'}).click();
  await expect(page.locator('dialog')).toContainText('відкритою розмовою');
  await page.locator('dialog').getByRole('button',{name:'Перезапустити Claude зараз'}).click();
  await expect(page.locator('#notice')).toContainText('Claude Desktop перезапускається');
  expect(restarts).toEqual([1]);

  await page.unroute('**/api/connect/claude-desktop');
  await page.route('**/api/connect/claude-desktop',reply(404,{detail:'Файла налаштувань Claude Desktop немає: запустіть Claude Desktop хоч раз і повторіть',fallback:true}));
  await page.route('**/api/connect/claude-desktop/bundle',reply(200,{path:'C:/Users/u/Obscura/claude/obscura.mcpb'}));
  await block.getByRole('button',{name:'Підключити Claude Desktop'}).click();
  await block.getByRole('button',{name:'Підготувати файл розширення'}).click();
  await expect(block.locator('.connect-result')).toContainText('Settings → Desktop app → Extensions');
  await expect(block.locator('.connect-result')).toContainText('obscura.mcpb');
});

test('Claude Code command to copy and the English block',async({page})=>{
  await page.route('**/api/connect/claude-code',reply(404,{found:false,command:'claude mcp add --scope user obscura -- obscura-mcp.exe'}));
  await page.goto('/');
  const block=page.locator('#claude-connect');
  if(!await block.evaluate(node=>node.open))await block.locator('summary').click();
  await block.getByRole('button',{name:'Підключити Claude Code'}).click();
  await expect(block.locator('.connect-result')).toContainText('Claude Code не знайдено');
  await expect(block.locator('code')).toHaveText('claude mcp add --scope user obscura -- obscura-mcp.exe');
  await expect(block.getByRole('button',{name:'Копіювати'})).toBeVisible();
  await page.locator('[data-ui-locale="en"]').click();
  await expect(block.locator('summary')).toHaveText('Connect to Claude');
  await expect(block.getByRole('button',{name:'Connect Claude Desktop'})).toBeVisible();
  await expect(block.locator('.connect-result')).toContainText('Claude Code was not found');
});
