import {confirmDialog} from './dialogs.js';
import {createTextEditor} from './text-editor.js';
import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';

const CLOSED=new Set(['completed','failed','cancelled']),STOPPED=new Set(['paused','interrupted','needs_review','alternative']);
// DATA-006: runs that wait for the author are offered for cancellation before a trash action; an active run blocks it.
async function stoppedRuns(storyId,activeMessage){
  const {runs}=await api('/api/stories/'+storyId+'/runs');
  const pending=(runs||[]).filter(run=>!CLOSED.has(run.state));
  if(pending.some(run=>!STOPPED.has(run.state)))throw new Error(activeMessage);
  return pending;
}
async function cancelRuns(pending,unfinishedMessage){
  for(const run of pending){
    const result=await api('/api/runs/'+run.id+'/cancel',json('POST',{}));
    if(!CLOSED.has(result.state))throw new Error(unfinishedMessage);
  }
}

function action(label,callback){const button=document.createElement('button');button.type='button';button.className='secondary';uiText(button,"textContent",()=>(label));button.onclick=callback;return button}

export function installSceneTrash(state,refresh,clear){
  const moveToTrash=async()=>{
    if(state.dirty||state.saving){notice(msg("m_a4c2e86ecc1a"),'error');return}
    if(!state.scene){notice(msg("m_f0f1417db6de"),'error');return}
    const sceneId=state.scene.id,revision=state.scene.revision;
    let pending;
    try{pending=await stoppedRuns(state.storyId,t("scenes.active_run"))}catch(error){notice(error.message,'error');return}
    if(!await confirmDialog(pending.length?t("scenes.delete_confirm_runs",{p0:pending.length}):t("scenes.delete_confirm")))return;
    if(state.dirty||state.saving||state.scene?.id!==sceneId||state.scene.revision!==revision)return;
    trash.disabled=true;state.saving=true;
    const editor=createTextEditor(document.querySelector("#editor")),readOnly=editor.isReadOnly();editor.readOnly(true);
    document.dispatchEvent(new CustomEvent("editor-state-changed"));
    try{
      await cancelRuns(pending,t("scenes.cancel_unfinished"));
      await api('/api/scenes/'+state.scene.id+'/trash',json('POST',{story_id:state.storyId,expected_revision:state.scene.revision}));
      clear();state.saving=false;await refresh();notice(msg("scenes.deleted"));
    }catch(error){notice(error.message,'error')}finally{trash.disabled=false;state.saving=false;editor.readOnly(readOnly);document.dispatchEvent(new CustomEvent('editor-state-changed'))}
  };
  const trash=action(live(()=>(t("scenes.delete"))),moveToTrash);
  // #104: the same action as an icon next to the selected scene; it stays enabled and a click explains a refusal.
  const holder=document.createElement('div'),listButton=document.createElement('button'),icon=document.createElement('span');
  holder.className='scene-row-actions';listButton.type='button';listButton.className='scene-delete';icon.className='icon icon-trash';icon.setAttribute('aria-hidden','true');
  uiAttr(listButton,'aria-label',()=>t("scenes.delete"));uiText(listButton,'title',()=>t("scenes.delete"));
  listButton.append(icon);listButton.onclick=moveToTrash;holder.append(listButton);
  function place(){const row=state.scene&&document.querySelector('#scene-list .scene-item.active');if(row?.after)row.after(holder);else holder.remove?.()}
  // STORE-FOOTER: no delete in the footer; a narrow screen has no list, so the named button sits under the scene picker.
  trash.className+=' scene-delete-mobile';const picker=document.querySelector('#scene-select-mobile');if(picker?.after)picker.after(trash);
  function availability(){const reason=!state.scene?t("m_f0f1417db6de"):state.saving?t("m_1705600b6470"):state.dirty?t("m_a4c2e86ecc1a"):'';trash.disabled=!!reason;uiText(trash,"title",()=>(diagnostic(reason)));place()}
  for(const event of ['scene-selected','story-refreshed','editor-state-changed'])document.addEventListener(event,availability);availability();
  const details=document.createElement('details'),summary=document.createElement('summary'),list=document.createElement('div');
  uiText(summary,"textContent",()=>(t("m_62ad9a54bdd0")));details.append(summary,list);document.querySelector('.scene-panel').append(details);
  let epoch=0;
  async function load(){
    const current=++epoch;
    try{
      const result=await api('/api/stories/'+state.storyId+'/trash');if(current!==epoch)return;
      list.replaceChildren();
      for(const scene of result.scenes||[]){
        const row=document.createElement('p'),title=document.createElement('span');uiText(title,"textContent",()=>(scene.title+' '));
        const restore=action(live(()=>(t("m_11b6e5a88fd6"))),async()=>{
          if(restore.disabled)return;
          if(state.dirty||state.saving){notice(msg("m_a4c2e86ecc1a"),'error');return}
          restore.disabled=true;
          try{
            const pending=await stoppedRuns(state.storyId,t("scenes.active_run"));
            if(pending.length&&!await confirmDialog(t("scenes.restore_confirm_runs",{p0:pending.length})))return;
            if(state.dirty||state.saving){notice(msg("m_a4c2e86ecc1a"),'error');return}
            // The same buffer lock as moving to trash: no save or other trash action while runs are cancelled.
            state.saving=true;document.dispatchEvent(new CustomEvent('editor-state-changed'));
            await cancelRuns(pending,t("scenes.cancel_unfinished"));
            await api('/api/scenes/'+scene.id+'/restore',json('POST',{story_id:state.storyId,expected_revision:scene.revision}));
            state.saving=false;await refresh();notice(msg("m_415e821184f4"));
          }catch(error){notice(error.message,'error')}
          finally{restore.disabled=false;if(state.saving){state.saving=false;document.dispatchEvent(new CustomEvent('editor-state-changed'))}}
        });row.append(title,restore);list.append(row);
      }
      if(!(result.scenes||[]).length){const empty=document.createElement('p');uiText(empty,"textContent",()=>(t("m_f5afb4e831d7")));list.append(empty)}
    }catch(error){notice(error.message,'error')}
  }
  document.addEventListener('story-refreshed',load);
}

