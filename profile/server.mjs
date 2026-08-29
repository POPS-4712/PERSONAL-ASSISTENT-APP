// Servicio de perfil: web para editar config/user_profile.json sin tocar JSON.
//
//   GET  /                -> interfaz web
//   GET  /health          -> { ok: true }
//   GET  /api/data        -> { modules, profile }
//   POST /api/profile     -> valida y guarda; body { selections, ubicacion_laboral }
//   GET  /profile         -> perfil "resuelto" (compat. PROFILE_API_URL antiguo)
//
// Sin dependencias: solo Node. El fichero vive en /config (montado desde ./config).

import http from 'node:http';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 7777);
const CONFIG_DIR = process.env.CONFIG_DIR || '/config';
const MODULES_PATH = join(CONFIG_DIR, 'modules.json');
const PROFILE_PATH = join(CONFIG_DIR, 'user_profile.json');

// Dimensiones de selección única (el resto son múltiples).
const SINGLE = new Set(['idioma', 'estilo_marca_personal', 'objetivo_profesional', 'frecuencia_automatizacion']);

const readJson = async (p, fallback) => {
  try {
    return JSON.parse(await readFile(p, 'utf8'));
  } catch {
    return fallback;
  }
};

async function loadModules() {
  const m = await readJson(MODULES_PATH, {});
  return m && typeof m === 'object' ? m : {};
}

async function loadProfile() {
  const p = await readJson(PROFILE_PATH, null);
  if (p && typeof p === 'object') {
    return {
      version: p.version || 1,
      updated_at: p.updated_at || null,
      selections: p.selections && typeof p.selections === 'object' ? p.selections : {},
      ubicacion_laboral: p.ubicacion_laboral || '',
    };
  }
  return { version: 1, updated_at: null, selections: {}, ubicacion_laboral: '' };
}

async function saveProfile(body) {
  const modules = await loadModules();
  const current = await loadProfile();

  const incoming = body && typeof body === 'object' ? body : {};
  const rawSel = incoming.selections && typeof incoming.selections === 'object' ? incoming.selections : {};

  const selections = {};
  for (const dim of Object.keys(modules)) {
    const validIds = new Set((modules[dim] || []).map((o) => o && o.id).filter(Boolean));
    let chosen = Array.isArray(rawSel[dim]) ? rawSel[dim] : rawSel[dim] != null ? [rawSel[dim]] : [];
    chosen = [...new Set(chosen.map(String).filter((id) => validIds.has(id)))];
    if (SINGLE.has(dim)) chosen = chosen.slice(0, 1);
    selections[dim] = chosen;
  }

  const out = {
    version: (current.version || 1) + 0,
    updated_at: new Date().toISOString(),
    selections,
    ubicacion_laboral: String(incoming.ubicacion_laboral ?? current.ubicacion_laboral ?? '').slice(0, 120),
  };

  await writeFile(PROFILE_PATH, JSON.stringify(out, null, 2) + '\n', 'utf8');
  return out;
}

// Perfil "resuelto": ids -> valores, para quien prefiera consumir HTTP.
async function resolvedProfile() {
  const modules = await loadModules();
  const profile = await loadProfile();
  const find = (dim, id) => (modules[dim] || []).find((o) => o && o.id === id);
  const pick = (dim) => (Array.isArray(profile.selections[dim]) ? profile.selections[dim] : []);

  const idioma = (find('idioma', pick('idioma')[0]) || {}).valores?.codigo || 'es';
  const em = find('estilo_marca_personal', pick('estilo_marca_personal')[0]) || {};
  const cats = [...new Set(pick('intereses_rss').flatMap((id) => find('intereses_rss', id)?.valores?.categorias_feed || []))];
  const kw = [...new Set(pick('formacion').flatMap((id) => find('formacion', id)?.valores?.keywords_linkedin || []))];

  return {
    configured: Object.values(profile.selections).some((v) => Array.isArray(v) && v.length),
    idioma,
    tono: em.valores?.tono || '',
    temas: em.valores?.temas || [],
    categorias_feed: cats,
    keywords_linkedin: kw,
    ubicacion_laboral: profile.ubicacion_laboral || '',
    selections: profile.selections,
  };
}

const send = (res, code, obj, type = 'application/json') => {
  const payload = type === 'application/json' ? JSON.stringify(obj) : obj;
  res.writeHead(code, { 'content-type': `${type}; charset=utf-8`, 'cache-control': 'no-store' });
  res.end(payload);
};

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');

    if (req.method === 'GET' && url.pathname === '/health') return send(res, 200, { ok: true });

    if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html')) {
      const html = await readFile(join(HERE, 'public', 'index.html'), 'utf8');
      return send(res, 200, html, 'text/html');
    }

    if (req.method === 'GET' && url.pathname === '/api/data') {
      return send(res, 200, { modules: await loadModules(), profile: await loadProfile(), single: [...SINGLE] });
    }

    if (req.method === 'GET' && url.pathname === '/profile') {
      return send(res, 200, await resolvedProfile());
    }

    if (req.method === 'POST' && url.pathname === '/api/profile') {
      let raw = '';
      req.on('data', (c) => {
        raw += c;
        if (raw.length > 1e5) req.destroy();
      });
      req.on('end', async () => {
        let body;
        try {
          body = JSON.parse(raw || '{}');
        } catch {
          return send(res, 400, { ok: false, error: 'JSON inválido' });
        }
        try {
          const saved = await saveProfile(body);
          send(res, 200, { ok: true, profile: saved });
        } catch (err) {
          send(res, 500, { ok: false, error: err.message });
        }
      });
      return;
    }

    send(res, 404, { ok: false, error: 'not found' });
  } catch (err) {
    send(res, 500, { ok: false, error: err.message });
  }
});

server.listen(PORT, () => console.log(`perfil escuchando en :${PORT}  (config: ${CONFIG_DIR})`));
