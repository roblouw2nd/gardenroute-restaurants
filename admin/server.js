/**
 * Garden Route Restaurants — Local Admin Dashboard
 * Run: node server.js  (or: npm start)
 * Open: http://localhost:3001
 */

const express = require('express');
const fs      = require('fs');
const path    = require('path');
const { execSync, spawn } = require('child_process');

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const DATA_DIR      = path.join(__dirname, '..', 'data', 'restaurants');
const SUBMISSIONS_F = path.join(__dirname, '..', 'data', 'submissions.json');
const SCRAPER_DIR   = path.join(__dirname, '..', 'scraper');

// ── Helpers ───────────────────────────────────────────────────────────────────

function loadAll() {
  return fs.readdirSync(DATA_DIR)
    .filter(f => f.endsWith('.json') && !f.startsWith('_'))
    .map(f => {
      try { return { file: f, ...JSON.parse(fs.readFileSync(path.join(DATA_DIR, f), 'utf-8')) }; }
      catch { return null; }
    })
    .filter(Boolean)
    .sort((a, b) => (b.google_rating || 0) - (a.google_rating || 0));
}

function loadSubmissions() {
  if (!fs.existsSync(SUBMISSIONS_F)) return [];
  try { return JSON.parse(fs.readFileSync(SUBMISSIONS_F, 'utf-8')); }
  catch { return []; }
}

function saveSubmissions(subs) {
  fs.mkdirSync(path.dirname(SUBMISSIONS_F), { recursive: true });
  fs.writeFileSync(SUBMISSIONS_F, JSON.stringify(subs, null, 2));
}

// ── API ───────────────────────────────────────────────────────────────────────

// List all restaurants (summary)
app.get('/api/restaurants', (req, res) => {
  const all = loadAll().map(r => ({
    file: r.file, slug: r.slug, name: r.name, town: r.town,
    google_rating: r.google_rating, google_review_count: r.google_review_count,
    featured: r.featured || false, price_level: r.price_level,
    cuisine_types: r.cuisine_types || [],
  }));
  res.json(all);
});

// Get single restaurant
app.get('/api/restaurants/:slug', (req, res) => {
  const all = loadAll();
  const r = all.find(x => x.slug === req.params.slug);
  if (!r) return res.status(404).json({ error: 'Not found' });
  res.json(r);
});

// Update restaurant (partial patch)
app.patch('/api/restaurants/:slug', (req, res) => {
  const all = loadAll();
  const r = all.find(x => x.slug === req.params.slug);
  if (!r) return res.status(404).json({ error: 'Not found' });

  const filePath = path.join(DATA_DIR, r.file);
  const current  = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  const allowed  = ['name','featured','description_short','description_long',
                    'phone','email','website','price_level','cuisine_types',
                    'tags','opening_hours','menu_url'];
  allowed.forEach(k => {
    if (req.body[k] !== undefined) current[k] = req.body[k];
  });
  current.last_updated = new Date().toISOString().split('T')[0];
  fs.writeFileSync(filePath, JSON.stringify(current, null, 2));
  res.json({ ok: true });
});

// Toggle featured
app.post('/api/restaurants/:slug/featured', (req, res) => {
  const all = loadAll();
  const r = all.find(x => x.slug === req.params.slug);
  if (!r) return res.status(404).json({ error: 'Not found' });
  const filePath = path.join(DATA_DIR, r.file);
  const current  = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  current.featured = !current.featured;
  fs.writeFileSync(filePath, JSON.stringify(current, null, 2));
  res.json({ featured: current.featured });
});

// Submissions
app.get('/api/submissions', (req, res) => res.json(loadSubmissions()));

app.patch('/api/submissions/:id', (req, res) => {
  const subs = loadSubmissions();
  const i = subs.findIndex(s => s.id === req.params.id);
  if (i === -1) return res.status(404).json({ error: 'Not found' });
  subs[i] = { ...subs[i], ...req.body };
  saveSubmissions(subs);
  res.json({ ok: true });
});

app.delete('/api/submissions/:id', (req, res) => {
  let subs = loadSubmissions();
  subs = subs.filter(s => s.id !== req.params.id);
  saveSubmissions(subs);
  res.json({ ok: true });
});

// Scraper control
let scraperProc = null;
let scraperLog  = [];

app.get('/api/scraper/status', (req, res) => {
  res.json({ running: scraperProc !== null, log: scraperLog.slice(-200) });
});

app.post('/api/scraper/run', (req, res) => {
  if (scraperProc) return res.status(409).json({ error: 'Scraper already running' });
  scraperLog = [];
  const args = req.body.corridor ? ['main.py', '--corridor'] : ['main.py'];
  scraperProc = spawn('python3', args, { cwd: SCRAPER_DIR });

  scraperProc.stdout.on('data', d => scraperLog.push(d.toString()));
  scraperProc.stderr.on('data', d => scraperLog.push('[ERR] ' + d.toString()));
  scraperProc.on('close', () => {
    scraperLog.push('\n✓ Scraper finished.');
    scraperProc = null;
  });

  res.json({ ok: true, message: 'Scraper started' });
});

app.post('/api/scraper/stop', (req, res) => {
  if (scraperProc) { scraperProc.kill(); scraperProc = null; }
  res.json({ ok: true });
});

// Stats
app.get('/api/stats', (req, res) => {
  const all = loadAll();
  const towns = [...new Set(all.map(r => r.town))];
  const featured = all.filter(r => r.featured).length;
  const subs = loadSubmissions();
  res.json({
    total: all.length,
    towns: towns.length,
    featured,
    submissions: subs.length,
    pending_submissions: subs.filter(s => s.status === 'pending').length,
  });
});

// ── Serve the SPA ─────────────────────────────────────────────────────────────
app.get('*', (req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`\n🌊 Garden Route Admin Dashboard`);
  console.log(`   Open: http://localhost:${PORT}\n`);
});
