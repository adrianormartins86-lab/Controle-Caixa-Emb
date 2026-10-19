// ============================================================
// Caixa EMB — Abatimento/Reembolso, Despesas, Mensagem de cobrança e Usuários
// (só Administrador e Meiry; Usuários só para o perfil admin)
// Usa as utilidades do app.js e do admin.js.
// Funções do banco: sql_mobile/04_funcoes_fase3.sql
// ============================================================
"use strict";

const campoValor = (id, rotulo, valor = "") =>
  `<label class="campo"><span>${rotulo}</span><input id="${id}" type="text" inputmode="decimal" autocomplete="off" placeholder="0,00" value="${valor}"></label>`;

// gaveta de exclusão com motivo obrigatório (abatimento e despesa)
function abrirExclusaoComMotivo({ titulo, resumo, aoConfirmar }) {
  abrirGaveta(`
    <h3>${esc(titulo)}</h3>
    <div class="aviso-perigo">${resumo}</div>
    <label class="campo"><span>Motivo da exclusão (obrigatório)</span><input id="xm-motivo" type="text" autocomplete="off"></label>
    <p class="dica">Some da lista e dos totais, mas fica guardado no banco com o motivo e quem excluiu.</p>
    <div class="acoes">
      <button class="btn btn-secundario" id="xm-voltar">Voltar</button>
      <button class="btn btn-perigo" id="xm-ok">Confirmar exclusão</button>
    </div>`, (g) => {
    focoNoCentro(g);
    g.querySelector("#xm-voltar").onclick = () => fecharGaveta();
    g.querySelector("#xm-ok").onclick = async () => {
      const motivo = g.querySelector("#xm-motivo").value.trim();
      if (!motivo) return toast("Informe o motivo da exclusão.", "erro");
      carregando(true);
      try { await aoConfirmar(motivo); fecharGaveta(); }
      catch (e) { toast(e.message, "erro"); }
      finally { carregando(false); }
    };
  });
}

// ============================================================
// ABATIMENTO / REEMBOLSO
// ============================================================
const ab = { cliente: "", dados: null };

