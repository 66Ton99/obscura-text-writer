// Language choice of the user-guide site (DOCS-SITE-S09). Ukrainian pages are the root, so a visitor
// whose browser lists no Ukrainian goes to the same page in English. A language picked with the
// switcher is remembered and wins over the browser (a remembered English also leaves Ukrainian pages). Crawlers stay put: hreflang links tell them about
// the other language. Storage may be unavailable (private mode, blocked cookies): then nothing is
// remembered and the browser languages decide.
(function(){
  var KEY='obscura.site.lang';
  var BOTS=/bot|crawl|spider|slurp|facebookexternalhit|preview/i;
  function read(){try{return window.localStorage.getItem(KEY)}catch(e){return null}}
  function write(lang){try{window.localStorage.setItem(KEY,lang)}catch(e){}}
  function speaksUkrainian(languages){
    for(var i=0;i<languages.length;i++)if(/^uk(-|$)/i.test(languages[i]||''))return true;
    return false;
  }
  var root=document.documentElement;
  var alt=root.getAttribute('data-alt');
  if(root.lang==='uk'&&alt){
    var stored=read();
    var languages=navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||''];
    var leave=stored==='en'||(stored!=='uk'&&!BOTS.test(navigator.userAgent||'')&&!speaksUkrainian(languages));
    // The query (utm_* of an ad) goes along; the hash does not, since section ids differ between languages.
    if(leave){window.location.replace(alt+(window.location.search||''));return}
  }
  document.addEventListener('click',function(event){
    var link=event.target&&event.target.closest?event.target.closest('a[data-lang]'):null;
    if(link)write(link.getAttribute('data-lang'));
  });
})();
