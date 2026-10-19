// ============================================================
// Caixa EMB — app do celular
// Conversa com o Supabase só pelas funções mob_* (ver sql/).
// ============================================================
"use strict";

const { SUPABASE_URL, SUPABASE_KEY, VERSAO } = window.CONFIG;
const $ = (sel) => document.querySelector(sel);
const CHAVE_SESSAO = "caixa_emb_sessao";

// ---------------- estado ----------------
let sessao = lerSessao();     // { token, usuario, perfil }
let dados = null;             // produtos, missões, clientes, formas, admin
let comandas = [];            // comandas abertas (do banco)
let pagina = "lancar";

const lanc = {
  cliente: null,
  carrinho: [],               // { produto, quantidade, preco_unitario, preco_extra, obs_item }
};

// ============================================================
// Utilidades
// ============================================================
function lerSessao() {
  try { return JSON.parse(localStorage.getItem(CHAVE_SESSAO)) || null; } catch { return null; }
}
function gravarSessao(s) {
  try { s ? localStorage.setItem(CHAVE_SESSAO, JSON.stringify(s)) : localStorage.removeItem(CHAVE_SESSAO); } catch {}
}
const fmtMoeda = (v) => Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const fmtData = (iso) => { if (!iso) return ""; const [a, m, d] = String(iso).slice(0, 10).split("-"); return `${d}/${m}/${a}`; };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sem_acento = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const arred = (v) => Math.round(Number(v) * 100) / 100;
function hojeISO() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
}
function tempoDesde(iso) {
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (min < 60) return `há ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `há ${h}h${String(min % 60).padStart(2, "0")}`;
  return `há ${Math.floor(h / 24)} dia(s)`;
}
function lerValor(txt) {
  // aceita "12,50", "12.50", "R$ 12,50"
  const n = parseFloat(String(txt || "").replace(/[^\d,.-]/g, "").replace(/\.(?=\d{3}(\D|$))/g, "").replace(",", "."));
  return isNaN(n) ? 0 : n;
}

let toastTimer;
function toast(msg, tipo = "") {
  const t = $("#toast");
  t.className = "toast " + tipo;
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), tipo === "erro" ? 4500 : 2800);
}
function carregando(on) { $("#carregando").hidden = !on; }

// ============================================================
// Supabase: chamada de função (RPC)
// ============================================================
async function rpc(fn, args = {}) {
  let resp;
  try {
    resp = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${fn}`, {
      method: "POST",
      headers: { apikey: SUPABASE_KEY, "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
  } catch {
    throw new Error("Sem conexão com a internet. Tente de novo.");
  }
  const texto = await resp.text();
  const corpo = texto ? JSON.parse(texto) : null;
  if (!resp.ok) {
    const msg = (corpo && (corpo.message || corpo.hint)) || `Erro ${resp.status}`;
    if (msg.includes("SESSAO_INVALIDA")) {
      sair(true);
      throw new Error("Sua sessão expirou. Entre de novo.");
    }
    throw new Error(msg);
  }
  return corpo;
}

// ============================================================
// Login
// ============================================================
async function mostrarLogin() {
  $("#app").hidden = true;
  $("#barra-total").hidden = true;
  $("#tela-login").hidden = false;
  $("#versao-login").textContent = `versão ${VERSAO}`;
  try {
    const nomes = await rpc("mob_usuarios");
    const sel = $("#login-usuario");
    sel.innerHTML = `<option value="">Escolha...</option>` + nomes.map((n) => `<option>${esc(n)}</option>`).join("");
    const ultimo = localStorage.getItem("caixa_emb_ultimo_usuario");
    if (ultimo && nomes.includes(ultimo)) sel.value = ultimo;
  } catch (e) {
    mostrarErroLogin(e.message);
  }
}
function mostrarErroLogin(msg) { const p = $("#login-erro"); p.textContent = msg; p.hidden = !msg; }

async function entrar() {
  const nome = $("#login-usuario").value;
  const senha = $("#login-senha").value;
  if (!nome) return mostrarErroLogin("Escolha o usuário.");
  if (!senha) return mostrarErroLogin("Digite a senha.");
  mostrarErroLogin("");
  $("#btn-entrar").disabled = true;
  try {
    const r = await rpc("mob_login", { p_nome: nome, p_senha: senha });
    if (r.erro) return mostrarErroLogin(r.erro);
    sessao = { token: r.token, usuario: r.usuario, perfil: r.perfil };
    gravarSessao(sessao);
    try { localStorage.setItem("caixa_emb_ultimo_usuario", nome); } catch {}
    $("#login-senha").value = "";
    await iniciarApp();
  } catch (e) {
    mostrarErroLogin(e.message);
  } finally {
    $("#btn-entrar").disabled = false;
  }
}

function sair(silencioso = false) {
  if (sessao && !silencioso) rpc("mob_logout", { p_token: sessao.token }).catch(() => {});
  sessao = null;
  gravarSessao(null);
  dados = null;
  lanc.cliente = null; lanc.carrinho = [];
  fecharGaveta();
  mostrarLogin();
}

// ============================================================
// Início
// ============================================================
async function iniciarApp() {
  carregando(true);
  try {
    dados = await rpc("mob_dados", { p_token: sessao.token });
  } catch (e) {
    carregando(false);
    if (sessao) toast(e.message, "erro");
    return;
  }
  carregando(false);
  $("#tela-login").hidden = true;
  $("#app").hidden = false;
  $("#topo-usuario").textContent = `${dados.usuario}${dados.admin ? " · administrador" : ""}`;
  $("#aba-mais").hidden = !dados.admin;

  $("#lanc-missao").innerHTML = `<option value="">Escolha...</option>` +
    dados.missoes.map((m) => `<option>${esc(m)}</option>`).join("");
  if (dados.missoes.length === 1) $("#lanc-missao").value = dados.missoes[0];
  $("#lanc-data").value = dados.hoje;
  $("#hoje-data").value = dados.hoje;

  await atualizarComandas();
  irPara(pagina);
}

async function recarregarCadastros() {
  try { dados = { ...dados, ...(await rpc("mob_dados", { p_token: sessao.token })) }; } catch { return; }
  const sel = $("#lanc-missao"), atual = sel.value;
  sel.innerHTML = `<option value="">Escolha...</option>` + dados.missoes.map((m) => `<option>${esc(m)}</option>`).join("");
  if (dados.missoes.includes(atual)) sel.value = atual;
}

// ============================================================
// Navegação
// ============================================================
const TITULOS = {
  lancar: "Novo pedido", comandas: "Comandas abertas", hoje: "Resumo do dia", mais: "Mais opções",
  config: "Configurações", extrato: "Extrato", pendentes: "Pagamentos pendentes", cobranca: "Gerar cobrança",
  fechamento: "Fechamento", resumocli: "Resumo por cliente", resumoprod: "Resumo por produto",
};
const PAGINAS = Object.keys(TITULOS);
// telas que ficam dentro do "Mais" (só administrador)
const SUB_MAIS = ["config", "extrato", "pendentes", "cobranca", "fechamento", "resumocli", "resumoprod"];
function irPara(pg) {
  if ((pg === "mais" || SUB_MAIS.includes(pg)) && !dados.admin) pg = "lancar";
  pagina = pg;
  for (const p of PAGINAS) $(`#pg-${p}`).hidden = p !== pg;
  const sub = SUB_MAIS.includes(pg);
  if (pg === "config") carregarConfig();
  if (pg === "extrato") carregarExtrato();
  if (pg === "pendentes") carregarPendentes();
  if (pg === "cobranca") carregarCobranca();
  if (pg === "fechamento") carregarFechamento();
  if (pg === "resumocli") carregarResumoCli();
  if (pg === "resumoprod") carregarResumoProd();
  const abaAtiva = sub ? "mais" : pg;
  document.querySelectorAll(".aba").forEach((b) => b.classList.toggle("ativa", b.dataset.pg === abaAtiva));
  $("#topo-titulo").textContent = TITULOS[pg];
  $("#btn-voltar").hidden = !sub;
  $("#topo-logo").hidden = sub;
  window.scrollTo({ top: 0 });
  if (pg === "lancar") renderLancar();
  if (pg === "comandas") { renderComandas(); atualizarComandas().then(renderComandas); }
  if (pg === "hoje") carregarResumo();
  $("#barra-total").hidden = pg !== "lancar";
}

async function atualizarComandas() {
  try { comandas = await rpc("mob_comandas", { p_token: sessao.token }); } catch (e) { toast(e.message, "erro"); }
  const b = $("#badge-comandas");
  b.textContent = comandas.length;
  b.hidden = comandas.length === 0;
}
const comandaDoCliente = (cli) => comandas.find((c) => c.cliente === cli) || null;

// ============================================================
// Tela LANÇAR
// ============================================================
function renderLancar() {
  const ca = comandaDoCliente(lanc.cliente);
  const travado = lanc.carrinho.length > 0;

  // cliente
  const v = $("#cliente-valor");
  v.textContent = lanc.cliente || "Escolha...";
  v.classList.toggle("vazio", !lanc.cliente);
  $("#btn-cliente").disabled = travado;
  $("#aviso-trava").hidden = !travado;

  // data / missão: travadas se já existe comanda aberta
  const data = $("#lanc-data"), missao = $("#lanc-missao");
  if (ca) {
    data.value = ca.data_lancamento;
    if (![...missao.options].some((o) => o.value === ca.evento)) missao.add(new Option(ca.evento, ca.evento));
    missao.value = ca.evento;
  }
  data.disabled = !!ca;
  missao.disabled = !!ca || travado;

  // info da comanda aberta
  const info = $("#info-comanda");
  if (ca) {
    info.hidden = false;
    info.innerHTML = `🧾 <strong>${esc(ca.cliente)}</strong> já tem comanda aberta: ` +
      `${ca.itens.length} item(ns), <strong>${fmtMoeda(ca.total)}</strong>. Os itens novos entram nela.` +
      `<ul>${ca.itens.map((i) => `<li>${Number(i.quantidade)}x ${esc(i.produto)} — ${fmtMoeda(i.total)}</li>`).join("")}</ul>`;
  } else {
    info.hidden = true;
  }

  renderProdutos();
  renderCarrinho();
}

function renderProdutos() {
  const termo = sem_acento($("#busca-produto").value.trim());
  const qtdPorProduto = {};
  lanc.carrinho.forEach((i) => (qtdPorProduto[i.produto] = (qtdPorProduto[i.produto] || 0) + i.quantidade));
  const lista = dados.produtos.filter((p) => !termo || sem_acento(p.nome).includes(termo));
  $("#grade-produtos").innerHTML = lista.length
    ? lista.map((p) => {
        const q = qtdPorProduto[p.nome];
        return `<button class="produto ${q ? "com-qtd" : ""}" data-produto="${esc(p.nome)}">
          <span class="produto-nome">${esc(p.nome)}</span>
          <span class="produto-preco">${fmtMoeda(p.preco)}</span>
          ${q ? `<span class="produto-qtd">${q}</span>` : ""}
        </button>`;
      }).join("")
    : `<div class="vazio-msg" style="grid-column:1/-1">Nenhum produto encontrado.</div>`;
}

function totalItem(i) { return arred(i.quantidade * (Number(i.preco_unitario) + Number(i.preco_extra || 0))); }
function totalCarrinho() { return arred(lanc.carrinho.reduce((s, i) => s + totalItem(i), 0)); }

function renderCarrinho() {
  const tem = lanc.carrinho.length > 0;
  const ca = comandaDoCliente(lanc.cliente);
  $("#titulo-itens").hidden = !tem;
  $("#titulo-itens").textContent = ca ? "Itens novos desta rodada" : "Itens do pedido";
  $("#bloco-obs").hidden = !(tem || ca);
  $("#lista-carrinho").innerHTML = lanc.carrinho.map((i, idx) => {
    const extra = Number(i.preco_extra) > 0 ? ` + ${fmtMoeda(i.preco_extra)} extra` : "";
    return `<div class="item">
      <button class="item-info item-editar" data-editar="${idx}">
        <div class="item-nome">${esc(i.produto)}</div>
        <div class="item-det">${fmtMoeda(i.preco_unitario)}${extra} · <span class="lapis">editar</span></div>
        ${i.obs_item ? `<div class="item-obs">${esc(i.obs_item)}</div>` : ""}
      </button>
      <div class="qtd">
        <button class="menos ${i.quantidade === 1 ? "lixo" : ""}" data-menos="${idx}" aria-label="Diminuir">${i.quantidade === 1 ? "🗑" : "−"}</button>
        <span>${i.quantidade}</span>
        <button data-mais="${idx}" aria-label="Aumentar">+</button>
      </div>
      <div class="item-total">${fmtMoeda(totalItem(i))}</div>
    </div>`;
  }).join("");

  // barra do total
  const totalNovo = totalCarrinho();
  const totalGeral = arred(totalNovo + (ca ? Number(ca.total) : 0));
  $("#barra-rotulo").textContent = ca ? "Total da comanda" : "Total do pedido";
  $("#barra-valor").textContent = fmtMoeda(totalGeral);
  $("#btn-guardar").disabled = !tem;
  $("#btn-fechar").disabled = !(tem || ca);
}

function adicionarProduto(nome) {
  if (!lanc.cliente) {
    toast("Escolha o cliente primeiro.", "erro");
    abrirEscolhaCliente();
    return;
  }
  const p = dados.produtos.find((x) => x.nome === nome);
  // soma no item igual (mesmo produto, sem extra/obs); senão cria linha nova
  const igual = lanc.carrinho.find((i) => i.produto === nome && !Number(i.preco_extra) && !i.obs_item && Number(i.preco_unitario) === Number(p.preco));
  if (igual) igual.quantidade += 1;
  else lanc.carrinho.push({ produto: nome, quantidade: 1, preco_unitario: Number(p.preco), preco_extra: 0, obs_item: "" });
  if (navigator.vibrate) navigator.vibrate(15);
  renderLancar();
}

function limparLancamento() {
  lanc.cliente = null;
  lanc.carrinho = [];
  $("#lanc-obs").value = "";
  $("#busca-produto").value = "";
  $("#lanc-data").value = hojeISO();
  renderLancar();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function itensParaEnvio() {
  return lanc.carrinho.map((i) => ({
    produto: i.produto, quantidade: i.quantidade,
    preco_unitario: Number(i.preco_unitario), preco_extra: Number(i.preco_extra || 0), obs_item: i.obs_item || "",
  }));
}

async function guardarNaComanda() {
  if (!lanc.cliente) return toast("Escolha o cliente.", "erro");
  if (!comandaDoCliente(lanc.cliente) && !$("#lanc-missao").value) return toast("Escolha a missão.", "erro");
  carregando(true);
  try {
    const r = await rpc("mob_lancar", {
      p_token: sessao.token, p_cliente: lanc.cliente, p_missao: $("#lanc-missao").value,
      p_data: $("#lanc-data").value, p_observacao: $("#lanc-obs").value, p_itens: itensParaEnvio(), p_fechar: null,
    });
    const cli = lanc.cliente;
    await atualizarComandas();
    limparLancamento();
    toast(`Guardado na comanda de ${cli} · ${fmtMoeda(r.total)}`, "ok");
  } catch (e) {
    toast(e.message, "erro");
  } finally {
    carregando(false);
  }
}

// ============================================================
// Gaveta (bottom sheet) — com suporte ao botão "voltar" do Android
// ============================================================
let gavetaAberta = false;
function abrirGaveta(html, aoAbrir) {
  $("#gaveta-conteudo").innerHTML = html;
  $("#veu").hidden = false;
  $("#gaveta").hidden = false;
  $("#gaveta").scrollTop = 0;
  if (!gavetaAberta) history.pushState({ gaveta: true }, "");
  gavetaAberta = true;
  if (aoAbrir) aoAbrir($("#gaveta"));
}
function fecharGaveta(viaVoltar = false) {
  if (!gavetaAberta) return;
  gavetaAberta = false;
  $("#veu").hidden = true;
  $("#gaveta").hidden = true;
  $("#gaveta-conteudo").innerHTML = "";
  if (!viaVoltar) history.back();
}
window.addEventListener("popstate", () => { if (gavetaAberta) fecharGaveta(true); });

// ---------- escolher cliente ----------
function abrirEscolhaCliente() {
  abrirGaveta(`
    <h3>Escolha o cliente</h3>
    <div class="busca-wrap"><input id="busca-cliente" type="search" placeholder="Digite para buscar..." autocomplete="off" enterkeyhint="search"></div>
    <div class="lista-escolha" id="lista-clientes"></div>
  `, (g) => {
    const inp = g.querySelector("#busca-cliente");
    const desenhar = () => {
      const termo = sem_acento(inp.value.trim());
      const abertos = new Set(comandas.map((c) => c.cliente));
      const lista = dados.clientes.filter((c) => !termo || sem_acento(c).includes(termo));
      // quem tem comanda aberta aparece primeiro
      lista.sort((a, b) => (abertos.has(b) - abertos.has(a)) || a.localeCompare(b, "pt-BR"));
      const exato = dados.clientes.some((c) => sem_acento(c) === termo);
      g.querySelector("#lista-clientes").innerHTML =
        (termo && !exato ? `<button class="opcao novo" data-novo="1">➕ Cadastrar “${esc(inp.value.trim())}”</button>` : "") +
        lista.map((c) => `<button class="opcao" data-cli="${esc(c)}"><span>${esc(c)}</span>${abertos.has(c) ? `<span class="tag">COMANDA ABERTA</span>` : ""}</button>`).join("") +
        (!lista.length && !termo ? `<div class="vazio-msg">Nenhum cliente cadastrado.</div>` : "");
    };
    inp.addEventListener("input", desenhar);
    g.querySelector("#lista-clientes").addEventListener("click", (ev) => {
      const b = ev.target.closest("button");
      if (!b) return;
      if (b.dataset.novo) return abrirNovoCliente(inp.value.trim());
      // se o cliente anterior tinha comanda (data/missão vieram dela), volta ao padrão
      if (comandaDoCliente(lanc.cliente) && !comandaDoCliente(b.dataset.cli)) {
        $("#lanc-data").value = hojeISO();
        $("#lanc-missao").value = dados.missoes.length === 1 ? dados.missoes[0] : "";
      }
      lanc.cliente = b.dataset.cli;
      fecharGaveta();
      renderLancar();
    });
    desenhar();
  });
}

function abrirNovoCliente(nomeInicial) {
  $("#gaveta-conteudo").innerHTML = `
    <h3>Novo cliente</h3>
    <label class="campo"><span>Nome</span><input id="nc-nome" type="text" autocomplete="off" value="${esc(nomeInicial)}"></label>
    <label class="campo"><span>Telefone/WhatsApp (opcional)</span><input id="nc-tel" type="tel" inputmode="tel" autocomplete="off" placeholder="43 99999-9999"></label>
    <div class="acoes">
      <button class="btn btn-secundario" id="nc-cancelar">Voltar</button>
      <button class="btn btn-primario" id="nc-salvar">Cadastrar</button>
    </div>`;
  $("#nc-cancelar").onclick = () => fecharGaveta();
  $("#nc-salvar").onclick = async () => {
    carregando(true);
    try {
      const r = await rpc("mob_novo_cliente", { p_token: sessao.token, p_nome: $("#nc-nome").value, p_telefone: $("#nc-tel").value });
      await recarregarCadastros();
      lanc.cliente = r.nome;
      fecharGaveta();
      renderLancar();
      toast(`Cliente ${r.nome} cadastrado.`, "ok");
    } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
  };
}

// ---------- editar item do carrinho ----------
function abrirEditarItem(idx) {
  const i = lanc.carrinho[idx];
  const admin = dados.admin;
  abrirGaveta(`
    <h3>${esc(i.produto)}</h3>
    <div class="linha-2">
      <label class="campo"><span>Preço unit. (R$)${admin ? "" : " 🔒"}</span>
        <input id="ei-preco" type="text" inputmode="decimal" value="${Number(i.preco_unitario).toFixed(2).replace(".", ",")}" ${admin ? "" : "disabled"}></label>
      <label class="campo"><span>Valor extra (R$)</span>
        <input id="ei-extra" type="text" inputmode="decimal" placeholder="0,00" value="${Number(i.preco_extra) ? Number(i.preco_extra).toFixed(2).replace(".", ",") : ""}"></label>
    </div>
    ${admin ? "" : `<p class="dica">Preço travado. Só administradores alteram. Use “Valor extra” para bacon, borda etc.</p>`}
    <label class="campo"><span>Obs. do item</span><input id="ei-obs" type="text" autocomplete="off" placeholder="Ex.: com bacon, sem cebola..." value="${esc(i.obs_item)}"></label>
    <div class="acoes">
      <button class="btn btn-perigo" id="ei-remover">Remover</button>
      <button class="btn btn-primario" id="ei-ok">Salvar</button>
    </div>`, (g) => {
      g.querySelectorAll("input").forEach((el) => el.addEventListener("focus", () => setTimeout(() => el.scrollIntoView({ block: "center", behavior: "smooth" }), 250)));
      g.querySelector("#ei-remover").onclick = () => { lanc.carrinho.splice(idx, 1); fecharGaveta(); renderLancar(); };
      g.querySelector("#ei-ok").onclick = () => {
        if (admin) i.preco_unitario = lerValor(g.querySelector("#ei-preco").value);
        i.preco_extra = Math.max(0, lerValor(g.querySelector("#ei-extra").value));
        i.obs_item = g.querySelector("#ei-obs").value.trim();
        fecharGaveta();
        renderLancar();
      };
    });
}

// ---------- fechar comanda / pagar ----------
// origem: { tipo: "lancar" } ou { tipo: "comanda", comanda }
function abrirPagamento(origem) {
  const ca = origem.tipo === "comanda" ? origem.comanda : comandaDoCliente(lanc.cliente);
  const total = origem.tipo === "comanda" ? Number(ca.total) : arred(totalCarrinho() + (ca ? Number(ca.total) : 0));
  const cliente = origem.tipo === "comanda" ? ca.cliente : lanc.cliente;
  if (!cliente) return toast("Escolha o cliente.", "erro");
  if (origem.tipo === "lancar" && !ca && !$("#lanc-missao").value) return toast("Escolha a missão.", "erro");

  const st = { situacao: "pago", forma: null };
  abrirGaveta(`
    <h3>Fechar comanda · ${esc(cliente)}</h3>
    <div class="total-gaveta"><span>Total</span><strong>${fmtMoeda(total)}</strong></div>
    <div class="campo"><span>Situação do pagamento</span></div>
    <div class="segmentos" id="pg-sit">
      <button data-s="pago" class="sel">✅ Pago</button>
      <button data-s="pendente">⏳ Pendente</button>
      <button data-s="parcial">💸 Parcial</button>
    </div>
    <div id="pg-bloco-forma">
      <div class="campo"><span>Forma de pagamento</span></div>
      <div class="chips" id="pg-formas">${dados.formas.map((f) => `<button data-f="${esc(f)}">${esc(f)}</button>`).join("")}</div>
    </div>
    <label class="campo" id="pg-bloco-parcial" hidden><span>Valor pago agora (R$)</span>
      <input id="pg-valor" type="text" inputmode="decimal" placeholder="0,00" autocomplete="off"></label>
    <p class="dica" id="pg-falta" hidden></p>
    ${origem.tipo === "comanda" ? `<label class="campo"><span>Observação (opcional)</span><input id="pg-obs" type="text" autocomplete="off" placeholder="Ex.: pagar na sexta..."></label>` : ""}
    <div class="acoes">
      <button class="btn btn-secundario" id="pg-voltar">Voltar</button>
      <button class="btn btn-primario" id="pg-confirmar">Confirmar</button>
    </div>`, (g) => {
      const atualizar = () => {
        g.querySelectorAll("#pg-sit button").forEach((b) => b.classList.toggle("sel", b.dataset.s === st.situacao));
        g.querySelectorAll("#pg-formas button").forEach((b) => b.classList.toggle("sel", b.dataset.f === st.forma));
        g.querySelector("#pg-bloco-forma").hidden = st.situacao === "pendente";
        g.querySelector("#pg-bloco-parcial").hidden = st.situacao !== "parcial";
        const falta = g.querySelector("#pg-falta");
        if (st.situacao === "parcial") {
          const pago = lerValor(g.querySelector("#pg-valor").value);
          falta.hidden = false;
          falta.innerHTML = `Ficará devendo <strong>${fmtMoeda(Math.max(0, total - pago))}</strong>.`;
        } else if (st.situacao === "pendente") {
          falta.hidden = false;
          falta.textContent = "A forma de pagamento é escolhida depois, na hora de receber.";
        } else falta.hidden = true;
      };
      g.querySelector("#pg-sit").onclick = (ev) => { const b = ev.target.closest("button"); if (b) { st.situacao = b.dataset.s; atualizar(); } };
      g.querySelector("#pg-formas").onclick = (ev) => { const b = ev.target.closest("button"); if (b) { st.forma = b.dataset.f; atualizar(); } };
      g.querySelector("#pg-valor").addEventListener("input", atualizar);
      g.querySelector("#pg-valor").addEventListener("focus", (e) => setTimeout(() => e.target.scrollIntoView({ block: "center", behavior: "smooth" }), 250));
      g.querySelector("#pg-voltar").onclick = () => fecharGaveta();
      g.querySelector("#pg-confirmar").onclick = async () => {
        const valor = st.situacao === "parcial" ? lerValor(g.querySelector("#pg-valor").value) : 0;
        if (st.situacao !== "pendente" && !st.forma) return toast("Escolha a forma de pagamento.", "erro");
        if (st.situacao === "parcial" && (valor <= 0 || valor > total)) return toast("Informe um valor pago maior que zero e até o total.", "erro");
        const fechar = { situacao: st.situacao, valor_pago: valor, forma: st.situacao === "pendente" ? null : st.forma };
        carregando(true);
        try {
          if (origem.tipo === "lancar") {
            await rpc("mob_lancar", {
              p_token: sessao.token, p_cliente: lanc.cliente, p_missao: $("#lanc-missao").value,
              p_data: $("#lanc-data").value, p_observacao: $("#lanc-obs").value, p_itens: itensParaEnvio(), p_fechar: fechar,
            });
          } else {
            await rpc("mob_fechar_comanda", {
              p_token: sessao.token, p_pedido_id: ca.pedido_id, p_situacao: fechar.situacao,
              p_valor_pago: fechar.valor_pago, p_forma: fechar.forma, p_observacao: g.querySelector("#pg-obs").value,
            });
          }
          fecharGaveta();
          await atualizarComandas();
          if (origem.tipo === "lancar") limparLancamento(); else renderComandas();
          toast(`Comanda de ${cliente} fechada · ${fmtMoeda(total)} 🎉`, "ok");
        } catch (e) {
          toast(e.message, "erro");
        } finally {
          carregando(false);
        }
      };
      atualizar();
    });
}

// ============================================================
// Tela COMANDAS
// ============================================================
function renderComandas() {
  const el = $("#lista-comandas");
  if (!comandas.length) {
    el.innerHTML = `<div class="vazio-msg">Nenhuma comanda aberta no momento. 👍</div>`;
    return;
  }
  el.innerHTML = comandas.map((c, idx) => `
    <button class="comanda" data-comanda="${idx}">
      <div class="comanda-topo"><span class="comanda-cli">${esc(c.cliente)}</span><span class="comanda-total">${fmtMoeda(c.total)}</span></div>
      <div class="comanda-meta">${esc(c.evento || "")} · ${fmtData(c.data_lancamento)} · aberta ${tempoDesde(c.aberta_desde)}</div>
      <div class="comanda-itens">${c.itens.map((i) => `${Number(i.quantidade)}x ${esc(i.produto)}`).join(", ")}</div>
    </button>`).join("");
}

function abrirComanda(c) {
  const admin = dados.admin;
  abrirGaveta(`
    <h3>${esc(c.cliente)}</h3>
    <p class="dica" style="margin-top:-8px">${esc(c.evento || "")} · ${fmtData(c.data_lancamento)} · aberta ${tempoDesde(c.aberta_desde)}</p>
    ${c.itens.map((i) => `
      <div class="linha-item-gaveta">
        <div><strong>${Number(i.quantidade)}x ${esc(i.produto)}</strong>
          ${i.obs_item ? `<div class="item-obs">${esc(i.obs_item)}</div>` : ""}
          <div class="item-det">${fmtMoeda(i.preco_unitario)} · por ${esc(i.lancado_por || "-")}</div></div>
        <div style="display:flex;align-items:center;gap:8px"><strong>${fmtMoeda(i.total)}</strong>
          ${admin ? `<button class="lixo-btn" data-rm="${i.id}" aria-label="Remover item">🗑</button>` : ""}</div>
      </div>`).join("")}
    <div class="total-gaveta" style="margin-top:12px"><span>Total</span><strong>${fmtMoeda(c.total)}</strong></div>
    <div class="acoes">
      <button class="btn btn-secundario" id="cm-add">➕ Adicionar itens</button>
      <button class="btn btn-primario" id="cm-fechar">Fechar e pagar</button>
    </div>
    ${admin ? `<button class="btn btn-texto btn-bloco" id="cm-cancelar">Cancelar comanda inteira</button>` : ""}
  `, (g) => {
    g.querySelector("#cm-add").onclick = () => {
      if (lanc.carrinho.length && lanc.cliente !== c.cliente) return toast("Há itens novos de outro cliente na tela Lançar.", "erro");
      lanc.cliente = c.cliente;
      fecharGaveta();
      irPara("lancar");
    };
    g.querySelector("#cm-fechar").onclick = () => abrirPagamento({ tipo: "comanda", comanda: c });
    g.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = async () => {
      if (b.dataset.confirmar !== "1") { b.dataset.confirmar = "1"; b.textContent = "OK?"; return; }
      carregando(true);
      try {
        await rpc("mob_remover_item", { p_token: sessao.token, p_item_id: Number(b.dataset.rm) });
        await atualizarComandas();
        const nova = comandas.find((x) => x.pedido_id === c.pedido_id);
        renderComandas();
        if (nova) abrirComanda(nova); else fecharGaveta();
        toast("Item removido.", "ok");
      } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
    }));
    const cancelar = g.querySelector("#cm-cancelar");
    if (cancelar) cancelar.onclick = async () => {
      if (cancelar.dataset.confirmar !== "1") {
        cancelar.dataset.confirmar = "1";
        cancelar.textContent = "Toque de novo para CONFIRMAR o cancelamento";
        cancelar.style.color = "var(--vermelho)";
        return;
      }
      carregando(true);
      try {
        await rpc("mob_cancelar_comanda", { p_token: sessao.token, p_pedido_id: c.pedido_id });
        fecharGaveta();
        await atualizarComandas();
        renderComandas();
        toast("Comanda cancelada.", "ok");
      } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
    };
  });
}

