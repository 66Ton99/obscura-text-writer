// PLAN-NUMBERING: keeps numbered lists of the scene plan in order while the author types (plain textarea only).
import {findLists,renumber,listsTouching,continueItem} from './plan-numbering.js';

// Structural edits only: typing inside a line never renumbers, so a number being typed ("1" → "12.") is not rewritten mid-way.
const BLOCK_TYPES=new Set(['insertFromPaste','insertFromDrop','deleteByDrag','deleteByCut']);
const LINE_TYPES=new Set(['insertText','insertLineBreak','insertParagraph','deleteContentBackward','deleteContentForward','deleteWordBackward','deleteWordForward']);
const breaks=text=>text.split('\n').length;

/** One replacement of the changed digits span, so the whole renumbering is one undo step. */
export function applyRenumber(element,lists,start=null){
  const text=element.value,{text:next,edits}=renumber(text,lists,start);
  if(!edits.length)return false;
  const from=edits[0].from,to=edits.at(-1).to,delta=next.length-text.length;
  const caret=element.selectionStart,caretEnd=element.selectionEnd;
  const shift=at=>at<=from?at:at>=to?at+delta:at+edits.filter(e=>e.to<=at).reduce((sum,e)=>sum+e.insert.length-(e.to-e.from),0);
  const span=next.slice(from,to+delta);
  // execCommand edits only the focused field; after a button click the focus is on the button.
  if(element.ownerDocument.activeElement!==element)element.focus();
  element.setSelectionRange(from,to);
  let done=false;
  try{done=element.ownerDocument.execCommand?.('insertText',false,span)===true&&element.value===next;}catch{done=false;}
  if(!done){
    element.value=text;element.setRangeText(span,from,to,'preserve');
    element.dispatchEvent(new Event('input',{bubbles:true}));
  }
  element.setSelectionRange(shift(caret),shift(caretEnd));
  return true;
}

export function installPlanNumbering({element,active}){
  let before=element.value,applying=false,inserting=false;
  const run=(lists,start=null)=>{applying=true;try{return applyRenumber(element,lists,start);}finally{applying=false;before=element.value;}};
  element.addEventListener('beforeinput',()=>{if(!applying)before=element.value;});
  element.addEventListener('input',event=>{
    if(applying)return;
    const after=element.value,old=before;before=after;
    // Our own Enter insert renumbers after execCommand returns: a nested execCommand would be refused and lose undo.
    if(inserting||!active())return;
    if(!BLOCK_TYPES.has(event.inputType)&&!(LINE_TYPES.has(event.inputType)&&breaks(old)!==breaks(after)))return;
    let start=0;while(start<old.length&&start<after.length&&old[start]===after[start])start++;
    let tail=0;while(tail<old.length-start&&tail<after.length-start&&old[old.length-1-tail]===after[after.length-1-tail])tail++;
    run(listsTouching(after,start,after.length-tail));
  });
  element.addEventListener('keydown',event=>{
    if(event.key!=='Enter'||event.shiftKey||event.ctrlKey||event.altKey||event.metaKey||event.isComposing||!active())return;
    if(element.selectionStart!==element.selectionEnd)return;
    const step=continueItem(element.value,element.selectionStart);
    if(!step)return;
    event.preventDefault();
    const doc=element.ownerDocument;
    if(step.clear){
      element.setSelectionRange(step.clear.from,step.clear.to);
      if(doc.execCommand?.('delete')!==true){element.setRangeText('',step.clear.from,step.clear.to,'end');element.dispatchEvent(new Event('input',{bubbles:true}));}
      // Leaving a list in the middle: the items below the now empty line start a new list from 1.
      const below=step.clear.from+1;
      run(findLists(element.value).filter(list=>list.start===below),1);
      return;
    }
    const at=element.selectionStart;
    inserting=true;
    try{
      if(doc.execCommand?.('insertText',false,step.insert)!==true){
        element.setRangeText(step.insert,at,element.selectionEnd,'end');
        element.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText'}));
      }
    }finally{inserting=false;}
    run(listsTouching(element.value,at,at+step.insert.length));
  });
  return {renumberAll:()=>active()&&run(findLists(element.value))};
}
