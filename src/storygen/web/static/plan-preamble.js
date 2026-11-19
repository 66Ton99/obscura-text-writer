import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
// PLAN-PREAMBLE: the plan preamble (global author notes) is edited after import; a save is a new plan version.
const root=document.querySelector('[data-story-id]'),form=document.querySelector('#plan-preamble-form');
if(root&&form){
  const id=root.dataset.storyId,area=form.elements.text,button=form.querySelector('button'),status=form.querySelector('[data-plan-preamble-status]');
  const review=form.querySelector('[data-plan-preamble-review]');
  let state=null;
  function sync(){button.disabled=!state||!state.editable||area.value.trim()===state.text.trim()}
  async function load(){
    state=await api(`/api/stories/${id}/plan-preamble`);
    area.value=state.text;area.disabled=!state.editable;
    uiText(status,'textContent',()=>state.editable?'':t(state.reason==='no_plan'?'plan_preamble.no_plan':'plan_preamble.no_scenes'));
    sync();
  }
  area.oninput=sync;
  form.onsubmit=async event=>{
    event.preventDefault();if(!state||button.disabled)return;
    button.disabled=true;
    try{
      const result=await api(`/api/stories/${id}/plan-preamble`,json('PUT',{text:area.value,expected_plan_version_id:state.plan_version_id}));
      if(result.changed){review.href=`/stories/${id}/revision`;review.hidden=false}
      notice(msg(result.changed?'plan_preamble.saved':'plan_preamble.unchanged'));
      await load();
    }catch(error){
      // A refused or conflicting save keeps the author's text in the field: nothing was written.
      notice(error.message,'error');sync();
    }
  };
  load().catch(error=>notice(error.message,'error'));
}
