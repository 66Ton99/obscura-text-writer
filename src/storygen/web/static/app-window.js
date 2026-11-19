// DESKTOP-001-S08: in the Obscura window, links to other sites open in the default browser, not in this window.
// Loaded only for a desktop launch; links of this Obscura (same origin) and non-web links behave as usual.
const external=href=>{
  try{const url=new URL(href,location.href);return (url.protocol==='http:'||url.protocol==='https:')&&url.origin!==location.origin?url.href:null}
  catch{return null}
};
const send=url=>fetch('/api/app-window/open-external',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})}).catch(()=>{});
const follow=event=>{
  if(event.defaultPrevented||(event.type==='click'&&event.button!==0)||(event.type==='auxclick'&&event.button!==1))return;
  const link=event.target.closest?.('a[href]');
  const url=link&&!link.hasAttribute('download')&&external(link.getAttribute('href'));
  if(!url)return;
  event.preventDefault();
  send(url);
};
document.addEventListener('click',follow,true);
document.addEventListener('auxclick',follow,true);
const open=window.open.bind(window);
window.open=(href,...rest)=>{
  const url=href==null?null:external(String(href));
  if(!url)return open(href,...rest);
  send(url);
  return null;
};
