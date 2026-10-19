// ============================================================
// Caixa EMB — relatórios (só Administrador e Meiry)
// Fechamento do período, Resumo por cliente e Resumo por produto,
// com os PDFs gerados no próprio celular (jsPDF em vendor/).
// Usa as utilidades do app.js e do admin.js (filtros, cartões de pedido...).
// Funções do banco: sql_mobile/03_funcoes_fase2.sql
// ============================================================
"use strict";

const TODOS_INI = "2000-01-01", TODOS_FIM = "2100-12-31";

function kpiHTML(itens) {
  return `<div class="kpis">${itens.map(([rot, val, cls = ""]) =>
    `<div class="kpi ${cls}"><small>${rot}</small><strong>${val}</strong></div>`).join("")}</div>`;
}
function listaValores(linhas, vazio) {
  if (!linhas.length) return `<p class="dica" style="margin:0">${vazio}</p>`;
  return `<ul class="formas">${linhas.map(([nome, valor, extra]) =>
    `<li><span>${esc(nome)}${extra ? ` <small class="qtd-mini">${extra}</small>` : ""}</span><strong>${valor}</strong></li>`).join("")}</ul>`;
}
function blocoRelatorio(titulo, corpo, rodape) {
  return `<div class="cartao bloco-rel"><h2 class="titulo-secao" style="margin-top:0">${titulo}</h2>${corpo}
    ${rodape ? `<div class="rodape-rel">${rodape}</div>` : ""}</div>`;
}
const fmtQtd = (q) => Number(q).toLocaleString("pt-BR", { maximumFractionDigits: 2 });

// ============================================================
// FECHAMENTO DO PERÍODO
// ============================================================
let fechamento = null;
let seqFech = 0;