async function carregarAbatimentos() {
  const el = $("#abatimentos-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  try {
    ab.dados = await rpc("mob_abatimentos", { p_token: sessao.token });
    renderAbatimentos();
  } catch (e) { el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`; }
}

function renderAbatimentos() {
  const el = $("#abatimentos-conteudo");
  const d = ab.dados;
  el.innerHTML = `
    <p class="dica" style="margin-top:0">Use quando o cliente amortizar parte do que deve com produto, serviço ou outra compensação, sem passar pelo caixa. O valor abate do pendente dele nos relatórios e na cobrança.</p>
    <div class="cartao">
      <button class="seletor" id="ab-cliente"><span class="seletor-rotulo">Cliente</span>
        <span class="seletor-valor ${ab.cliente ? "" : "vazio"}">${esc(ab.cliente || "Escolha...")}</span><span class="seta">›</span></button>
      <div class="linha-2">
        <label class="campo"><span>Data</span><input id="ab-data" type="date" value="${hojeISO()}"></label>
        ${campoValor("ab-valor", "Valor (R$)")}
      </div>
      <label class="campo"><span>Observação (opcional)</span><input id="ab-obs" type="text" autocomplete="off" placeholder="Ex.: pagou com 2 marmitex"></label>
      <button class="btn btn-primario btn-bloco" id="ab-salvar">💾 Registrar abatimento</button>
    </div>
    <h2 class="titulo-secao">Abatimentos registrados · ${fmtMoeda(d.total)}</h2>
    ${d.lista.length ? `<div class="cfg-lista" style="margin-top:0">${d.lista.map((a) => `
      <button class="cfg-item" data-ab="${a.id}">
        <span>${esc(a.cliente)}<small>${fmtData(a.data)} · por ${esc(a.lancado_por || "-")}${a.observacao ? ` · ${esc(a.observacao)}` : ""}</small></span>
        <span class="preco">${fmtMoeda(a.valor)}</span>
      </button>`).join("")}</div>
      <p class="dica">Toque num abatimento para excluir (correção).</p>`
    : `<div class="vazio-msg">Nenhum abatimento registrado ainda.</div>`}`;

  $("#ab-valor").addEventListener("focus", (e) => setTimeout(() => e.target.scrollIntoView({ block: "center", behavior: "smooth" }), 250));
  $("#ab-obs").addEventListener("focus", (e) => setTimeout(() => e.target.scrollIntoView({ block: "center", behavior: "smooth" }), 250));
  $("#ab-cliente").onclick = async () => {
    try { await carregarListasAdmin(); } catch (e) { return toast(e.message, "erro"); }
    abrirEscolha({ titulo: "Cliente do abatimento", opcoes: listasAdmin.clientes, comTodos: false,
      aoEscolher: (v) => { ab.cliente = v; const s = $("#ab-cliente .seletor-valor"); s.textContent = v; s.classList.remove("vazio"); } });
  };
  $("#ab-salvar").onclick = async () => {
    const valor = arred(lerValor($("#ab-valor").value));
    if (!ab.cliente) return toast("Escolha o cliente.", "erro");
    if (valor <= 0) return toast("Informe um valor maior que zero.", "erro");
    carregando(true);
    try {
      await rpc("mob_salvar_abatimento", { p_token: sessao.token, p_data: $("#ab-data").value, p_cliente: ab.cliente, p_valor: valor, p_observacao: $("#ab-obs").value });
      toast(`Abatimento de ${fmtMoeda(valor)} registrado para ${ab.cliente}.`, "ok");
      ab.cliente = "";
      await carregarAbatimentos();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
  };
}

$("#abatimentos-conteudo").addEventListener("click", (e) => {
  const b = e.target.closest("[data-ab]");
  if (!b) return;
  const a = ab.dados.lista.find((x) => String(x.id) === b.dataset.ab);
  abrirExclusaoComMotivo({
    titulo: "Excluir abatimento",
    resumo: `<strong>${esc(a.cliente)}</strong> · ${fmtData(a.data)} · ${fmtMoeda(a.valor)}${a.observacao ? `<br><small>${esc(a.observacao)}</small>` : ""}`,
    aoConfirmar: async (motivo) => {
      await rpc("mob_excluir_abatimento", { p_token: sessao.token, p_id: a.id, p_motivo: motivo });
      toast("Abatimento excluído.", "ok");
      carregarAbatimentos();
    },
  });
});

// ============================================================
// DESPESAS
// ============================================================
const desp = { linhas: [{ descricao: "", valor: "" }, { descricao: "", valor: "" }], dia: null, dados: null };

async function carregarDespesas() {
  const el = $("#despesas-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  try {
    desp.dados = await rpc("mob_despesas", { p_token: sessao.token });
    renderDespesas();
  } catch (e) { el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`; }
}

const linhasValidas = () => desp.linhas.filter((l) => l.descricao.trim() && arred(lerValor(l.valor)) > 0);
const totalDespesasNovas = () => arred(linhasValidas().reduce((s, l) => s + arred(lerValor(l.valor)), 0));

