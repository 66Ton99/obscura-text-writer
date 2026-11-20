import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const F=await import(pathToFileURL(root+'/src/storygen/web/static/brief-form.js'));
const {parseBrief,stripPlannerNumbers,serializeBrief,briefForSave,canSaveBrief,moveItem,insertBefore,removeItem}=F;

// parseBrief: a valid brief, introduced kept as given.
const source={objective:'Мета',beats:['А','Б "в лапках"\nз переносом'],constraints:['Без діалогів'],proposed_changes:[],introduced:['c1']};
const parsed=parseBrief(JSON.stringify(source));
assert.equal(parsed.ok,true);
assert.deepEqual(parsed.model,{objective:'Мета',beats:['А','Б "в лапках"\nз переносом'],constraints:['Без діалогів'],proposed_changes:[],introduced:['c1'],hasIntroduced:true});

// Missing optional lists become empty; introduced null is kept as null.
const minimal=parseBrief('{"objective":"О","beats":["x"],"introduced":null}');
assert.equal(minimal.ok,true);
assert.deepEqual(minimal.model.constraints,[]);
assert.equal(minimal.model.introduced,null);
assert.equal(minimal.model.hasIntroduced,true);
assert.equal(parseBrief('{"objective":"О","beats":["x"]}').model.hasIntroduced,false);

// Empty beats are allowed while editing; empty or blank text gives an empty model with one empty beat.
assert.equal(parseBrief('{"objective":"","beats":[]}').ok,true);
assert.deepEqual(parseBrief('  \n').model,{objective:'',beats:[''],constraints:[],proposed_changes:[],introduced:null,hasIntroduced:false});

// What the form cannot show faithfully is not ok: unknown keys, wrong types, broken JSON.
assert.equal(parseBrief('{"objective":"О","beats":["x"],"mood":"y"}').ok,false);
assert.equal(parseBrief('{"objective":1,"beats":["x"]}').ok,false);
assert.equal(parseBrief('{"objective":"О","beats":[1]}').ok,false);
assert.equal(parseBrief('{"objective":"О","beats":"x"}').ok,false);
assert.equal(parseBrief('[]').ok,false);
const broken=parseBrief('{"objective":"О",');
assert.equal(broken.ok,false);
assert.ok(broken.error.length>0);

// stripPlannerNumbers: only a full 1..n sequence is stripped.
assert.deepEqual(stripPlannerNumbers(['1. А','2) Б','3.  В']),{beats:['А','Б','В'],stripped:true});
assert.deepEqual(stripPlannerNumbers(['1. А','3. Б']),{beats:['1. А','3. Б'],stripped:false});
assert.deepEqual(stripPlannerNumbers(['1990 рік, осінь','2. Б']),{beats:['1990 рік, осінь','2. Б'],stripped:false});
assert.deepEqual(stripPlannerNumbers(['А','Б']),{beats:['А','Б'],stripped:false});
assert.deepEqual(stripPlannerNumbers([]),{beats:[],stripped:false});

// serializeBrief: key order, empties kept, introduced only when it was in the source.
const text=serializeBrief({...parsed.model,beats:['',...parsed.model.beats]});
assert.deepEqual(Object.keys(JSON.parse(text)),['objective','beats','constraints','proposed_changes','introduced']);
assert.deepEqual(JSON.parse(text).beats,['','А','Б "в лапках"\nз переносом']);
assert.deepEqual(JSON.parse(text).introduced,['c1']);
assert.equal(text,JSON.stringify(JSON.parse(text),null,2));
assert.equal('introduced' in JSON.parse(serializeBrief(parseBrief('{"objective":"О","beats":["x"]}').model)),false);
assert.equal(JSON.parse(serializeBrief(minimal.model)).introduced,null);

// briefForSave drops items blank after trim; unparseable text goes as written.
const saved=JSON.parse(briefForSave(JSON.stringify({objective:'О',beats:[' ','А','  Б  '],constraints:['',' к '],proposed_changes:['\n'],introduced:['c1']})));
assert.deepEqual(saved,{objective:'О',beats:['А','  Б  '],constraints:[' к '],proposed_changes:[],introduced:['c1']});
assert.equal(briefForSave('{"objective":"О",'),'{"objective":"О",');
assert.equal(briefForSave('{"objective":"О","beats":["x"],"mood":"y"}'),'{"objective":"О","beats":["x"],"mood":"y"}');

// canSaveBrief needs one beat that is not blank.
assert.equal(canSaveBrief({beats:['',' ']}),false);
assert.equal(canSaveBrief({beats:['','А']}),true);
assert.equal(canSaveBrief({beats:[]}),false);

// List operations return new arrays.
const list=['А','Б','В'];
assert.deepEqual(moveItem(list,0,1),['Б','А','В']);
assert.deepEqual(moveItem(list,2,-1),['А','В','Б']);
assert.deepEqual(moveItem(list,0,-1),['А','Б','В']);
assert.deepEqual(moveItem(list,2,1),['А','Б','В']);
assert.deepEqual(insertBefore(list,0),['','А','Б','В']);
assert.deepEqual(insertBefore(list,1),['А','','Б','В']);
assert.deepEqual(insertBefore(list,3),['А','Б','В','']);
assert.deepEqual(removeItem(list,1),['А','В']);
assert.deepEqual(list,['А','Б','В']);
console.log('brief form ok');
