// WAITLIST-001: the waitlist Worker against a fake D1 and a fake Turnstile check.
// Every test name starts with its scenario id; tests/test_waitlist_worker.py checks them by that prefix.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, { handle, purge, retentionCutoff, verifyTurnstile, REFUSAL } from '../src/index.js';

const SITE = 'https://obscurawriter.com';

// A D1 stand-in that keeps rows and honours the waitlist INSERT's ON CONFLICT(email) DO NOTHING.
function fakeDb({ fail = false, rows = [] } = {}) {
  const db = {
    calls: [],
    rows: new Map(rows.map((row) => [row.email, { ...row }])),
    prepare(sql) {
      return {
        bind(...values) {
          return {
            async run() {
              db.calls.push([sql, values]);
              if (fail) throw new Error('D1 down');
              if (!sql.startsWith('INSERT INTO waitlist')) return { meta: { changes: 1 } };
              const [email, lang, privacy_edition, created_at] = values;
              if (db.rows.has(email)) return { meta: { changes: 0 } };
              db.rows.set(email, { email, lang, privacy_edition, created_at });
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

// A chunked body: a stream has no Content-Length, so only the byte count of what was read can refuse it.
function streamed(text) {
  const bytes = new TextEncoder().encode(text);
  const body = new ReadableStream({
    start(controller) {
      for (let at = 0; at < bytes.length; at += 1000) controller.enqueue(bytes.slice(at, at + 1000));
      controller.close();
    },
  });
  const request = new Request('https://waitlist.obscurawriter.com/', {
    method: 'POST', body, duplex: 'half',
    headers: { Origin: SITE, 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  assert.equal(request.headers.get('Content-Length'), null);
  return request;
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

test('S02: same address in another case gives the same ok and leaves the row unchanged', async () => {
  const before = { email: 'ann@example.com', lang: 'uk', privacy_edition: '2026-11-01', created_at: '2026-11-02T08:00:00Z' };
  const db = fakeDb({ rows: [before] });
  const res = await handle(form({ ...GOOD, email: '  Ann@Example.COM ' }), env(db), deps());
  assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-ok');
  assert.equal(db.calls[0][1][0], 'ann@example.com');
  assert.equal(db.rows.size, 1);
  assert.deepEqual(db.rows.get('ann@example.com'), before);
});

test('S02: a new address after an existing one adds exactly one row', async () => {
  const db = fakeDb();
  const first = await handle(form(GOOD), env(db), deps());
  const again = await handle(form({ ...GOOD, email: 'ANN@example.com', lang: 'uk' }), env(db), deps());
  assert.equal(first.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-ok');
  assert.equal(again.headers.get('Location'), 'https://obscurawriter.com/paid.html#waitlist-ok');
  assert.equal(db.rows.size, 1);
  assert.equal(db.rows.get('ann@example.com').lang, 'en');
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
    [413, streamed(big)],
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
    [fakeDb({ fail: true }), undefined, 'Error'],
    [fakeDb(), () => { throw new TypeError('fetch failed'); }, 'TypeError'],
  ];
  for (const [db, verify, name] of runs) {
    const logs = [];
    const res = await handle(form(GOOD), env(db), deps({ verify, logs }));
    assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-error');
    assert.deepEqual(logs, [{ state: 'error', error: name }]);
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
  await handle(form(GOOD), env(), deps({ logs, verify: () => ({ success: false }) }));
  assert.deepEqual(logs, [{ state: 'ok' }, { state: 'invalid' }, { refused: 403 }, { state: 'captcha' }]);
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

test('S09: a missing day clamps to the end of the target month, never deleting early', () => {
  assert.equal(retentionCutoff(new Date('2028-02-29T03:17:00Z'), '24'), '2026-02-28T03:17:00Z');
  assert.equal(retentionCutoff(new Date('2027-03-31T03:17:00Z'), '1'), '2027-02-28T03:17:00Z');
  assert.equal(retentionCutoff(new Date('2028-03-31T03:17:00Z'), '1'), '2028-02-29T03:17:00Z');
  assert.equal(retentionCutoff(new Date('2027-01-31T00:00:00Z'), '3'), '2026-10-31T00:00:00Z');
  assert.equal(retentionCutoff(new Date('2027-01-15T00:00:00Z'), '13'), '2025-12-15T00:00:00Z');
});

// The real Turnstile check, with fetch stubbed: what is sent to siteverify and how its answers are read.
async function withFetch(answer, run) {
  const original = globalThis.fetch;
  const sent = [];
  globalThis.fetch = async (url, init) => {
    sent.push({ url, method: init.method, body: Object.fromEntries(init.body.entries()) });
    if (answer instanceof Error) throw answer;
    return answer;
  };
  try {
    return await run(sent);
  } finally {
    globalThis.fetch = original;
  }
}

test('S04: verifyTurnstile posts secret, token and client address to siteverify', async () => {
  await withFetch(Response.json({ success: true, hostname: 'obscurawriter.com' }), async (sent) => {
    assert.deepEqual(await verifyTurnstile('tok', '203.0.113.7', { TURNSTILE_SECRET: 's3' }), { success: true, hostname: 'obscurawriter.com' });
    assert.deepEqual(sent, [{
      url: 'https://challenges.cloudflare.com/turnstile/v0/siteverify', method: 'POST',
      body: { secret: 's3', response: 'tok', remoteip: '203.0.113.7' },
    }]);
  });
  await withFetch(Response.json({ success: false }), async (sent) => {
    await verifyTurnstile('tok', null, { TURNSTILE_SECRET: 's3' });
    assert.deepEqual(sent[0].body, { secret: 's3', response: 'tok' });
  });
});

test('S06: verifyTurnstile throws on a non-200 answer or a network failure', async () => {
  await withFetch(new Response('busy', { status: 503 }), async () => {
    await assert.rejects(verifyTurnstile('tok', null, { TURNSTILE_SECRET: 's3' }), /siteverify 503/);
  });
  await withFetch(new TypeError('fetch failed'), async () => {
    await assert.rejects(verifyTurnstile('tok', null, { TURNSTILE_SECRET: 's3' }), TypeError);
  });
});

test('S01: worker.fetch uses the real Turnstile check and records the address', async () => {
  const db = fakeDb();
  const quiet = console.log;
  console.log = () => {};
  try {
    await withFetch(Response.json({ success: true, hostname: 'obscurawriter.com' }), async (sent) => {
      const res = await worker.fetch(form(GOOD), { ...env(db), TURNSTILE_SECRET: 's3' });
      assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-ok');
      assert.equal(sent.length, 1);
      assert.equal(sent[0].body.secret, 's3');
    });
  } finally {
    console.log = quiet;
  }
  assert.equal(db.rows.size, 1);
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
