// STORE-MCP-001 S08–S11, S15–S16: «Connect to Claude» in the library. Claude Desktop is never called «connected»: Obscura can only
// prove that the entry is in its settings file; Claude reads that file when it starts.
import {confirmDialog} from './dialogs.js';
import {t,uiText} from './i18n.js';
import {api,notice} from './api.js';

const root=document.querySelector('#claude-connect');
const result=root?.querySelector('.connect-result');

function line(key,params={},tag='p'){const element=document.createElement(tag);uiText(element,'textContent',()=>t(key,params));return element}
function button(key,kind=''){const element=document.createElement('button');element.type='button';if(kind)element.className=kind;uiText(element,'textContent',()=>t(key));return element}
function show(...nodes){result.replaceChildren(...nodes)}
function post(path){return api('/api/connect/'+path,{method:'POST'})}

function restartChoice(){
  const box=document.createElement('div');box.className='connect-restart';
  const now=button('connect.restart_now'),self=button('connect.restart_self','secondary');
  const help=line('connect.restart_self_help');help.hidden=true;help.className='connect-self-help';
  now.addEventListener('click',async()=>{
    if(!await confirmDialog(t('connect.restart_warning'),{accept:t('connect.restart_now')}))return;
    now.disabled=true;
    try{const answer=await post('claude-desktop/restart');notice(t(answer.started?'connect.restarted':'connect.restart_failed'),answer.started?'success':'error')}
    catch(error){notice(error.message,'error')}finally{now.disabled=false}
  });
  self.addEventListener('click',()=>{help.hidden=false});
  box.append(now,self);
  return [box,help];
}

async function fallback(){
  const prepare=button('connect.fallback_prepare');
  show(line('connect.fallback_title',{},'h3'),line('connect.fallback_intro'),prepare);
  prepare.addEventListener('click',async()=>{
    prepare.disabled=true;
    try{const answer=await post('claude-desktop/bundle');show(line('connect.fallback_title',{},'h3'),line('connect.fallback_steps',{p0:answer.path}))}
    catch(error){notice(error.message,'error');prepare.disabled=false}
  });
}

async function desktop(){
  try{
    const answer=await post('claude-desktop');
    show(line(answer.result==='unchanged'?'connect.desktop_unchanged':'connect.desktop_added',{p0:answer.path}),...restartChoice());
  }catch(error){
    notice(error.message,'error');
    if(error.data?.fallback)await fallback();
  }
}

function commandBox(key,command){
  const code=document.createElement('code');code.textContent=command;
  const copy=button('connect.copy','secondary');
  copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(command);notice(t('connect.copied'))}catch(error){notice(error.message,'error')}});
  show(line(key),code,copy);
}

async function code(){
  try{
    const answer=await post('claude-code');
    if(!answer.connected)commandBox('connect.code_failed',answer.command);
    else if(answer.skills)show(line('connect.code_connected_skills'));
    else if(answer.conflict)show(line('connect.skills_conflict',{p0:answer.conflict}));
    else if(answer.reason==='no_plugin')show(line('connect.code_connected'));
    else commandBox('connect.code_skills_failed',(answer.plugin_commands||[]).join('\n'));
  }catch(error){
    if(error.status===404&&error.data?.command)commandBox('connect.code_missing',error.data.command);else notice(error.message,'error');
  }
}

async function skills(){
  try{const answer=await post('claude-desktop/skills');show(line('connect.skills_steps',{p0:answer.folder}))}
  catch(error){notice(error.message,'error')}
}

const actions={desktop,code,skills,other:fallback};
root?.addEventListener('click',async event=>{
  const target=event.target.closest('[data-connect]');
  if(!target||target.disabled)return;
  target.disabled=true;
  try{await actions[target.dataset.connect]()}finally{target.disabled=false}
});