// ============================================================
// Tela HOJE
// ============================================================
async function carregarResumo() {
  const el = $("#resumo-dia");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  try {
    const r = await rpc("mob_resumo_dia", { p_token: sessao.token, p_data: $("#hoje-data").value || hojeISO() });
    const sit = (p) => (Number(p.pago) >= Number(p.total) - 0.005 ? ["pago", "Pago"] : Number(p.pago) > 0 ? ["parcial", "Parcial"] : ["pendente", "Pendente"]);
    el.innerHTML = `
      <div class="kpis">
        <div class="kpi destaque"><small>Total vendido · ${r.n_pedidos} pedido(s)</small><strong>${fmtMoeda(r.total)}</strong></div>
        <div class="kpi receb"><small>Recebido</small><strong>${fmtMoeda(r.recebido)}</strong></div>
        <div class="kpi pend"><small>Pendente</small><strong>${fmtMoeda(r.pendente)}</strong></div>
      </div>
      ${r.por_forma.length ? `<div class="cartao"><ul class="formas">${r.por_forma.map((f) => `<li><span>${esc(f.forma)}</span><strong>${fmtMoeda(f.valor)}</strong></li>`).join("")}</ul></div>` : ""}
      <h2 class="titulo-secao">Pedidos fechados</h2>
      ${r.pedidos.length ? r.pedidos.map((p) => {
        const [cls, rot] = sit(p);
        return `<div class="ped">
          <div class="ped-topo"><span>${esc(p.cliente)}</span><span>${fmtMoeda(p.total)}</span></div>
          <div class="ped-meta"><span class="etiqueta ${cls}">${rot}</span> ${esc(p.forma || "")} · ${esc(p.evento || "")} · por ${esc(p.lancado_por || "-")}</div>
          <div class="ped-itens">${esc(p.itens)}</div>
        </div>`;
      }).join("") : `<div class="vazio-msg">Nenhum pedido fechado nesse dia.</div>`}
      ${comandas.length ? `<p class="dica">Comandas ainda abertas não entram neste resumo (veja a aba Comandas).</p>` : ""}`;
  } catch (e) {
    el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`;
  }
}

// ============================================================
// Tela CONFIGURAÇÕES (só admin)
// ============================================================
const cfg = { aba: "produtos", dados: null };
const CFG_NOVO = { produtos: "➕ Novo produto", missoes: "➕ Nova missão", clientes: "➕ Novo cliente" };

async function carregarConfig() {
  $("#cfg-lista").innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  try {
    cfg.dados = await rpc("mob_config_listar", { p_token: sessao.token });
    renderConfig();
  } catch (e) {
    $("#cfg-lista").innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`;
  }
}

