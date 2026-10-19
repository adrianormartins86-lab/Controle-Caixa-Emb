// ============================================================
// Caixa EMB — telas de administração (só Administrador e Meiry)
// Extrato, Pagamentos pendentes e Gerar cobrança.
// Usa as utilidades do app.js ($, rpc, abrirGaveta, toast...).
// Funções do banco: sql_mobile/02_funcoes_fase1.sql
// ============================================================
"use strict";

const FORMAS = ["Dinheiro", "Pix", "Cartão Débito", "Cartão Crédito", "Bonificação"];
let listasAdmin = null;   // { clientes: [...], missoes: [...] } para os filtros

async function carregarListasAdmin(forcar = false) {
  if (listasAdmin && !forcar) return listasAdmin;
  listasAdmin = await rpc("mob_admin_listas", { p_token: sessao.token });
  return listasAdmin;
}

const dinheiroTxt = (v) => Number(v || 0).toFixed(2).replace(".", ",");
function somarDias(iso, dias) {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() + dias);
  return d.toISOString().slice(0, 10);
}
function situacaoPedido(p) {
  if (Number(p.pendente) <= 0.001) return ["pago", "Pago"];
  if (Number(p.valor_pago) > 0.001) return ["parcial", "Parcial"];
  return ["pendente", "Pendente"];
}
const itensTxt = (p) => p.itens.map((i) => `${Number(i.quantidade)}x ${i.produto}${i.obs_item ? ` (${i.obs_item})` : ""}`).join(", ");
const focoNoCentro = (g) => g.querySelectorAll("input[type=text],input[type=tel],textarea").forEach((el) =>
  el.addEventListener("focus", () => setTimeout(() => el.scrollIntoView({ block: "center", behavior: "smooth" }), 250)));

// ------------------------------------------------------------
// Escolha com busca (cliente, missão...) dentro da gaveta
// ------------------------------------------------------------
// continuarNaGaveta: o próximo passo abre outra gaveta (só troca o conteúdo, não fecha)
function abrirEscolha({ titulo, opcoes, comTodos = true, continuarNaGaveta = false, aoEscolher }) {
  abrirGaveta(`
    <h3>${esc(titulo)}</h3>
    <div class="busca-wrap"><input id="esc-busca" type="search" placeholder="Digite para buscar..." autocomplete="off" enterkeyhint="search"></div>
    <div class="lista-escolha" id="esc-lista"></div>`, (g) => {
    const inp = g.querySelector("#esc-busca");
    const desenhar = () => {
      const termo = sem_acento(inp.value.trim());
      const lista = opcoes.filter((o) => !termo || sem_acento(o).includes(termo));
      g.querySelector("#esc-lista").innerHTML =
        (comTodos && !termo ? `<button class="opcao" data-v=""><span><strong>Todos</strong></span></button>` : "") +
        lista.map((o) => `<button class="opcao" data-v="${esc(o)}"><span>${esc(o)}</span></button>`).join("") +
        (!lista.length ? `<div class="vazio-msg">Nada encontrado.</div>` : "");
    };
    inp.addEventListener("input", desenhar);
    g.querySelector("#esc-lista").addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-v]");
      if (!b) return;
      if (!continuarNaGaveta) fecharGaveta();
      aoEscolher(b.dataset.v);
    });
    desenhar();
  });
}

// ------------------------------------------------------------
// Filtros (Extrato e Pendentes usam o mesmo bloco)
// ------------------------------------------------------------
function novoFiltro() {
  const hoje = hojeISO();
  return { modo: "periodo", ini: somarDias(hoje, -30), fim: hoje, dia: hoje, cliente: "", missao: "", situacao: "todos" };
}
const filtros = { extrato: novoFiltro(), pendentes: novoFiltro() };
const periodoDe = (f) => (f.modo === "dia" ? [f.dia, f.dia] : [f.ini, f.fim]);

