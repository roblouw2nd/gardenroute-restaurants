/**
 * Garden Route Restaurants — Local Admin Dashboard
 * Run: node server.js  (or: npm start)
 * Open: http://localhost:3001
 */

const express  = require('express');
const fs       = require('fs');
const path     = require('path');
const { spawn } = require('child_process');
const multer   = require('multer');

const app = express();
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

const ROOT          = path.join(__dirname, '..');
const DATA_DIR      = path.join(ROOT, 'data', 'restaurants');
const BLOGS_DIR     = path.join(ROOT, 'data', 'blogs');
const REVIEWS_DIR   = path.join(ROOT, 'data', 'reviews');
const SUBMISSIONS_F = path.join(ROOT, 'data', 'submissions.json');
const SCRAPER_DIR   = path.join(ROOT, 'scraper');
const IMG_BASE      = path.join(ROOT, 'site', 'public', 'images');

[BLOGS_DIR, REVIEWS_DIR].forEach(d => fs.mkdirSync(d, { recursive: true }));

// ── Multer (image uploads) ────────────────────────────────────────────────────
const upload = multer({
  storage: multer.diskStorage({
    destination: (req, file, cb) => {
      const dir = path.join(IMG_BASE, req.params.slug);
      fs.mkdirSync(dir, { recursive: true });
      cb(null, dir);
    },
    filename: (req, file, cb) => {
      const idx = req.params.idx || Date.now();
      const ext = path.extname(file.originalname) || '.jpg';
      cb(null, `${idx}${ext}`);
    },
  }),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => cb(null, file.mimetype.startsWith('image/')),
});

// Serve uploaded images
app.use('/images', express.static(IMG_BASE));

// ── Helpers ───────────────────────────────────────────────────────────────────
function loadAll() {
  return fs.readdirSync(DATA_DIR)
    .filter(f => f.endsWith('.json') && !f.startsWith('_'))
    .map(f => {
      try { return { file: f, ...JSON.parse(fs.readFileSync(path.join(DATA_DIR, f), 'utf-8')) }; }
      catch { return null; }
    })
    .filter(Boolean)
    .sort((a, b) => {
      const ap = a.sort_priority || 0, bp = b.sort_priority || 0;
      if (bp !== ap) return bp - ap;
      return (b.google_rating || 0) - (a.google_rating || 0);
    });
}

function getFile(slug) {
  const all = loadAll();
  return all.find(x => x.slug === slug);
}

function saveRestaurant(slug, data) {
  const r = getFile(slug);
  if (!r) return false;
  const filePath = path.join(DATA_DIR, r.file);
  data.last_updated = new Date().toISOString().split('T')[0];
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
  return true;
}

function loadJson(fpath, def = []) {
  if (!fs.existsSync(fpath)) return def;
  try { return JSON.parse(fs.readFileSync(fpath, 'utf-8')); }
  catch { return def; }
}

function saveJson(fpath, data) {
  fs.mkdirSync(path.dirname(fpath), { recursive: true });
  fs.writeFileSync(fpath, JSON.stringify(data, null, 2));
}

function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

// ── RESTAURANTS ───────────────────────────────────────────────────────────────

app.get('/api/restaurants', (req, res) => {
  const all = loadAll().map(r => ({
    file: r.file, slug: r.slug, name: r.name, town: r.town,
    google_rating: r.google_rating, google_review_count: r.google_review_count,
    featured: r.featured || false, home_featured: r.home_featured || false,
    price_level: r.price_level, cuisine_types: r.cuisine_types || [],
    sort_priority: r.sort_priority || 0,
    photos: r.photos || [], description_short: r.description_short || '',
    phone: r.phone || '', website: r.website || '', email: r.email || '',
  }));
  res.json(all);
});

app.get('/api/restaurants/:slug', (req, res) => {
  const r = getFile(req.params.slug);
  if (!r) return res.status(404).json({ error: 'Not found' });
  res.json(r);
});

// Full update
app.patch('/api/restaurants/:slug', (req, res) => {
  const r = getFile(req.params.slug);
  if (!r) return res.status(404).json({ error: 'Not found' });
  const filePath = path.join(DATA_DIR, r.file);
  const current  = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  const allowed  = [
    'name', 'featured', 'home_featured', 'sort_priority',
    'description_short', 'description_long',
    'phone', 'email', 'website', 'price_level',
    'cuisine_types', 'tags', 'opening_hours', 'menu_url',
    'seo_title', 'seo_description', 'photos',
  ];
  allowed.forEach(k => { if (req.body[k] !== undefined) current[k] = req.body[k]; });
  current.last_updated = new Date().toISOString().split('T')[0];
  fs.writeFileSync(filePath, JSON.stringify(current, null, 2));
  res.json({ ok: true });
});

