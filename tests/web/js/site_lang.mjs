// DOCS-SITE-S09: docs/site/site.js sends a visitor without Ukrainian in the browser to the English page.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const code=readFileSync(process.argv[2]+'/docs/site/site.js','utf-8');

function run({lang='uk',alt='en/install.html',languages=['en-US'],language,userAgent='Mozilla/5.0',stored=null,storage=true,search='?utm_source=ad',hash='#вимоги'}={}){
  const replaced=[];const saved={};let listener=null;
  const store=storage?{getItem:key=>key==='obscura.site.lang'?stored:null,setItem:(key,value)=>{saved[key]=value}}:null;
  const window={
    get localStorage(){if(!store)throw new Error('SecurityError');return store},
    location:{search,hash,replace:url=>replaced.push(url)},
  };
  const document={
    documentElement:{lang,getAttribute:name=>name==='data-alt'?alt:null},
    addEventListener:(type,fn)=>{if(type==='click')listener=fn},
  };
  vm.runInNewContext(code,{window,document,navigator:{languages,language,userAgent}});
  return {replaced,saved,click:target=>listener&&listener({target})};
}

// No Ukrainian in the browser: the English page, with the ad's query and without the Ukrainian section id.
assert.deepEqual(run({languages:['en-US','de']}).replaced,['en/install.html?utm_source=ad']);
// Ukrainian anywhere in the list keeps the page.
assert.deepEqual(run({languages:['en-US','uk-UA']}).replaced,[]);
assert.deepEqual(run({languages:['uk']}).replaced,[]);
// A tag that only starts with the letters "uk" is not Ukrainian.
assert.deepEqual(run({languages:['ukx']}).replaced,['en/install.html?utm_source=ad']);
// Older browsers expose only navigator.language.
assert.deepEqual(run({languages:[],language:'uk-UA'}).replaced,[]);
assert.deepEqual(run({languages:undefined,language:'fr'}).replaced,['en/install.html?utm_source=ad']);
// A remembered choice wins over the browser.
assert.deepEqual(run({languages:['en-US'],stored:'uk'}).replaced,[]);
assert.deepEqual(run({languages:['uk-UA'],stored:'en'}).replaced,['en/install.html?utm_source=ad']);
// Crawlers stay on the page they asked for.
assert.deepEqual(run({userAgent:'Mozilla/5.0 (compatible; Googlebot/2.1)'}).replaced,[]);
// English pages never move.
assert.deepEqual(run({lang:'en',alt:'../install.html',languages:['uk-UA'],stored:'uk'}).replaced,[]);
// Storage that throws neither breaks the page nor the redirect.
assert.deepEqual(run({storage:false,languages:['en-US']}).replaced,['en/install.html?utm_source=ad']);
const blocked=run({storage:false,languages:['uk-UA']});
blocked.click({closest:()=>({getAttribute:()=>'en'})});
assert.deepEqual(blocked.replaced,[]);

// The switcher remembers the language it leads to; other clicks remember nothing.
const page=run({languages:['uk-UA']});
page.click({closest:selector=>selector==='a[data-lang]'?{getAttribute:name=>name==='data-lang'?'en':null}:null});
assert.deepEqual(page.saved,{'obscura.site.lang':'en'});
const other=run({languages:['uk-UA']});
other.click({closest:()=>null});
assert.deepEqual(other.saved,{});
console.log('site language choice: ok');
