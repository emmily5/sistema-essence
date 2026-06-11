/* ====== Sistema Essence — front-end ====== */
const App = (() => {
  "use strict";

  // ---------- Utilidades ----------
  const FORMAS = ["Prazo", "Pix", "Dinheiro", "Cartão"];

  function fmtMoeda(v) {
    const n = Number(v) || 0;
    return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }
  function fmtData(iso) {
    if (!iso) return "—";
    const p = iso.split("-");
    if (p.length !== 3) return iso;
    return `${p[2]}/${p[1]}/${p[0]}`;
  }
  function hojeIso() {
    const d = new Date();
    const off = d.getTimezoneOffset();
    const local = new Date(d.getTime() - off * 60000);
    return local.toISOString().slice(0, 10);
  }
  function nomeMes(ym) {
    const meses = ["janeiro","fevereiro","março","abril","maio","junho",
      "julho","agosto","setembro","outubro","novembro","dezembro"];
    const [a, m] = (ym || hojeIso().slice(0,7)).split("-");
    return `${meses[parseInt(m,10)-1]} de ${a}`;
  }
  function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>(
    {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}

  // ---------- API ----------
  async function api(url, opt = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opt,
    });
    if (!res.ok) {
      let msg = "Ocorreu um erro.";
      try { msg = (await res.json()).erro || msg; } catch (e) {}
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    return ct.includes("json") ? res.json() : res;
  }

  // ---------- Toast ----------
  function toast(msg, tipo = "sucesso") {
    const wrap = document.getElementById("toast-wrap");
    const el = document.createElement("div");
    el.className = "toast " + tipo;
    el.innerHTML = `<span>${tipo === "erro" ? "⚠️" : "✅"}</span><span>${esc(msg)}</span>`;
    wrap.appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 3200);
  }

  // ---------- Modal ----------
  function abrirModal(titulo, html, large = false) {
    document.getElementById("modal-title").textContent = titulo;
    document.getElementById("modal-body").innerHTML = html;
    document.getElementById("modal").classList.toggle("modal-lg", large);
    document.getElementById("modal-overlay").classList.add("open");
  }
  function fecharModal() {
    document.getElementById("modal-overlay").classList.remove("open");
    document.getElementById("modal").classList.remove("modal-lg");
  }
  let confirmCb = null;
  function confirmar(texto, cb, botao = "Apagar") {
    document.getElementById("confirm-text").textContent = texto;
    document.getElementById("confirm-ok").textContent = botao;
    confirmCb = cb;
    document.getElementById("confirm-overlay").classList.add("open");
  }
  function fecharConfirm() {
    document.getElementById("confirm-overlay").classList.remove("open");
    confirmCb = null;
  }

  // ---------- Estado ----------
  let perfumesCache = [];

  // ================= VIEWS =================
  const container = () => document.getElementById("view-container");

  async function carregarBadge() {
    try {
      const inad = await api("/api/inadimplencia");
      const badge = document.getElementById("badge-inad");
      if (inad.length > 0) {
        badge.textContent = inad.length;
        badge.style.display = "inline-block";
      } else {
        badge.style.display = "none";
      }
    } catch (e) {}
  }

  // ---------- Dashboard ----------
  async function viewDashboard() {
    container().innerHTML = `<div class="empty">Carregando…</div>`;
    const d = await api("/api/dashboard");

    const metaTxt = d.meta_atingida
      ? `<span class="meta-ok">Meta atingida! 🎉</span>`
      : `Faltam <strong>${fmtMoeda(d.falta_meta)}</strong> para a meta`;

    container().innerHTML = `
      <div class="page-head">
        <div>
          <h1>Dashboard</h1>
          <p>Resumo de ${nomeMes(d.mes)}</p>
        </div>
        <button class="btn btn-primary" onclick="App.editarMeta()">🎯 Definir meta</button>
      </div>

      <div class="cards">
        <div class="card destaque">
          <div class="card-label">💰 Faturamento do mês</div>
          <div class="card-value">${fmtMoeda(d.faturamento)}</div>
          <div class="card-sub">${d.num_vendas} venda(s) • ticket médio ${fmtMoeda(d.ticket_medio)}</div>
        </div>
        <div class="card">
          <div class="card-label">📈 Lucro do mês</div>
          <div class="card-value">${fmtMoeda(d.lucro)}</div>
          <div class="card-sub">Soma do lucro das vendas</div>
        </div>
        <div class="card">
          <div class="card-label">🎯 Meta do mês</div>
          <div class="card-value">${fmtMoeda(d.meta)}</div>
          <div class="card-sub">${metaTxt}</div>
        </div>
        <div class="card">
          <div class="card-label">📦 Total investido</div>
          <div class="card-value">${fmtMoeda(d.total_investido)}</div>
          <div class="card-sub">Custo do estoque atual</div>
        </div>
        <div class="card">
          <div class="card-label">🧾 Débitos em aberto</div>
          <div class="card-value">${fmtMoeda(d.debitos_abertos)}</div>
          <div class="card-sub">${d.debitos_qtd} cliente(s) em atraso</div>
        </div>

        <div class="card progress-card">
          <div class="card-label">Progresso da meta</div>
          <div class="progress-bar"><div class="progress-fill" style="width:${d.progresso}%"></div></div>
          <div class="progress-meta">
            <span>${fmtMoeda(d.faturamento)} de ${fmtMoeda(d.meta)}</span>
            <span><strong>${d.progresso}%</strong></span>
          </div>
        </div>
      </div>
    `;
  }

  async function editarMeta() {
    const cfg = await api("/api/config");
    const meta = cfg.meta_mensal || "0";
    abrirModal("Definir meta de vendas do mês", `
      <div class="field full">
        <label>Meta mensal (R$)</label>
        <input type="number" id="f-meta" step="0.01" min="0" value="${esc(meta)}">
        <span class="hint">Valor que você quer vender neste mês.</span>
      </div>
      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="App.fecharModal()">Cancelar</button>
        <button class="btn btn-primary" onclick="App.salvarMeta()">Salvar meta</button>
      </div>
    `);
  }
  async function salvarMeta() {
    const v = document.getElementById("f-meta").value;
    if (v === "" || Number(v) < 0) { toast("Informe um valor válido.", "erro"); return; }
    try {
      await api("/api/config", { method: "PUT", body: JSON.stringify({ meta_mensal: v }) });
      fecharModal();
      toast("Meta atualizada!");
      viewDashboard();
    } catch (e) { toast(e.message, "erro"); }
  }

  // ---------- Perfumes ----------
  async function viewPerfumes() {
    container().innerHTML = `
      <div class="page-head">
        <div><h1>Perfumes</h1><p>Cadastro e estoque dos seus produtos</p></div>
        <button class="btn btn-primary" onclick="App.formPerfume()">＋ Adicionar perfume</button>
      </div>
      <div class="toolbar">
        <div class="search"><input id="busca-perfume" placeholder="Buscar por nome ou marca…"></div>
      </div>
      <div class="table-wrap" id="tabela-perfumes"></div>
    `;
    perfumesCache = await api("/api/perfumes");
    renderPerfumes(perfumesCache);
    document.getElementById("busca-perfume").addEventListener("input", (e) => {
      const t = e.target.value.toLowerCase();
      renderPerfumes(perfumesCache.filter(p =>
        p.nome.toLowerCase().includes(t) || (p.marca||"").toLowerCase().includes(t)));
    });
  }

  function renderPerfumes(lista) {
    const wrap = document.getElementById("tabela-perfumes");
    if (!lista.length) {
      wrap.innerHTML = `<div class="empty"><div class="big">🧴</div>Nenhum perfume cadastrado ainda.<br>Clique em <strong>Adicionar perfume</strong> para começar.</div>`;
      return;
    }
    wrap.innerHTML = `
      <table>
        <thead><tr>
          <th>Perfume</th><th>Marca</th>
          <th class="t-right">Custo</th><th class="t-right">Venda</th>
          <th class="t-right">Lucro</th><th class="t-right">Margem</th>
          <th class="t-center">Estoque</th><th class="t-right">Ações</th>
        </tr></thead>
        <tbody>
          ${lista.map(p => `
            <tr>
              <td><strong>${esc(p.nome)}</strong></td>
              <td>${esc(p.marca) || "—"}</td>
              <td class="t-right">${fmtMoeda(p.preco_custo)}</td>
              <td class="t-right">${fmtMoeda(p.valor_final)}</td>
              <td class="t-right lucro-pos">${fmtMoeda(p.lucro)}</td>
              <td class="t-right">${p.margem.toLocaleString("pt-BR",{minimumFractionDigits:1,maximumFractionDigits:1})}%</td>
              <td class="t-center">${p.estoque == 0
                ? '<span class="pill pill-estoque-0">Esgotado</span>'
                : p.estoque}</td>
              <td class="acoes">
                <button class="btn-icon" title="Editar" onclick="App.formPerfume(${p.id})">✏️</button>
                <button class="btn-icon" title="Apagar" onclick="App.apagarPerfume(${p.id})">🗑️</button>
              </td>
            </tr>`).join("")}
        </tbody>
      </table>`;
  }

  function formPerfume(id) {
    const p = id ? perfumesCache.find(x => x.id === id) : null;
    abrirModal(p ? "Editar perfume" : "Adicionar perfume", `
      <div class="form-grid">
        <div class="field full">
          <label>Nome do perfume *</label>
          <input id="p-nome" value="${p ? esc(p.nome) : ""}" placeholder="Ex.: Essence Floral">
        </div>
        <div class="field full">
          <label>Marca (opcional)</label>
          <input id="p-marca" value="${p ? esc(p.marca) : ""}" placeholder="Ex.: La Vie">
        </div>
        <div class="field">
          <label>Preço de custo (R$) *</label>
          <input type="number" id="p-custo" step="0.01" min="0" value="${p ? p.preco_custo : ""}" oninput="App.calcLucro()">
        </div>
        <div class="field">
          <label>Valor final de venda (R$) *</label>
          <input type="number" id="p-final" step="0.01" min="0" value="${p ? p.valor_final : ""}" oninput="App.calcLucro()">
        </div>
        <div class="field">
          <label>Quantidade em estoque</label>
          <input type="number" id="p-estoque" step="1" min="0" value="${p ? p.estoque : "0"}">
        </div>
        <div class="field">
          <label>Lucro (calculado)</label>
          <div class="calc" id="p-lucro" style="padding:11px 0">—</div>
        </div>
      </div>
      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="App.fecharModal()">Cancelar</button>
        <button class="btn btn-primary" onclick="App.salvarPerfume(${id || 0})">Salvar</button>
      </div>
    `);
    calcLucro();
  }

  function calcLucro() {
    const c = parseFloat(document.getElementById("p-custo").value) || 0;
    const f = parseFloat(document.getElementById("p-final").value) || 0;
    const lucro = f - c;
    const margem = f ? (lucro / f * 100) : 0;
    document.getElementById("p-lucro").textContent =
      `${fmtMoeda(lucro)}  (margem ${margem.toFixed(1)}%)`;
  }

  async function salvarPerfume(id) {
    const nome = document.getElementById("p-nome").value.trim();
    const custo = document.getElementById("p-custo").value;
    const final = document.getElementById("p-final").value;
    if (!nome) { toast("Informe o nome do perfume.", "erro"); return; }
    if (custo === "" || final === "") { toast("Preencha custo e valor de venda.", "erro"); return; }
    const body = JSON.stringify({
      nome,
      marca: document.getElementById("p-marca").value.trim(),
      preco_custo: custo,
      valor_final: final,
      estoque: document.getElementById("p-estoque").value || 0,
    });
    try {
      if (id) await api(`/api/perfumes/${id}`, { method: "PUT", body });
      else await api("/api/perfumes", { method: "POST", body });
      fecharModal();
      toast(id ? "Perfume atualizado!" : "Perfume cadastrado!");
      viewPerfumes();
    } catch (e) { toast(e.message, "erro"); }
  }

  function apagarPerfume(id) {
    const p = perfumesCache.find(x => x.id === id);
    confirmar(`Apagar o perfume "${p ? p.nome : ""}"? Esta ação não pode ser desfeita.`, async () => {
      try {
        await api(`/api/perfumes/${id}`, { method: "DELETE" });
        fecharConfirm();
        toast("Perfume apagado.");
        viewPerfumes();
      } catch (e) { toast(e.message, "erro"); }
    });
  }

  // ---------- Vendas / Clientes ----------
  let vendasFiltros = { status: "", forma: "", mes: "", busca: "" };

  async function viewVendas() {
    await garantirPerfumes();
    container().innerHTML = `
      <div class="page-head">
        <div><h1>Clientes / Vendas</h1><p>Cada ficha pode ter vários perfumes e pagamentos</p></div>
        <div style="display:flex;gap:10px">
          <button class="btn btn-ghost" onclick="App.baixarPDF()">📄 Relatório geral</button>
          <button class="btn btn-primary" onclick="App.formVenda()">＋ Nova ficha</button>
        </div>
      </div>
      <div class="toolbar">
        <div class="search"><input id="busca-venda" placeholder="Buscar cliente…" value="${esc(vendasFiltros.busca)}"></div>
        <select class="filtro" id="f-status">
          <option value="">Todos os status</option>
          <option value="Pago">Pago</option>
          <option value="Pendente">Pendente</option>
        </select>
        <select class="filtro" id="f-forma">
          <option value="">Toda forma de pagamento</option>
          ${FORMAS.map(f => `<option value="${f}">${f}</option>`).join("")}
        </select>
        <input class="filtro" type="month" id="f-mes" value="${esc(vendasFiltros.mes)}" title="Filtrar por mês da compra">
        <button class="btn btn-ghost btn-sm" onclick="App.limparFiltros()">Limpar</button>
      </div>
      <div class="table-wrap" id="tabela-vendas"></div>
    `;
    document.getElementById("f-status").value = vendasFiltros.status;
    document.getElementById("f-forma").value = vendasFiltros.forma;
    ["f-status","f-forma","f-mes"].forEach(id =>
      document.getElementById(id).addEventListener("change", aplicarFiltrosVendas));
    document.getElementById("busca-venda").addEventListener("input", debounce(aplicarFiltrosVendas, 250));
    carregarVendas();
  }

  function limparFiltros() {
    vendasFiltros = { status: "", forma: "", mes: "", busca: "" };
    viewVendas();
  }
  function aplicarFiltrosVendas() {
    vendasFiltros.status = document.getElementById("f-status").value;
    vendasFiltros.forma = document.getElementById("f-forma").value;
    vendasFiltros.mes = document.getElementById("f-mes").value;
    vendasFiltros.busca = document.getElementById("busca-venda").value.trim();
    carregarVendas();
  }

  async function carregarVendas() {
    const q = new URLSearchParams();
    if (vendasFiltros.status) q.set("status", vendasFiltros.status);
    if (vendasFiltros.forma) q.set("forma", vendasFiltros.forma);
    if (vendasFiltros.mes) q.set("mes", vendasFiltros.mes);
    if (vendasFiltros.busca) q.set("busca", vendasFiltros.busca);
    const vendas = await api("/api/vendas?" + q.toString());
    renderVendas(vendas);
  }

  function statusPill(v) {
    if (v.status === "Pago") return '<span class="pill pill-pago">Quitado</span>';
    if (v.atrasada) return '<span class="pill pill-atraso">Atrasado</span>';
    return '<span class="pill pill-pendente">Pendente</span>';
  }

  function resumoItens(v) {
    if (!v.itens || !v.itens.length) return "—";
    const nomes = v.itens.map(i => i.perfume_nome || "Perfume");
    const primeiro = nomes[0];
    return nomes.length > 1
      ? `${esc(primeiro)} <span class="card-sub">+${nomes.length - 1} item(ns)</span>`
      : esc(primeiro);
  }

  function renderVendas(lista) {
    const wrap = document.getElementById("tabela-vendas");
    if (!lista.length) {
      wrap.innerHTML = `<div class="empty"><div class="big">👤</div>Nenhuma ficha encontrada.</div>`;
      return;
    }
    wrap.innerHTML = `
      <table>
        <thead><tr>
          <th>Cliente</th><th>Itens</th>
          <th class="t-right">Total</th><th class="t-right">Pago</th><th class="t-right">Saldo</th>
          <th>Vencimento</th><th>Forma</th><th class="t-center">Status</th>
          <th class="t-right">Ações</th>
        </tr></thead>
        <tbody>
          ${lista.map(v => `
            <tr class="${v.atrasada ? "row-atraso" : ""}">
              <td><strong>${esc(v.nome_cliente)}</strong></td>
              <td>${resumoItens(v)}</td>
              <td class="t-right">${fmtMoeda(v.total)}</td>
              <td class="t-right">${fmtMoeda(v.pago)}</td>
              <td class="t-right ${v.saldo > 0 ? "" : "lucro-pos"}"><strong>${fmtMoeda(v.saldo)}</strong></td>
              <td>${fmtData(v.data_vencimento)}</td>
              <td><span class="pill pill-forma">${esc(v.forma_pagamento)}</span></td>
              <td class="t-center">${statusPill(v)}</td>
              <td class="acoes">
                <button class="btn-icon" title="Gerar relatório" onclick="App.gerarRelatorio(${v.id})">📄</button>
                ${v.saldo > 0
                  ? `<button class="btn-icon" title="Receber pagamento" onclick="App.formPagamento(${v.id})">💵</button>` : ""}
                <button class="btn-icon" title="Editar" onclick="App.formVenda(${v.id})">✏️</button>
                <button class="btn-icon" title="Apagar" onclick="App.apagarVenda(${v.id})">🗑️</button>
              </td>
            </tr>`).join("")}
        </tbody>
      </table>`;
  }

  // ----- opções de perfume para os selects -----
  function perfumeOptions(selId) {
    return '<option value="">— escolher perfume —</option>' + perfumesCache.map(p =>
      `<option value="${p.id}" data-final="${p.valor_final}" ${String(p.id) === String(selId) ? "selected" : ""}>`
      + `${esc(p.nome)}${p.marca ? " — " + esc(p.marca) : ""} (estoque ${p.estoque})</option>`).join("");
  }

  function linhaItem(it = {}) {
    return `
      <tr>
        <td><select class="it-perf" onchange="App.itemPerfumeMudou(this)">${perfumeOptions(it.perfume_id)}</select></td>
        <td><input class="it-qtd" type="number" min="1" step="1" value="${it.quantidade != null ? it.quantidade : 1}" oninput="App.recalcResumo()" style="width:70px"></td>
        <td><input class="it-valor" type="number" min="0" step="0.01" value="${it.valor != null ? it.valor : ""}" oninput="App.recalcResumo()" style="width:100px"></td>
        <td><input class="it-data" type="date" value="${it.data_compra || hojeIso()}"></td>
        <td><input class="it-obs" value="${it.observacao ? esc(it.observacao) : ""}" placeholder="ex.: extra forte" style="width:130px"></td>
        <td><button class="btn-icon" title="Remover item" onclick="App.removerLinha(this)">❌</button></td>
      </tr>`;
  }

  function linhaPagamento(pg = {}) {
    return `
      <tr>
        <td><input class="pg-valor" type="number" min="0" step="0.01" value="${pg.valor != null ? pg.valor : ""}" oninput="App.recalcResumo()" placeholder="R$" style="width:120px"></td>
        <td><input class="pg-data" type="date" value="${pg.data || hojeIso()}"></td>
        <td><button class="btn-icon" title="Remover pagamento" onclick="App.removerLinha(this)">❌</button></td>
      </tr>`;
  }

  function lerItens() {
    return [...document.querySelectorAll("#itens-tbody tr")].map(tr => ({
      perfume_id: tr.querySelector(".it-perf").value || null,
      quantidade: tr.querySelector(".it-qtd").value || 1,
      valor: tr.querySelector(".it-valor").value || 0,
      data_compra: tr.querySelector(".it-data").value || hojeIso(),
      observacao: tr.querySelector(".it-obs").value.trim(),
    }));
  }
  function lerPagamentos() {
    return [...document.querySelectorAll("#pags-tbody tr")]
      .map(tr => ({ valor: tr.querySelector(".pg-valor").value || 0, data: tr.querySelector(".pg-data").value || hojeIso() }))
      .filter(p => Number(p.valor) > 0);
  }

  function addItem() {
    document.getElementById("itens-tbody").insertAdjacentHTML("beforeend", linhaItem());
    recalcResumo();
  }
  function addPagamento() {
    document.getElementById("pags-tbody").insertAdjacentHTML("beforeend", linhaPagamento());
    recalcResumo();
  }
  function removerLinha(btn) {
    btn.closest("tr").remove();
    recalcResumo();
  }
  function itemPerfumeMudou(sel) {
    const tr = sel.closest("tr");
    const opt = sel.options[sel.selectedIndex];
    const campoValor = tr.querySelector(".it-valor");
    const qtd = Number(tr.querySelector(".it-qtd").value) || 1;
    if (opt && opt.dataset.final && !campoValor.value) {
      campoValor.value = (Number(opt.dataset.final) * qtd).toFixed(2);
    }
    recalcResumo();
  }
  function recalcResumo() {
    const total = lerItens().reduce((s, i) => s + (Number(i.valor) || 0), 0);
    const pago = lerPagamentos().reduce((s, p) => s + (Number(p.valor) || 0), 0);
    const saldo = total - pago;
    const el = document.getElementById("resumo-ficha");
    if (!el) return;
    const quitado = total > 0 && saldo <= 0.004;
    el.innerHTML = `
      <span>Total: <strong>${fmtMoeda(total)}</strong></span>
      <span>Pago: <strong>${fmtMoeda(pago)}</strong></span>
      <span>Saldo: <strong class="${saldo > 0 ? "saldo-deve" : "lucro-pos"}">${fmtMoeda(Math.max(saldo, 0))}</strong></span>
      ${quitado ? '<span class="pill pill-pago">Quitado ✓</span>' : ""}`;
  }

  async function formVenda(id) {
    await garantirPerfumes();
    let v = null;
    if (id) v = await api(`/api/vendas/${id}`);

    const itensIniciais = (v && v.itens.length) ? v.itens.map(linhaItem).join("") : linhaItem();
    const pagsIniciais = (v && v.pagamentos.length) ? v.pagamentos.map(linhaPagamento).join("") : "";

    abrirModal(v ? "Editar ficha do cliente" : "Nova ficha / venda", `
      <div class="form-grid">
        <div class="field full">
          <label>Nome do cliente *</label>
          <input id="v-cliente" value="${v ? esc(v.nome_cliente) : ""}" placeholder="Ex.: Dorinha Carcará">
        </div>
        <div class="field">
          <label>Forma de pagamento</label>
          <select id="v-forma">
            ${FORMAS.map(f => `<option value="${f}" ${v && v.forma_pagamento === f ? "selected" : ""}>${f}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>Vencimento (para prazo/pendência)</label>
          <input type="date" id="v-venc" value="${v && v.data_vencimento ? v.data_vencimento : ""}">
          <span class="hint">Data limite para quitar. Vence + saldo &gt; 0 = inadimplente.</span>
        </div>
        <div class="field full">
          <label>Observação geral (opcional)</label>
          <input id="v-obs" value="${v ? esc(v.observacao) : ""}" placeholder="Ex.: combinou de pagar em 3x">
        </div>
      </div>

      <div class="bloco-titulo">
        <h4>🧴 Perfumes da compra</h4>
        <button class="btn btn-ghost btn-sm" onclick="App.addItem()">＋ Adicionar perfume</button>
      </div>
      <div class="mini-table">
        <table>
          <thead><tr><th>Perfume</th><th>Qtd</th><th>Valor (R$)</th><th>Data da compra</th><th>Obs.</th><th></th></tr></thead>
          <tbody id="itens-tbody">${itensIniciais}</tbody>
        </table>
      </div>

      <div class="bloco-titulo">
        <h4>💵 Pagamentos recebidos</h4>
        <button class="btn btn-ghost btn-sm" onclick="App.addPagamento()">＋ Adicionar pagamento</button>
      </div>
      <div class="mini-table">
        <table>
          <thead><tr><th>Valor (R$)</th><th>Data do pagamento</th><th></th></tr></thead>
          <tbody id="pags-tbody">${pagsIniciais}</tbody>
        </table>
      </div>

      <div id="resumo-ficha" class="resumo-ficha"></div>

      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="App.fecharModal()">Cancelar</button>
        <button class="btn btn-primary" onclick="App.salvarVenda(${id || 0})">Salvar ficha</button>
      </div>
    `, true);
    recalcResumo();
  }

  async function salvarVenda(id) {
    const nome = document.getElementById("v-cliente").value.trim();
    if (!nome) { toast("Informe o nome do cliente.", "erro"); return; }
    const itens = lerItens();
    if (!itens.length || itens.every(i => !i.perfume_id && !Number(i.valor))) {
      toast("Adicione pelo menos um perfume à compra.", "erro"); return;
    }
    for (const i of itens) {
      if (i.valor === 0 || Number(i.valor) < 0) { toast("Cada item precisa de um valor válido.", "erro"); return; }
    }
    const body = JSON.stringify({
      nome_cliente: nome,
      forma_pagamento: document.getElementById("v-forma").value,
      data_vencimento: document.getElementById("v-venc").value,
      observacao: document.getElementById("v-obs").value.trim(),
      itens, pagamentos: lerPagamentos(),
    });
    try {
      if (id) await api(`/api/vendas/${id}`, { method: "PUT", body });
      else await api("/api/vendas", { method: "POST", body });
      fecharModal();
      toast(id ? "Ficha atualizada!" : "Ficha registrada!");
      carregarVendas();
      carregarBadge();
    } catch (e) { toast(e.message, "erro"); }
  }

  // ----- registrar pagamento avulso -----
  async function formPagamento(id) {
    const v = await api(`/api/vendas/${id}`);
    abrirModal(`Receber pagamento — ${v.nome_cliente}`, `
      <p class="card-sub" style="margin-bottom:14px">
        Total: <strong>${fmtMoeda(v.total)}</strong> &nbsp;•&nbsp;
        Já pago: <strong>${fmtMoeda(v.pago)}</strong> &nbsp;•&nbsp;
        Saldo devedor: <strong class="saldo-deve">${fmtMoeda(v.saldo)}</strong>
      </p>
      <div class="form-grid">
        <div class="field">
          <label>Valor recebido (R$) *</label>
          <input type="number" id="pg-novo-valor" step="0.01" min="0" value="${v.saldo.toFixed(2)}">
        </div>
        <div class="field">
          <label>Data do pagamento</label>
          <input type="date" id="pg-novo-data" value="${hojeIso()}">
        </div>
      </div>
      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="App.fecharModal()">Cancelar</button>
        <button class="btn btn-success" onclick="App.salvarPagamento(${id})">Registrar pagamento</button>
      </div>
    `);
  }
  async function salvarPagamento(id) {
    const valor = document.getElementById("pg-novo-valor").value;
    if (valor === "" || Number(valor) <= 0) { toast("Informe um valor válido.", "erro"); return; }
    try {
      await api(`/api/vendas/${id}/pagamentos`, {
        method: "POST",
        body: JSON.stringify({ valor, data: document.getElementById("pg-novo-data").value }),
      });
      fecharModal();
      toast("Pagamento registrado! 🎉");
      carregarVendas();
      carregarBadge();
    } catch (e) { toast(e.message, "erro"); }
  }

  function quitarVenda(id) {
    confirmar("Registrar o pagamento do saldo restante e quitar esta ficha?", async () => {
      try {
        await api(`/api/vendas/${id}/quitar`, { method: "POST" });
        fecharConfirm();
        toast("Ficha quitada! 🎉");
        carregarVendas();
        carregarBadge();
        if (document.querySelector('.menu-item.active')?.dataset.view === "inadimplencia") viewInadimplencia();
      } catch (e) { toast(e.message, "erro"); }
    }, "Quitar");
  }

  function apagarVenda(id) {
    confirmar("Apagar esta ficha? Ela vai para a Lixeira e o estoque dos itens será devolvido.", async () => {
      try {
        await api(`/api/vendas/${id}`, { method: "DELETE" });
        fecharConfirm();
        toast("Ficha enviada para a lixeira.");
        carregarVendas();
        carregarBadge();
      } catch (e) { toast(e.message, "erro"); }
    });
  }

  // ----- relatório de texto do cliente (copiar p/ WhatsApp) -----
  async function gerarRelatorio(id) {
    const r = await api(`/api/vendas/${id}/relatorio`);
    abrirModal("Relatório do cliente", `
      <p class="card-sub" style="margin-bottom:12px">Confira e clique em <strong>Copiar</strong> para colar no WhatsApp.</p>
      <textarea id="rel-texto" class="rel-area" rows="18">${esc(r.texto)}</textarea>
      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="App.fecharModal()">Fechar</button>
        <button class="btn btn-primary" onclick="App.copiarRelatorio()">📋 Copiar texto</button>
      </div>
    `, true);
  }
  function copiarRelatorio() {
    const area = document.getElementById("rel-texto");
    area.select();
    const texto = area.value;
    const ok = () => toast("Relatório copiado! Cole no WhatsApp. 📋");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(texto).then(ok).catch(() => { document.execCommand("copy"); ok(); });
    } else { document.execCommand("copy"); ok(); }
  }

  // ---------- Inadimplência ----------
  async function viewInadimplencia() {
    container().innerHTML = `<div class="empty">Carregando…</div>`;
    const lista = await api("/api/inadimplencia");
    let html = `
      <div class="page-head">
        <div><h1>Inadimplência</h1><p>Clientes com saldo devedor e prazo vencido</p></div>
      </div>`;
    if (!lista.length) {
      html += `<div class="empty"><div class="big">🎉</div>Nenhum cliente em atraso. Tudo em dia!</div>`;
      container().innerHTML = html;
      return;
    }
    const total = lista.reduce((s, v) => s + (v.saldo || 0), 0);
    html += `
      <div class="alerta-banner">⚠️ Você tem <strong>${lista.length}</strong> cliente(s) em atraso, devendo <strong>${fmtMoeda(total)}</strong> no total.</div>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Cliente</th><th class="t-right">Total</th><th class="t-right">Pago</th>
            <th class="t-right">Saldo devedor</th>
            <th class="t-center">Atraso</th><th>Venceu em</th><th>Forma</th><th class="t-right">Ações</th>
          </tr></thead>
          <tbody>
            ${lista.map(v => `
              <tr class="row-atraso">
                <td><strong>${esc(v.nome_cliente)}</strong>${v.observacao ? `<br><span class="card-sub">${esc(v.observacao)}</span>` : ""}</td>
                <td class="t-right">${fmtMoeda(v.total)}</td>
                <td class="t-right">${fmtMoeda(v.pago)}</td>
                <td class="t-right"><strong class="saldo-deve">${fmtMoeda(v.saldo)}</strong></td>
                <td class="t-center"><span class="pill pill-atraso">${v.dias_atraso} dia(s)</span></td>
                <td>${fmtData(v.data_vencimento)}</td>
                <td><span class="pill pill-forma">${esc(v.forma_pagamento)}</span></td>
                <td class="t-right" style="white-space:nowrap">
                  <button class="btn-icon" title="Gerar relatório" onclick="App.gerarRelatorio(${v.id})">📄</button>
                  <button class="btn btn-success btn-sm" onclick="App.formPagamento(${v.id})">Receber</button>
                  <button class="btn-icon" title="Quitar tudo" onclick="App.quitarVenda(${v.id})">✅</button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    container().innerHTML = html;
  }

  async function salvarPix() {
    try {
      await api("/api/config", {
        method: "PUT",
        body: JSON.stringify({
          pix_chave: document.getElementById("cfg-pix-chave").value.trim(),
          pix_nome: document.getElementById("cfg-pix-nome").value.trim(),
          pix_empresa: document.getElementById("cfg-pix-empresa").value.trim(),
        }),
      });
      toast("Dados do Pix atualizados!");
    } catch (e) { toast(e.message, "erro"); }
  }

  // ---------- Relatório PDF ----------
  function baixarPDF() {
    window.location.href = "/api/relatorio.pdf";
    toast("Relatório PDF gerado! Verifique seus downloads.");
  }

  // ---------- Lixeira ----------
  async function viewLixeira() {
    container().innerHTML = `<div class="empty">Carregando…</div>`;
    const d = await api("/api/lixeira");
    const total = d.perfumes.length + d.vendas.length;

    let html = `
      <div class="page-head">
        <div><h1>Lixeira</h1><p>Itens apagados ficam aqui por ${d.retencao_dias} dias antes de sumir de vez</p></div>
        ${total ? `<button class="btn btn-danger" onclick="App.esvaziarLixeira()">Esvaziar lixeira</button>` : ""}
      </div>`;

    if (!total) {
      html += `<div class="empty"><div class="big">🗑️</div>A lixeira está vazia.</div>`;
      container().innerHTML = html;
      return;
    }

    html += `<div class="alerta-banner" style="background:var(--laranja-claro);border-color:#ffd9a8;color:var(--laranja-escuro)">
      ℹ️ Itens apagados podem ser <strong>restaurados</strong> dentro de ${d.retencao_dias} dias. Após esse prazo são removidos automaticamente.
    </div>`;

    if (d.perfumes.length) {
      html += `<h3 style="margin:6px 0 12px">🧴 Perfumes apagados</h3>
        <div class="table-wrap" style="margin-bottom:26px"><table>
          <thead><tr><th>Perfume</th><th>Marca</th><th class="t-right">Venda</th>
            <th class="t-center">Expira em</th><th class="t-right">Ações</th></tr></thead>
          <tbody>
          ${d.perfumes.map(p => `
            <tr>
              <td><strong>${esc(p.nome)}</strong></td>
              <td>${esc(p.marca) || "—"}</td>
              <td class="t-right">${fmtMoeda(p.valor_final)}</td>
              <td class="t-center"><span class="pill pill-pendente">${p.dias_restantes} dia(s)</span></td>
              <td class="acoes">
                <button class="btn btn-success btn-sm" onclick="App.restaurar2('perfumes',${p.id})">↩️ Restaurar</button>
                <button class="btn-icon" title="Excluir de vez" onclick="App.excluirDef('perfumes',${p.id},'${esc(p.nome).replace(/'/g,"")}')">❌</button>
              </td>
            </tr>`).join("")}
          </tbody></table></div>`;
    }

    if (d.vendas.length) {
      html += `<h3 style="margin:6px 0 12px">👤 Fichas de clientes apagadas</h3>
        <div class="table-wrap"><table>
          <thead><tr><th>Cliente</th><th>Itens</th><th class="t-right">Total</th>
            <th class="t-center">Expira em</th><th class="t-right">Ações</th></tr></thead>
          <tbody>
          ${d.vendas.map(v => `
            <tr>
              <td><strong>${esc(v.nome_cliente)}</strong></td>
              <td>${v.num_itens} item(ns)</td>
              <td class="t-right">${fmtMoeda(v.total)}</td>
              <td class="t-center"><span class="pill pill-pendente">${v.dias_restantes} dia(s)</span></td>
              <td class="acoes">
                <button class="btn btn-success btn-sm" onclick="App.restaurar2('vendas',${v.id})">↩️ Restaurar</button>
                <button class="btn-icon" title="Excluir de vez" onclick="App.excluirDef('vendas',${v.id},'${esc(v.nome_cliente).replace(/'/g,"")}')">❌</button>
              </td>
            </tr>`).join("")}
          </tbody></table></div>`;
    }

    container().innerHTML = html;
  }

  async function restaurar2(tipo, id) {
    try {
      await api(`/api/lixeira/${tipo}/${id}/restaurar`, { method: "POST" });
      toast("Item restaurado!");
      carregarBadge();
      viewLixeira();
    } catch (e) { toast(e.message, "erro"); }
  }

  function excluirDef(tipo, id, nome) {
    confirmar(`Excluir "${nome}" DE VEZ? Isso não pode ser desfeito.`, async () => {
      try {
        await api(`/api/lixeira/${tipo}/${id}`, { method: "DELETE" });
        fecharConfirm();
        toast("Item excluído definitivamente.");
        viewLixeira();
      } catch (e) { toast(e.message, "erro"); }
    }, "Excluir de vez");
  }

  function esvaziarLixeira() {
    confirmar("Esvaziar a lixeira apaga TODOS os itens de vez. Continuar?", async () => {
      try {
        await api("/api/lixeira/esvaziar", { method: "POST" });
        fecharConfirm();
        toast("Lixeira esvaziada.");
        viewLixeira();
      } catch (e) { toast(e.message, "erro"); }
    }, "Esvaziar");
  }

  // ---------- Configurações ----------
  async function viewConfig() {
    const cfg = await api("/api/config");
    container().innerHTML = `
      <div class="page-head"><div><h1>Configurações</h1><p>Meta, backup e restauração dos dados</p></div></div>

      <div class="cards" style="grid-template-columns:1fr">
        <div class="card">
          <div class="card-label">🎯 Meta de vendas do mês</div>
          <div class="card-value">${fmtMoeda(cfg.meta_mensal || 0)}</div>
          <div style="margin-top:14px">
            <button class="btn btn-primary" onclick="App.editarMeta()">Alterar meta</button>
          </div>
        </div>

        <div class="card">
          <div class="card-label">💬 Rodapé do relatório (chave Pix)</div>
          <p class="card-sub" style="margin:8px 0 14px">
            Estes dados aparecem no fim do relatório que você gera para cada cliente.
          </p>
          <div class="form-grid">
            <div class="field full">
              <label>Chave Pix</label>
              <input id="cfg-pix-chave" value="${esc(cfg.pix_chave || "")}" placeholder="Ex.: 84 994274834">
            </div>
            <div class="field full">
              <label>Nome do titular</label>
              <input id="cfg-pix-nome" value="${esc(cfg.pix_nome || "")}" placeholder="Ex.: Ana Julia Ramalho">
            </div>
            <div class="field full">
              <label>Razão social / empresa</label>
              <input id="cfg-pix-empresa" value="${esc(cfg.pix_empresa || "")}" placeholder="Ex.: Cloudwalk Ip Ltda">
            </div>
          </div>
          <div style="margin-top:14px"><button class="btn btn-primary" onclick="App.salvarPix()">Salvar dados do Pix</button></div>
        </div>

        <div class="card">
          <div class="card-label">📄 Relatório geral em PDF</div>
          <p class="card-sub" style="margin:8px 0 16px">
            Baixe um relatório com todos os clientes, perfumes vendidos, datas de compra e de pagamento.
          </p>
          <button class="btn btn-primary" onclick="App.baixarPDF()">⬇️ Baixar relatório PDF</button>
        </div>

        <div class="card">
          <div class="card-label">💾 Backup dos dados</div>
          <p class="card-sub" style="margin:8px 0 16px">
            Baixe uma cópia de segurança de todos os seus dados (perfumes, vendas e configurações).
            Guarde esse arquivo em local seguro — pendrive, nuvem ou outra pasta.
          </p>
          <button class="btn btn-primary" onclick="App.baixarBackup()">⬇️ Baixar backup agora</button>
        </div>

        <div class="card">
          <div class="card-label">♻️ Restaurar dados</div>
          <p class="card-sub" style="margin:8px 0 16px">
            Selecione um arquivo de backup (.db) para restaurar. <strong>Atenção:</strong> isso substitui
            os dados atuais (uma cópia de segurança automática é criada antes).
          </p>
          <input type="file" id="restore-file" accept=".db" style="margin-bottom:12px;display:block">
          <button class="btn btn-ghost" onclick="App.restaurar()">Restaurar do arquivo</button>
        </div>
      </div>`;
  }

  function baixarBackup() {
    window.location.href = "/api/backup";
    toast("Backup gerado! Verifique seus downloads.");
  }

  async function restaurar() {
    const input = document.getElementById("restore-file");
    if (!input.files.length) { toast("Selecione um arquivo de backup.", "erro"); return; }
    confirmar("Restaurar vai substituir todos os dados atuais por este backup. Continuar?", async () => {
      const fd = new FormData();
      fd.append("arquivo", input.files[0]);
      try {
        const res = await fetch("/api/restore", { method: "POST", body: fd });
        if (!res.ok) { throw new Error((await res.json()).erro || "Falha ao restaurar."); }
        fecharConfirm();
        toast("Dados restaurados com sucesso!");
        carregarBadge();
        irPara("dashboard");
      } catch (e) { toast(e.message, "erro"); }
    }, "Restaurar");
  }

  // ---------- Helpers ----------
  async function garantirPerfumes() {
    perfumesCache = await api("/api/perfumes");
  }
  function debounce(fn, ms) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  }

  // ---------- Roteamento ----------
  const views = {
    dashboard: viewDashboard,
    perfumes: viewPerfumes,
    vendas: viewVendas,
    inadimplencia: viewInadimplencia,
    lixeira: viewLixeira,
    config: viewConfig,
  };

  async function irPara(nome) {
    document.querySelectorAll(".menu-item").forEach(m =>
      m.classList.toggle("active", m.dataset.view === nome));
    if (location.hash !== "#" + nome) location.hash = nome;
    try {
      await (views[nome] || viewDashboard)();
    } catch (e) {
      container().innerHTML = `<div class="empty"><div class="big">😕</div>${esc(e.message)}</div>`;
    }
  }

  function init() {
    document.querySelectorAll(".menu-item").forEach(m =>
      m.addEventListener("click", (e) => { e.preventDefault(); irPara(m.dataset.view); }));
    window.addEventListener("hashchange", () => {
      const nome = location.hash.replace("#", "");
      if (views[nome] && !document.querySelector(`.menu-item.active[data-view="${nome}"]`)) irPara(nome);
    });
    document.getElementById("confirm-ok").addEventListener("click", () => {
      if (confirmCb) confirmCb();
    });
    document.getElementById("modal-overlay").addEventListener("click", (e) => {
      if (e.target.id === "modal-overlay") fecharModal();
    });
    document.getElementById("confirm-overlay").addEventListener("click", (e) => {
      if (e.target.id === "confirm-overlay") fecharConfirm();
    });
    carregarBadge();
    const inicial = location.hash.replace("#", "");
    irPara(views[inicial] ? inicial : "dashboard");
  }

  // expõe métodos usados no HTML
  return {
    init, irPara, fecharModal, fecharConfirm,
    editarMeta, salvarMeta,
    formPerfume, calcLucro, salvarPerfume, apagarPerfume,
    formVenda, salvarVenda, apagarVenda, limparFiltros,
    addItem, addPagamento, removerLinha, itemPerfumeMudou, recalcResumo,
    formPagamento, salvarPagamento, quitarVenda,
    gerarRelatorio, copiarRelatorio,
    baixarBackup, restaurar, baixarPDF, salvarPix,
    restaurar2, excluirDef, esvaziarLixeira,
  };
})();

document.addEventListener("DOMContentLoaded", App.init);
