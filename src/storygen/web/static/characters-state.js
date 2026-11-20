import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
export class CharacterBuffer{
  cards=[];revision=null;dirty=false;saving=false;epoch=0;loadToken=0;previewToken=0;
  beginLoad(){return ++this.loadToken}
  loaded(data,token){
    if(token!==this.loadToken||this.dirty||this.saving)return false;
    this.cards=structuredClone(data.cards);this.revision=data.revision;this.epoch++;return true;
  }
  changed(){this.dirty=true;this.epoch++;this.loadToken++}
  beginSave(){
    if(this.saving)throw new Error(t("m_01f186c728c3"));
    this.saving=true;this.loadToken++;return {epoch:this.epoch,cards:structuredClone(this.cards),expected_revision:this.revision};
  }
  saved(data,snapshot){
    this.saving=false;
    if(this.epoch!==snapshot.epoch)return false;
    this.cards=structuredClone(data.cards);this.revision=data.revision;this.dirty=false;this.epoch++;return true;
  }
  failed(){this.saving=false}
  previewRequest(scene_id){return {token:++this.previewToken,epoch:this.epoch,scene_id}}
  previewCurrent(request,scene_id){return request.token===this.previewToken&&request.epoch===this.epoch&&request.scene_id===scene_id}
}

// CHARACTER-TIME-S04 (#75): card search. The name rule mirrors characters/names.py (CHARACTER-NAMES); a test keeps them equal.
const OTHER_NAMES=/^(?:інше\s+ім['’ʼ]я|інші\s+імена|також\s+відом(?:ий|а|і)\s+як|other\s+names?|also\s+known\s+as|aka)\s*:\s*(.*)$/iu;
export function normalizeName(value){
  return String(value||'').normalize('NFKC').toLowerCase().replace(/[’ʼ]/g,"'").split(/\s+/).filter(Boolean).join(' ').replace(/\.+$/,'');
}
function plainLine(line){return line.replace(/\*\*|__|\*/g,'').trim().replace(/^[\s\-—–]+/,'').trim()}
function splitNames(value){
  const spans=[],stack=[];
  [...value].forEach((char,index)=>{if(char==='(')stack.push(index);else if(char===')'&&stack.length){const start=stack.pop();if(!stack.length)spans.push([start,index+1])}});
  const names=[];let start=0;
  [...value].forEach((char,index)=>{if((char===','||char===';')&&!spans.some(([left,right])=>left<=index&&index<right)){names.push(value.slice(start,index));start=index+1}});
  names.push(value.slice(start));
  return names.map(name=>name.trim().replace(/\.+$/,'').trim()).filter(name=>name&&/[\p{L}\p{N}]/u.test(name));
}
export function cardNames(card){
  const names=[card.name||'',...(card.entries||[]).flatMap(entry=>String(entry.text||'').split(/\r?\n/).flatMap(line=>{const match=OTHER_NAMES.exec(plainLine(line));return match?splitNames(match[1]):[]}))];
  const seen=new Set();return names.filter(name=>{const key=normalizeName(name);if(!name||seen.has(key))return false;seen.add(key);return true});
}
export function cardMatches(card,query){
  const wanted=normalizeName(query);
  if(!wanted||!String(card.name||'').trim())return true;
  return cardNames(card).some(name=>normalizeName(name).includes(wanted));
}
export function findTarget(cards,query){
  const wanted=normalizeName(query);
  const exact=cards.findIndex(card=>wanted&&cardNames(card).some(name=>normalizeName(name)===wanted));
  return exact>=0?exact:cards.findIndex(card=>cardMatches(card,query));
}