// Delete restaurant + its images
app.delete('/api/restaurants/:slug', (req, res) => {
  const r = getFile(req.params.slug);
  if (!r) return res.status(404).json({ error: 'Not found' });
  fs.unlinkSync(path.join(DATA_DIR, r.file));
  const imgDir = path.join(IMG_BASE, req.params.slug);
  if (fs.existsSync(imgDir)) fs.rmSync(imgDir, { recursive: true });
  res.json({ ok: true });
});

// Toggle featured
app.post('/api/restaurants/:slug/featured', (req, res) => {
  const r = getFile(req.params.slug);
  if (!r) return res.status(404).json({ error: 'Not found' });
  const filePath = path.join(DATA_DIR, r.file);
  const current  = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  current.featured = !current.featured;
  current.last_updated = new Date().toISOString().split('T')[0];
  fs.writeFileSync(filePath, JSON.stringify(current, null, 2));
  res.json({ featured: current.featured });
});

// Toggle home_featured
app.post('/api/restaurants/:slug/home_featured', (req, res) => {
  const r = getFile(req.params.slug);
  if (!r) return res.status(404).json({ error: 'Not found' });
  const filePath = path.join(DATA_DIR, r.file);
  const current  = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  current.home_featured = !current.home_featured;
  current.last_updated = new Date().toISOString().split('T')[0];
  fs.writeFileSync(filePath, JSON.stringify(current, null, 2));
  res.json({ home_featured: current.home_featured });
});

// Set sort priority
app.post('/api/restaurants/:slug/priority', (req, res) => {
  const r = getFile(req.params.slug);
  if (!r) return res.status(404).json({ error: 'Not found' });
  const filePath = path.join(DATA_DIR, r.file);
  const current  = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  current.sort_priority = parseInt(req.body.priority) || 0;
  current.last_updated = new Date().toISOString().split('T')[0];
  fs.writeFileSync(filePath, JSON.stringify(current, null, 2));
  res.json({ ok: true });
});

// ── IMAGES ────────────────────────────────────────────────────────────────────

// List images for a restaurant
app.get('/api/restaurants/:slug/images', (req, res) => {
  const imgDir = path.join(IMG_BASE, req.params.slug);
  if (!fs.existsSync(imgDir)) return res.json([]);
  const files = fs.readdirSync(imgDir)
    .filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f))
    .sort()
    .map(f => `/images/${req.params.slug}/${f}`);
  res.json(files);
});

// Upload image
app.post('/api/restaurants/:slug/images/:idx', upload.single('image'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file' });
  const rel = `/images/${req.params.slug}/${req.file.filename}`;
  // Update the photos array in the JSON
  const r = getFile(req.params.slug);
  if (r) {
    const filePath = path.join(DATA_DIR, r.file);
    const current  = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    const idx = parseInt(req.params.idx);
    if (!current.photos) current.photos = [];
    if (current.photos[idx]) {
      current.photos[idx].url = rel;
    } else {
      current.photos.push({ url: rel, source: 'upload', caption: '' });
    }
    current.last_updated = new Date().toISOString().split('T')[0];
    fs.writeFileSync(filePath, JSON.stringify(current, null, 2));
  }
  res.json({ url: rel });
});

// Delete a specific image
app.delete('/api/restaurants/:slug/images/:filename', (req, res) => {
  const imgPath = path.join(IMG_BASE, req.params.slug, req.params.filename);
  if (fs.existsSync(imgPath)) fs.unlinkSync(imgPath);
  // Remove from photos array
  const r = getFile(req.params.slug);
  if (r) {
    const filePath = path.join(DATA_DIR, r.file);
    const current  = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    const target = `/images/${req.params.slug}/${req.params.filename}`;
    current.photos = (current.photos || []).filter(p => p.url !== target);
    current.last_updated = new Date().toISOString().split('T')[0];
    fs.writeFileSync(filePath, JSON.stringify(current, null, 2));
  }
  res.json({ ok: true });
});

// ── BLOGS ─────────────────────────────────────────────────────────────────────

