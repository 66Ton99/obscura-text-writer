// WAITLIST-001: the paid-version waitlist. The site's form posts here; the Worker checks the form and
// Turnstile, stores the address once in D1 and sends the visitor back to the page with a result anchor.
// Neither the address nor the Turnstile token is ever logged.

export const REFUSAL =
  'Запит відхилено. Якщо ви заповнювали форму на obscurawriter.com, напишіть на privacy@obscurawriter.com.\n' +
  'Request refused. If you were filling in the form on obscurawriter.com, write to privacy@obscurawriter.com.\n';

const MAX_BODY = 4096;
const FORM_TYPE = 'application/x-www-form-urlencoded';
// One @, visible ASCII without spaces, a domain of non-empty dot-separated labels with at least one dot.
const EMAIL = /^[\x21-\x3f\x41-\x7e]+@[\x21-\x2d\x2f-\x3f\x41-\x7e]+(\.[\x21-\x2d\x2f-\x3f\x41-\x7e]+)+$/;
const INSERT =
  'INSERT INTO waitlist (email, lang, privacy_edition, created_at) VALUES (?, ?, ?, ?) ON CONFLICT(email) DO NOTHING';
const SITEVERIFY = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';

function defaultLog(entry) {
  console.log(JSON.stringify(entry));
}

export function normalizeEmail(raw) {
  const email = String(raw ?? '').trim().toLowerCase();
  return email.length <= 254 && EMAIL.test(email) ? email : null;
}

export function allowedOrigins(env) {
  return String(env.ALLOWED_ORIGINS ?? '').split(',').map((origin) => origin.trim()).filter(Boolean);
}

function stamp(date) {
  return date.toISOString().slice(0, 19) + 'Z';
}

function refuse(status, log) {
  log({ refused: status });
  return new Response(REFUSAL, { status, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}

function back(origin, lang, state) {
  const page = `${origin}/${lang === 'en' ? 'en/' : ''}paid.html#waitlist-${state}`;
  return new Response(null, { status: 303, headers: { Location: page } });
}

export async function verifyTurnstile(token, ip, env) {
  const body = new FormData();
  body.append('secret', env.TURNSTILE_SECRET ?? '');
  body.append('response', token);
  if (ip) body.append('remoteip', ip);
  const answer = await fetch(SITEVERIFY, { method: 'POST', body });
  if (!answer.ok) throw new Error(`siteverify ${answer.status}`);
  return answer.json();
}

export async function handle(request, env, deps = {}) {
  const verify = deps.verify ?? ((token, ip) => verifyTurnstile(token, ip, env));
  const now = deps.now ?? (() => new Date());
  const log = deps.log ?? defaultLog;

  if (request.method !== 'POST' || new URL(request.url).pathname !== '/') return refuse(405, log);
  const origin = request.headers.get('Origin');
  if (!origin || !allowedOrigins(env).includes(origin)) return refuse(403, log);
  if (!(request.headers.get('Content-Type') ?? '').toLowerCase().startsWith(FORM_TYPE)) return refuse(415, log);
  if (Number(request.headers.get('Content-Length') ?? 0) > MAX_BODY) return refuse(413, log);
  const raw = await request.text();
  if (new TextEncoder().encode(raw).length > MAX_BODY) return refuse(413, log);

  const fields = new URLSearchParams(raw);
  const lang = fields.get('lang') === 'en' ? 'en' : 'uk';
  const result = (state, error) => {
    log(error ? { state, error } : { state });
    return back(origin, lang, state);
  };
  const email = normalizeEmail(fields.get('email'));
  if (!email || fields.get('consent') !== 'yes') return result('invalid');

  const token = fields.get('cf-turnstile-response') ?? '';
  if (!token) return result('captcha');
  let check;
  try {
    check = await verify(token, request.headers.get('CF-Connecting-IP'));
  } catch (error) {
    return result('error', error?.name ?? 'Error');
  }
  if (check?.success !== true || check.hostname !== new URL(origin).hostname) return result('captcha');

  try {
    await env.DB.prepare(INSERT).bind(email, lang, env.PRIVACY_EDITION, stamp(now())).run();
  } catch (error) {
    return result('error', error?.name ?? 'Error');
  }
  return result('ok');
}

// Rows older than RETENTION_MONTHS are deleted daily. A day missing from the target month (29 February
// two years back, 31 March − 1) clamps to that month's last day, so no row goes before its time.
export function retentionCutoff(now, months) {
  if (!/^\d+$/.test(String(months ?? '')) || Number(months) <= 0) return null;
  const total = now.getUTCFullYear() * 12 + now.getUTCMonth() - Number(months);
  const year = Math.floor(total / 12);
  const month = total - year * 12;
  const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const cutoff = new Date(Date.UTC(year, month, Math.min(now.getUTCDate(), lastDay),
    now.getUTCHours(), now.getUTCMinutes(), now.getUTCSeconds()));
  return stamp(cutoff);
}

export async function purge(env, now, log = defaultLog) {
  const cutoff = retentionCutoff(now, env.RETENTION_MONTHS);
  if (cutoff === null) {
    log({ purge: 'invalid RETENTION_MONTHS' });
    return null;
  }
  const outcome = await env.DB.prepare('DELETE FROM waitlist WHERE created_at < ?').bind(cutoff).run();
  const purged = outcome?.meta?.changes ?? 0;
  log({ purged });
  return purged;
}

export default {
  fetch(request, env) {
    return handle(request, env);
  },
  scheduled(event, env, ctx) {
    ctx.waitUntil(purge(env, new Date(event.scheduledTime)));
  },
};