function montarFiltros(tela, aoMudar) {
  const f = filtros[tela];
  const el = $(`#filtros-${tela}`);
  el.innerHTML = `
    <div class="cartao filtros">
      <div class="segmentos seg-2" data-campo="modo">
        <button data-v="periodo" class="${f.modo === "periodo" ? "sel" : ""}">Período</button>
        <button data-v="dia" class="${f.modo === "dia" ? "sel" : ""}">Dia único</button>
      </div>
      ${f.modo === "dia"
        ? `<label class="campo"><span>Dia</span><input type="date" data-campo="dia" value="${f.dia}"></label>`
        : `<div class="linha-2">
             <label class="campo"><span>De</span><input type="date" data-campo="ini" value="${f.ini}"></label>
             <label class="campo"><span>Até</span><input type="date" data-campo="fim" value="${f.fim}"></label>
           </div>`}
      <button class="seletor seletor-fino" data-escolher="cliente">
        <span class="seletor-rotulo">Cliente</span>
        <span class="seletor-valor ${f.cliente ? "" : "vazio"}">${esc(f.cliente || "Todos")}</span>
        ${f.cliente ? `<span class="limpar-filtro" data-limpar="cliente" aria-label="Limpar">✕</span>` : `<span class="seta">›</span>`}
      </button>
      <button class="seletor seletor-fino" data-escolher="missao">
        <span class="seletor-rotulo">Missão</span>
        <span class="seletor-valor ${f.missao ? "" : "vazio"}">${esc(f.missao || "Todas")}</span>
        ${f.missao ? `<span class="limpar-filtro" data-limpar="missao" aria-label="Limpar">✕</span>` : `<span class="seta">›</span>`}
      </button>
      ${tela === "extrato" ? `
      <div class="segmentos" data-campo="situacao" style="margin-bottom:0">
        <button data-v="todos" class="${f.situacao === "todos" ? "sel" : ""}">Todos</button>
        <button data-v="pendentes" class="${f.situacao === "pendentes" ? "sel" : ""}">Pendentes</button>
        <button data-v="pagos" class="${f.situacao === "pagos" ? "sel" : ""}">Pagos</button>
      </div>` : ""}
    </div>`;

  el.querySelectorAll(".segmentos").forEach((seg) => seg.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    f[seg.dataset.campo] = b.dataset.v;
    montarFiltros(tela, aoMudar);
    aoMudar();
  }));
  el.querySelectorAll("input[type=date]").forEach((inp) => inp.addEventListener("change", () => {
    if (!inp.value) { inp.value = f[inp.dataset.campo]; return; }
    f[inp.dataset.campo] = inp.value;
    // "De" depois de "Até": acompanha a outra data
    if (f.ini > f.fim) {
      if (inp.dataset.campo === "ini") f.fim = f.ini; else f.ini = f.fim;
      montarFiltros(tela, aoMudar);
    }
    aoMudar();
  }));
  el.querySelectorAll("[data-escolher]").forEach((b) => b.addEventListener("click", async (e) => {
    const campo = b.dataset.escolher;
    if (e.target.closest("[data-limpar]")) {
      f[campo] = "";
      montarFiltros(tela, aoMudar);
      return aoMudar();
    }
    try { await carregarListasAdmin(); } catch (err) { return toast(err.message, "erro"); }
    abrirEscolha({
      titulo: campo === "cliente" ? "Filtrar por cliente" : "Filtrar por missão",
      opcoes: campo === "cliente" ? listasAdmin.clientes : listasAdmin.missoes,
      aoEscolher: (v) => { f[campo] = v; montarFiltros(tela, aoMudar); aoMudar(); },
    });
  }));
}

async function buscarExtrato(tela) {
  const f = filtros[tela];
  const [ini, fim] = periodoDe(f);
  return rpc("mob_extrato", {
    p_token: sessao.token, p_ini: ini, p_fim: fim, p_cliente: f.cliente || null,
    p_missao: f.missao || null, p_situacao: tela === "extrato" ? f.situacao : "todos",
  });
}

// ============================================================
// EXTRATO
// ============================================================
let extrato = null;
let seqExtrato = 0;   // descarta resposta antiga se o filtro mudou no meio