async function carregarFechamento() {
  montarFiltros("fechamento", carregarFechamento);
  const el = $("#fechamento-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  const seq = ++seqFech;
  const f = filtros.fechamento;
  const [ini, fim] = periodoDe(f);
  try {
    const r = await rpc("mob_fechamento", { p_token: sessao.token, p_ini: ini, p_fim: fim, p_cliente: f.cliente || null, p_missao: f.missao || null });
    if (seq !== seqFech) return;
    fechamento = r;
    renderFechamento();
  } catch (e) {
    if (seq === seqFech) el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`;
  }
}

function renderFechamento() {
  const r = fechamento;
  const el = $("#fechamento-conteudo");
  if (!r.n_linhas) {
    el.innerHTML = `<div class="vazio-msg">Nenhum lançamento encontrado com esses filtros.</div>`;
    return;
  }
  el.innerHTML = `
    <p class="dica" style="margin-top:0">${esc(legendaFiltros("fechamento"))}</p>
    <button class="btn btn-primario btn-bloco" id="fech-pdf">📄 Gerar PDF do fechamento</button>
    <div style="height:12px"></div>
    ${kpiHTML([
      ["Consumo no período", fmtMoeda(r.total_consumo), "destaque"],
      ["Recebido", fmtMoeda(r.total_receb), "receb"],
      ["⏳ A receber", fmtMoeda(r.total_receber), "pend"],
    ])}
    ${blocoRelatorio("💳 Recebido por forma de pagamento",
      listaValores(r.por_forma.map((x) => [x.forma, fmtMoeda(x.valor)]), "Nenhum recebimento registrado no período."),
      r.por_forma.length ? `Total recebido: <strong>${fmtMoeda(r.total_receb)}</strong>` : "")}
    ${blocoRelatorio("🎯 Consumo por missão",
      listaValores(r.por_missao.map((x) => [x.missao || "-", fmtMoeda(x.total)]), "-"),
      `Total geral: <strong>${fmtMoeda(r.total_consumo)}</strong>`)}
    ${blocoRelatorio("🍔 Consumo por produto",
      listaValores(r.por_produto.map((x) => [x.produto, fmtMoeda(x.total), `${fmtQtd(x.qtde)}x`]), "-"),
      `Total do consumo: <strong>${fmtMoeda(r.total_consumo)}</strong>`)}
    ${blocoRelatorio("✅ Clientes que pagaram",
      listaValores(r.pagantes.map((x) => [x.cliente, fmtMoeda(x.valor)]), "Nenhum recebimento no período."),
      r.pagantes.length ? `Total pago: <strong>${fmtMoeda(r.total_pago)}</strong>` : "")}
    ${blocoRelatorio("⏳ A receber por cliente (em aberto)",
      listaValores(r.a_receber.map((x) => [x.cliente, fmtMoeda(x.valor)]), "Nada em aberto. 🎉"),
      r.a_receber.length ? `Total a receber: <strong>${fmtMoeda(r.total_receber)}</strong>` +
        (Number(r.abatido) > 0.001 ? `<br><small>(já descontado ${fmtMoeda(r.abatido)} em abatimentos/reembolsos do período)</small>` : "") : "")}`;
  $("#fech-pdf").onclick = () => gerarPDF(pdfFechamento);
}

// ============================================================
// RESUMO POR CLIENTE
// ============================================================
let resumoCli = null;
let pedidosCli = null;
let seqResCli = 0;

async function carregarResumoCli() {
  montarFiltros("resumocli", carregarResumoCli);
  const el = $("#resumocli-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  const seq = ++seqResCli;
  const f = filtros.resumocli;
  const [ini, fim] = periodoDe(f);
  try {
    const [r, ext] = await Promise.all([
      rpc("mob_resumo_clientes", { p_token: sessao.token, p_ini: ini, p_fim: fim, p_cliente: f.cliente || null, p_missao: f.missao || null }),
      // cliente escolhido: traz os pedidos dele (mesmo cartão do Extrato)
      f.cliente ? rpc("mob_extrato", { p_token: sessao.token, p_ini: ini || TODOS_INI, p_fim: fim || TODOS_FIM,
                                        p_cliente: f.cliente, p_missao: f.missao || null, p_situacao: "todos" }) : null,
    ]);
    if (seq !== seqResCli) return;
    resumoCli = r;
    // em aberto primeiro, depois os pagos; cada grupo do mais recente para o mais antigo
    pedidosCli = ext ? [...ext.pedidos].sort((a, b) =>
      ((Number(b.pendente) > 0.001) - (Number(a.pendente) > 0.001)) || String(b.criado_em).localeCompare(String(a.criado_em))) : null;
    renderResumoCli();
  } catch (e) {
    if (seq === seqResCli) el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`;
  }
}

function renderResumoCli() {
  const r = resumoCli;
  const f = filtros.resumocli;
  const el = $("#resumocli-conteudo");
  if (!r.clientes.length) {
    el.innerHTML = `<div class="vazio-msg">Nenhum lançamento encontrado com esses filtros.</div>`;
    return;
  }
  const kpis = kpiHTML([
    ["Total geral", fmtMoeda(r.total), "destaque"],
    ["Recebido", fmtMoeda(r.recebido), "receb"],
    ["⏳ A receber", fmtMoeda(r.a_receber), "pend"],
  ]) + (Number(r.abatido) > 0.001 ? `<p class="dica" style="margin-top:-6px">Já descontado ${fmtMoeda(r.abatido)} em abatimentos/reembolsos.</p>` : "");

  if (f.cliente) {
    el.innerHTML = kpis + `
      <h2 class="titulo-secao">Pedidos de ${esc(f.cliente)}</h2>
      ${pedidosCli.length ? pedidosCli.map((p, i) => cartaoPedido(p, i)).join("") : `<div class="vazio-msg">Nenhum pedido.</div>`}`;
    return;
  }
  el.innerHTML = kpis + `
    <h2 class="titulo-secao">Clientes (${r.clientes.length}) · quem deve mais primeiro</h2>
    <div class="cfg-lista" style="margin-top:0">
      ${r.clientes.map((c) => `
        <button class="cfg-item" data-cli="${esc(c.cliente)}">
          <span>${esc(c.cliente)}<small>Total ${fmtMoeda(c.total)} · Pago ${fmtMoeda(c.valor_pago)}${Number(c.abatido) > 0.001 ? ` · Abatido ${fmtMoeda(c.abatido)}` : ""}</small></span>
          ${Number(c.pendente) > 0.001
            ? `<span class="preco" style="color:var(--laranja)">${fmtMoeda(c.pendente)}</span>`
            : `<span class="etiqueta pago">Em dia</span>`}
        </button>`).join("")}
    </div>
    <p class="dica">Toque no cliente para ver os pedidos dele.</p>`;
}

$("#resumocli-conteudo").addEventListener("click", (e) => {
  const c = e.target.closest("[data-cli]");
  if (c) { filtros.resumocli.cliente = c.dataset.cli; carregarResumoCli(); window.scrollTo({ top: 0, behavior: "smooth" }); return; }
  const p = e.target.closest("[data-ped]");
  if (p) abrirPedido(pedidosCli[+p.dataset.ped], "resumocli");
});

// ============================================================
// RESUMO POR PRODUTO
// ============================================================
let resumoProd = null;
let seqResProd = 0;

async function carregarResumoProd() {
  montarFiltros("resumoprod", carregarResumoProd);
  const el = $("#resumoprod-conteudo");
  el.innerHTML = `<div class="vazio-msg">Carregando...</div>`;
  const seq = ++seqResProd;
  const f = filtros.resumoprod;
  const [ini, fim] = periodoDe(f);
  try {
    const r = await rpc("mob_resumo_produto", { p_token: sessao.token, p_ini: ini, p_fim: fim, p_produto: f.produto || null });
    if (seq !== seqResProd) return;
    resumoProd = r;
    renderResumoProd();
  } catch (e) {
    if (seq === seqResProd) el.innerHTML = `<div class="vazio-msg">${esc(e.message)}</div>`;
  }
}

function renderResumoProd() {
  const r = resumoProd;
  const f = filtros.resumoprod;
  const el = $("#resumoprod-conteudo");
  if (!r.linhas.length) {
    el.innerHTML = `<div class="vazio-msg">Nenhum lançamento encontrado com esses filtros.</div>`;
    return;
  }
  const topo = `
    <p class="dica" style="margin-top:0">${esc(legendaFiltros("resumoprod"))}</p>
    <button class="btn btn-secundario btn-bloco" id="prod-pdf">📄 Exportar em PDF (${r.linhas.length} linha${r.linhas.length > 1 ? "s" : ""})</button>
    <div style="height:12px"></div>
    ${kpiHTML([
      [`Total geral · ${fmtQtd(r.qtde)} un.`, fmtMoeda(r.total), "destaque"],
      ["Recebido", fmtMoeda(r.recebido), "receb"],
      ["⏳ A receber", fmtMoeda(r.a_receber), "pend"],
    ])}`;
  if (!f.produto) {
    el.innerHTML = topo + `
      <h2 class="titulo-secao">Por produto (${r.por_produto.length})</h2>
      <div class="cfg-lista" style="margin-top:0">
        ${r.por_produto.map((p) => `
          <button class="cfg-item" data-prod="${esc(p.produto)}">
            <span>${esc(p.produto)}<small>${fmtQtd(p.qtde)} un.${Number(p.pendente) > 0.001 ? ` · a receber ${fmtMoeda(p.pendente)}` : ""}</small></span>
            <span class="preco">${fmtMoeda(p.total)}</span>
          </button>`).join("")}
      </div>
      <p class="dica">Toque no produto para ver quem comprou e quando.</p>`;
  } else {
    el.innerHTML = topo + `
      <h2 class="titulo-secao">Lançamentos de ${esc(f.produto)}</h2>
      <div class="cfg-lista" style="margin-top:0">
        ${r.linhas.map((l) => {
          const cls = l.situacao === "Pago" ? "pago" : l.situacao === "Parcial" ? "parcial" : "pendente";
          return `<div class="cfg-item linha-prod">
            <span>${esc(l.cliente)}<small>${fmtData(l.data)} · ${fmtQtd(l.quantidade)} un.</small></span>
            <span class="lp-dir"><strong>${fmtMoeda(l.total)}</strong><span class="etiqueta ${cls}">${l.situacao}</span></span>
          </div>`;
        }).join("")}
      </div>`;
  }
  $("#prod-pdf").onclick = () => gerarPDF(pdfResumoProduto);
}

$("#resumoprod-conteudo").addEventListener("click", (e) => {
  const b = e.target.closest("[data-prod]");
  if (b) { filtros.resumoprod.produto = b.dataset.prod; carregarResumoProd(); window.scrollTo({ top: 0, behavior: "smooth" }); }
});

// ============================================================
// PDF — biblioteca carregada só na hora de gerar
// ============================================================
const AZUL_PDF = [11, 61, 145], MAGENTA_PDF = [230, 0, 126], AZUL_CLARO_PDF = [238, 243, 251];
const moedaPDF = (v) => fmtMoeda(v).replace(/ /g, " ");   // jsPDF não lida bem com espaço "duro"

function carregarScript(src) {
  return new Promise((ok, falha) => {
    const s = document.createElement("script");
    s.src = src; s.onload = ok; s.onerror = () => falha(new Error("Não foi possível carregar o gerador de PDF. Confira a internet."));
    document.head.appendChild(s);
  });
}
async function libPDF() {
  if (!window.jspdf) await carregarScript("vendor/jspdf.umd.min.js");
  if (!window.jspdf.jsPDF.API.autoTable) await carregarScript("vendor/jspdf.plugin.autotable.min.js");
  return window.jspdf.jsPDF;
}
let logoPDF;   // { dados, w, h } ou null
async function carregarLogoPDF() {
  if (logoPDF !== undefined) return logoPDF;
  try {
    const blob = await (await fetch("icons/logo.png")).blob();
    const dados = await new Promise((ok) => { const fr = new FileReader(); fr.onload = () => ok(fr.result); fr.readAsDataURL(blob); });
    const img = await new Promise((ok, falha) => { const i = new Image(); i.onload = () => ok(i); i.onerror = falha; i.src = dados; });
    logoPDF = { dados, w: img.naturalWidth, h: img.naturalHeight };
  } catch { logoPDF = null; }
  return logoPDF;
}

// cabeçalho: logo + título + linha do período; devolve o Y onde o conteúdo começa
function cabecalhoPDF(doc, titulo, periodo, margem) {
  const larg = doc.internal.pageSize.getWidth() - 2 * margem;
  let x = margem;
  if (logoPDF) {
    const h = 16, w = Math.min(28, (logoPDF.w / logoPDF.h) * h);
    doc.addImage(logoPDF.dados, "PNG", margem, margem, w, h);
    x = margem + w + 4;
  }
  doc.setFont("helvetica", "bold"); doc.setFontSize(16); doc.setTextColor(...AZUL_PDF);
  doc.text(titulo, x, margem + 10);
  doc.setFont("helvetica", "normal"); doc.setFontSize(9); doc.setTextColor(128);
  const linhas = doc.splitTextToSize(periodo, larg);
  doc.text(linhas, margem, margem + 22);
  return margem + 22 + linhas.length * 4 + 3;
}

function rodapePDF(doc, margem) {
  const n = doc.getNumberOfPages();
  const agora = new Date().toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "short" });
  for (let i = 1; i <= n; i++) {
    doc.setPage(i);
    doc.setFont("helvetica", "normal"); doc.setFontSize(7); doc.setTextColor(150);
    const h = doc.internal.pageSize.getHeight(), w = doc.internal.pageSize.getWidth();
    doc.text(`Gerado em ${agora} por ${dados.usuario}`, margem, h - 6);
    doc.text(`Página ${i} de ${n}`, w - margem, h - 6, { align: "right" });
  }
}

