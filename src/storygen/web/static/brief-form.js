// BRIEF-FORM: the writer's brief (WritersBrief JSON) as a form model and back. Pure functions; the UI lives in brief-editor.js.
const KEYS=['objective','beats','constraints','proposed_changes','introduced'];
const LISTS=['beats','constraints','proposed_changes'];
const strings=value=>Array.isArray(value)&&value.every(item=>typeof item==='string');

/** {ok:true, model} or {ok:false, error}. Unknown keys are not ok: the form would not show them. */
export function parseBrief(text){
  if(!String(text??'').trim())return {ok:true,model:{objective:'',beats:[''],constraints:[],proposed_changes:[],introduced:null,hasIntroduced:false}};
  let data;
  try{data=JSON.parse(text);}catch(error){return {ok:false,error:error.message};}
  if(!data||typeof data!=='object'||Array.isArray(data))return {ok:false,error:'not an object'};
  const unknown=Object.keys(data).filter(key=>!KEYS.includes(key));
  if(unknown.length)return {ok:false,error:`unknown fields: ${unknown.join(', ')}`};
  if(typeof data.objective!=='string')return {ok:false,error:'objective'};
  for(const key of LISTS)if(key in data&&!strings(data[key])||key==='beats'&&!strings(data[key]))return {ok:false,error:key};
  if('introduced' in data&&data.introduced!==null&&!strings(data.introduced))return {ok:false,error:'introduced'};
  return {ok:true,model:{objective:data.objective,beats:[...data.beats],constraints:[...(data.constraints||[])],proposed_changes:[...(data.proposed_changes||[])],introduced:'introduced' in data?data.introduced:null,hasIntroduced:'introduced' in data}};
}

/** Strips "1. ", "2) " … only when every beat i carries number i+1 in order. */
export function stripPlannerNumbers(beats){
  const heads=beats.map((beat,i)=>new RegExp(`^\\s*${i+1}[.)]\\s+`).exec(beat));
  if(!beats.length||heads.some(head=>!head))return {beats:[...beats],stripped:false};
  return {beats:beats.map((beat,i)=>beat.slice(heads[i][0].length)),stripped:true};
}

/** The buffer text of the form: every item kept, in WritersBrief key order. */
export function serializeBrief(model){
  const data={objective:model.objective,beats:model.beats,constraints:model.constraints,proposed_changes:model.proposed_changes};
  if(model.hasIntroduced)data.introduced=model.introduced;
  return JSON.stringify(data,null,2);
}

/** What the save sends: items blank after trim are dropped; text the form cannot read goes as written. */
export function briefForSave(text){
  const parsed=parseBrief(text);
  if(!parsed.ok||!String(text).trim())return text;
  const model={...parsed.model};
  for(const key of LISTS)model[key]=model[key].filter(item=>item.trim());
  return serializeBrief(model);
}

export const canSaveBrief=model=>model.beats.some(beat=>beat.trim());

export function moveItem(list,index,step){
  const target=index+step;
  if(target<0||target>=list.length)return [...list];
  const next=[...list];[next[index],next[target]]=[next[target],next[index]];return next;
}
export const insertBefore=(list,index)=>[...list.slice(0,index),'',...list.slice(index)];
export const removeItem=(list,index)=>list.filter((_,i)=>i!==index);