export function installLibraryTrash(){
  for(const button of document.querySelectorAll('[data-trash-story]'))button.onclick=async()=>{
    if(button.disabled)return;
    button.disabled=true;
    try{
      const pending=await stoppedRuns(button.dataset.trashStory,t("m_6be0942b3149"));
      const message=pending.length?t("m_3c7a4d78d4f4",{p0:(pending.length)}):t("m_b1e87fa38fde");
      if(!await confirmDialog(message))return;
      await cancelRuns(pending,t("m_6fd8fbdc1385"));
      await api('/api/stories/'+button.dataset.trashStory+'/trash',json('POST',{expected_revision:Number(button.dataset.revision)}));location.reload();
    }catch(error){notice(error.message,'error')}
    finally{button.disabled=false}
  };
  const list=document.querySelector('#story-trash-list');
  async function load(){
    try{
      const result=await api('/api/trash');list.replaceChildren();
      for(const story of result.stories){
        const row=document.createElement('p'),title=document.createElement('span');uiText(title,"textContent",()=>(story.title+' '));
        const restore=action(live(()=>(t("m_11b6e5a88fd6"))),async()=>{
          restore.disabled=true;
          try{await api('/api/stories/'+story.id+'/restore',json('POST',{expected_revision:story.revision}));location.reload()}
          catch(error){notice(error.message,'error');restore.disabled=false}
        });row.append(title,restore);list.append(row);
      }
      if(!result.stories.length)uiText(list,"textContent",()=>(t("m_f5afb4e831d7")));
    }catch(error){notice(error.message,'error')}
  }
  load();
}