app.get('/api/blogs', (req, res) => {
  const files = fs.existsSync(BLOGS_DIR)
    ? fs.readdirSync(BLOGS_DIR).filter(f => f.endsWith('.json'))
    : [];
  const blogs = files.map(f => {
    try { return JSON.parse(fs.readFileSync(path.join(BLOGS_DIR, f), 'utf-8')); }
    catch { return null; }
  }).filter(Boolean).sort((a, b) => new Date(b.date) - new Date(a.date));
  res.json(blogs);
});

app.get('/api/blogs/:id', (req, res) => {
  const fpath = path.join(BLOGS_DIR, `${req.params.id}.json`);
  if (!fs.existsSync(fpath)) return res.status(404).json({ error: 'Not found' });
  res.json(JSON.parse(fs.readFileSync(fpath, 'utf-8')));
});

app.post('/api/blogs', (req, res) => {
  const id   = req.body.id || uid();
  const blog = {
    id,
    title:   req.body.title || 'Untitled',
    slug:    req.body.slug || id,
    excerpt: req.body.excerpt || '',
    content: req.body.content || '',
    author:  req.body.author || 'Garden Route Team',
    date:    req.body.date || new Date().toISOString().split('T')[0],
    tags:    req.body.tags || [],
    published: req.body.published || false,
    hero_image: req.body.hero_image || '',
    seo_title: req.body.seo_title || '',
    seo_description: req.body.seo_description || '',
  };
  saveJson(path.join(BLOGS_DIR, `${id}.json`), blog);
  res.json(blog);
});

app.patch('/api/blogs/:id', (req, res) => {
  const fpath = path.join(BLOGS_DIR, `${req.params.id}.json`);
  if (!fs.existsSync(fpath)) return res.status(404).json({ error: 'Not found' });
  const current = JSON.parse(fs.readFileSync(fpath, 'utf-8'));
  const updated = { ...current, ...req.body, id: req.params.id };
  saveJson(fpath, updated);
  res.json({ ok: true });
});

app.delete('/api/blogs/:id', (req, res) => {
  const fpath = path.join(BLOGS_DIR, `${req.params.id}.json`);
  if (fs.existsSync(fpath)) fs.unlinkSync(fpath);
  res.json({ ok: true });
});

// ── CRITIC REVIEWS ────────────────────────────────────────────────────────────

app.get('/api/reviews', (req, res) => {
  const files = fs.existsSync(REVIEWS_DIR)
    ? fs.readdirSync(REVIEWS_DIR).filter(f => f.endsWith('.json'))
    : [];
  const reviews = files.map(f => {
    try { return JSON.parse(fs.readFileSync(path.join(REVIEWS_DIR, f), 'utf-8')); }
    catch { return null; }
  }).filter(Boolean).sort((a, b) => new Date(b.date) - new Date(a.date));
  res.json(reviews);
});

app.post('/api/reviews', (req, res) => {
  const id = req.body.id || uid();
  const review = {
    id,
    restaurant_slug: req.body.restaurant_slug || '',
    restaurant_name: req.body.restaurant_name || '',
    critic_name:     req.body.critic_name || '',
    score:           req.body.score || 0,
    title:           req.body.title || '',
    body:            req.body.body || '',
    date:            req.body.date || new Date().toISOString().split('T')[0],
    published:       req.body.published || false,
  };
  saveJson(path.join(REVIEWS_DIR, `${id}.json`), review);
  res.json(review);
});

app.patch('/api/reviews/:id', (req, res) => {
  const fpath = path.join(REVIEWS_DIR, `${req.params.id}.json`);
  if (!fs.existsSync(fpath)) return res.status(404).json({ error: 'Not found' });
  const current = JSON.parse(fs.readFileSync(fpath, 'utf-8'));
  saveJson(fpath, { ...current, ...req.body, id: req.params.id });
  res.json({ ok: true });
});

app.delete('/api/reviews/:id', (req, res) => {
  const fpath = path.join(REVIEWS_DIR, `${req.params.id}.json`);
  if (fs.existsSync(fpath)) fs.unlinkSync(fpath);
  res.json({ ok: true });
});

// ── SUBMISSIONS ───────────────────────────────────────────────────────────────

app.get('/api/submissions', (req, res) => res.json(loadJson(SUBMISSIONS_F)));

