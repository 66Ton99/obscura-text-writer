import assert from 'node:assert/strict';
// STORE-FOOTER: isStoreEdition() is true only for the store edition; a failed app info counts as the full edition.
const cases=[[()=>Promise.resolve({ok:true,json:()=>Promise.resolve({edition:'store'})}),true],
  [()=>Promise.resolve({ok:true,json:()=>Promise.resolve({edition:'full'})}),false],
  [()=>Promise.resolve({ok:true,json:()=>Promise.resolve({edition:'paid'})}),false],
  [()=>Promise.resolve({ok:false}),false],
  [()=>Promise.reject(new Error('offline')),false]];
let n=0;
for(const [fetch,expected] of cases){
  globalThis.fetch=fetch;
  const {isStoreEdition}=await import(`../../../src/storygen/web/static/app-info.js?case=${n++}`);
  assert.equal(await isStoreEdition(),expected);
}
console.log('isStoreEdition passed');
