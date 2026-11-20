import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const {findLists,renumber,listsTouching,continueItem}=await import(pathToFileURL(root+'/src/storygen/web/static/plan-numbering.js'));
const apply=(text,lists=findLists(text))=>renumber(text,lists).text;

// S02: a new first item shifts the rest; parsed lines stay untouched.
const plan='## Сцена 2: Озеро\nХто бере участь: Анна, Борис\nПочаток: ранок\n1. Нове\n1. А\n2. Б\n';
assert.equal(apply(plan),'## Сцена 2: Озеро\nХто бере участь: Анна, Борис\nПочаток: ранок\n1. Нове\n2. А\n3. Б\n');

// Deletion and moves renumber from the first item's number.
assert.equal(apply('1. А\n3. В'),'1. А\n2. В');
assert.equal(apply('5) А\n5) Б\n9) В'),'5) А\n6) Б\n7) В');
assert.equal(apply('1. А\n3. В\n2. Б'),'1. А\n2. В\n3. Б');

// A blank line splits two lists; a non-item line without indent ends a list.
assert.equal(apply('1. А\n1. Б\n\n1. В\n5. Г'),'1. А\n2. Б\n\n1. В\n2. Г');
assert.equal(apply('1. А\nТекст\n1. Б'),'1. А\nТекст\n1. Б');

// Continuation lines (deeper indent) stay inside the list; deeper items are not renumbered with it.
assert.equal(apply('1. А\n   продовження\n1. Б'),'1. А\n   продовження\n2. Б');
assert.equal(apply('1. А\n  1. а\n  1. б\n1. Б'),'1. А\n  1. а\n  2. б\n2. Б');

// Different delimiters are different lists; "2026.рік" is not an item.
assert.equal(apply('1. А\n1) Б'),'1. А\n1) Б');
assert.equal(apply('2026.рік\n2026.рік'),'2026.рік\n2026.рік');
assert.equal(findLists('2026.рік').length,0);

// 9 -> 10 keeps the rest of the line; CRLF is kept.
assert.equal(apply('8. а\n8. б\n8. в'),'8. а\n9. б\n10. в');
assert.equal(apply('1. А\r\n1. Б\r\n'),'1. А\r\n2. Б\r\n');

// An explicit start restarts a list from that number.
assert.equal(renumber('4. А\n5. Б',findLists('4. А\n5. Б'),1).text,'1. А\n2. Б');

// Correct lists give no edits; a list past 999999 is left alone.
assert.deepEqual(renumber('1. А\n2. Б',findLists('1. А\n2. Б')).edits,[]);
assert.equal(apply('999999. А\n1. Б'),'999999. А\n1. Б');

// listsTouching picks every list a changed range crosses.
const two='1. А\n3. В\n\n1. Х\n1. Б\n2. Y';
const lists=listsTouching(two,two.indexOf('1. Б'),two.indexOf('1. Б')+4);
assert.equal(lists.length,1);
assert.equal(renumber(two,lists).text,'1. А\n3. В\n\n1. Х\n2. Б\n3. Y');
assert.equal(renumber(two,listsTouching(two,0,two.length)).text,'1. А\n2. В\n\n1. Х\n2. Б\n3. Y');
assert.equal(listsTouching('Текст\n1. А',2,2).length,0);

// S01: Enter at the end of an item continues the list with the same indent and delimiter.
assert.deepEqual(continueItem('  1) А\n  2) Б',6),{insert:'\n  2) ',caret:12});
assert.deepEqual(continueItem('1. Порожній\n2. ',15),{clear:{from:12,to:15}});
assert.equal(continueItem('1. А посередині',4),null);
assert.equal(continueItem('Текст',5),null);
console.log('plan numbering ok');