async function carregarExtrato() {
  montarFiltros("extrato", carregarExtrato);
  const el = $("#extrato-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  const seq = ++seqExtrato;
  try {
    const r = await buscarExtrato("extrato");
    if (seq !== seqExtrato) return;
    extrato = r;
    renderExtrato();
  } catch (e) {
    if (seq === seqExtrato) el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`;
  }
}

function cartaoPedido(p, idx, opc = {}) {
  const [cls, rot] = situacaoPedido(p);
  const restante = Number(p.pendente) > 0.001 && Number(p.valor_pago) > 0.001 ? ` · falta ${fmtMoeda(p.pendente)}` : "";
  return `<button class="ped ped-btn" data-ped="${idx}">
    <div class="ped-topo"><span>${esc(p.cliente)}</span><span>${fmtMoeda(opc.mostrarPendente ? p.pendente : p.total)}</span></div>
    <div class="ped-meta"><span class="etiqueta ${cls}">${rot}</span> ${fmtData(p.data_lancamento)} · ${esc(p.evento || "")}${restante}${p.formas ? ` · ${esc(p.formas)}` : ""}</div>
    <div class="ped-itens">${esc(itensTxt(p))}</div>
    ${p.observacao ? `<div class="item-obs">${esc(p.observacao)}</div>` : ""}
  </button>`;
}

function renderExtrato() {
  const r = extrato;
  const el = $("#extrato-conteudo");
  // mais recente primeiro (no celular é o que se procura primeiro)
  const pedidos = [...r.pedidos].reverse();
  el.innerHTML = `
    <div class="kpis">
      <div class="kpi destaque"><small>Total no período</small><strong>${fmtMoeda(r.total)}</strong></div>
      <div class="kpi pend"><small>⏳ A receber</small><strong>${fmtMoeda(r.a_receber)}</strong></div>
      <div class="kpi"><small>Pedidos · Clientes</small><strong>${r.n_pedidos} · ${r.n_clientes}</strong></div>
    </div>
    ${Number(r.abatido) > 0.001 ? `<p class="dica" style="margin-top:-6px">Já descontado ${fmtMoeda(r.abatido)} em abatimentos/reembolsos do período.</p>` : ""}
    <h2 class="titulo-secao">Pedidos</h2>
    ${pedidos.length ? pedidos.map((p) => cartaoPedido(p, r.pedidos.indexOf(p))).join("") : `<div class="vazio-msg">Nenhum lançamento encontrado nesse período.</div>`}`;
}

$("#extrato-conteudo").addEventListener("click", (e) => {
  const b = e.target.closest("[data-ped]");
  if (b) abrirPedido(extrato.pedidos[+b.dataset.ped], "extrato");
});

// ---------- detalhe do pedido ----------
function abrirPedido(p, origem) {
  const [cls, rot] = situacaoPedido(p);
  abrirGaveta(`
    <h3>${esc(p.cliente)} <span class="etiqueta ${cls}" style="vertical-align:middle">${rot}</span></h3>
    <ul class="info-ped">
      <li><span>Data</span><strong>${fmtData(p.data_lancamento)}</strong></li>
      <li><span>Missão</span><strong>${esc(p.evento || "-")}</strong></li>
      <li><span>Lançado por</span><strong>${esc(p.lancado_por || "-")}</strong></li>
      ${p.data_pagamento ? `<li><span>Pago em</span><strong>${fmtData(p.data_pagamento)}</strong></li>` : ""}
      ${p.formas ? `<li><span>Forma</span><strong>${esc(p.formas)}</strong></li>` : ""}
      ${p.observacao ? `<li><span>Obs.</span><strong>${esc(p.observacao)}</strong></li>` : ""}
    </ul>
    ${p.itens.map((i) => `
      <div class="linha-item-gaveta">
        <div><strong>${Number(i.quantidade)}x ${esc(i.produto)}</strong>
          ${i.obs_item ? `<div class="item-obs">${esc(i.obs_item)}</div>` : ""}
          <div class="item-det">${fmtMoeda(i.preco_unitario)} cada</div></div>
        <strong>${fmtMoeda(i.total)}</strong>
      </div>`).join("")}
    <div class="total-gaveta" style="margin-top:12px"><span>Total</span><strong>${fmtMoeda(p.total)}</strong></div>
    ${Number(p.valor_pago) > 0.001 && Number(p.pendente) > 0.001 ? `<p class="dica" style="margin-top:-6px">Já pago ${fmtMoeda(p.valor_pago)} · falta <strong>${fmtMoeda(p.pendente)}</strong></p>` : ""}
    ${Number(p.pendente) > 0.001 ? `<button class="btn btn-primario btn-bloco" id="pd-receber">💰 Receber ${fmtMoeda(p.pendente)}</button>` : ""}
    <div class="acoes">
      <button class="btn btn-secundario" id="pd-editar">✏️ Editar</button>
      <button class="btn btn-perigo" id="pd-excluir">🗑️ Excluir</button>
    </div>`, (g) => {
    const rec = g.querySelector("#pd-receber");
    if (rec) rec.onclick = () => abrirReceber(p, origem);
    g.querySelector("#pd-editar").onclick = () => abrirEditarPedido(p, origem);
    g.querySelector("#pd-excluir").onclick = () => abrirExcluirPedido(p, origem);
  });
}

function recarregarOrigem(origem) {
  if (origem === "extrato") return carregarExtrato();
  if (origem === "pendentes") return carregarPendentes();
}

async function abrirEditarPedido(p, origem) {
  try { await carregarListasAdmin(); } catch (e) { return toast(e.message, "erro"); }
  const ed = { cliente: p.cliente, missao: p.evento || "" };
  abrirGaveta(`
    <h3>Editar pedido</h3>
    <button class="seletor" id="ep-cliente"><span class="seletor-rotulo">Cliente</span><span class="seletor-valor" id="ep-cliente-v"></span><span class="seta">›</span></button>
    <div class="linha-2">
      <label class="campo"><span>Data</span><input id="ep-data" type="date" value="${p.data_lancamento}"></label>
      <label class="campo"><span>Missão</span><select id="ep-missao"></select></label>
    </div>
    <label class="campo"><span>Observação do pedido</span><input id="ep-obs" type="text" autocomplete="off" value="${esc(p.observacao || "")}"></label>
    <p class="dica">Os itens e valores não mudam aqui. Para corrigir item, exclua o pedido e lance de novo.</p>
    <div class="acoes">
      <button class="btn btn-secundario" id="ep-voltar">Voltar</button>
      <button class="btn btn-primario" id="ep-salvar">Salvar</button>
    </div>`, (g) => {
    focoNoCentro(g);
    const missoes = listasAdmin.missoes.includes(ed.missao) || !ed.missao ? listasAdmin.missoes : [ed.missao, ...listasAdmin.missoes];
    g.querySelector("#ep-missao").innerHTML = missoes.map((m) => `<option>${esc(m)}</option>`).join("");
    g.querySelector("#ep-missao").value = ed.missao;
    g.querySelector("#ep-cliente-v").textContent = ed.cliente;
    // guarda o que já foi digitado ao trocar de cliente (a lista abre na mesma gaveta)
    g.querySelector("#ep-cliente").onclick = () => {
      const data = g.querySelector("#ep-data").value, missao = g.querySelector("#ep-missao").value, obs = g.querySelector("#ep-obs").value;
      abrirEscolha({
        titulo: "Trocar cliente", opcoes: listasAdmin.clientes, comTodos: false, continuarNaGaveta: true,
        // reabre a edição já com o novo cliente (mesmo pedido_id)
        aoEscolher: (v) => abrirEditarPedido({ ...p, cliente: v, data_lancamento: data, evento: missao, observacao: obs }, origem),
      });
    };
    g.querySelector("#ep-voltar").onclick = () => fecharGaveta();
    g.querySelector("#ep-salvar").onclick = async () => {
      const data = g.querySelector("#ep-data").value;
      if (!data) return toast("Informe a data.", "erro");
      carregando(true);
      try {
        await rpc("mob_editar_pedido", {
          p_token: sessao.token, p_pedido_id: p.pedido_id, p_cliente: ed.cliente,
          p_missao: g.querySelector("#ep-missao").value, p_data: data, p_observacao: g.querySelector("#ep-obs").value,
        });
        fecharGaveta();
        toast(`Pedido de ${ed.cliente} atualizado.`, "ok");
        recarregarOrigem(origem);
      } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
    };
  });
}

function abrirExcluirPedido(p, origem) {
  abrirGaveta(`
    <h3>Excluir pedido</h3>
    <div class="aviso-perigo">
      <strong>${esc(p.cliente)}</strong> · ${fmtData(p.data_lancamento)} · ${fmtMoeda(p.total)}<br>
      <small>${esc(itensTxt(p))}</small>
    </div>
    <label class="campo"><span>Motivo da exclusão (obrigatório)</span><input id="ex-motivo" type="text" autocomplete="off" placeholder="Ex.: lançado em duplicidade"></label>
    <p class="dica">O pedido some do extrato e dos relatórios, mas fica guardado no banco com o motivo e quem excluiu.</p>
    <div class="acoes">
      <button class="btn btn-secundario" id="ex-voltar">Voltar</button>
      <button class="btn btn-perigo" id="ex-ok">Confirmar exclusão</button>
    </div>`, (g) => {
    focoNoCentro(g);
    g.querySelector("#ex-voltar").onclick = () => fecharGaveta();
    g.querySelector("#ex-ok").onclick = async () => {
      const motivo = g.querySelector("#ex-motivo").value.trim();
      if (!motivo) return toast("Informe o motivo da exclusão.", "erro");
      carregando(true);
      try {
        await rpc("mob_excluir_pedido", { p_token: sessao.token, p_pedido_id: p.pedido_id, p_motivo: motivo });
        fecharGaveta();
        toast(`Pedido de ${p.cliente} excluído.`, "ok");
        recarregarOrigem(origem);
      } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
    };
  });
}

// ---------- receber um pedido ----------
function chipsFormas(sel) {
  return `<div class="chips" id="rc-formas">${FORMAS.map((f) => `<button data-f="${esc(f)}" class="${f === sel ? "sel" : ""}">${esc(f)}</button>`).join("")}</div>`;
}

function abrirReceber(p, origem) {
  const st = { forma: null, corrigir: false };
  const pago = Number(p.valor_pago), total = Number(p.total), pend = Number(p.pendente);
  abrirGaveta(`
    <h3>Receber · ${esc(p.cliente)}</h3>
    <ul class="info-ped">
      <li><span>Pedido de ${fmtData(p.data_lancamento)}</span><strong>${fmtMoeda(total)}</strong></li>
      ${pago > 0.001 ? `<li><span>Já pago</span><strong>${fmtMoeda(pago)}</strong></li>` : ""}
      <li><span>Pendente</span><strong style="color:var(--laranja)">${fmtMoeda(pend)}</strong></li>
    </ul>
    <div class="campo"><span>Forma de pagamento</span></div>
    ${chipsFormas(null)}
    <label class="campo"><span id="rc-rotulo">Valor recebido agora (R$)</span>
      <input id="rc-valor" type="text" inputmode="decimal" autocomplete="off" value="${dinheiroTxt(pend)}"></label>
    <p class="dica" id="rc-resta"></p>
    ${pago > 0.001 ? `<label class="chave"><span>Corrigir o total já pago<small class="sub-chave">Use se um pagamento foi lançado errado</small></span><input id="rc-corrigir" type="checkbox"></label>` : ""}
    <div class="acoes">
      <button class="btn btn-secundario" id="rc-voltar">Voltar</button>
      <button class="btn btn-primario" id="rc-ok">Confirmar</button>
    </div>`, (g) => {
    focoNoCentro(g);
    const inp = g.querySelector("#rc-valor");
    const novoTotalPago = () => arred(st.corrigir ? lerValor(inp.value) : pago + lerValor(inp.value));
    const atualizar = () => {
      g.querySelectorAll("#rc-formas button").forEach((b) => b.classList.toggle("sel", b.dataset.f === st.forma));
      const n = novoTotalPago();
      const resta = arred(total - n);
      g.querySelector("#rc-resta").innerHTML = n > total + 0.001
        ? `<span style="color:var(--vermelho)">Passa do total do pedido (${fmtMoeda(total)}).</span>`
        : resta <= 0.001 ? "✅ Pedido fica <strong>quitado</strong>." : `Ficará faltando <strong>${fmtMoeda(resta)}</strong>.`;
    };
    g.querySelector("#rc-formas").onclick = (e) => { const b = e.target.closest("button"); if (b) { st.forma = b.dataset.f; atualizar(); } };
    inp.addEventListener("input", atualizar);
    const cor = g.querySelector("#rc-corrigir");
    if (cor) cor.onchange = () => {
      st.corrigir = cor.checked;
      g.querySelector("#rc-rotulo").textContent = st.corrigir ? "Total pago do pedido (R$)" : "Valor recebido agora (R$)";
      inp.value = dinheiroTxt(st.corrigir ? pago : pend);
      atualizar();
    };
    g.querySelector("#rc-voltar").onclick = () => fecharGaveta();
    g.querySelector("#rc-ok").onclick = async () => {
      if (!st.forma) return toast("Escolha a forma de pagamento.", "erro");
      const n = novoTotalPago();
      if (!st.corrigir && lerValor(inp.value) <= 0) return toast("Informe o valor recebido.", "erro");
      if (n < 0 || n > total + 0.001) return toast(`O total pago tem que ficar entre R$ 0,00 e ${fmtMoeda(total)}.`, "erro");
      carregando(true);
      try {
        const r = await rpc("mob_registrar_pagamento", { p_token: sessao.token, p_pedido_id: p.pedido_id, p_valor_pago: n, p_forma: st.forma });
        mostrarConfirmacao("✅ Pagamento registrado", Number(r.resta) <= 0.001
          ? `<p>Pedido de <strong>${esc(p.cliente)}</strong> quitado (${esc(st.forma)}).</p>`
          : `<p>Registrado <strong>${fmtMoeda(n - (st.corrigir ? 0 : pago))}</strong> de ${esc(p.cliente)} (${esc(st.forma)}).</p><p>Resta <strong>${fmtMoeda(r.resta)}</strong>.</p>`);
        recarregarOrigem(origem);
      } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
    };
    atualizar();
  });
}

// janela de confirmação (fica até tocar em OK — deixa claro que salvou)
function mostrarConfirmacao(titulo, html) {
  abrirGaveta(`<h3>${esc(titulo)}</h3><div class="confirmacao">${html}</div>
    <button class="btn btn-primario btn-bloco" id="cf-ok" style="margin-top:12px">OK</button>`,
    (g) => { g.querySelector("#cf-ok").onclick = () => fecharGaveta(); });
}

// ============================================================
// PAGAMENTOS PENDENTES
// ============================================================
let pendentes = null;
let seqPendentes = 0;

async function carregarPendentes() {
  montarFiltros("pendentes", carregarPendentes);
  const el = $("#pendentes-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  const seq = ++seqPendentes;
  try {
    const r = await buscarExtrato("pendentes");
    if (seq !== seqPendentes) return;
    // só pedidos com valor em aberto, mais antigo primeiro (mesma ordem da liquidação)
    pendentes = r.pedidos.filter((p) => Number(p.pendente) > 0.001);
    renderPendentes();
  } catch (e) {
    if (seq === seqPendentes) el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`;
  }
}

function renderPendentes() {
  const el = $("#pendentes-conteudo");
  const f = filtros.pendentes;
  if (!pendentes.length) {
    el.innerHTML = `<div class="vazio-msg">Nenhum pagamento pendente com esses filtros. 🎉</div>`;
    return;
  }
  const devido = arred(pendentes.reduce((s, p) => s + Number(p.pendente), 0));
  el.innerHTML = `
    <div class="kpis">
      <div class="kpi destaque"><small>Pendente · ${pendentes.length} pedido(s)</small><strong>${fmtMoeda(devido)}</strong></div>
    </div>
    ${f.cliente ? `
    <div class="cartao liquidar">
      <strong>💵 Liquidar por valor · ${esc(f.cliente)}</strong>
      <p class="dica">Digite quanto o cliente pagou. Quita os pedidos mais antigos primeiro, até acabar o valor.</p>
      <div class="campo"><span>Forma de pagamento</span></div>
      <div class="chips" id="lq-formas">${FORMAS.map((x) => `<button data-f="${esc(x)}">${esc(x)}</button>`).join("")}</div>
      <label class="campo"><span>Valor recebido (R$)</span>
        <input id="lq-valor" type="text" inputmode="decimal" autocomplete="off" placeholder="0,00"></label>
      <div class="acoes-linha">
        <button class="btn btn-secundario" id="lq-tudo">Quitar tudo (${fmtMoeda(devido)})</button>
        <button class="btn btn-primario" id="lq-ok">✅ Liquidar</button>
      </div>
    </div>` : `<p class="dica">Escolha um cliente no filtro para liquidar vários pedidos de uma vez por valor.</p>`}
    <h2 class="titulo-secao">Pedidos em aberto (mais antigos primeiro)</h2>
    ${pendentes.map((p, i) => cartaoPedido(p, i, { mostrarPendente: true })).join("")}`;

  if (f.cliente) {
    const lq = { forma: null };
    const formas = $("#lq-formas");
    formas.onclick = (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      lq.forma = b.dataset.f;
      formas.querySelectorAll("button").forEach((x) => x.classList.toggle("sel", x === b));
    };
    $("#lq-valor").addEventListener("focus", (e) => setTimeout(() => e.target.scrollIntoView({ block: "center", behavior: "smooth" }), 250));
    $("#lq-tudo").onclick = () => { $("#lq-valor").value = dinheiroTxt(devido); };
    $("#lq-ok").onclick = async () => {
      const valor = arred(lerValor($("#lq-valor").value));
      if (!lq.forma) return toast("Escolha a forma de pagamento.", "erro");
      if (valor <= 0) return toast("Informe o valor recebido.", "erro");
      if (valor > devido + 0.001) return toast(`O valor passa do total pendente (${fmtMoeda(devido)}).`, "erro");
      const [ini, fim] = periodoDe(f);
      carregando(true);
      try {
        const r = await rpc("mob_liquidar_cliente", {
          p_token: sessao.token, p_cliente: f.cliente, p_valor: valor, p_forma: lq.forma,
          p_ini: ini, p_fim: fim, p_missao: f.missao || null,
        });
        if (!r.detalhes.length) toast("Nenhum pedido pendente para liquidar.", "erro");
        else mostrarConfirmacao("✅ Pagamento registrado", `
          <p>Liquidado <strong>${fmtMoeda(r.aplicado)}</strong> de ${esc(f.cliente)} (${esc(lq.forma)}), do mais antigo para o mais novo:</p>
          <ul>${r.detalhes.map((d) => `<li>${fmtData(d.data)} — ${esc(d.itens)}: <strong>${fmtMoeda(d.aplicado)}</strong> (${d.quitado ? "quitado" : "parcial"})</li>`).join("")}</ul>
          ${Number(r.sobra) > 0.009 ? `<p>Sobrou ${fmtMoeda(r.sobra)} não aplicado (não há mais pendências).</p>` : ""}`);
        carregarPendentes();
      } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
    };
  }
}

$("#pendentes-conteudo").addEventListener("click", (e) => {
  const b = e.target.closest("[data-ped]");
  if (b) abrirReceber(pendentes[+b.dataset.ped], "pendentes");
});

// ============================================================
// GERAR COBRANÇA
// ============================================================
let cobranca = null;

async function carregarCobranca() {
  const el = $("#cobranca-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  try {
    cobranca = await rpc("mob_cobranca", { p_token: sessao.token });
    renderCobranca();
  } catch (e) {
    el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`;
  }
}

function renderCobranca() {
  const el = $("#cobranca-conteudo");
  if (!cobranca.devedores.length) {
    el.innerHTML = `<div class="vazio-msg">Nenhum cliente com valor em aberto. 🎉</div>`;
    return;
  }
  const termo = sem_acento($("#cob-busca").value.trim());
  const lista = cobranca.devedores.filter((d) => !termo || sem_acento(d.cliente).includes(termo));
  const total = arred(cobranca.devedores.reduce((s, d) => s + Number(d.total), 0));
  el.innerHTML = `
    <p class="dica">${cobranca.devedores.length} cliente(s) devendo · ${fmtMoeda(total)} no total</p>
    <div class="cfg-lista" style="margin-top:6px">
      ${lista.map((d) => `
        <button class="cfg-item" data-dev="${esc(d.cliente)}">
          <span>${esc(d.cliente)}<small>${d.telefone ? esc(d.telefone) : "📵 sem telefone"}</small></span>
          <span class="preco" style="color:var(--laranja)">${fmtMoeda(d.total)}</span>
        </button>`).join("") || `<div class="vazio-msg">Nada encontrado.</div>`}
    </div>`;
}

// mesmo texto do sistema do navegador
function montarMensagemCobranca(d) {
  const grupos = [];
  for (const it of d.itens) {
    const data = fmtData(it.data);
    let g = grupos[grupos.length - 1];
    if (!g || g.data !== data) grupos.push((g = { data, itens: [] }));
    g.itens.push(it);
  }
  const linhas = [];
  for (const g of grupos) {
    linhas.push(`\n${g.data}`);
    for (const it of g.itens) linhas.push(`${Math.round(Number(it.quantidade))} ${it.produto} ${dinheiroTxt(it.pendente)}`);
    if (g.itens.length > 1) linhas.push(`Total do dia: ${dinheiroTxt(g.itens.reduce((s, i) => s + Number(i.pendente), 0))}`);
  }
  let fecho = `\n\nTotal em aberto: R$ ${dinheiroTxt(d.total)}`;
  if (cobranca.pix_chave) {
    fecho += `\n\nSe puder realizar o pix na chave ${cobranca.pix_chave}` +
      (cobranca.pix_nome ? ` (${cobranca.pix_nome})` : "") +
      " e mandar o comprovante, agradecemos.\nDeus abençoe!!";
  }
  return `Paz, ${d.cliente}!\n\nSua conta se encontra em aberto do consumo:\n` + linhas.join("\n") + fecho;
}

function linkWhatsapp(tel, msg) {
  let dig = String(tel || "").replace(/\D/g, "");
  if (dig && !dig.startsWith("55")) dig = "55" + dig;
  return `https://wa.me/${dig}?text=${encodeURIComponent(msg)}`;
}

function abrirCobranca(d) {
  abrirGaveta(`
    <h3>Cobrança · ${esc(d.cliente)}</h3>
    <div class="total-gaveta"><span>Total em aberto</span><strong>${fmtMoeda(d.total)}</strong></div>
    <label class="campo"><span>Mensagem (pode editar antes de enviar)</span>
      <textarea id="cb-msg" rows="12"></textarea></label>
    ${d.telefone ? "" : `<p class="dica">📵 Cliente sem telefone. O WhatsApp vai abrir para você escolher o contato. Para ir direto, cadastre o telefone em Configurações › Clientes.</p>`}
    <div class="acoes">
      <button class="btn btn-secundario" id="cb-copiar">📋 Copiar</button>
      <a class="btn btn-whats" id="cb-whats" target="_blank" rel="noopener">📲 WhatsApp</a>
    </div>`, (g) => {
    const ta = g.querySelector("#cb-msg");
    ta.value = montarMensagemCobranca(d);
    const atualizarLink = () => (g.querySelector("#cb-whats").href = linkWhatsapp(d.telefone, ta.value));
    ta.addEventListener("input", atualizarLink);
    atualizarLink();
    g.querySelector("#cb-copiar").onclick = async () => {
      try { await navigator.clipboard.writeText(ta.value); toast("Mensagem copiada.", "ok"); }
      catch { ta.select(); document.execCommand("copy"); toast("Mensagem copiada.", "ok"); }
    };
  });
}

$("#cob-busca").addEventListener("input", () => cobranca && renderCobranca());
$("#cobranca-conteudo").addEventListener("click", (e) => {
  const b = e.target.closest("[data-dev]");
  if (b) abrirCobranca(cobranca.devedores.find((d) => d.cliente === b.dataset.dev));
});

// ============================================================
// Menu "Mais" e botão voltar
// ============================================================
$("#pg-mais").addEventListener("click", (e) => { const b = e.target.closest("[data-ir]"); if (b) irPara(b.dataset.ir); });
$("#btn-voltar").addEventListener("click", () => irPara("mais"));