function renderDespesas() {
  const el = $("#despesas-conteudo");
  const d = desp.dados;
  el.innerHTML = `
    <p class="dica" style="margin-top:0">Escolha o dia e registre os itens de despesa. Pode adicionar quantas linhas precisar antes de salvar.</p>
    <div class="cartao">
      <label class="campo"><span>Dia das despesas</span><input id="dp-dia" type="date" value="${desp.dia || hojeISO()}"></label>
      <div id="dp-linhas"></div>
      <button class="btn btn-texto" id="dp-mais">➕ Adicionar linha</button>
      <div class="total-gaveta" style="margin:8px 0 12px"><span>Total a lançar</span><strong id="dp-total">${fmtMoeda(totalDespesasNovas())}</strong></div>
      <button class="btn btn-primario btn-bloco" id="dp-salvar">💾 Registrar despesas do dia</button>
    </div>
    <h2 class="titulo-secao">Despesas registradas · ${fmtMoeda(d.total)}</h2>
    ${d.lista.length ? `<div class="cfg-lista" style="margin-top:0">${d.lista.map((x) => `
      <button class="cfg-item" data-desp="${x.id}">
        <span>${esc(x.descricao)}<small>${fmtData(x.data)} · por ${esc(x.lancado_por || "-")}</small></span>
        <span class="preco">${fmtMoeda(x.valor)}</span>
      </button>`).join("")}</div>
      <p class="dica">Toque numa despesa para excluir (correção).</p>`
    : `<div class="vazio-msg">Nenhuma despesa registrada ainda.</div>`}`;
  desenharLinhasDespesa();
  $("#dp-dia").addEventListener("change", (e) => (desp.dia = e.target.value));
  $("#dp-mais").onclick = () => { desp.linhas.push({ descricao: "", valor: "" }); desenharLinhasDespesa(true); };
  $("#dp-salvar").onclick = async () => {
    const itens = linhasValidas().map((l) => ({ descricao: l.descricao.trim(), valor: arred(lerValor(l.valor)) }));
    if (!itens.length) return toast("Adicione ao menos uma linha com descrição e valor.", "erro");
    carregando(true);
    try {
      const r = await rpc("mob_salvar_despesas", { p_token: sessao.token, p_data: $("#dp-dia").value, p_itens: itens });
      toast(`${r.n} despesa(s) registrada(s) em ${fmtData($("#dp-dia").value)} · ${fmtMoeda(r.total)}`, "ok");
      desp.linhas = [{ descricao: "", valor: "" }, { descricao: "", valor: "" }];
      await carregarDespesas();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
  };
}

function desenharLinhasDespesa(focarUltima = false) {
  const box = $("#dp-linhas");
  box.innerHTML = desp.linhas.map((l, i) => `
    <div class="linha-despesa">
      <input type="text" data-i="${i}" data-c="descricao" placeholder="Descrição" autocomplete="off" value="${esc(l.descricao)}">
      <input type="text" data-i="${i}" data-c="valor" inputmode="decimal" placeholder="0,00" autocomplete="off" value="${esc(l.valor)}">
      <button class="lixo-btn" data-rm="${i}" aria-label="Remover linha" ${desp.linhas.length === 1 ? "disabled" : ""}>🗑</button>
    </div>`).join("");
  box.querySelectorAll("input").forEach((inp) => {
    inp.addEventListener("input", () => { desp.linhas[+inp.dataset.i][inp.dataset.c] = inp.value; $("#dp-total").textContent = fmtMoeda(totalDespesasNovas()); });
    inp.addEventListener("focus", () => setTimeout(() => inp.scrollIntoView({ block: "center", behavior: "smooth" }), 250));
  });
  box.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => {
    desp.linhas.splice(+b.dataset.rm, 1);
    desenharLinhasDespesa();
    $("#dp-total").textContent = fmtMoeda(totalDespesasNovas());
  }));
  if (focarUltima) box.querySelector(".linha-despesa:last-child input").focus();
}

$("#despesas-conteudo").addEventListener("click", (e) => {
  const b = e.target.closest("[data-desp]");
  if (!b) return;
  const x = desp.dados.lista.find((y) => String(y.id) === b.dataset.desp);
  abrirExclusaoComMotivo({
    titulo: "Excluir despesa",
    resumo: `<strong>${esc(x.descricao)}</strong> · ${fmtData(x.data)} · ${fmtMoeda(x.valor)}`,
    aoConfirmar: async (motivo) => {
      await rpc("mob_excluir_despesa", { p_token: sessao.token, p_id: x.id, p_motivo: motivo });
      toast("Despesa excluída.", "ok");
      carregarDespesas();
    },
  });
});

// ============================================================
// MENSAGEM DE COBRANÇA (chave Pix + textos de abertura e fecho)
// ============================================================
const MARCADORES = [["{cliente}", "nome do cliente"], ["{total}", "total em aberto"], ["{chave_pix}", "chave Pix"], ["{nome_pix}", "nome do recebedor"]];

