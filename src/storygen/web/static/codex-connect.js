// Codex file configuration and skill installation are independent author actions.
import {api} from './api.js';
import {t,uiText,diagnostic} from './i18n.js';

const root=document.querySelector('#codex-connect');
if(root){
  const mcp=root.querySelector('.codex-mcp-result'),skills=root.querySelector('.codex-skills-result');
  const command=root.querySelector('code'),copy=root.querySelector('[data-codex-copy]');
  const hint=root.querySelector('.codex-copy-help'),availability=root.querySelector('.codex-availability');
  const actions=[...root.querySelectorAll('[data-codex-action]')];
  let available=false,pending=false;
  function line(key,params={}){
    const el=document.createElement('p');
    el.dataset.i18n=key;el.dataset.i18nParams=JSON.stringify(params);
    uiText(el,'textContent',()=>t(key,params));return el;
  }
  function updateButtons(){for(const el of actions)el.disabled=pending||(el.dataset.codexAction==='skills'&&!available)}
  function showCommand(value){if(typeof value==='string'){command.textContent=value;copy.hidden=false}}
  function report(box,answer){
    const result=answer.result;
    const reasons={install_busy:'codex.install_busy',unsafe_install_root:'codex.unsafe_install_root'};
    const specific=(answer.errors||[]).map(reason=>reasons[reason]).filter(Boolean);
    box.replaceChildren(...(specific.length?specific.map(key=>line(key)):[line('codex.'+result)]));
    const success=box===skills&&(result==='installed'||result==='unchanged');
    for(const field of ['path','installed','restored','conflicts','backups']){
      if(success&&field==='installed')continue;
      const values=Array.isArray(answer[field])?answer[field]:answer[field]?[answer[field]]:[];
      for(const value of values)box.append(line('codex.'+(field==='installed'?'installed_list':field),{p0:value}));
    }
    if(success){
      const changed=new Set(answer.installed||[]);
      for(const name of answer.names||[])box.append(line(changed.has(name)?'codex.installed_list':'codex.current_name',{p0:name}));
    }
  }
  function failure(box,error){
    if(error.data?.result)report(box,error.data);
    else{
      const el=document.createElement('p');
      uiText(el,'textContent',()=>error.data?.detail_original?diagnostic(error.data.detail_original):t('codex.failed'));
      box.replaceChildren(el);
    }
  }
  async function load(){
    pending=true;updateButtons();
    try{
      const answer=await api('/api/connect/codex/status');
      available=answer.skills.available;
      availability.replaceChildren(line(available?'codex.skills_help':'codex.unsupported'));
      if(answer.mcp.state==='error')failure(mcp,{data:answer.mcp});
      else mcp.replaceChildren(line('codex.state_'+answer.mcp.state),line('codex.path',{p0:answer.mcp.path}));
      if(answer.skills.state==='error')failure(skills,{data:answer.skills});
      else if(available)skills.replaceChildren(line('codex.skills_'+answer.skills.state));
      showCommand(answer.command);
    }catch(error){failure(mcp,error)}
    finally{pending=false;updateButtons()}
  }
  root.addEventListener('click',async event=>{
    const button=event.target.closest('[data-codex-action]');
    if(!button||button.disabled||pending)return;
    const action=button.dataset.codexAction,box=action==='mcp'?mcp:skills;
    pending=true;updateButtons();box.replaceChildren(line('codex.pending'));
    try{
      const answer=await api('/api/connect/codex'+(action==='skills'?'/skills':''),{method:'POST'});
      if(action==='mcp'){
        mcp.replaceChildren(line('codex.saved'),line('codex.path',{p0:answer.path}));
        if(answer.backup)mcp.append(line('codex.backups',{p0:answer.backup}));
        showCommand(answer.command);
      }else report(skills,answer);
    }catch(error){failure(box,error)}
    finally{pending=false;updateButtons()}
  });
  copy.addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(command.textContent);hint.replaceChildren(line('codex.copied'))}
    catch{
      const selection=window.getSelection(),range=document.createRange();
      range.selectNodeContents(command);selection.removeAllRanges();selection.addRange(range);
      hint.replaceChildren(line('codex.copy_manual'));
    }
  });
  let loaded=false;
  root.addEventListener('toggle',()=>{
    if(root.open&&!loaded){loaded=true;load()}
  });
  if(root.open){loaded=true;load()}
}
