/**
 * Vercel Function: POST /api/form
 *
 * Receives the "Claim your listing" (/claim) and "Add a restaurant" (/submit)
 * forms and emails each one to the site mailbox over SMTP. The browser is then
 * redirected back to the form page with ?success=true or ?error=true.
 *
 * Set these in Vercel → Project → Settings → Environment Variables:
 *   SMTP_HOST   e.g. envoy.aserv.co.za
 *   SMTP_PORT   465 (SSL) or 587 (STARTTLS) — defaults to 465
 *   SMTP_USER   the mailbox that sends, e.g. info@gardenroute-restaurants.co.za
 *   SMTP_PASS   that mailbox's password
 *   MAIL_TO     optional — where requests are delivered (defaults to SMTP_USER)
 */
import nodemailer from 'nodemailer';

const SITE_URL = 'https://www.gardenroute-restaurants.co.za';
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SLUG_RE  = /^[a-z0-9-]{1,150}$/;

// One entry per form. `fields` is [input name, label in the email, max length].
const FORMS = {
  claim: {
    page: '/claim/',
    required: ['restaurant', 'name', 'role', 'email', 'authorised'],
    replyTo: 'email',
    subject: f => `Listing claim: ${f.restaurant}`,
    fields: [
      ['restaurant', 'Listing', 150],
      ['name', 'Name', 120],
      ['role', 'Role', 60],
      ['email', 'Work email', 200],
      ['phone', 'Phone', 40],
      ['authorised', 'Confirmed authorised', 10],
      ['message', 'Requested changes', 2000],
    ],
  },
  'add-restaurant': {
    page: '/submit/',
    required: ['name', 'town'],
    replyTo: 'submitter_email',
    subject: f => `New restaurant suggestion: ${f.name} (${f.town})`,
    fields: [
      ['name', 'Restaurant name', 150],
      ['town', 'Town', 60],
      ['address', 'Street address', 200],
      ['website', 'Website', 300],
      ['restaurant_email', 'Restaurant contact email', 200],
      ['notes', 'Notes', 2000],
      ['submitter_email', 'Submitted by', 200],
    ],
  },
};

const MULTILINE = new Set(['message', 'notes']);
const EMAIL_FIELDS = new Set(['email', 'restaurant_email', 'submitter_email']);

function clean(value, max, multiline) {
  const s = String(value ?? '').replace(/\r\n?/g, '\n');
  return (multiline ? s : s.replace(/\n+/g, ' ')).trim().slice(0, max);
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).send('Method not allowed');
  }

  const body = typeof req.body === 'string'
    ? Object.fromEntries(new URLSearchParams(req.body))
    : (req.body || {});

  const form = FORMS[body['form-name']];
  if (!form) return res.status(400).send('Unknown form');

  const done = (ok) => res.redirect(303, `${form.page}?${ok ? 'success' : 'error'}=true`);

  // Honeypot: bots fill the hidden field. Report success, send nothing.
  if (body['bot-field']) return done(true);

  const data = {};
  for (const [name, , max] of form.fields) data[name] = clean(body[name], max, MULTILINE.has(name));

  const valid =
    form.required.every(name => data[name]) &&
    [...EMAIL_FIELDS].every(name => !data[name] || EMAIL_RE.test(data[name])) &&
    (!('restaurant' in data) || SLUG_RE.test(data.restaurant));
  if (!valid) return done(false);

  const { SMTP_HOST, SMTP_USER, SMTP_PASS } = process.env;
  if (!SMTP_HOST || !SMTP_USER || !SMTP_PASS) {
    console.error('form: SMTP_HOST / SMTP_USER / SMTP_PASS are not set');
    return done(false);
  }
  const port = Number(process.env.SMTP_PORT) || 465;

  const lines = form.fields
    .filter(([name]) => data[name])
    .map(([name, label]) => MULTILINE.has(name) ? `${label}:\n${data[name]}` : `${label}: ${data[name]}`);
  if (data.restaurant) lines.push(`Listing page: ${SITE_URL}/${data.restaurant}/`);

  try {
    const transport = nodemailer.createTransport({
      host: SMTP_HOST,
      port,
      secure: port === 465,
      auth: { user: SMTP_USER, pass: SMTP_PASS },
    });
    await transport.sendMail({
      from: `"Garden Route Restaurants" <${SMTP_USER}>`,
      to: process.env.MAIL_TO || SMTP_USER,
      replyTo: data[form.replyTo] || undefined,
      subject: form.subject(data),
      text: lines.join('\n\n'),
    });
    return done(true);
  } catch (err) {
    console.error('form: send failed', err);
    return done(false);
  }
}
