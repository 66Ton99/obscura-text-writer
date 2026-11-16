// WAITLIST-001: the waitlist Worker against a fake D1 and a fake Turnstile check.
// Every test name starts with its scenario id; tests/test_waitlist_worker.py checks them by that prefix.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, { handle, purge, retentionCutoff, REFUSAL } from '../src/index.js';

const SITE = 'https://obscurawriter.com';

function fakeDb({ fail = false } = {}) {
  const db = {
    calls: [],
    prepare(sql) {
      return {
        bind(...values) {
          return {
            async run() {
              db.calls.push([sql, values]);
              if (fail) throw new Error('D1 down');
              return { meta: { changes: 1 } };
            },
          };
        },
      };
    },
  };
  return db;
}

function env(db = fakeDb()) {
  return { ALLOWED_ORIGINS: 'https://obscurawriter.com, http://localhost:8000', PRIVACY_EDITION: '2026-11-15', DB: db };
}

function deps({ verify, logs = [] } = {}) {
  const calls = [];
  return {
    calls,
    verify: async (token, ip) => {
      calls.push([token, ip]);
      return verify ? verify(token, ip) : { success: true, hostname: 'obscurawriter.com' };
    },
    now: () => new Date('2026-11-16T10:20:30.456Z'),
    log: (entry) => logs.push(entry),
  };
}

function form(fields, { origin = SITE, type = 'application/x-www-form-urlencoded', body, method = 'POST', path = '/', headers = {} } = {}) {
  const all = { ...headers };
  if (origin !== null) all.Origin = origin; // null = no Origin header (undefined would take the default)
  if (type) all['Content-Type'] = type;
  return new Request(`https://waitlist.obscurawriter.com${path}`, {
    method,
    headers: all,
    body: method === 'GET' ? undefined : body ?? new URLSearchParams(fields).toString(),
  });
}

const GOOD = { email: 'ann@example.com', consent: 'yes', lang: 'en', 'cf-turnstile-response': 't' };

test('S01: new address is recorded and redirects to the page language', async () => {
  const db = fakeDb();
  const res = await handle(form(GOOD), env(db), deps());
  assert.equal(res.status, 303);
  assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-ok');
  assert.equal(db.calls.length, 1);
  assert.deepEqual(db.calls[0][1], ['ann@example.com', 'en', '2026-11-15', '2026-11-16T10:20:30Z']);
  assert.match(db.calls[0][0], /^INSERT INTO waitlist \(email, lang, privacy_edition, created_at\) VALUES \(\?, \?, \?, \?\) ON CONFLICT\(email\) DO NOTHING$/);
});

test('S01: unknown lang falls back to uk', async () => {
  const db = fakeDb();
  const res = await handle(form({ ...GOOD, lang: 'de' }), env(db), deps());
  assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/paid.html#waitlist-ok');
  assert.equal(db.calls[0][1][1], 'uk');
});

test('S01: localhost origin redirects back to localhost', async () => {
  const db = fakeDb();
  const d = deps({ verify: () => ({ success: true, hostname: 'localhost' }) });
  const res = await handle(form({ ...GOOD, lang: 'uk' }, { origin: 'http://localhost:8000' }), env(db), d);
  assert.equal(res.headers.get('Location'), 'http://localhost:8000/paid.html#waitlist-ok');
  assert.equal(db.calls.length, 1);
});

test('S01: the client address goes to Turnstile but not to D1', async () => {
  const db = fakeDb();
  const d = deps();
  await handle(form(GOOD, { headers: { 'CF-Connecting-IP': '203.0.113.7' } }), env(db), d);
  assert.deepEqual(d.calls, [['t', '203.0.113.7']]);
  assert.ok(!JSON.stringify(db.calls).includes('203.0.113.7'));
});

test('S02: same address in another case gives the same ok', async () => {
  const db = fakeDb();
  const res = await handle(form({ ...GOOD, email: '  Ann@Example.COM ' }), env(db), deps());
  assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-ok');
  assert.equal(db.calls[0][1][0], 'ann@example.com');
  assert.match(db.calls[0][0], /ON CONFLICT\(email\) DO NOTHING/);
});

test('S03: invalid email or missing consent gives invalid without verify or D1', async () => {
  const cases = [
    { email: '' }, { email: 'no-at' }, { email: 'a@b' }, { email: 'a@@b.c' }, { email: 'a b@c.d' },
    { email: 'тест@приклад.укр' }, { email: 'a\tb@c.d' }, { email: 'a@b..c' }, { email: '@b.c' },
    { email: 'a'.repeat(243) + '@example.com' },
    { consent: undefined }, { consent: 'on' },
  ];
  for (const change of cases) {
    const fields = { ...GOOD, ...change };
    for (const key of Object.keys(fields)) if (fields[key] === undefined) delete fields[key];
    const db = fakeDb();
    const d = deps();
    const res = await handle(form(fields), env(db), d);
    assert.equal(res.status, 303, JSON.stringify(change));
    assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-invalid', JSON.stringify(change));
    assert.equal(d.calls.length, 0, JSON.stringify(change));
    assert.equal(db.calls.length, 0, JSON.stringify(change));
  }
});