function renderConfig() {
  document.querySelectorAll("#cfg-abas button").forEach((b) => b.classList.toggle("sel", b.dataset.cfg === cfg.aba));
  $("#cfg-novo").textContent = CFG_NOVO[cfg.aba];
  if (!cfg.dados) return;
  const termo = sem_acento($("#cfg-busca").value.trim());
  // ativos primeiro, depois inativos
  const lista = cfg.dados[cfg.aba]
    .filter((r) => !termo || sem_acento(r.nome).includes(termo))
    .sort((a, b) => (b.ativo - a.ativo) || a.nome.localeCompare(b.nome, "pt-BR"));
  $("#cfg-lista").innerHTML = lista.length
    ? lista.map((r) => `
      <button class="cfg-item ${r.ativo ? "" : "inativo"}" data-id="${r.id}">
        <span>${esc(r.nome)}${cfg.aba === "clientes" && r.telefone ? `<small>${esc(r.telefone)}</small>` : ""}</span>
        ${!r.ativo ? `<span class="off">INATIVO</span>` : cfg.aba === "produtos" ? `<span class="preco">${fmtMoeda(r.preco)}</span>` : ""}
      </button>`).join("")
    : `<div class="vazio-msg">Nada encontrado.</div>`;
}

function abrirEdicaoCfg(reg) {
  const novo = !reg;
  reg = reg || { id: null, nome: "", preco: "", telefone: "", ativo: true };
  const titulos = { produtos: "produto", missoes: "missão", clientes: "cliente" };
  abrirGaveta(`
    <h3>${novo ? "Novo" : "Editar"} ${titulos[cfg.aba]}</h3>
    <label class="campo"><span>Nome</span><input id="cf-nome" type="text" autocomplete="off" value="${esc(reg.nome)}"></label>
    ${cfg.aba === "produtos" ? `<label class="campo"><span>Preço (R$)</span><input id="cf-preco" type="text" inputmode="decimal" autocomplete="off" placeholder="0,00"
        value="${reg.preco === "" ? "" : Number(reg.preco).toFixed(2).replace(".", ",")}"></label>` : ""}
    ${cfg.aba === "clientes" ? `<label class="campo"><span>Telefone/WhatsApp</span><input id="cf-tel" type="tel" inputmode="tel" autocomplete="off" placeholder="43 99999-9999" value="${esc(reg.telefone || "")}"></label>` : ""}
    <label class="chave"><span>Ativo (aparece para lançar)</span><input id="cf-ativo" type="checkbox" ${reg.ativo ? "checked" : ""}></label>
    ${!novo && cfg.aba !== "clientes" ? `<p class="dica">Mudar o nome não altera os lançamentos antigos, que continuam com o nome anterior.</p>` : ""}
    <div class="acoes">
      <button class="btn btn-secundario" id="cf-voltar">Voltar</button>
      <button class="btn btn-primario" id="cf-salvar">Salvar</button>
    </div>`, (g) => {
      g.querySelectorAll("input[type=text],input[type=tel]").forEach((el) => el.addEventListener("focus", () => setTimeout(() => el.scrollIntoView({ block: "center", behavior: "smooth" }), 250)));
      g.querySelector("#cf-voltar").onclick = () => fecharGaveta();
      g.querySelector("#cf-salvar").onclick = async () => {
        const base = { p_token: sessao.token, p_id: reg.id, p_nome: g.querySelector("#cf-nome").value, p_ativo: g.querySelector("#cf-ativo").checked };
        const chamadas = {
          produtos: ["mob_salvar_produto", { ...base, p_preco: lerValor(g.querySelector("#cf-preco")?.value) }],
          missoes: ["mob_salvar_missao", base],
          clientes: ["mob_salvar_cliente", { ...base, p_telefone: g.querySelector("#cf-tel")?.value || "" }],
        };
        const [fn, args] = chamadas[cfg.aba];
        if (cfg.aba === "produtos" && !String(g.querySelector("#cf-preco").value).trim()) return toast("Informe o preço.", "erro");
        carregando(true);
        try {
          await rpc(fn, args);
          fecharGaveta();
          await Promise.all([carregarConfig(), recarregarCadastros()]);
          toast("Salvo.", "ok");
        } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
      };
    });
}