const ESTILO_TABELA = {
  theme: "grid",
  styles: { fontSize: 8, cellPadding: 1.3, lineColor: [211, 211, 211], lineWidth: 0.15, textColor: [27, 36, 51] },
  headStyles: { fillColor: AZUL_PDF, textColor: 255, fontStyle: "bold" },
  footStyles: { fillColor: [255, 255, 255], textColor: [27, 36, 51], fontStyle: "bold" },
  alternateRowStyles: { fillColor: AZUL_CLARO_PDF },
  showFoot: "lastPage",
};

// ---------- Fechamento: 2 colunas, igual ao sistema do navegador ----------
function pdfFechamento(JsPDF) {
  const r = fechamento;
  const doc = new JsPDF({ unit: "mm", format: "a4" });
  const M = 12, VAO = 6;
  const W = doc.internal.pageSize.getWidth(), H = doc.internal.pageSize.getHeight();
  const COL = (W - 2 * M - VAO) / 2;
  const yIni = cabecalhoPDF(doc, "Fechamento — Gerenciamento de Caixa", legendaFiltros("fechamento"), M);

  // desenha uma seção (título + tabela) na coluna x, a partir do y; devolve o novo y
  const secao = (titulo, head, body, foot, x, y, numericas) => {
    if (y > H - M - 20) {                     // título não fica sozinho no pé da página
      const pg = doc.getCurrentPageInfo().pageNumber;
      if (pg === doc.getNumberOfPages()) doc.addPage(); else doc.setPage(pg + 1);
      y = M;
    }
    doc.setFont("helvetica", "bold"); doc.setFontSize(10); doc.setTextColor(...MAGENTA_PDF);
    doc.text(titulo, x, y + 3);
    const colunas = {};
    numericas.forEach((i) => (colunas[i] = { halign: "right" }));
    doc.autoTable({
      ...ESTILO_TABELA, head: [head], body, foot: foot ? [foot] : undefined,
      startY: y + 5, margin: { left: x, right: W - x - COL, top: M, bottom: M + 4 }, tableWidth: COL,
      columnStyles: colunas,
      didParseCell: (d) => { if (d.section === "foot" && numericas.includes(d.column.index)) d.cell.styles.halign = "right"; },
    });
    return doc.lastAutoTable.finalY + 5;
  };

  // coluna da esquerda
  let y = yIni;
  y = secao("Recebido por forma de pagamento", ["Forma", "Recebido"],
    r.por_forma.length ? r.por_forma.map((x) => [x.forma, moedaPDF(x.valor)]) : [["(nenhum recebimento)", "-"]],
    r.por_forma.length ? ["TOTAL", moedaPDF(r.total_receb)] : null, M, y, [1]);
  if (r.por_missao.length) {
    y = secao("Consumo por missão", ["Missão", "Total"], r.por_missao.map((x) => [x.missao || "-", moedaPDF(x.total)]),
      ["TOTAL", moedaPDF(r.total_consumo)], M, y, [1]);
  }
  secao("Consumo por produto", ["Produto", "Qtde", "Total"],
    r.por_produto.map((x) => [x.produto, fmtQtd(x.qtde), moedaPDF(x.total)]),
    ["TOTAL", "", moedaPDF(r.total_consumo)], M, y, [1, 2]);

  // coluna da direita (volta para a página 1)
  doc.setPage(1);
  const xD = M + COL + VAO;
  y = yIni;
  y = secao("Clientes que pagaram", ["Cliente", "Pago"],
    r.pagantes.length ? r.pagantes.map((x) => [x.cliente, moedaPDF(x.valor)]) : [["(nenhum recebimento)", "-"]],
    r.pagantes.length ? ["TOTAL", moedaPDF(r.total_pago)] : null, xD, y, [1]);
  y = secao("A receber por cliente", ["Cliente", "Deve"],
    r.a_receber.length ? r.a_receber.map((x) => [x.cliente, moedaPDF(x.valor)]) : [["(nada em aberto)", "-"]],
    r.a_receber.length ? ["TOTAL", moedaPDF(r.total_receber)] : null, xD, y, [1]);
  if (Number(r.abatido) > 0.001) {
    doc.setFont("helvetica", "normal"); doc.setFontSize(7.5); doc.setTextColor(110);
    doc.text(`(já descontado ${moedaPDF(r.abatido)} em abatimentos/reembolsos do período)`, xD, y - 1, { maxWidth: COL });
  }

  rodapePDF(doc, M);
  const f = filtros.fechamento;
  const fimData = f.modo === "dia" ? f.dia : f.fim;
  const nome = `${f.modo === "dia" ? "fechamento_dia" : "fechamento_periodo"}_${fmtData(fimData).replace(/\//g, "-")}.pdf`;
  return { doc, nome };
}

