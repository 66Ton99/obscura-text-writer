// PLAN-NUMBERING: numbered lists in the plain-text scene plan. Pure functions; the editor binding lives in plan-numbering-editor.js.
const ITEM=/^([ \t]*)(\d{1,6})([.)])([ \t]+|$)/;
const MAX=999999;

function lines(text){
  const result=[];let from=0;
  for(const part of text.split('\n')){
    const body=part.endsWith('\r')?part.slice(0,-1):part;
    result.push({from,to:from+body.length,body});from+=part.length+1;
  }
  return result;
}
const indentOf=body=>body.match(/^[ \t]*/)[0].length;

/** Lists: runs of items with one indent and delimiter; deeper non-empty lines continue a list, anything else ends it. */
export function findLists(text){
  const rows=lines(text),taken=new Set(),lists=[];
  rows.forEach((row,index)=>{
    const head=ITEM.exec(row.body);
    if(!head||taken.has(index))return;
    const indent=head[1].length,delim=head[3],items=[];let last=index;
    for(let j=index;j<rows.length;j++){
      const body=rows[j].body;
      if(!body.trim())break;
      const match=ITEM.exec(body);
      if(match&&match[1].length===indent&&match[3]===delim){
        const from=rows[j].from+match[1].length;
        items.push({line:j,from,to:from+match[2].length,number:Number(match[2])});taken.add(j);last=j;
      }else if(indentOf(body)>indent)last=j;
      else break;
    }
    lists.push({start:rows[index].from,end:rows[last].to,indent,delim,items});
  });
  return lists.sort((a,b)=>a.start-b.start);
}

/** Item i of each list gets first+i (first: the list's own first number, or `start`); only the digits change. Lists that would pass 999999 stay as they are. */
export function renumber(text,lists,start=null){
  const edits=[];
  for(const list of lists){
    const first=list.items.length?(start??list.items[0].number):undefined;
    if(first===undefined||first+list.items.length-1>MAX)continue;
    list.items.forEach((item,i)=>{if(item.number!==first+i)edits.push({from:item.from,to:item.to,insert:String(first+i)})});
  }
  edits.sort((a,b)=>a.from-b.from);
  let result='',at=0;
  for(const edit of edits){result+=text.slice(at,edit.from)+edit.insert;at=edit.to;}
  return {text:result+text.slice(at),edits};
}

/** Every list whose lines cross [from, to] of the new text. */
export function listsTouching(text,from,to){
  return findLists(text).filter(list=>from<=list.end&&to>=list.start);
}

/** Enter at the end of an item: continue the list, or clear an empty item's marker. */
export function continueItem(text,offset){
  const row=lines(text).find(item=>offset>=item.from&&offset<=item.to);
  if(!row||offset!==row.to)return null;
  const match=ITEM.exec(row.body);
  if(!match)return null;
  if(!row.body.slice(match[0].length).trim())return {clear:{from:row.from,to:row.to}};
  const next=Number(match[2])+1;
  if(next>MAX)return null;
  const insert='\n'+match[1]+next+match[3]+' ';
  return {insert,caret:offset+insert.length};
}