// ============================================================
// Eventos
// ============================================================
$("#cfg-abas").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { cfg.aba = b.dataset.cfg; $("#cfg-busca").value = ""; renderConfig(); } });
$("#cfg-busca").addEventListener("input", renderConfig);
$("#cfg-novo").addEventListener("click", () => abrirEdicaoCfg(null));
$("#cfg-lista").addEventListener("click", (e) => {
  const b = e.target.closest("[data-id]");
  if (b) abrirEdicaoCfg(cfg.dados[cfg.aba].find((r) => String(r.id) === b.dataset.id));
});
$("#btn-entrar").addEventListener("click", entrar);
$("#login-senha").addEventListener("keydown", (e) => { if (e.key === "Enter") entrar(); });
$("#btn-sair").addEventListener("click", () => sair());
document.querySelectorAll(".aba").forEach((b) => b.addEventListener("click", () => irPara(b.dataset.pg)));
$("#veu").addEventListener("click", () => fecharGaveta());

$("#btn-cliente").addEventListener("click", abrirEscolhaCliente);
$("#busca-produto").addEventListener("input", renderProdutos);
$("#grade-produtos").addEventListener("click", (e) => { const b = e.target.closest("[data-produto]"); if (b) adicionarProduto(b.dataset.produto); });
$("#lista-carrinho").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.mais) { lanc.carrinho[+b.dataset.mais].quantidade++; renderLancar(); }
  else if (b.dataset.menos) {
    const i = +b.dataset.menos;
    if (lanc.carrinho[i].quantidade > 1) lanc.carrinho[i].quantidade--; else lanc.carrinho.splice(i, 1);
    renderLancar();
  } else if (b.dataset.editar) abrirEditarItem(+b.dataset.editar);
});
$("#btn-limpar").addEventListener("click", (e) => {
  const b = e.currentTarget;
  if (!lanc.carrinho.length) return;
  if (b.dataset.confirmar !== "1") {
    b.dataset.confirmar = "1"; b.textContent = "Toque de novo para confirmar";
    setTimeout(() => { b.dataset.confirmar = ""; b.textContent = "Limpar itens novos"; }, 3000);
    return;
  }
  b.dataset.confirmar = ""; b.textContent = "Limpar itens novos";
  lanc.carrinho = [];
  renderLancar();
});
$("#lanc-obs").addEventListener("focus", (e) => setTimeout(() => e.target.scrollIntoView({ block: "center", behavior: "smooth" }), 300));
$("#btn-guardar").addEventListener("click", guardarNaComanda);
$("#btn-fechar").addEventListener("click", () => abrirPagamento({ tipo: "lancar" }));
$("#lista-comandas").addEventListener("click", (e) => { const b = e.target.closest("[data-comanda]"); if (b) abrirComanda(comandas[+b.dataset.comanda]); });
$("#hoje-data").addEventListener("change", carregarResumo);