async function carregarPix() {
  const el = $("#pix-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  let p;
  try { p = await rpc("mob_pix", { p_token: sessao.token }); }
  catch (e) { el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`; return; }
  el.innerHTML = `
    <div class="cartao">
      <label class="campo"><span>Chave Pix / número</span><input id="px-chave" type="text" autocomplete="off" value="${esc(p.chave || "")}"></label>
      <label class="campo"><span>Nome do recebedor</span><input id="px-nome" type="text" autocomplete="off" value="${esc(p.nome || "")}"></label>
    </div>
    <div class="cartao">
      <label class="campo"><span>Abertura (antes da lista do consumo)</span>
        <textarea id="px-abertura" rows="3">${esc(p.abertura || COB_ABERTURA_PADRAO)}</textarea></label>
      <button class="btn btn-texto" data-padrao="abertura">↺ Voltar ao texto padrão</button>
      <label class="campo" style="margin-top:6px"><span>Fecho (depois do total)</span>
        <textarea id="px-fecho" rows="4">${esc(p.fecho || COB_FECHO_PADRAO)}</textarea></label>
      <button class="btn btn-texto" data-padrao="fecho">↺ Voltar ao texto padrão</button>
      <div class="campo" style="margin:10px 0 6px"><span>Toque para inserir no texto (troca pelo valor real de cada cliente):</span></div>
      <div class="chips chips-marcador">${MARCADORES.map(([m, d]) => `<button data-m="${m}" title="${d}">${m}</button>`).join("")}</div>
      <p class="dica" style="margin-top:-6px">A lista do consumo e os totais entram sozinhos entre a abertura e o fecho. Sem chave Pix cadastrada, um fecho que usa {chave_pix} não entra na mensagem.</p>
      <button class="btn btn-primario btn-bloco" id="px-salvar">💾 Salvar</button>
    </div>
    <h2 class="titulo-secao">Prévia (cliente de exemplo)</h2>
    <div class="cartao previa-msg" id="px-previa"></div>`;

  let ultimoCampo = $("#px-fecho");
  const cfgAtual = () => ({
    pix_chave: $("#px-chave").value.trim(), pix_nome: $("#px-nome").value.trim(),
    cob_abertura: $("#px-abertura").value, cob_fecho: $("#px-fecho").value,
  });
  const exemplo = { cliente: "Maria", bruto: 25, abatido: 0, total: 25, itens: [
    { data: hojeISO(), produto: "Marmita", quantidade: 1, pendente: 18 },
    { data: hojeISO(), produto: "Refrigerante", quantidade: 1, pendente: 7 }] };
  const previa = () => {
    const c = cfgAtual();
    // campo apagado de propósito: mensagem fica sem aquele trecho
    if (!c.cob_abertura.trim()) c.cob_abertura = " ";
    if (!c.cob_fecho.trim()) c.cob_fecho = " ";
    $("#px-previa").textContent = montarMensagemCobranca(exemplo, c).trim();
  };
  ["#px-chave", "#px-nome", "#px-abertura", "#px-fecho"].forEach((s) => $(s).addEventListener("input", previa));
  ["#px-abertura", "#px-fecho"].forEach((s) => $(s).addEventListener("focus", (e) => (ultimoCampo = e.target)));
  el.querySelectorAll("textarea,input").forEach((x) => x.addEventListener("focus", () => setTimeout(() => x.scrollIntoView({ block: "center", behavior: "smooth" }), 250)));
  el.querySelector(".chips-marcador").addEventListener("click", (e) => {
    const b = e.target.closest("[data-m]");
    if (!b) return;
    const t = ultimoCampo, ini = t.selectionStart ?? t.value.length, fim = t.selectionEnd ?? t.value.length;
    t.value = t.value.slice(0, ini) + b.dataset.m + t.value.slice(fim);
    t.focus();
    t.setSelectionRange(ini + b.dataset.m.length, ini + b.dataset.m.length);
    previa();
  });
  el.querySelectorAll("[data-padrao]").forEach((b) => (b.onclick = () => {
    const alvo = b.dataset.padrao === "abertura" ? $("#px-abertura") : $("#px-fecho");
    alvo.value = b.dataset.padrao === "abertura" ? COB_ABERTURA_PADRAO : COB_FECHO_PADRAO;
    previa();
  }));
  previa();

  $("#px-salvar").onclick = async () => {
    const c = cfgAtual();
    // igual ao padrão: guarda vazio (se um dia o padrão mudar, acompanha)
    const ab = c.cob_abertura.trim() === COB_ABERTURA_PADRAO ? "" : (c.cob_abertura.trim() || " ");
    const fe = c.cob_fecho.trim() === COB_FECHO_PADRAO ? "" : (c.cob_fecho.trim() || " ");
    carregando(true);
    try {
      await rpc("mob_salvar_mensagem", { p_token: sessao.token, p_chave: c.pix_chave, p_nome: c.pix_nome, p_abertura: ab, p_fecho: fe });
      toast("Mensagem salva. Já vale para as próximas cobranças.", "ok");
    } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
  };
}

// ============================================================
// USUÁRIOS (só perfil admin)
// ============================================================
let usuarios = [];
const PERFIS = {
  operador: "Lança pedidos e comandas, cadastra clientes",
  gestor: "Tudo, menos gerenciar usuários",
  admin: "Tudo, inclusive usuários",
};

async function carregarUsuarios() {
  const el = $("#usuarios-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  try { usuarios = await rpc("mob_usuarios_listar", { p_token: sessao.token }); }
  catch (e) { el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`; return; }
  el.innerHTML = `
    <button class="btn btn-primario btn-bloco" id="us-novo">➕ Novo usuário</button>
    <div class="cfg-lista">${usuarios.map((u) => `
      <button class="cfg-item ${u.ativo ? "" : "inativo"}" data-us="${u.id}">
        <span>${esc(u.nome)}<small>${esc(u.perfil)}${u.nome === dados.usuario ? " · você" : ""}</small></span>
        ${u.ativo ? "" : `<span class="off">INATIVO</span>`}
      </button>`).join("")}</div>
    <p class="dica">Prefira inativar em vez de excluir: o "Lançado por" dos pedidos antigos continua fazendo sentido. Ao inativar ou trocar a senha, a pessoa é desconectada dos celulares.</p>`;
  $("#us-novo").onclick = () => abrirUsuario(null);
}

$("#usuarios-conteudo").addEventListener("click", (e) => {
  const b = e.target.closest("[data-us]");
  if (b) abrirUsuario(usuarios.find((u) => String(u.id) === b.dataset.us));
});

function abrirUsuario(u) {
  const novo = !u;
  const st = { perfil: u ? u.perfil : "operador" };
  abrirGaveta(`
    <h3>${novo ? "Novo usuário" : esc(u.nome)}</h3>
    ${novo ? `<label class="campo"><span>Nome</span><input id="us-nome" type="text" autocomplete="off"></label>` : ""}
    <div class="campo"><span>Perfil</span></div>
    <div class="segmentos" id="us-perfil">${Object.keys(PERFIS).map((p) => `<button data-p="${p}">${p}</button>`).join("")}</div>
    <p class="dica" id="us-perfil-desc" style="margin-top:-8px"></p>
    <label class="campo"><span>${novo ? "Senha inicial" : "Nova senha (deixe em branco para manter a atual)"}</span>
      <!-- type="text" + máscara via CSS: o navegador não oferece salvar/gerar senha -->
      <input id="us-senha" type="text" class="senha" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" data-lpignore="true" data-form-type="other"></label>
    ${novo ? "" : `<label class="chave"><span>Ativo (pode entrar no sistema)</span><input id="us-ativo" type="checkbox" ${u.ativo ? "checked" : ""}></label>`}
    <div class="acoes">
      <button class="btn btn-secundario" id="us-voltar">Voltar</button>
      <button class="btn btn-primario" id="us-salvar">${novo ? "Cadastrar" : "Salvar"}</button>
    </div>`, (g) => {
    focoNoCentro(g);
    const marcar = () => {
      g.querySelectorAll("#us-perfil button").forEach((b) => b.classList.toggle("sel", b.dataset.p === st.perfil));
      g.querySelector("#us-perfil-desc").textContent = PERFIS[st.perfil];
    };
    g.querySelector("#us-perfil").onclick = (e) => { const b = e.target.closest("button"); if (b) { st.perfil = b.dataset.p; marcar(); } };
    g.querySelector("#us-voltar").onclick = () => fecharGaveta();
    g.querySelector("#us-salvar").onclick = async () => {
      const senha = g.querySelector("#us-senha").value;
      const nome = novo ? g.querySelector("#us-nome").value.trim() : u.nome;
      if (novo && !nome) return toast("Informe o nome.", "erro");
      if (novo && !senha) return toast("Informe a senha inicial.", "erro");
      carregando(true);
      try {
        await rpc("mob_salvar_usuario", {
          p_token: sessao.token, p_id: novo ? null : u.id, p_nome: nome, p_perfil: st.perfil,
          p_ativo: novo ? true : g.querySelector("#us-ativo").checked, p_senha: senha || null,
        });
        fecharGaveta();
        toast(novo ? `Usuário ${nome} criado.` : senha ? `Senha de ${nome} atualizada.` : `${nome} atualizado.`, "ok");
        carregarUsuarios();
      } catch (e) { toast(e.message, "erro"); } finally { carregando(false); }
    };
    marcar();
  });
}