// ---------- Resumo por produto: tabela única ----------
function pdfResumoProduto(JsPDF) {
  const r = resumoProd;
  const f = filtros.resumoprod;
  const doc = new JsPDF({ unit: "mm", format: "a4" });
  const M = 14;
  let y = cabecalhoPDF(doc, "Resumo por Produto", legendaFiltros("resumoprod") + ".", M);
  doc.setFont("helvetica", "normal"); doc.setFontSize(11); doc.setTextColor(...AZUL_PDF);
  const partes = [["Total geral: ", moedaPDF(r.total)], ["   |   Recebido: ", moedaPDF(r.recebido)], ["   |   A receber: ", moedaPDF(r.a_receber)]];
  let x = M;
  for (const [rot, val] of partes) {
    doc.setFont("helvetica", "normal"); doc.text(rot, x, y + 2); x += doc.getTextWidth(rot) + 1;
    doc.setFont("helvetica", "bold"); doc.text(val, x, y + 2); x += doc.getTextWidth(val);
  }
  y += 7;

  const comProduto = !f.produto;
  const head = comProduto ? ["Data", "Cliente", "Produto", "Qtde", "Valor", "Situação"] : ["Data", "Cliente", "Qtde", "Valor", "Situação"];
  const larguras = comProduto ? [20, 42, 42, 14, 24, 25] : [24, 62, 16, 28, 28];
  const body = r.linhas.map((l) => comProduto
    ? [fmtData(l.data), l.cliente, l.produto, fmtQtd(l.quantidade), moedaPDF(l.total), l.situacao]
    : [fmtData(l.data), l.cliente, fmtQtd(l.quantidade), moedaPDF(l.total), l.situacao]);
  const colunas = {};
  larguras.forEach((w, i) => (colunas[i] = { cellWidth: w }));
  const iQtd = comProduto ? 3 : 2;
  colunas[iQtd].halign = "right"; colunas[iQtd + 1].halign = "right";
  doc.autoTable({
    ...ESTILO_TABELA, head: [head], body, startY: y,
    margin: { left: M, right: M, top: M, bottom: M + 4 }, columnStyles: colunas,
    tableWidth: larguras.reduce((a, b) => a + b, 0),
  });

  rodapePDF(doc, M);
  const nomeProd = f.produto ? sem_acento(f.produto).replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") : "todos";
  return { doc, nome: `resumo_produto_${nomeProd}_${fmtData(hojeISO()).replace(/\//g, "-")}.pdf` };
}

