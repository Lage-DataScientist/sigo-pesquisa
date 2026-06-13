"""
Servidor web SIGO — Pesquisa de Formandos por NIF.

Arranque:
    python -m uvicorn web.app:app --reload --port 8000
    Ou diretamente: python web/app.py
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from sigo.modules.auth import login, is_logged_in
from sigo.modules.session import save_session, load_session
from sigo.modules.formandos import pesquisar

# ── Estado global da sessão Playwright ───────────────────────────────────────

_pw = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None
_lock = asyncio.Lock()
_status = {"ok": False, "msg": "A inicializar..."}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pw, _browser, _context, _page, _status

    _pw = await async_playwright().start()
    _browser = await _pw.chromium.launch(headless=True, slow_mo=0)
    _context = await _browser.new_context()
    _context.set_default_timeout(30_000)
    _page = await _context.new_page()

    try:
        restored = await load_session(_context)
        if restored:
            await _page.goto("https://www.sigo.pt/Inicio.jsp")
            await _page.wait_for_load_state("networkidle")

        if not await is_logged_in(_page):
            ok = await login(_page)
            if ok:
                await save_session(_context)
                _status = {"ok": True, "msg": "Sessão SIGO activa"}
            else:
                _status = {"ok": False, "msg": "Falha na autenticação SIGO"}
        else:
            _status = {"ok": True, "msg": "Sessão SIGO restaurada"}
    except Exception as exc:
        _status = {"ok": False, "msg": f"Erro: {exc}"}

    yield

    if _context:
        await _context.close()
    if _browser:
        await _browser.close()
    if _pw:
        await _pw.stop()


app = FastAPI(title="SIGO Pesquisa", lifespan=lifespan)

# ── Modelos ───────────────────────────────────────────────────────────────────

class PesquisaRequest(BaseModel):
    nif: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


@app.get("/api/status")
async def api_status():
    return _status


@app.post("/api/pesquisar")
async def api_pesquisar(req: PesquisaRequest):
    nif = req.nif.strip().replace(" ", "")

    if not nif:
        raise HTTPException(400, "NIF obrigatório.")
    if not re.fullmatch(r"\d{9}", nif):
        raise HTTPException(400, "NIF inválido — deve ter exactamente 9 dígitos.")
    if not _status["ok"]:
        raise HTTPException(503, f"SIGO indisponível: {_status['msg']}")

    async with _lock:
        try:
            resultados = await pesquisar(_page, nif=nif)
        except Exception as exc:
            # Tentar re-login se a sessão expirou
            try:
                await login(_page)
                resultados = await pesquisar(_page, nif=nif)
            except Exception:
                raise HTTPException(500, f"Erro ao pesquisar: {exc}")

    if not resultados:
        return {"encontrado": False, "nif": nif, "resultados": []}

    return {
        "encontrado": True,
        "nif": nif,
        "resultados": [
            {
                "n_sigo": f.n_sigo,
                "nome": f.nome,
                "nif": f.nif,
                "n_identificacao": f.n_identificacao,
                "data_nascimento": f.data_nascimento,
            }
            for f in resultados
        ],
    }


# ── HTML do Dashboard ─────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!doctype html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SIGO — Pesquisa de Formandos</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <style>
    :root { --sigo-blue: #003876; --sigo-light: #e8f0fb; }
    body { background: #f4f6fa; min-height: 100vh; }

    /* Sidebar */
    #sidebar {
      width: 240px; min-height: 100vh;
      background: var(--sigo-blue);
      color: #fff;
      position: fixed; top: 0; left: 0;
    }
    #sidebar .brand { padding: 1.5rem 1rem; border-bottom: 1px solid rgba(255,255,255,.15); }
    #sidebar .brand h5 { font-weight: 700; letter-spacing: .5px; margin: 0; }
    #sidebar .brand small { opacity: .6; font-size: .75rem; }
    #sidebar .nav-link {
      color: rgba(255,255,255,.75); padding: .6rem 1rem;
      border-radius: .4rem; margin: .15rem .5rem;
      transition: background .15s;
    }
    #sidebar .nav-link:hover, #sidebar .nav-link.active {
      color: #fff; background: rgba(255,255,255,.15);
    }
    #sidebar .nav-link i { width: 1.4rem; }
    #status-badge { font-size: .72rem; }

    /* Main */
    #main { margin-left: 240px; padding: 2rem; }

    /* Cards */
    .card { border: none; box-shadow: 0 1px 6px rgba(0,0,0,.08); }
    .card-header { border-bottom: 1px solid rgba(0,0,0,.06); background: #fff; font-weight: 600; }

    /* Search input */
    #nif-input { font-size: 1.05rem; letter-spacing: .1rem; }
    #nif-input:focus { border-color: var(--sigo-blue); box-shadow: 0 0 0 .2rem rgba(0,56,118,.2); }

    /* Table */
    .table thead th { background: var(--sigo-light); color: var(--sigo-blue); font-size: .8rem; text-transform: uppercase; letter-spacing: .05rem; }
    .table td { vertical-align: middle; font-size: .9rem; }
    .badge-inscrito { background: #d4edda; color: #155724; }
    .badge-nao { background: #f8d7da; color: #721c24; }

    /* Spinner overlay */
    #spinner-overlay {
      display: none; position: fixed; inset: 0;
      background: rgba(255,255,255,.6); z-index: 9999;
      align-items: center; justify-content: center;
    }
    #spinner-overlay.show { display: flex; }

    /* Stats */
    .stat-card { border-left: 4px solid var(--sigo-blue); }
    .stat-card.found { border-left-color: #28a745; }
    .stat-card.notfound { border-left-color: #dc3545; }
    .stat-card .num { font-size: 1.8rem; font-weight: 700; color: var(--sigo-blue); }
    .stat-card.found .num { color: #28a745; }
    .stat-card.notfound .num { color: #dc3545; }

    @media (max-width: 768px) {
      #sidebar { display: none; }
      #main { margin-left: 0; padding: 1rem; }
    }
  </style>
</head>
<body>

<!-- Spinner -->
<div id="spinner-overlay">
  <div class="text-center">
    <div class="spinner-border text-primary" style="width:3rem;height:3rem;" role="status"></div>
    <div class="mt-3 text-muted fw-semibold">A pesquisar no SIGO...</div>
  </div>
</div>

<!-- Sidebar -->
<nav id="sidebar">
  <div class="brand">
    <h5><i class="bi bi-mortarboard-fill me-2"></i>SIGO</h5>
    <small>Gestão de Formandos</small>
  </div>
  <div class="px-2 mt-3">
    <ul class="nav flex-column gap-1">
      <li class="nav-item">
        <a class="nav-link active" href="#"><i class="bi bi-search"></i> Pesquisar NIF</a>
      </li>
    </ul>
  </div>
  <div class="position-absolute bottom-0 w-100 p-3" style="border-top:1px solid rgba(255,255,255,.1)">
    <div id="status-badge" class="d-flex align-items-center gap-2">
      <span class="badge bg-secondary" id="conn-badge">
        <i class="bi bi-circle-fill me-1" style="font-size:.5rem"></i>A verificar...
      </span>
    </div>
  </div>
</nav>

<!-- Main -->
<div id="main">

  <!-- Page header -->
  <div class="d-flex align-items-center justify-content-between mb-4">
    <div>
      <h4 class="mb-0 fw-bold" style="color:var(--sigo-blue)">Pesquisa de Formandos</h4>
      <small class="text-muted">Consulta por NIF no portal SIGO</small>
    </div>
    <div class="d-flex gap-2">
      <button class="btn btn-outline-danger btn-sm" onclick="limparTabela()" title="Limpar tabela de resultados">
        <i class="bi bi-trash3"></i> Limpar
      </button>
      <button class="btn btn-success btn-sm" onclick="exportarCSV()" title="Exportar resultados para CSV">
        <i class="bi bi-download"></i> Exportar CSV
      </button>
    </div>
  </div>

  <!-- Stats -->
  <div class="row g-3 mb-4" id="stats-row" style="display:none!important">
    <div class="col-sm-4">
      <div class="card stat-card p-3">
        <div class="num" id="stat-total">0</div>
        <div class="text-muted small">Pesquisas</div>
      </div>
    </div>
    <div class="col-sm-4">
      <div class="card stat-card found p-3">
        <div class="num" id="stat-found">0</div>
        <div class="text-muted small">Encontrados</div>
      </div>
    </div>
    <div class="col-sm-4">
      <div class="card stat-card notfound p-3">
        <div class="num" id="stat-notfound">0</div>
        <div class="text-muted small">Não encontrados</div>
      </div>
    </div>
  </div>

  <!-- Search card -->
  <div class="card mb-4">
    <div class="card-header py-3">
      <i class="bi bi-search me-2"></i>Pesquisar por NIF
    </div>
    <div class="card-body p-4">
      <form id="search-form" onsubmit="pesquisar(event)">
        <div class="row g-3 align-items-end">
          <div class="col-md-5">
            <label class="form-label fw-semibold">NIF</label>
            <input
              type="text" id="nif-input"
              class="form-control form-control-lg"
              placeholder="000000000"
              maxlength="9"
              pattern="\\d{9}"
              inputmode="numeric"
              autocomplete="off"
              required
            >
            <div class="form-text text-muted">9 dígitos numéricos</div>
          </div>
          <div class="col-md-3">
            <button type="submit" class="btn btn-primary btn-lg w-100">
              <i class="bi bi-search me-1"></i> Pesquisar
            </button>
          </div>
        </div>
        <div id="search-error" class="alert alert-danger mt-3 d-none py-2"></div>
      </form>
    </div>
  </div>

  <!-- Results card -->
  <div class="card" id="results-card" style="display:none!important">
    <div class="card-header py-3 d-flex align-items-center justify-content-between">
      <span><i class="bi bi-table me-2"></i>Resultados</span>
      <span class="badge bg-secondary" id="result-count">0 registos</span>
    </div>
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-hover mb-0" id="results-table">
          <thead>
            <tr>
              <th>NIF Pesquisado</th>
              <th>Estado</th>
              <th>Nome</th>
              <th>Nº SIGO</th>
            </tr>
          </thead>
          <tbody id="results-body"></tbody>
        </table>
      </div>
    </div>
  </div>

</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
  // ── Estado ──────────────────────────────────────────────────────────────────
  const rows = [];   // { nif, encontrado, nome, n_sigo }
  let statsTotal = 0, statsFound = 0;

  // ── Verificar estado da ligação ──────────────────────────────────────────────
  async function checkStatus() {
    try {
      const r = await fetch('/api/status');
      const data = await r.json();
      const badge = document.getElementById('conn-badge');
      if (data.ok) {
        badge.className = 'badge bg-success';
        badge.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:.5rem"></i>' + data.msg;
      } else {
        badge.className = 'badge bg-danger';
        badge.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:.5rem"></i>' + data.msg;
      }
    } catch (e) {
      document.getElementById('conn-badge').className = 'badge bg-danger';
      document.getElementById('conn-badge').textContent = 'Servidor offline';
    }
  }

  // ── Pesquisar ────────────────────────────────────────────────────────────────
  async function pesquisar(e) {
    e.preventDefault();
    const nif = document.getElementById('nif-input').value.trim();
    const errEl = document.getElementById('search-error');

    // Validação frontend
    if (!/^\\d{9}$/.test(nif)) {
      errEl.textContent = 'O NIF deve ter exactamente 9 dígitos numéricos.';
      errEl.classList.remove('d-none');
      return;
    }
    errEl.classList.add('d-none');

    // Mostrar spinner
    document.getElementById('spinner-overlay').classList.add('show');

    try {
      const resp = await fetch('/api/pesquisar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nif }),
      });

      const data = await resp.json();

      if (!resp.ok) {
        errEl.textContent = data.detail || 'Erro desconhecido.';
        errEl.classList.remove('d-none');
        return;
      }

      // Acumular resultados
      if (data.encontrado) {
        data.resultados.forEach(f => {
          rows.push({ nif_pesq: nif, encontrado: true, nome: f.nome, n_sigo: f.n_sigo });
        });
        statsFound++;
      } else {
        rows.push({ nif_pesq: nif, encontrado: false, nome: '', n_sigo: '' });
      }
      statsTotal++;

      renderTabela();
      document.getElementById('nif-input').value = '';
      document.getElementById('nif-input').focus();

    } catch (err) {
      errEl.textContent = 'Erro de ligação ao servidor.';
      errEl.classList.remove('d-none');
    } finally {
      document.getElementById('spinner-overlay').classList.remove('show');
    }
  }

  // ── Renderizar tabela ────────────────────────────────────────────────────────
  function renderTabela() {
    const tbody = document.getElementById('results-body');
    tbody.innerHTML = '';

    rows.forEach((r, i) => {
      const tr = document.createElement('tr');

      if (r.encontrado) {
        tr.innerHTML = `
          <td class="font-monospace">${r.nif_pesq}</td>
          <td><span class="badge badge-inscrito px-2 py-1"><i class="bi bi-check-circle me-1"></i>Registado</span></td>
          <td class="fw-semibold">${r.nome}</td>
          <td class="font-monospace">${r.n_sigo}</td>
        `;
      } else {
        tr.innerHTML = `
          <td class="font-monospace">${r.nif_pesq}</td>
          <td><span class="badge badge-nao px-2 py-1"><i class="bi bi-x-circle me-1"></i>Não encontrado</span></td>
          <td class="text-muted">—</td>
          <td class="text-muted">—</td>
        `;
      }
      tbody.appendChild(tr);
    });

    // Mostrar/ocultar secções
    const count = rows.length;
    document.getElementById('result-count').textContent = count + (count === 1 ? ' registo' : ' registos');
    document.getElementById('results-card').style.display = count > 0 ? '' : 'none';
    document.getElementById('stats-row').style.display = count > 0 ? '' : 'none';

    // Stats
    document.getElementById('stat-total').textContent = statsTotal;
    document.getElementById('stat-found').textContent = statsFound;
    document.getElementById('stat-notfound').textContent = statsTotal - statsFound;
  }

  // ── Limpar ──────────────────────────────────────────────────────────────────
  function limparTabela() {
    rows.length = 0;
    statsTotal = 0;
    statsFound = 0;
    renderTabela();
    document.getElementById('search-error').classList.add('d-none');
  }

  // ── Exportar CSV ─────────────────────────────────────────────────────────────
  function exportarCSV() {
    if (rows.length === 0) {
      alert('Sem resultados para exportar.');
      return;
    }

    const header = ['NIF Pesquisado', 'Estado', 'Nome', 'Nº SIGO'];
    const csvRows = [header.join(';')];

    rows.forEach(r => {
      const estado = r.encontrado ? 'Registado' : 'Não encontrado';
      csvRows.push([r.nif_pesq, estado, r.nome, r.n_sigo].join(';'));
    });

    const bom = '\\uFEFF';  // BOM para Excel reconhecer UTF-8
    const blob = new Blob([bom + csvRows.join('\\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sigo_formandos_' + new Date().toISOString().slice(0,10) + '.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Tecla Enter no campo NIF ──────────────────────────────────────────────
  document.getElementById('nif-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') document.getElementById('search-form').requestSubmit();
  });

  // ── Só aceitar dígitos no input ───────────────────────────────────────────
  document.getElementById('nif-input').addEventListener('input', function() {
    this.value = this.value.replace(/\\D/g, '').slice(0, 9);
  });

  // ── Init ──────────────────────────────────────────────────────────────────
  checkStatus();
  setInterval(checkStatus, 30_000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=False)