// ao voltar para o app (estava em segundo plano), atualiza as comandas
document.addEventListener("visibilitychange", async () => {
  if (document.visibilityState === "visible" && sessao && dados) {
    await atualizarComandas();
    if (pagina === "comandas") renderComandas();
    if (pagina === "lancar") renderLancar();
  }
});

// ---------- campos de data sempre em dd/mm/aaaa ----------
// O campo de data nativo mostra o formato do idioma do navegador (num
// computador em inglês aparece mm/dd/aaaa). Aqui todo <input type="date">
// do app ganha uma "capa" com a data em português; o campo de verdade fica
// por baixo (o resto do código continua lendo .value normalmente) e o toque
// abre o calendário — sem teclado no celular.
const DESCRITOR_VALOR = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
function campoDataBR(inp) {
  if (inp.dataset.br) return;
  inp.dataset.br = "1";
  const capa = document.createElement("div");
  capa.className = "data-br";
  inp.parentNode.insertBefore(capa, inp);
  const mostra = document.createElement("button");
  mostra.type = "button";
  mostra.className = "data-br-mostra";
  capa.append(inp, mostra);
  inp.tabIndex = -1;
  const desenhar = () => {
    const v = DESCRITOR_VALOR.get.call(inp);
    mostra.innerHTML = `<span class="${v ? "" : "vazio"}">${v ? fmtData(v) : "dd/mm/aaaa"}</span><span class="data-br-ic" aria-hidden="true">📅</span>`;
    mostra.disabled = inp.disabled;
  };
  // valor trocado pelo código (ex.: data da comanda) também atualiza a capa
  Object.defineProperty(inp, "value", {
    get: () => DESCRITOR_VALOR.get.call(inp),
    set: (v) => { DESCRITOR_VALOR.set.call(inp, v); desenhar(); },
  });
  new MutationObserver(desenhar).observe(inp, { attributes: true, attributeFilter: ["disabled"] });
  inp.addEventListener("change", desenhar);
  inp.addEventListener("input", desenhar);
  mostra.addEventListener("click", () => {
    if (inp.disabled) return;
    try { inp.showPicker(); } catch { inp.focus(); inp.click(); }
  });
  desenhar();
}
const varrerDatas = (raiz) => raiz.querySelectorAll?.('input[type="date"]').forEach(campoDataBR);
varrerDatas(document);
new MutationObserver((muds) => muds.forEach((m) => m.addedNodes.forEach((n) => {
  if (n.nodeType !== 1) return;
  if (n.matches('input[type="date"]')) campoDataBR(n); else varrerDatas(n);
}))).observe(document.body, { childList: true, subtree: true });

// ---------- service worker (permite instalar como app) ----------
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}

// ---------- começa ----------
if (sessao) iniciarApp(); else mostrarLogin();
