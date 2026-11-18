import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
const names=['start-story','draft-scene','publish','series-bible','setup-models'].map(n=>'obscura-'+n);
const reply=(status,body)=>route=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
const initial={mcp:{state:'missing',path:'C:/fixture/config.toml'},skills:{available:true,state:'missing',present:[],conflicts:[],versions:{}},command:"codex mcp add obscura -- 'bridge.exe'"};
async function open(page,status=initial){
  await page.route('**/api/connect/codex/status',reply(200,status));
  await page.goto('/');
  const root=page.locator('#codex-connect');
  await root.locator('summary').focus();
  await page.keyboard.press('Enter');
  await expect(root).toHaveAttribute('open','');
  return root;
}

test('Codex independent actions and saved-file wording',async({page})=>{
  const calls=[];
  await page.route('**/api/connect/codex',route=>{calls.push('mcp');return reply(200,{result:'configured',path:'C:/fixture/config.toml',backup:null,command:initial.command})(route)});
  await page.route('**/api/connect/codex/skills',route=>{calls.push('skills');return reply(200,{result:'installed',names,installed:names,backups:[]})(route)});
  const root=await open(page);
  await expect(root.locator('code')).toHaveText(initial.command);
  await root.locator('[data-codex-action="mcp"]').click();
  expect(calls).toEqual(['mcp']);
  await expect(root.locator('.codex-mcp-result')).toContainText('Налаштування Codex збережено.');
  await expect(root.locator('.codex-mcp-result')).not.toContainText('підключено');
  await root.locator('[data-codex-action="skills"]').click();
  expect(calls).toEqual(['mcp','skills']);
  for(const name of names)await expect(root.locator('.codex-skills-result')).toContainText(name);
  await page.locator('[data-ui-locale="en"]').click();
  await expect(root.locator('.codex-mcp-result')).toContainText('Codex settings saved. Open a new session or restart Codex.');
});

test('Codex conflict and partial lists remain literal after language switch',async({page})=>{
  const path='C:/'+('long-path/'.repeat(12))+'<author>/backup';
  await page.route('**/api/connect/codex/skills',reply(500,{result:'partial',conflicts:['obscura-start-story'],restored:['obscura-publish'],installed:['obscura-draft-scene'],backups:[path]}));
  const root=await open(page);
  await root.locator('[data-codex-action="skills"]').click();
  await expect(root.locator('.codex-skills-result')).toContainText('Часткове встановлення');
  await expect(root.locator('.codex-skills-result')).toContainText(path);
  await expect(root.locator('author')).toHaveCount(0);
  await page.locator('[data-ui-locale="en"]').click();
  await expect(root.locator('.codex-skills-result')).toContainText('Partial installation');
  await expect(root.locator('.codex-skills-result')).toContainText('Restored: obscura-publish');
  await expect(root.locator('.codex-skills-result')).toContainText(path);
  expect(await root.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
  await page.unroute('**/api/connect/codex/skills');
  await page.route('**/api/connect/codex/skills',reply(409,{result:'conflict',conflicts:['obscura-start-story'],backups:[]}));
  await root.locator('[data-codex-action="skills"]').click();
  await expect(root.locator('.codex-skills-result')).toContainText('Conflicts: obscura-start-story');
});

test('Codex Store keeps MCP enabled',async({page})=>{
  const root=await open(page,{...initial,skills:{...initial.skills,available:false,state:'unsupported'}});
  await expect(root.locator('[data-codex-action="skills"]')).toBeDisabled();
  await expect(root.locator('[data-codex-action="mcp"]')).toBeEnabled();
  await expect(root).toContainText('Скіли Codex поки встановлюються лише з робочої копії');
});

test('Codex pending disables both actions and clipboard failure offers selection',async({page})=>{
  let release;
  const gate=new Promise(resolve=>release=resolve);
  await page.route('**/api/connect/codex',async route=>{await gate;await reply(200,{result:'unchanged',path:'C:/fixture/config.toml',command:initial.command})(route)});
  const root=await open(page);
  await root.locator('[data-codex-action="mcp"]').click();
  await expect(root.locator('[data-codex-action="mcp"]')).toBeDisabled();
  await expect(root.locator('[data-codex-action="skills"]')).toBeDisabled();
  release();
  await expect(root.locator('[data-codex-action="skills"]')).toBeEnabled();
  await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('denied'))},configurable:true}));
  await root.getByRole('button',{name:'Копіювати команду'}).click();
  await expect(root).toContainText('Виділіть команду й скопіюйте її вручну');
});


test('Codex status stays lazy until the first expansion',async({page})=>{
  let calls=0;
  await page.route('**/api/connect/codex/status',route=>{calls++;return reply(200,initial)(route)});
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  expect(calls).toBe(0);
  const summary=page.locator('#codex-connect summary');
  await summary.click();
  await expect.poll(()=>calls).toBe(1);
  await summary.click();await summary.click();
  await page.waitForLoadState('networkidle');
  expect(calls).toBe(1);
});

test('Codex status errors preserve the other action and command',async({page})=>{
  const root=await open(page,{...initial,mcp:{state:'error',path:null,reason:'config_home_must_be_absolute',detail_original:'Не вдалося зберегти налаштування Codex; перевірте файл і повторіть'}});
  await expect(root.locator('.codex-mcp-result')).toContainText('Не вдалося');
  await expect(root.locator('[data-codex-action="skills"]')).toBeEnabled();
  await expect(root.locator('code')).toHaveText(initial.command);
  await page.unroute('**/api/connect/codex/status');
  await page.route('**/api/connect/codex/status',reply(200,{...initial,skills:{...initial.skills,state:'error',reason:'skill_source_invalid',detail_original:'Не вдалося встановити всі скіли Codex; перевірте конфлікти та резервні копії'}}));
  await page.reload();
  await page.locator('#codex-connect summary').click();
  await expect(page.locator('.codex-skills-result')).toContainText('Не вдалося');
  await expect(page.locator('[data-codex-action="mcp"]')).toBeEnabled();
  await expect(page.locator('#codex-connect code')).toHaveText(initial.command);
});

test('Codex busy and unsafe roots give specific recovery in both languages',async({page})=>{
  const root=await open(page);
  for(const [reason,uk,en] of [['install_busy','Інший установник','Another installer'],['unsafe_install_root','Небезпечний шлях','Unsafe path']]){
    await page.route('**/api/connect/codex/skills',reply(409,{result:'conflict',errors:[reason],conflicts:[],backups:[]}));
    await page.locator('[data-ui-locale="uk"]').click();
    await root.locator('[data-codex-action="skills"]').click();
    await expect(root.locator('.codex-skills-result')).toContainText(uk);
    await expect(root.locator('.codex-skills-result')).not.toContainText('авторські файли');
    await page.locator('[data-ui-locale="en"]').click();
    await expect(root.locator('.codex-skills-result')).toContainText(en);
    await page.unroute('**/api/connect/codex/skills');
  }
});
