// Servicio de scraping de ofertas de empleo.
//
//   GET  /health            -> { ok: true }
//   POST /scrape            -> { ok, source, scrapedAt, jobs: [...] }
//        body JSON: { keywords: "a,b,c", location: "Barcelona", maxJobs: 30 }
//
// Estrategia:
//   1. LinkedIn (páginas públicas de invitado, sin login) con Playwright.
//   2. Si LinkedIn bloquea o no devuelve nada -> arbeitnow.com (API pública,
//      sin credenciales). Así el workflow SIEMPRE tiene datos con los que
//      trabajar aunque LinkedIn corte el acceso anónimo.
//
// El scraping con login real de LinkedIn/InfoJobs (cookies) se añade al final,
// cuando se configuren las credenciales.

import http from 'node:http';
import { chromium } from 'playwright';

const PORT = Number(process.env.PORT || 3000);
const NAV_TIMEOUT = Number(process.env.SCRAPE_NAV_TIMEOUT || 25000);
const UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

const clean = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();
const tokens = (kw) =>
  String(kw || '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);

// ---------------------------------------------------------------- LinkedIn ---
async function scrapeLinkedIn({ keywords, location, maxJobs }) {
  const terms = tokens(keywords).slice(0, 3);
  if (terms.length === 0) terms.push('');

  const browser = await chromium.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const ctx = await browser.newContext({ userAgent: UA, locale: 'es-ES' });
  const page = await ctx.newPage();
  const seen = new Set();
  const jobs = [];

  try {
    for (const term of terms) {
      if (jobs.length >= maxJobs) break;
      const url =
        'https://www.linkedin.com/jobs/search?' +
        new URLSearchParams({
          keywords: term,
          location: location || '',
          f_TPR: 'r604800', // última semana
          position: '1',
          pageNum: '0',
        }).toString();

      try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
      } catch {
        continue;
      }

      // Muro de login / captcha -> abortamos LinkedIn.
      if (/\/authwall|\/checkpoint\/challenge|\/login/.test(page.url())) {
        throw new Error('linkedin-authwall');
      }

      await page
        .waitForSelector('.jobs-search__results-list li, .base-search-card', { timeout: 8000 })
        .catch(() => {});

      const cards = await page.$$eval(
        '.jobs-search__results-list li, ul.jobs-search__results-list > li',
        (lis) =>
          lis.map((li) => {
            const q = (sel) => li.querySelector(sel);
            const a = q('a.base-card__full-link, a.base-search-card__title-link, a[href*="/jobs/view/"]');
            return {
              title: q('.base-search-card__title')?.textContent || q('h3')?.textContent || '',
              company: q('.base-search-card__subtitle')?.textContent || q('h4')?.textContent || '',
              location: q('.job-search-card__location')?.textContent || '',
              link: a?.href || '',
              postedAt: q('time')?.getAttribute('datetime') || '',
            };
          })
      );

      for (const c of cards) {
        const link = clean(c.link).split('?')[0];
        if (!link || seen.has(link)) continue;
        seen.add(link);
        jobs.push({
          title: clean(c.title),
          company: clean(c.company),
          location: clean(c.location),
          link,
          postedAt: clean(c.postedAt),
          descriptionSnippet: '',
          matchedTerm: term,
        });
        if (jobs.length >= maxJobs) break;
      }
    }
  } finally {
    await browser.close().catch(() => {});
  }

  return jobs;
}

// --------------------------------------------------------------- arbeitnow ---
async function scrapeArbeitnow({ keywords, maxJobs }) {
  const terms = tokens(keywords);
  const res = await fetch('https://www.arbeitnow.com/api/job-board-api', {
    headers: { 'user-agent': UA, accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`arbeitnow ${res.status}`);
  const body = await res.json();
  const rows = Array.isArray(body.data) ? body.data : [];

  const match = (job) => {
    if (terms.length === 0) return true;
    const hay = (
      job.title +
      ' ' +
      (job.tags || []).join(' ') +
      ' ' +
      (job.job_types || []).join(' ')
    ).toLowerCase();
    return terms.some((t) => hay.includes(t));
  };

  return rows
    .filter(match)
    .slice(0, maxJobs)
    .map((j) => ({
      title: clean(j.title),
      company: clean(j.company_name),
      location: clean(j.location) + (j.remote ? ' (remoto)' : ''),
      link: j.url,
      postedAt: j.created_at ? new Date(j.created_at * 1000).toISOString() : '',
      descriptionSnippet: clean(String(j.description || '').replace(/<[^>]+>/g, '')).slice(0, 500),
      matchedTerm: terms.find((t) =>
        (j.title + ' ' + (j.tags || []).join(' ')).toLowerCase().includes(t)
      ) || '',
    }));
}

// ------------------------------------------------------------------ server ---
async function handleScrape(payload) {
  const keywords = payload.keywords || '';
  const location = payload.location || 'Barcelona';
  const maxJobs = Math.min(Number(payload.maxJobs) || 30, 60);

  let jobs = [];
  let source = 'linkedin';
  try {
    jobs = await scrapeLinkedIn({ keywords, location, maxJobs });
  } catch (err) {
    console.log('[scrape] linkedin fallo:', err.message);
    jobs = [];
  }

  if (jobs.length === 0) {
    source = 'arbeitnow';
    jobs = await scrapeArbeitnow({ keywords, maxJobs });
  }

  return { ok: true, source, scrapedAt: new Date().toISOString(), count: jobs.length, jobs };
}

const server = http.createServer((req, res) => {
  const send = (code, obj) => {
    res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(obj));
  };

  if (req.method === 'GET' && req.url === '/health') return send(200, { ok: true });

  if (req.method === 'POST' && req.url === '/scrape') {
    let raw = '';
    req.on('data', (c) => {
      raw += c;
      if (raw.length > 1e6) req.destroy();
    });
    req.on('end', async () => {
      let payload = {};
      try {
        payload = raw ? JSON.parse(raw) : {};
      } catch {
        return send(400, { ok: false, error: 'JSON inválido' });
      }
      try {
        const result = await handleScrape(payload);
        send(200, result);
      } catch (err) {
        console.error('[scrape] error:', err);
        send(500, { ok: false, error: err.message });
      }
    });
    return;
  }

  send(404, { ok: false, error: 'not found' });
});

server.listen(PORT, () => console.log(`scraper escuchando en :${PORT}`));