// gera e mostra as opções: compartilhar (WhatsApp etc.), baixar ou abrir
async function gerarPDF(montar) {
  carregando(true);
  let arquivo, url;
  try {
    const JsPDF = await libPDF();
    await carregarLogoPDF();
    const { doc, nome } = montar(JsPDF);
    const blob = doc.output("blob");
    arquivo = new File([blob], nome, { type: "application/pdf" });
    url = URL.createObjectURL(blob);
  } catch (e) {
    carregando(false);
    return toast(e.message || "Erro ao gerar o PDF.", "erro");
  }
  carregando(false);
  const podeCompartilhar = !!(navigator.canShare && navigator.canShare({ files: [arquivo] }));
  abrirGaveta(`
    <h3>📄 PDF pronto</h3>
    <p class="dica" style="margin-top:-6px">${esc(arquivo.name)}</p>
    ${podeCompartilhar ? `<button class="btn btn-primario btn-bloco" id="pdf-compartilhar">📤 Compartilhar (WhatsApp...)</button>` : ""}
    <div class="acoes">
      <a class="btn btn-secundario" id="pdf-baixar" href="${url}" download="${esc(arquivo.name)}">⬇️ Baixar</a>
      <a class="btn btn-secundario" href="${url}" target="_blank" rel="noopener">👁️ Abrir</a>
    </div>`, (g) => {
    const b = g.querySelector("#pdf-compartilhar");
    if (b) b.onclick = async () => {
      try { await navigator.share({ files: [arquivo], title: arquivo.name }); }
      catch (e) { if (e.name !== "AbortError") toast("Não deu para compartilhar. Use Baixar.", "erro"); }
    };
  });
}