app.patch('/api/submissions/:id', (req, res) => {
  const subs = loadJson(SUBMISSIONS_F);
  const i = subs.findIndex(s => s.id === req.params.id);
  if (i === -1) return res.status(404).json({ error: 'Not found' });
  subs[i] = { ...subs[i], ...req.body };
  saveJson(SUBMISSIONS_F, subs);
  res.json({ ok: true });
});

app.delete('/api/submissions/:id', (req, res) => {
  saveJson(SUBMISSIONS_F, loadJson(SUBMISSIONS_F).filter(s => s.id !== req.params.id));
  res.json({ ok: true });
});

// ── SCRAPER ───────────────────────────────────────────────────────────────────

let scraperProc = null;
let scraperLog  = [];

app.get('/api/scraper/status', (req, res) => {
  res.json({ running: scraperProc !== null, log: scraperLog.slice(-300) });
});

app.post('/api/scraper/run', (req, res) => {
  if (scraperProc) return res.status(409).json({ error: 'Already running' });
  scraperLog = [];
  const args = req.body.corridor ? ['main.py', '--corridor'] : ['main.py'];
  scraperProc = spawn('python3', args, { cwd: SCRAPER_DIR });
  scraperProc.stdout.on('data', d => scraperLog.push(d.toString()));
  scraperProc.stderr.on('data', d => scraperLog.push('[ERR] ' + d.toString()));
  scraperProc.on('close', () => { scraperLog.push('\n✓ Scraper finished.'); scraperProc = null; });
  res.json({ ok: true });
});

app.post('/api/scraper/stop', (req, res) => {
  if (scraperProc) { scraperProc.kill(); scraperProc = null; }
  res.json({ ok: true });
});

// ── GIT PUBLISH ───────────────────────────────────────────────────────────────

let publishLog  = [];
let publishProc = null;

app.get('/api/publish/status', (req, res) => {
  res.json({ running: publishProc !== null, log: publishLog });
});

app.post('/api/publish', (req, res) => {
  if (publishProc) return res.status(409).json({ error: 'Already running' });
  const message = req.body.message || `Content update ${new Date().toLocaleDateString('en-ZA')}`;
  publishLog = [];

  // Run git add -A && git commit && git push as a shell sequence
  publishProc = spawn('bash', [
    '-c',
    `cd "${ROOT}" && git add -A && git diff --cached --quiet && echo "NOCHANGES" || (git commit -m "${message.replace(/"/g, "'")}" && git push origin main)`
  ]);

  publishProc.stdout.on('data', d => publishLog.push(d.toString()));
  publishProc.stderr.on('data', d => publishLog.push(d.toString()));
  publishProc.on('close', code => {
    if (publishLog.join('').includes('NOCHANGES')) {
      publishLog.push('\n⚠ Nothing to publish — no changes since last push.');
    } else if (code === 0) {
      publishLog.push('\n✓ Published! Netlify will deploy in ~2 minutes.');
    } else {
      publishLog.push(`\n✗ git exited with code ${code}`);
    }
    publishProc = null;
  });

  res.json({ ok: true });
});

// ── STATS ─────────────────────────────────────────────────────────────────────

app.get('/api/stats', (req, res) => {
  const all  = loadAll();
  const subs = loadJson(SUBMISSIONS_F);
  const noPhoto = all.filter(r => !r.photos?.length || !r.photos[0]?.url).length;
  const noDesc  = all.filter(r => !r.description_short).length;
  const noHours = all.filter(r => !r.opening_hours || Object.values(r.opening_hours).every(v => v === 'Hours not available')).length;
  res.json({
    total: all.length,
    towns: [...new Set(all.map(r => r.town))].length,
    featured: all.filter(r => r.featured).length,
    home_featured: all.filter(r => r.home_featured).length,
    no_photo: noPhoto,
    no_description: noDesc,
    no_hours: noHours,
    pending_submissions: subs.filter(s => s.status === 'pending').length,
    blogs: fs.existsSync(BLOGS_DIR) ? fs.readdirSync(BLOGS_DIR).filter(f => f.endsWith('.json')).length : 0,
    reviews: fs.existsSync(REVIEWS_DIR) ? fs.readdirSync(REVIEWS_DIR).filter(f => f.endsWith('.json')).length : 0,
  });
});

// ── SPA ───────────────────────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));
app.get('*', (req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`\n🌊 Garden Route Admin  →  http://localhost:${PORT}\n`);
});