test('S04: turnstile failure, wrong hostname or empty token gives captcha without a row', async () => {
  const cases = [
    [GOOD, () => ({ success: false, 'error-codes': ['timeout-or-duplicate'] })],
    [GOOD, () => ({ success: true, hostname: 'evil.example' })],
    [GOOD, () => ({ success: true })],
    [{ ...GOOD, 'cf-turnstile-response': '' }, undefined],
  ];
  for (const [fields, verify] of cases) {
    const db = fakeDb();
    const res = await handle(form(fields), env(db), deps({ verify }));
    assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-captcha');
    assert.equal(db.calls.length, 0);
  }
});

test('S05: refusals are plain text without redirect', async () => {
  const big = new URLSearchParams({ ...GOOD, pad: 'x'.repeat(5000) }).toString();
  const cases = [
    [405, form(GOOD, { method: 'GET' })],
    [405, form(GOOD, { method: 'PUT' })],
    [405, form(GOOD, { path: '/other' })],
    [403, form(GOOD, { origin: null })],
    [403, form(GOOD, { origin: 'null' })],
    [403, form(GOOD, { origin: 'https://www.obscurawriter.com' })],
    [403, form(GOOD, { origin: 'https://obscurawriter.com.evil.example' })],
    [415, form(GOOD, { type: 'application/json' })],
    [415, form(GOOD, { type: '' })],
    [413, form(GOOD, { headers: { 'Content-Length': '5000' } })],
    [413, form(GOOD, { body: big })],
  ];
  for (const [status, request] of cases) {
    const db = fakeDb();
    const d = deps();
    const res = await handle(request, env(db), d);
    assert.equal(res.status, status);
    assert.equal(res.headers.get('Location'), null);
    assert.equal(res.headers.get('Content-Type'), 'text/plain; charset=utf-8');
    assert.equal(await res.text(), REFUSAL);
    assert.equal(d.calls.length, 0);
    assert.equal(db.calls.length, 0);
  }
});

test('S05: the refusal text names privacy@ in both languages', () => {
  assert.match(REFUSAL, /Запит відхилено/);
  assert.match(REFUSAL, /Request refused/);
  assert.equal(REFUSAL.match(/privacy@obscurawriter\.com/g).length, 2);
});

test('S06: D1 or network failure gives error and logs no address', async () => {
  const runs = [
    [fakeDb({ fail: true }), undefined],
    [fakeDb(), () => { throw new TypeError('fetch failed'); }],
  ];
  for (const [db, verify] of runs) {
    const logs = [];
    const res = await handle(form(GOOD), env(db), deps({ verify, logs }));
    assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-error');
    assert.ok(logs.some((entry) => entry.state === 'error' && entry.error));
    const text = JSON.stringify(logs);
    assert.ok(!text.includes('ann@example.com'));
    assert.ok(!text.includes('"t"'));
  }
});

test('S06: every outcome is logged without the address', async () => {
  const logs = [];
  await handle(form(GOOD), env(), deps({ logs }));
  await handle(form({ ...GOOD, email: 'bad' }), env(), deps({ logs }));
  await handle(form(GOOD, { origin: 'null' }), env(), deps({ logs }));
  assert.deepEqual(logs, [{ state: 'ok' }, { state: 'invalid' }, { refused: 403 }]);
});

test('S09: purge deletes rows older than the retention period', async () => {
  const calls = [];
  const db = { prepare: (sql) => ({ bind: (...values) => ({ run: async () => { calls.push([sql, values]); return { meta: { changes: 3 } }; } }) }) };
  const logs = [];
  assert.equal(retentionCutoff(new Date('2028-11-16T03:17:00.900Z'), '24'), '2026-11-16T03:17:00Z');
  assert.equal(await purge({ DB: db, RETENTION_MONTHS: '24' }, new Date('2028-11-16T03:17:00Z'), (e) => logs.push(e)), 3);
  assert.deepEqual(calls, [['DELETE FROM waitlist WHERE created_at < ?', ['2026-11-16T03:17:00Z']]]);
  assert.deepEqual(logs, [{ purged: 3 }]);
});

test('S09: invalid RETENTION_MONTHS deletes nothing', async () => {
  for (const months of ['', 'abc', '0', '-1', '1.5', ' 24', undefined]) {
    const db = fakeDb();
    const logs = [];
    assert.equal(retentionCutoff(new Date('2028-11-16T03:17:00Z'), months), null, String(months));
    assert.equal(await purge({ DB: db, RETENTION_MONTHS: months }, new Date('2028-11-16T03:17:00Z'), (e) => logs.push(e)), null);
    assert.equal(db.calls.length, 0);
    assert.deepEqual(logs, [{ purge: 'invalid RETENTION_MONTHS' }]);
  }
});

test('S09: scheduled hands purge to waitUntil', async () => {
  const db = fakeDb();
  const pending = [];
  const quiet = console.log;
  console.log = () => {};
  try {
    worker.scheduled({ scheduledTime: Date.parse('2028-11-16T03:17:00Z') }, { DB: db, RETENTION_MONTHS: '24' }, { waitUntil: (p) => pending.push(p) });
    assert.equal(pending.length, 1);
    await pending[0];
  } finally {
    console.log = quiet;
  }
  assert.deepEqual(db.calls, [['DELETE FROM waitlist WHERE created_at < ?', ['2026-11-16T03:17:00Z']]]);
});
