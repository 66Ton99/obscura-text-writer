import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {normalizeName,cardNames,cardMatches,findTarget}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/characters-state.js'));
const card=(name,...texts)=>({name,entries:texts.map(text=>({text}))});
assert.equal(normalizeName('  Анна   Марія ’ '),"анна марія '");
const host=card('Хазяїн','Вік: 40',"- **Інше ім’я:** Джон, Бос");
assert.deepEqual(cardNames(host),['Хазяїн','Джон','Бос']);
assert.equal(cardMatches(host,'джон'),true);
assert.equal(cardMatches(host,'ХАЗ'),true);
assert.equal(cardMatches(host,'40'),false);
assert.equal(cardMatches(host,''),true);
assert.equal(cardMatches(card(''),'зовсім інше'),true);
const cards=[card('Маріанна'),card('Анна'),host];
assert.equal(findTarget(cards,'анна'),1);
assert.equal(findTarget(cards,'анн'),0);
assert.equal(findTarget(cards,'бос'),2);
assert.equal(findTarget(cards,'ніхто'),-1);
// Parity with characters/names.py: the cases come from the Python test as JSON.
if(process.argv[3])console.log(JSON.stringify(JSON.parse(process.argv[3]).map(item=>cardNames(item))));
