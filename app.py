# ============================================================
# Lanchonete da Igreja - Lançamento de Cobranças
# Streamlit + Supabase
# ============================================================
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from supabase import create_client, Client

TZ = ZoneInfo("America/Sao_Paulo")

LOGO = "EMB.png"  # logo na raiz do repositório
TEM_LOGO = Path(LOGO).exists()

st.set_page_config(
    page_title="Lanchonete da Igreja",
    page_icon=LOGO if TEM_LOGO else "🍔",  # ícone da aba do navegador
    layout="wide",
)

if TEM_LOGO:
    st.logo(LOGO)  # logo no topo da sidebar

# ------------------------------------------------------------
# Tema Molicenter (azul / branco / magenta)
# Ajuste os tons oficiais aqui se necessário:
AZUL = "#0B3D91"
AZUL_ESCURO = "#062A66"
MAGENTA = "#E6007E"
MAGENTA_HOVER = "#C4006B"
AZUL_CLARO = "#EEF3FB"

st.markdown(
    f"""
    <style>
    /* Sidebar azul com texto branco */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {AZUL} 0%, {AZUL_ESCURO} 100%);
    }}
    [data-testid="stSidebar"] * {{
        color: #FFFFFF !important;
    }}
    [data-testid="stSidebar"] .stButton > button {{
        background: transparent;
        border: 1px solid #FFFFFF;
        color: #FFFFFF;
        border-radius: 8px;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        background: {MAGENTA};
        border-color: {MAGENTA};
    }}

    /* Faixa superior magenta -> azul */
    header[data-testid="stHeader"] {{
        background: linear-gradient(90deg, {MAGENTA} 0%, {AZUL} 60%);
    }}
    /* Título dentro do cabeçalho */
    header[data-testid="stHeader"]::before {{
        content: "Controle de Caixa - Embaixada de Cristo";
        position: absolute;
        left: 260px;
        top: 50%;
        transform: translateY(-50%);
        color: #FFFFFF;
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: 0.5px;
        white-space: nowrap;
        pointer-events: none;
    }}

    /* Títulos em azul */
    h1, h2, h3 {{
        color: {AZUL} !important;
    }}

    /* Botões primários em magenta */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button {{
        background: {MAGENTA};
        border: none;
        color: #FFFFFF;
    }}
    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button:hover {{
        background: {MAGENTA_HOVER};
        color: #FFFFFF;
    }}

    /* Cards de métricas */
    [data-testid="stMetric"] {{
        background: {AZUL_CLARO};
        border-left: 5px solid {MAGENTA};
        border-radius: 10px;
        padding: 10px 14px;
    }}
    [data-testid="stMetricLabel"] {{
        color: {AZUL} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Conexão Supabase
# ------------------------------------------------------------
@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_KEY"],
    )

def hoje_br() -> date:
    return datetime.now(TZ).date()

# ------------------------------------------------------------
# Login simples (senha única em st.secrets)
# ------------------------------------------------------------
def tela_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_esq, col_meio, col_dir = st.columns([1, 1.1, 1])

    with col_meio:
        with st.container(border=True):
            if TEM_LOGO:
                c_tit, c_logo = st.columns([4, 1])
                with c_tit:
                    st.markdown(
                        f"<h3 style='text-align:center; margin-bottom:0;'>Lanchonete da Igreja</h3>"
                        f"<p style='text-align:center; color:{AZUL}; font-size:0.8rem;'>"
                        f"Sistema de Lançamento de Cobranças</p>",
                        unsafe_allow_html=True,
                    )
                with c_logo:
                    st.image(LOGO, width=60)
            else:
                st.markdown(
                    f"<h3 style='text-align:center; margin-bottom:0;'>🍔 Lanchonete da Igreja</h3>"
                    f"<p style='text-align:center; color:{AZUL}; font-size:0.8rem;'>"
                    f"Sistema de Lançamento de Cobranças</p>",
                    unsafe_allow_html=True,
                )

            st.divider()

            with st.form("login_form"):
                senha = st.text_input("🔑 Senha de acesso:", type="password")
                entrar = st.form_submit_button(
                    "Entrar no Sistema", use_container_width=True, type="primary"
                )

            if entrar:
                if senha == st.secrets["SENHA_ADMIN"]:
                    st.session_state["logado"] = True
                    st.session_state["perfil"] = "Administrador"
                    st.rerun()
                elif senha == st.secrets["SENHA_USUARIO"]:
                    st.session_state["logado"] = True
                    st.session_state["perfil"] = "Usuário"
                    st.rerun()
                else:
                    st.error("Senha incorreta.")


if not st.session_state.get("logado"):
    tela_login()
    st.stop()

PERFIL = st.session_state.get("perfil", "Usuário")
EH_ADMIN = PERFIL == "Administrador"

sb = get_supabase()

# ------------------------------------------------------------
# Funções de dados
# ------------------------------------------------------------
@st.cache_data(ttl=60)
def carregar_produtos(somente_ativos: bool = True) -> pd.DataFrame:
    q = sb.table("produtos").select("*").order("nome")
    if somente_ativos:
        q = q.eq("ativo", True)
    dados = q.execute().data
    return pd.DataFrame(dados)

def limpar_cache_produtos():
    carregar_produtos.clear()

@st.cache_data(ttl=60)
def carregar_eventos(somente_ativos: bool = True) -> pd.DataFrame:
    # A tabela continua se chamando 'eventos' para não quebrar o banco, mas a interface mostrará 'Missões'
    q = sb.table("eventos").select("*").order("nome")
    if somente_ativos:
        q = q.eq("ativo", True)
    return pd.DataFrame(q.execute().data)

def limpar_cache_eventos():
    carregar_eventos.clear()

@st.cache_data(ttl=60)
def carregar_clientes(somente_ativos: bool = True) -> pd.DataFrame:
    q = sb.table("clientes").select("*").order("nome")
    if somente_ativos:
        q = q.eq("ativo", True)
    return pd.DataFrame(q.execute().data)

def limpar_cache_clientes():
    carregar_clientes.clear()

def carregar_lancamentos(
    data_ini: date,
    data_fim: date,
    cliente: str | None,
    situacao: str = "Todos",
    evento: str = "Todos",
    incluir_excluidos: bool = False,
) -> pd.DataFrame:
    q = (
        sb.table("lancamentos")
        .select("*")
        .gte("data_lancamento", data_ini.isoformat())
        .lte("data_lancamento", data_fim.isoformat())
        .order("criado_em", desc=True)
    )
    if not incluir_excluidos:
        q = q.eq("excluido", False)
    if cliente and cliente != "Todos":
        q = q.eq("cliente", cliente)
    if evento and evento != "Todos":
        q = q.eq("evento", evento)
    if situacao == "⏳ Pendentes":
        q = q.eq("pago", False)
    elif situacao == "✅ Pagos":
        q = q.eq("pago", True)
    return pd.DataFrame(q.execute().data)

def clientes_existentes_no_historico() -> list[str]:
    # Busca clientes que já existem na tabela de lançamentos para não perder o histórico
    dados = sb.table("lancamentos").select("cliente").eq("excluido", False).execute().data
    return sorted({d["cliente"] for d in dados})

# Formas de pagamento aceitas
FORMAS_PAGAMENTO = ["Dinheiro", "Pix", "Cartão Débito", "Cartão Crédito", "Bonificação"]

@st.cache_data(ttl=300)
def carregar_config() -> dict:
    dados = sb.table("config").select("*").execute().data
    return {d["chave"]: (d["valor"] or "") for d in dados}

def salvar_config(chave: str, valor: str):
    sb.table("config").upsert({"chave": chave, "valor": valor}).execute()
    carregar_config.clear()

def telefone_do_cliente(nome: str) -> str:
    df = carregar_clientes(somente_ativos=False)
    if df.empty or "telefone" not in df.columns:
        return ""
    achou = df.loc[df["nome"] == nome, "telefone"]
    return (achou.iloc[0] or "") if not achou.empty else ""

def link_whatsapp(telefone: str, mensagem: str) -> str:
    # limpa tudo que não for dígito; assume DDI 55 (Brasil) se vier sem
    digitos = "".join(c for c in str(telefone) if c.isdigit())
    if digitos and not digitos.startswith("55"):
        digitos = "55" + digitos
    from urllib.parse import quote
    return f"https://wa.me/{digitos}?text={quote(mensagem)}"


def gerar_pdf_fechamento(periodo_txt, por_forma, total_receb, por_produto,
                         total_consumo, pagantes, total_pago, a_receber, total_receber,
                         por_missao=None, total_missao=0.0):
    """Monta o PDF do fechamento com as visões dispostas em 2 colunas."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                    Spacer, Image as RLImage, KeepTogether)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    AZUL_RL = colors.HexColor("#0B3D91")
    MAGENTA_RL = colors.HexColor("#E6007E")
    AZUL_CLARO_RL = colors.HexColor("#EEF3FB")

    def moeda(v):
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=styles["Title"], textColor=AZUL_RL, fontSize=16)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.grey, fontSize=9)
    sec = ParagraphStyle("sec", parent=styles["Heading3"], textColor=MAGENTA_RL, fontSize=10, spaceBefore=2, spaceAfter=2)

    # largura útil de cada coluna (A4 - margens, dividido em 2 com um vão)
    COL_W = 91 * mm

    def bloco_tabela(dados, larguras):
        t = Table(dados, colWidths=larguras, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AZUL_RL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),  # linha TOTAL em negrito
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AZUL_CLARO_RL]),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        return t

    def secao(titulo_txt, tabela):
        # retorna a lista de flowables da seção (sem KeepTogether p/ caber em célula)
        return [Paragraph(titulo_txt, sec), tabela, Spacer(1, 4)]

    # monta cada seção como um "flowable" único
    secoes = []

    # Forma de pagamento
    linhas = [["Forma", "Recebido"]] + [[f, moeda(v)] for f, v in por_forma]
    linhas.append(["TOTAL", moeda(total_receb)])
    secoes.append(secao("Recebido por forma de pagamento", bloco_tabela(linhas, [50 * mm, 41 * mm])))

    # Por missão
    if por_missao:
        linhas = [["Missão", "Total"]] + [[m, moeda(v)] for m, v in por_missao]
        linhas.append(["TOTAL", moeda(total_missao)])
        secoes.append(secao("Consumo por missão", bloco_tabela(linhas, [50 * mm, 41 * mm])))

    # Consumo por produto
    linhas = [["Produto", "Qtde", "Total"]] + [[p, str(int(q)), moeda(v)] for p, q, v in por_produto]
    linhas.append(["TOTAL", "", moeda(total_consumo)])
    secoes.append(secao("Consumo por produto", bloco_tabela(linhas, [46 * mm, 15 * mm, 30 * mm])))

    # Clientes que pagaram
    if pagantes:
        linhas = [["Cliente", "Pago"]] + [[c, moeda(v)] for c, v in pagantes]
        linhas.append(["TOTAL", moeda(total_pago)])
    else:
        linhas = [["Cliente", "Pago"], ["(nenhum recebimento)", "-"]]
    secoes.append(secao("Clientes que pagaram", bloco_tabela(linhas, [55 * mm, 36 * mm])))

    # A receber por cliente
    if a_receber:
        linhas = [["Cliente", "Deve"]] + [[c, moeda(v)] for c, v in a_receber]
        linhas.append(["TOTAL", moeda(total_receber)])
    else:
        linhas = [["Cliente", "Deve"], ["(nada em aberto)", "-"]]
    secoes.append(secao("A receber por cliente", bloco_tabela(linhas, [55 * mm, 36 * mm])))

    # distribui as seções em 2 colunas (esquerda/direita) alternadamente
    col_esq, col_dir = [], []
    for i, s in enumerate(secoes):
        (col_esq if i % 2 == 0 else col_dir).extend(s)

    def coluna_para_tabela(flowables):
        # empilha os flowables da coluna numa tabela vertical de 1 coluna
        if not flowables:
            return Spacer(1, 1)
        t = Table([[f] for f in flowables], colWidths=[COL_W])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return t

    elems = []
    # cabeçalho
    if TEM_LOGO:
        try:
            cab = Table([[RLImage(LOGO, width=16 * mm, height=16 * mm),
                          Paragraph("Fechamento — Lanchonete da Igreja", titulo)]],
                        colWidths=[20 * mm, None])
            cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            elems.append(cab)
        except Exception:
            elems.append(Paragraph("Fechamento — Lanchonete da Igreja", titulo))
    else:
        elems.append(Paragraph("Fechamento — Lanchonete da Igreja", titulo))
    elems.append(Paragraph(periodo_txt, sub))
    elems.append(Spacer(1, 6))

    # grid de 2 colunas
    grid = Table([[coluna_para_tabela(col_esq), coluna_para_tabela(col_dir)]],
                 colWidths=[COL_W, COL_W])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 6),
        ("LEFTPADDING", (1, 0), (1, 0), 6),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elems.append(grid)

    doc.build(elems)
    buf.seek(0)
    return buf.getvalue()


# ------------------------------------------------------------
# Navegação (menu conforme o perfil)
# ------------------------------------------------------------
MENU_USUARIO = ["🧾 Lançamento", "📋 Extrato"]
MENU_ADMIN = ["🧾 Lançamento", "📋 Extrato", "📊 Resumo por cliente",
              "📱 Gerar Cobrança", "⚙️ Configurações"]

with st.sidebar:
    st.caption(f"👤 Perfil: **{PERFIL}**")
    st.markdown("**menu:**")
    pagina = st.radio(
        "Menu",
        MENU_ADMIN if EH_ADMIN else MENU_USUARIO,
        label_visibility="collapsed",
    )
    st.divider()
    if st.button("Sair", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ============================================================
# TELA: CADASTROS (Produtos, Missões, Clientes)
# ============================================================
if pagina == "⚙️ Configurações":
    if not EH_ADMIN:
        st.warning("Acesso restrito ao administrador.")
        st.stop()

    st.markdown("### 🛒 Cadastro de Produtos")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Novo produto**")
        with st.form("form_produto", clear_on_submit=True):
            nome = st.text_input("Nome do produto")
            preco = st.number_input("Preço (R$)", min_value=0.0, step=0.50, format="%.2f")
            salvar = st.form_submit_button("➕ Cadastrar", type="primary", use_container_width=True)

        if salvar:
            if not nome.strip():
                st.warning("Informe o nome do produto.")
            else:
                try:
                    sb.table("produtos").insert(
                        {"nome": nome.strip(), "preco": preco}
                    ).execute()
                    limpar_cache_produtos()
                    st.success(f"Produto **{nome.strip()}** cadastrado!")
                except Exception as e:
                    if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                        st.error("Já existe um produto com esse nome.")
                    else:
                        st.error(f"Erro ao cadastrar: {e}")

    with col2:
        st.markdown("**Produtos cadastrados** (edite direto na tabela)")
        df_prod = carregar_produtos(somente_ativos=False)

        if df_prod.empty:
            st.info("Nenhum produto cadastrado ainda.")
        else:
            df_edit = st.data_editor(
                df_prod[["id", "nome", "preco", "ativo"]],
                hide_index=True,
                use_container_width=True,
                disabled=["id"],
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "nome": st.column_config.TextColumn("Produto"),
                    "preco": st.column_config.NumberColumn("Preço (R$)", format="R$ %.2f", step=0.50),
                    "ativo": st.column_config.CheckboxColumn("Ativo"),
                },
                key="editor_produtos",
            )

            if st.button("💾 Salvar alterações", type="primary", key="btn_salvar_produtos"):
                alterados = 0
                for _, row in df_edit.iterrows():
                    original = df_prod.loc[df_prod["id"] == row["id"]].iloc[0]
                    if (
                        row["nome"] != original["nome"]
                        or float(row["preco"]) != float(original["preco"])
                        or bool(row["ativo"]) != bool(original["ativo"])
                    ):
                        sb.table("produtos").update(
                            {
                                "nome": str(row["nome"]).strip(),
                                "preco": float(row["preco"]),
                                "ativo": bool(row["ativo"]),
                            }
                        ).eq("id", int(row["id"])).execute()
                        alterados += 1
                limpar_cache_produtos()
                if alterados:
                    st.success(f"{alterados} produto(s) atualizado(s)!")
                    st.rerun()
                else:
                    st.info("Nenhuma alteração detectada.")

            st.caption("💡 Desmarque **Ativo** para tirar um produto do lançamento sem apagar o histórico.")


    # --- missões (no DB a tabela chama 'eventos') ---
    st.divider()
    st.markdown("### 🎪 Missões")
    ce1, ce2 = st.columns([1, 2])

    with ce1:
        st.markdown("**Nova missão**")
        with st.form("form_evento", clear_on_submit=True):
            nome_ev = st.text_input("Nome da missão", placeholder="Ex.: Missão Sertão, Jovem...")
            salvar_ev = st.form_submit_button("➕ Cadastrar missão", type="primary", use_container_width=True)
        if salvar_ev:
            if not nome_ev.strip():
                st.warning("Informe o nome da missão.")
            else:
                try:
                    sb.table("eventos").insert({"nome": nome_ev.strip().title()}).execute()
                    limpar_cache_eventos()
                    st.success(f"Missão **{nome_ev.strip().title()}** cadastrada!")
                    st.rerun()
                except Exception as e:
                    if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                        st.error("Já existe uma missão com esse nome.")
                    else:
                        st.error(f"Erro ao cadastrar: {e}")

    with ce2:
        st.markdown("**Missões cadastradas**")
        df_ev = carregar_eventos(somente_ativos=False)
        if df_ev.empty:
            st.info("Nenhuma missão cadastrada.")
        else:
            df_ev_edit = st.data_editor(
                df_ev[["id", "nome", "ativo"]],
                hide_index=True,
                use_container_width=True,
                disabled=["id"],
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "nome": st.column_config.TextColumn("Missão"),
                    "ativo": st.column_config.CheckboxColumn("Ativo"),
                },
                key="editor_eventos",
            )
            if st.button("💾 Salvar missões", key="btn_salvar_missoes"):
                alterados = 0
                for _, row in df_ev_edit.iterrows():
                    original = df_ev.loc[df_ev["id"] == row["id"]].iloc[0]
                    if row["nome"] != original["nome"] or bool(row["ativo"]) != bool(original["ativo"]):
                        sb.table("eventos").update(
                            {"nome": str(row["nome"]).strip(), "ativo": bool(row["ativo"])}
                        ).eq("id", int(row["id"])).execute()
                        alterados += 1
                limpar_cache_eventos()
                if alterados:
                    st.success(f"{alterados} missão(ões) atualizada(s)!")
                    st.rerun()
                else:
                    st.info("Nenhuma alteração detectada.")


    # --- clientes ---
    st.divider()
    st.markdown("### 👥 Clientes")
    cc1, cc2 = st.columns([1, 2])

    with cc1:
        st.markdown("**Novo cliente**")
        with st.form("form_cliente", clear_on_submit=True):
            nome_cli = st.text_input("Nome do cliente")
            tel_cli = st.text_input("Telefone/WhatsApp", placeholder="43 99999-9999")
            salvar_cli = st.form_submit_button("➕ Cadastrar cliente", type="primary", use_container_width=True)
        if salvar_cli:
            if not nome_cli.strip():
                st.warning("Informe o nome do cliente.")
            else:
                try:
                    sb.table("clientes").insert({
                        "nome": nome_cli.strip().title(),
                        "telefone": tel_cli.strip() or None,
                    }).execute()
                    limpar_cache_clientes()
                    st.success(f"Cliente **{nome_cli.strip().title()}** cadastrado!")
                    st.rerun()
                except Exception as e:
                    if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                        st.error("Já existe um cliente com esse nome.")
                    else:
                        st.error(f"Erro ao cadastrar: {e}")

    with cc2:
        st.markdown("**Clientes cadastrados**")
        df_cli = carregar_clientes(somente_ativos=False)
        if df_cli.empty:
            st.info("Nenhum cliente cadastrado.")
        else:
            if "telefone" not in df_cli.columns:
                df_cli["telefone"] = ""
            df_cli["telefone"] = df_cli["telefone"].fillna("")
            df_cli_edit = st.data_editor(
                df_cli[["id", "nome", "telefone", "ativo"]],
                hide_index=True,
                use_container_width=True,
                disabled=["id"],
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "nome": st.column_config.TextColumn("Cliente"),
                    "telefone": st.column_config.TextColumn("Telefone/WhatsApp"),
                    "ativo": st.column_config.CheckboxColumn("Ativo"),
                },
                key="editor_clientes",
            )
            if st.button("💾 Salvar clientes", key="btn_salvar_clientes"):
                alterados = 0
                for _, row in df_cli_edit.iterrows():
                    original = df_cli.loc[df_cli["id"] == row["id"]].iloc[0]
                    if (row["nome"] != original["nome"]
                            or bool(row["ativo"]) != bool(original["ativo"])
                            or str(row["telefone"]) != str(original["telefone"])):
                        sb.table("clientes").update({
                            "nome": str(row["nome"]).strip(),
                            "telefone": str(row["telefone"]).strip() or None,
                            "ativo": bool(row["ativo"]),
                        }).eq("id", int(row["id"])).execute()
                        alterados += 1
                limpar_cache_clientes()
                if alterados:
                    st.success(f"{alterados} cliente(s) atualizado(s)!")
                    st.rerun()
                else:
                    st.info("Nenhuma alteração detectada.")

    # --- configurações do Pix (para a mensagem de cobrança) ---
    st.divider()
    st.markdown("### ⚙️ Configuração da cobrança (Pix)")
    cfg = carregar_config()
    with st.form("form_config"):
        colp1, colp2 = st.columns(2)
        with colp1:
            pix_chave = st.text_input("Chave Pix / número", value=cfg.get("pix_chave", ""))
        with colp2:
            pix_nome = st.text_input("Nome do recebedor", value=cfg.get("pix_nome", ""))
        salvar_cfg = st.form_submit_button("💾 Salvar configuração", type="primary")
    if salvar_cfg:
        salvar_config("pix_chave", pix_chave.strip())
        salvar_config("pix_nome", pix_nome.strip())
        st.success("Configuração salva! Será usada nas mensagens de cobrança.")
        st.rerun()


# ============================================================
# TELA: LANÇAMENTO
# ============================================================
elif pagina == "🧾 Lançamento":
    st.markdown("### 🧾 Novo Lançamento")

    df_prod = carregar_produtos(somente_ativos=True)
    if df_prod.empty:
        st.warning("Cadastre pelo menos um produto na aba **⚙️ Configurações** antes de lançar.")
        st.stop()

    precos = dict(zip(df_prod["nome"], df_prod["preco"].astype(float)))

    if "carrinho" not in st.session_state:
        st.session_state["carrinho"] = []

    # --- dados do pedido ---
    df_ev = carregar_eventos(somente_ativos=True)
    lista_missoes = df_ev["nome"].tolist() if not df_ev.empty else ["Geral"]

    df_clientes = carregar_clientes(somente_ativos=True)
    if df_clientes.empty:
        st.warning("Cadastre pelo menos um cliente na aba **⚙️ Configurações** para prosseguir.")
        st.stop()
    lista_clientes = df_clientes["nome"].tolist()

    col_ev, col_a, col_b = st.columns([1.2, 2, 1])
    with col_ev:
        missao_sel = st.selectbox("🎪 Missão", lista_missoes)
    with col_a:
        cliente_sel = st.selectbox("Cliente", lista_clientes, help="Escolha um cliente previamente cadastrado.")
    with col_b:
        data_lanc = st.date_input("Data", value=hoje_br(), format="DD/MM/YYYY")

    st.divider()

    # --- adicionar itens ao pedido ---
    st.markdown("**Adicionar produto ao pedido**")
    
    # Adicionamos mais uma coluna (c_extra) e reajustamos os tamanhos para caber tudo
    c1, c2, c3, c_extra, c4, c5 = st.columns([2.0, 0.7, 1.1, 1.1, 2.0, 1.1])
    with c1:
        produto_sel = st.selectbox("Produto", df_prod["nome"].tolist(), key="sel_produto")
    with c2:
        qtde = st.number_input("Qtde", min_value=1, value=1, step=1, key="inp_qtde")
    with c3:
        preco_padrao = precos.get(produto_sel, 0.0)
        preco_unit = st.number_input(
            "Preço unit. (R$)",
            min_value=0.0,
            value=preco_padrao,
            step=0.50,
            format="%.2f",
            key=f"inp_preco_{produto_sel}",
        )
    with c_extra:
        preco_extra = st.number_input(
            "Valor extra (R$)",
            min_value=0.0,
            value=0.0,
            step=0.50,
            format="%.2f",
            key=f"inp_extra_{produto_sel}",
            help="Bacon, borda recheada, etc."
        )
    with c4:
        obs_item = st.text_input(
            "Obs. do item",
            key="inp_obs_item",
            placeholder="Ex: com bacon...",
        )
    with c5:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Adicionar", use_container_width=True):
            st.session_state["carrinho"].append(
                {
                    "produto": produto_sel,
                    "quantidade": int(qtde),
                    "preco_unitario": preco_unit,
                    "preco_extra": preco_extra,
                    "obs_item": obs_item.strip(),
                    # O total já calcula o preço unitário + o valor extra
                    "total": round(qtde * (preco_unit + preco_extra), 2),
                }
            )
            st.rerun()

    # --- carrinho ---
    carrinho = st.session_state["carrinho"]
    if carrinho:
        st.markdown("**Itens do pedido:**")
        df_car = pd.DataFrame(carrinho)
        for i, item in enumerate(carrinho):
            ic1, ic2, ic3, ic4, ic5 = st.columns([3, 1, 1.5, 1.5, 0.7])
            rotulo = item["produto"]
            if item.get("obs_item"):
                rotulo += f"  \n:gray[_{item['obs_item']}_]"
            ic1.markdown(rotulo)
            ic2.write(f"x {item['quantidade']}")
            
            # Mostra o valor extra na tela do carrinho de forma elegante
            if item.get("preco_extra", 0) > 0:
                ic3.write(f"R$ {item['preco_unitario']:.2f}  \n*(+ R$ {item['preco_extra']:.2f})*")
            else:
                ic3.write(f"R$ {item['preco_unitario']:.2f}")
                
            ic4.write(f"**R$ {item['total']:.2f}**")
            if ic5.button("🗑️", key=f"del_{i}"):
                carrinho.pop(i)
                st.rerun()

        observacao = st.text_input(
            "Observação do pedido (opcional)",
            placeholder="Ex.: pagar na sexta, entregar na mesa 3...",
        )

        total_pedido = df_car["total"].sum()
        st.markdown(f"#### 💰 Total do pedido: R$ {total_pedido:.2f}")

        situacao = st.radio(
            "Situação do pagamento",
            ["✅ Pago", "⏳ Pendente", "💸 Parcial"],
            horizontal=True,
            help="Parcial: cliente pagou só uma parte agora; o restante fica como pendente no extrato.",
        )

        valor_pago_input = 0.0
        forma_pgto = None
        if situacao == "💸 Parcial":
            valor_pago_input = st.number_input(
                "Valor pago agora (R$)",
                min_value=0.0,
                max_value=float(total_pedido),
                value=0.0,
                step=0.50,
                format="%.2f",
                help=f"Total do pedido: R$ {total_pedido:.2f}. O que faltar vira pendente.",
            )
            falta = total_pedido - valor_pago_input
            st.caption(f"Ficará **devendo R$ {falta:.2f}** deste pedido.")

        # Forma de pagamento aparece quando há recebimento agora (Pago ou Parcial).
        # Pendente não pede forma - ela será escolhida no extrato, na hora de receber.
        if situacao in ("✅ Pago", "💸 Parcial"):
            forma_pgto = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO)

        col_s1, col_s2 = st.columns([1, 3])
        with col_s1:
            if st.button("✅ Salvar lançamento", type="primary", use_container_width=True):
                if not cliente_sel or not cliente_sel.strip():
                    st.error("Selecione um cliente.")
                elif situacao == "💸 Parcial" and valor_pago_input <= 0:
                    st.error("Informe o valor pago (maior que zero) ou escolha Pendente.")
                else:
                    pedido_id = uuid.uuid4().hex[:8]
                    esta_pago = situacao == "✅ Pago"
                    # Bonificação: pedido cortesia, marca como pago sem gerar cobrança
                    eh_bonificacao = forma_pgto == "Bonificação"

                    # Distribui o valor pago do pedido entre as linhas (itens),
                    # proporcional ao total de cada item, para o somatório bater certo.
                    if esta_pago:
                        valor_pago_por_item = [it["total"] for it in carrinho]
                    elif situacao == "💸 Parcial":
                        restante = round(valor_pago_input, 2)
                        valor_pago_por_item = []
                        for idx, it in enumerate(carrinho):
                            if idx == len(carrinho) - 1:
                                # última linha recebe o que sobrou (evita erro de arredondamento)
                                valor_pago_por_item.append(round(restante, 2))
                            else:
                                parcela = min(it["total"], restante)
                                valor_pago_por_item.append(round(parcela, 2))
                                restante = round(restante - parcela, 2)
                    else:  # Pendente
                        valor_pago_por_item = [0.0 for _ in carrinho]

                    linhas = [
                        {
                            "pedido_id": pedido_id,
                            "cliente": cliente_sel.strip().title(),
                            "evento": missao_sel,
                            "produto": it["produto"],
                            "quantidade": it["quantidade"],
                            # Soma o unitário + extra antes de mandar para o banco de dados
                            "preco_unitario": it["preco_unitario"] + it.get("preco_extra", 0.0),
                            "obs_item": it.get("obs_item") or None,
                            "observacao": observacao.strip() or None,
                            "data_lancamento": data_lanc.isoformat(),
                            "pago": esta_pago,
                            "valor_pago": valor_pago_por_item[idx],
                            "forma_pagamento": forma_pgto if situacao in ("✅ Pago", "💸 Parcial") else None,
                            "data_pagamento": data_lanc.isoformat() if esta_pago else None,
                            "lancado_por": PERFIL,
                        }
                        for idx, it in enumerate(carrinho)
                    ]
                    try:
                        sb.table("lancamentos").insert(linhas).execute()
                        st.session_state["carrinho"] = []
                        st.success(f"Lançamento salvo para **{cliente_sel.strip().title()}**! 🎉")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
        with col_s2:
            if st.button("🧹 Limpar itens"):
                st.session_state["carrinho"] = []
                st.rerun()
    else:
        st.info("Nenhum item adicionado ainda. Escolha um produto acima e clique em **Adicionar**.")

# ============================================================
# TELA: EXTRATO
# ============================================================
elif pagina == "📋 Extrato":
    st.markdown("### 📋 Extrato de Lançamentos")

    df_ev_todos = carregar_eventos(somente_ativos=False)
    lista_missao_filtro = ["Todos"] + (df_ev_todos["nome"].tolist() if not df_ev_todos.empty else [])

    # Junta os clientes do histórico (tabela lançamentos) com os da nova tabela clientes
    cli_historico = clientes_existentes_no_historico()
    df_cli_todos = carregar_clientes(somente_ativos=False)
    cli_cadastrados = df_cli_todos["nome"].tolist() if not df_cli_todos.empty else []
    lista_cli_filtro = ["Todos"] + sorted(list(set(cli_historico + cli_cadastrados)))

    f1, f2, f3, f4, f5 = st.columns([1, 1, 1.4, 1.1, 1.1])
    with f1:
        data_ini = st.date_input("De", value=hoje_br() - timedelta(days=30), format="DD/MM/YYYY")
    with f2:
        data_fim = st.date_input("Até", value=hoje_br(), format="DD/MM/YYYY")
    with f3:
        cliente_filtro = st.selectbox("Cliente", lista_cli_filtro)
    with f4:
        missao_filtro = st.selectbox("Missão", lista_missao_filtro)
    with f5:
        situacao_filtro = st.selectbox("Situação", ["Todos", "⏳ Pendentes", "✅ Pagos"])

    # excluídos nunca entram na visão normal (ficam guardados no banco com o motivo)
    ver_excluidos = False

    df = carregar_lancamentos(
        data_ini, data_fim, cliente_filtro, situacao_filtro, missao_filtro, ver_excluidos
    )

    if df.empty:
        st.info("Nenhum lançamento encontrado nesse período.")
    else:
        df["data_lancamento"] = pd.to_datetime(df["data_lancamento"]).dt.strftime("%d/%m/%Y")
        
        # Formatando Data de Pagamento
        if "data_pagamento" in df.columns:
            df["data_pagamento"] = pd.to_datetime(df["data_pagamento"]).dt.strftime("%d/%m/%Y").fillna("-")
        else:
            df["data_pagamento"] = "-"
            
        # valor_pago pode não existir em registros muito antigos -> assume 0
        if "valor_pago" not in df.columns:
            df["valor_pago"] = 0.0
        df["valor_pago"] = df["valor_pago"].fillna(0.0)
        df["pendente"] = (df["total"] - df["valor_pago"]).round(2).clip(lower=0)

        def situacao_linha(row):
            if row.get("excluido"):
                return "🚫 Excluído"
            if row["pendente"] <= 0.001:
                return "✅ Pago"
            if row["valor_pago"] > 0.001:
                return "💸 Parcial"
            return "⏳ Pendente"

        df["situacao"] = df.apply(situacao_linha, axis=1)

        def fmt_moeda(v: float) -> str:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        df_validos = df.loc[~df["excluido"]] if "excluido" in df.columns else df
        total_pendente = df_validos["pendente"].sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total no período", fmt_moeda(df_validos["total"].sum()))
        m2.metric("⏳ A receber", fmt_moeda(total_pendente))
        m3.metric("Pedidos", df_validos["pedido_id"].nunique())
        m4.metric("Clientes", df_validos["cliente"].nunique())

        # ------------------------------------------------------------
        # Visão AGRUPADA POR PEDIDO (uma linha por pedido)
        # ------------------------------------------------------------
        st.markdown("#### 📦 Pedidos")

        def resumo_itens(sub: pd.DataFrame) -> str:
            partes = []
            for _, r in sub.iterrows():
                p = f"{int(r['quantidade'])}x {r['produto']}"
                if r.get("obs_item"):
                    p += f" ({r['obs_item']})"
                partes.append(p)
            return ", ".join(partes)

        grupos = []
        for pid, sub in df_validos.groupby("pedido_id"):
            grupos.append({
                "pedido_id": pid,
                "data_lancamento": sub["data_lancamento"].iloc[0],
                "data_pagamento": sub["data_pagamento"].iloc[0],
                "cliente": sub["cliente"].iloc[0],
                "evento": sub["evento"].iloc[0],
                "itens": resumo_itens(sub),
                "total": round(sub["total"].sum(), 2),
                "valor_pago": round(sub["valor_pago"].sum(), 2),
                "pendente": round(sub["pendente"].sum(), 2),
                "observacao": sub["observacao"].iloc[0],
                "situacao": ("✅ Pago" if sub["pendente"].sum() <= 0.001
                             else ("💸 Parcial" if sub["valor_pago"].sum() > 0.001
                                   else "⏳ Pendente")),
            })
        df_ped = pd.DataFrame(grupos).sort_values(["situacao", "cliente"])

        st.dataframe(
            df_ped[["data_lancamento", "data_pagamento", "cliente", "evento", "itens",
                    "total", "valor_pago", "pendente", "situacao", "observacao"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "data_lancamento": st.column_config.TextColumn("Data Lanç."),
                "data_pagamento": st.column_config.TextColumn("Data Pgto"),
                "cliente": st.column_config.TextColumn("Cliente"),
                "evento": st.column_config.TextColumn("Missão"),
                "itens": st.column_config.TextColumn("Itens do Pedido", width="large"),
                "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                "valor_pago": st.column_config.NumberColumn("Pgto Parcial", format="R$ %.2f"),
                "pendente": st.column_config.NumberColumn("Valor Pendente", format="R$ %.2f"),
                "situacao": st.column_config.TextColumn("Situação"),
                "observacao": st.column_config.TextColumn("Obs. Pedido"),
            },
        )

        # detalhe item a item (opcional)
        with st.expander("🔍 Ver detalhe item a item"):
            st.dataframe(
                df[["data_lancamento", "cliente", "evento", "produto", "obs_item",
                    "quantidade", "preco_unitario", "total", "situacao"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "data_lancamento": st.column_config.TextColumn("Data"),
                    "cliente": st.column_config.TextColumn("Cliente"),
                    "evento": st.column_config.TextColumn("Missão"),
                    "produto": st.column_config.TextColumn("Produto"),
                    "obs_item": st.column_config.TextColumn("Obs. Item"),
                    "quantidade": st.column_config.NumberColumn("Qtde", format="%d"),
                    "preco_unitario": st.column_config.NumberColumn("Preço Unit.", format="R$ %.2f"),
                    "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                    "situacao": st.column_config.TextColumn("Situação"),
                },
            )

        # ------------------------------------------------------------
        # Registrar / ajustar recebimento por pedido (somente administrador)
        # ------------------------------------------------------------
        def registrar_pagamento_pedido(pedido_id: str, valor_recebido: float, df_ref: pd.DataFrame,
                                        forma: str | None = None):
            """Distribui o valor recebido entre as linhas do pedido e grava valor_pago/pago/forma."""
            itens = df_ref.loc[df_ref["pedido_id"] == pedido_id].sort_values("id")
            restante = round(valor_recebido, 2)
            total_pedido = round(itens["total"].sum(), 2)
            quitou_tudo = valor_recebido >= total_pedido - 0.001
            ids = itens["id"].tolist()
            for pos, (_, item) in enumerate(itens.iterrows()):
                if pos == len(ids) - 1:
                    pago_item = round(restante, 2)
                else:
                    pago_item = round(min(item["total"], restante), 2)
                    restante = round(restante - pago_item, 2)
                update = {
                    "valor_pago": pago_item,
                    "pago": pago_item >= item["total"] - 0.001,
                    "data_pagamento": hoje_br().isoformat() if quitou_tudo else None,
                }
                if forma:
                    update["forma_pagamento"] = forma
                sb.table("lancamentos").update(update).eq("id", int(item["id"])).execute()

        pedidos_abertos = df_ped.loc[df_ped["pendente"] > 0.001]
        if EH_ADMIN and not pedidos_abertos.empty:
            st.markdown("#### 💰 Receber / ajustar pagamento")
            st.caption("Escolha a forma, digite quanto o cliente pagou e salve. O sistema recalcula o pendente sozinho.")

            for _, ped in pedidos_abertos.iterrows():
                pid = ped["pedido_id"]
                with st.container(border=True):
                    c1, c2, c3, c4, c5, c6 = st.columns([1.5, 2.4, 1.1, 1.4, 1.5, 1.2])
                    c1.markdown(f"**{ped['cliente']}**  \n:gray[{ped['data_lancamento']}]")
                    c2.markdown(f"{ped['itens']}")
                    c3.markdown(f"Total  \n**{fmt_moeda(ped['total'])}**")
                    forma_sel = c4.selectbox("Forma", FORMAS_PAGAMENTO, key=f"fp_{pid}")
                    novo_valor = c5.number_input(
                        "Valor pago (R$)",
                        min_value=0.0,
                        max_value=float(ped["total"]),
                        value=float(ped["valor_pago"]),
                        step=0.50,
                        format="%.2f",
                        key=f"vp_{pid}",
                    )
                    c6.markdown("<br>", unsafe_allow_html=True)
                    if c6.button("💾 Salvar", key=f"save_{pid}", use_container_width=True):
                        registrar_pagamento_pedido(pid, novo_valor, df_validos, forma_sel)
                        if novo_valor >= ped["total"] - 0.001:
                            st.success(f"Pedido de {ped['cliente']} quitado ({forma_sel})!")
                        else:
                            falta = ped["total"] - novo_valor
                            st.success(f"Registrado R$ {novo_valor:.2f} de {ped['cliente']} ({forma_sel}) — resta R$ {falta:.2f}.")
                        st.rerun()

                    # botão rápido de quitar tudo com a forma escolhida
                    if ped["pendente"] > 0.001:
                        if c6.button("✔️ Quitar tudo", key=f"quit_{pid}", use_container_width=True):
                            registrar_pagamento_pedido(pid, float(ped["total"]), df_validos, forma_sel)
                            st.success(f"Pedido de {ped['cliente']} quitado ({forma_sel})!")
                            st.rerun()

            if cliente_filtro != "Todos":
                if st.button(f"✅ Quitar TODOS os pedidos abertos de {cliente_filtro}", type="primary"):
                    for _, ped in pedidos_abertos.iterrows():
                        registrar_pagamento_pedido(ped["pedido_id"], float(ped["total"]), df_validos)
                    st.success(f"Todos os pedidos de {cliente_filtro} foram quitados!")
                    st.rerun()

        # ------------------------------------------------------------
        # Fechamento do dia (por forma de pgto / por produto / por cliente)
        # ------------------------------------------------------------
        if EH_ADMIN:
            # Cabeçalho do fechamento: expander à esquerda, botão de PDF à direita
            col_fech, col_pdf = st.columns([4, 1.2])
            with col_fech:
                exp_fech = st.expander("📑 Fechamento do período (resumos)")
            with exp_fech:
                fmt = fmt_moeda

                # 1) Recebido por forma de pagamento
                st.markdown("**💳 Recebido por forma de pagamento**")
                recebidos = df_validos.loc[df_validos["valor_pago"] > 0.001].copy()
                total_receb = 0.0
                por_forma_pdf = []
                if recebidos.empty or "forma_pagamento" not in recebidos.columns:
                    st.caption("Nenhum recebimento registrado no período.")
                else:
                    recebidos["forma_pagamento"] = recebidos["forma_pagamento"].fillna("(não informado)")
                    por_forma = recebidos.groupby("forma_pagamento", as_index=False)["valor_pago"].sum()
                    total_receb = recebidos["valor_pago"].sum()
                    por_forma_pdf = list(por_forma.itertuples(index=False, name=None))
                    st.dataframe(
                        por_forma, hide_index=True, use_container_width=True,
                        column_config={
                            "forma_pagamento": st.column_config.TextColumn("Forma"),
                            "valor_pago": st.column_config.NumberColumn("Recebido", format="R$ %.2f"),
                        },
                    )
                    st.caption(f"Total recebido: **{fmt(total_receb)}**")

                # 2) Consumo por produto
                st.divider()
                st.markdown("**🍔 Consumo por produto**")
                por_produto = df_validos.groupby("produto", as_index=False).agg(
                    qtde=("quantidade", "sum"), total=("total", "sum")
                ).sort_values("total", ascending=False)
                total_consumo = df_validos["total"].sum()
                por_produto_pdf = list(por_produto.itertuples(index=False, name=None))
                st.dataframe(
                    por_produto, hide_index=True, use_container_width=True,
                    column_config={
                        "produto": st.column_config.TextColumn("Produto"),
                        "qtde": st.column_config.NumberColumn("Qtde", format="%d"),
                        "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                    },
                )
                st.caption(f"Total do consumo: **{fmt(total_consumo)}**")

                # Consumo por missão
                st.divider()
                st.markdown("**🎪 Consumo por missão**")
                por_missao = df_validos.groupby("evento", as_index=False)["total"].sum().sort_values("total", ascending=False)
                total_missao = df_validos["total"].sum()
                por_missao_pdf = list(por_missao.itertuples(index=False, name=None))
                st.dataframe(
                    por_missao, hide_index=True, use_container_width=True,
                    column_config={
                        "evento": st.column_config.TextColumn("Missão"),
                        "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                    },
                )
                st.caption(f"Total geral: **{fmt(total_missao)}**")

                # 3) Clientes que pagaram (total ou parcial)
                st.divider()
                st.markdown("**✅ Clientes que pagaram**")
                pagantes = (
                    df_validos.loc[df_validos["valor_pago"] > 0.001]
                    .groupby("cliente", as_index=False)["valor_pago"].sum()
                    .sort_values("valor_pago", ascending=False)
                )
                total_pago = pagantes["valor_pago"].sum() if not pagantes.empty else 0.0
                pagantes_pdf = list(pagantes.itertuples(index=False, name=None)) if not pagantes.empty else []
                if pagantes.empty:
                    st.caption("Nenhum recebimento no período.")
                else:
                    st.dataframe(
                        pagantes, hide_index=True, use_container_width=True,
                        column_config={
                            "cliente": st.column_config.TextColumn("Cliente"),
                            "valor_pago": st.column_config.NumberColumn("Pago", format="R$ %.2f"),
                        },
                    )
                    st.caption(f"Total pago: **{fmt(total_pago)}**")

                # 4) A receber por cliente (em aberto)
                st.divider()
                st.markdown("**⏳ A receber por cliente (em aberto)**")
                a_receber = (
                    df_validos.loc[df_validos["pendente"] > 0.001]
                    .groupby("cliente", as_index=False)["pendente"].sum()
                    .sort_values("pendente", ascending=False)
                )
                total_receber = a_receber["pendente"].sum() if not a_receber.empty else 0.0
                a_receber_pdf = list(a_receber.itertuples(index=False, name=None)) if not a_receber.empty else []
                if a_receber.empty:
                    st.caption("Nada em aberto. 🎉")
                else:
                    st.dataframe(
                        a_receber, hide_index=True, use_container_width=True,
                        column_config={
                            "cliente": st.column_config.TextColumn("Cliente"),
                            "pendente": st.column_config.NumberColumn("Deve", format="R$ %.2f"),
                        },
                    )
                    st.caption(f"Total a receber: **{fmt(total_receber)}**")

            # --- gerar PDF com as 4 visões (botão ao lado do cabeçalho) ---
            periodo_txt = f"Período: {data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
            if missao_filtro != "Todos":
                periodo_txt += f"  •  Missão: {missao_filtro}"
            if cliente_filtro != "Todos":
                periodo_txt += f"  •  Cliente: {cliente_filtro}"
            with col_pdf:
                try:
                    pdf_bytes = gerar_pdf_fechamento(
                        periodo_txt, por_forma_pdf, total_receb, por_produto_pdf,
                        total_consumo, pagantes_pdf, total_pago, a_receber_pdf, total_receber,
                        por_missao_pdf, total_missao,
                    )
                    st.download_button(
                        "📄 Baixar PDF",
                        data=pdf_bytes,
                        file_name=f"fechamento_{data_fim.strftime('%d-%m-%Y')}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Erro no PDF: {e}")

        # edição do cabeçalho do pedido (cliente / missão / data / observação)
        if EH_ADMIN and not df_ped.empty:
            with st.expander("✏️ Editar um pedido (cliente / missão / data / observação)"):
                pids_ed = df_ped["pedido_id"].tolist()

                def formata_pedido_edicao(pid):
                    p = df_ped.loc[df_ped["pedido_id"] == pid].iloc[0]
                    return f"{p['data_lancamento']} | {p['cliente']} | {p['evento']} | {p['itens']} — R$ {p['total']:.2f}"

                pid_editar = st.selectbox(
                    "Selecione o pedido para editar",
                    pids_ed,
                    format_func=formata_pedido_edicao,
                    key="sel_editar_pedido",
                )

                ped_ed = df_ped.loc[df_ped["pedido_id"] == pid_editar].iloc[0]

                # opções de missão e cliente
                df_ev_ed = carregar_eventos(somente_ativos=False)
                opcoes_missao = df_ev_ed["nome"].tolist() if not df_ev_ed.empty else []
                if ped_ed["evento"] and ped_ed["evento"] not in opcoes_missao:
                    opcoes_missao = [ped_ed["evento"]] + opcoes_missao

                df_cli_ed = carregar_clientes(somente_ativos=False)
                opcoes_cliente = df_cli_ed["nome"].tolist() if not df_cli_ed.empty else []
                if ped_ed["cliente"] and ped_ed["cliente"] not in opcoes_cliente:
                    opcoes_cliente = [ped_ed["cliente"]] + opcoes_cliente

                with st.form("form_editar_pedido"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        novo_cliente = st.selectbox(
                            "Cliente",
                            opcoes_cliente,
                            index=opcoes_cliente.index(ped_ed["cliente"]) if ped_ed["cliente"] in opcoes_cliente else 0,
                        )
                        nova_missao = st.selectbox(
                            "Missão",
                            opcoes_missao,
                            index=opcoes_missao.index(ped_ed["evento"]) if ped_ed["evento"] in opcoes_missao else 0,
                        )
                    with ec2:
                        # data atual do pedido (dd/mm/aaaa -> date)
                        try:
                            data_atual = datetime.strptime(ped_ed["data_lancamento"], "%d/%m/%Y").date()
                        except Exception:
                            data_atual = hoje_br()
                        nova_data = st.date_input("Data", value=data_atual, format="DD/MM/YYYY")
                        nova_obs = st.text_input(
                            "Observação do pedido",
                            value=ped_ed["observacao"] if pd.notna(ped_ed["observacao"]) and ped_ed["observacao"] else "",
                        )

                    salvar_ed = st.form_submit_button("💾 Salvar alterações", type="primary")

                if salvar_ed:
                    sb.table("lancamentos").update({
                        "cliente": novo_cliente.strip().title(),
                        "evento": nova_missao,
                        "data_lancamento": nova_data.isoformat(),
                        "observacao": nova_obs.strip() or None,
                    }).eq("pedido_id", pid_editar).execute()
                    st.success(f"Pedido de {novo_cliente} atualizado!")
                    st.rerun()

        # exclusão LÓGICA por pedido (correção) - apaga o pedido inteiro
        if EH_ADMIN and not df_ped.empty:
            with st.expander("🗑️ Excluir um pedido (correção)"):
                pids = df_ped["pedido_id"].tolist()

                # rótulo amigável: mesmo formato do quadro de Pedidos
                def formata_pedido_exclusao(pid):
                    p = df_ped.loc[df_ped["pedido_id"] == pid].iloc[0]
                    return f"{p['data_lancamento']} | {p['cliente']} | {p['itens']} — R$ {p['total']:.2f}"

                pid_excluir = st.selectbox(
                    "Selecione o pedido para excluir",
                    pids,
                    format_func=formata_pedido_exclusao,
                )

                ped_sel = df_ped.loc[df_ped["pedido_id"] == pid_excluir].iloc[0]
                st.caption(
                    f"**Pedido selecionado:** {ped_sel['data_lancamento']} — {ped_sel['cliente']} — "
                    f"{ped_sel['itens']} — R$ {ped_sel['total']:.2f}"
                )

                motivo = st.text_input("Motivo da exclusão (obrigatório)")
                if st.button("Confirmar exclusão", type="secondary"):
                    if not motivo.strip():
                        st.error("Informe o motivo da exclusão.")
                    else:
                        # marca todos os itens do pedido como excluídos
                        sb.table("lancamentos").update(
                            {
                                "excluido": True,
                                "motivo_exclusao": motivo.strip(),
                                "excluido_por": PERFIL,
                                "excluido_em": datetime.now(TZ).isoformat(),
                            }
                        ).eq("pedido_id", pid_excluir).execute()
                        st.success(f"Pedido de {ped_sel['cliente']} excluído (fica guardado com o motivo).")
                        st.rerun()


# ============================================================
# TELA: RESUMO POR CLIENTE (todos os períodos)
# ============================================================
elif pagina == "📊 Resumo por cliente":
    st.markdown("### 📊 Resumo por cliente")
    st.caption("Considera todos os lançamentos, de todos os períodos.")

    dados_all = sb.table("lancamentos").select("*").eq("excluido", False).execute().data
    df_all = pd.DataFrame(dados_all)

    if df_all.empty:
        st.info("Nenhum lançamento registrado ainda.")
    else:
        if "valor_pago" not in df_all.columns:
            df_all["valor_pago"] = 0.0
        df_all["valor_pago"] = df_all["valor_pago"].fillna(0.0)
        df_all["pendente"] = (df_all["total"] - df_all["valor_pago"]).round(2).clip(lower=0)

        def fmt_moeda(v: float) -> str:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total geral", fmt_moeda(df_all["total"].sum()))
        m2.metric("Recebido", fmt_moeda(df_all["valor_pago"].sum()))
        m3.metric("⏳ A receber", fmt_moeda(df_all["pendente"].sum()))

        resumo = (
            df_all.groupby("cliente", as_index=False)[["total", "valor_pago", "pendente"]]
            .sum()
            .sort_values("pendente", ascending=False)
        )
        st.dataframe(
            resumo,
            hide_index=True,
            use_container_width=True,
            column_config={
                "cliente": st.column_config.TextColumn("Cliente"),
                "total": st.column_config.NumberColumn("Total (R$)", format="R$ %.2f"),
                "valor_pago": st.column_config.NumberColumn("Pago (R$)", format="R$ %.2f"),
                "pendente": st.column_config.NumberColumn("Devendo (R$)", format="R$ %.2f"),
            },
        )

# ============================================================
# TELA: GERAR COBRANÇA (WhatsApp) - pendências de todos os dias
# ============================================================
elif pagina == "📱 Gerar Cobrança":
    st.markdown("### 📱 Gerar Cobrança (WhatsApp)")
    st.caption("Levanta as pendências de todos os dias e produtos do cliente.")

    dados_all = sb.table("lancamentos").select("*").eq("excluido", False).execute().data
    df_all = pd.DataFrame(dados_all)

    if df_all.empty:
        st.info("Nenhum lançamento registrado ainda.")
    else:
        if "valor_pago" not in df_all.columns:
            df_all["valor_pago"] = 0.0
        df_all["valor_pago"] = df_all["valor_pago"].fillna(0.0)
        df_all["pendente"] = (df_all["total"] - df_all["valor_pago"]).round(2).clip(lower=0)
        df_all["data_fmt"] = pd.to_datetime(df_all["data_lancamento"]).dt.strftime("%d/%m/%Y")

        devedores = (
            df_all.loc[df_all["pendente"] > 0.001]
            .groupby("cliente")["pendente"].sum().sort_values(ascending=False)
        )
        if devedores.empty:
            st.success("Nenhum cliente com valor em aberto. 🎉")
        else:
            opcoes = [f"{c}  —  deve R$ {v:.2f}".replace(".", ",") for c, v in devedores.items()]
            escolha = st.selectbox("Cliente com pendência", opcoes)
            cli_cobrar = devedores.index[opcoes.index(escolha)]

            cfg = carregar_config()
            pix_chave = cfg.get("pix_chave", "")
            pix_nome = cfg.get("pix_nome", "")

            # itens em aberto do cliente, agrupados por data
            itens_cli = df_all.loc[
                (df_all["cliente"] == cli_cobrar) & (df_all["pendente"] > 0.001)
            ].sort_values("data_lancamento")
            linhas_msg = []
            for data_ped, sub in itens_cli.groupby("data_fmt"):
                linhas_msg.append(f"\n{data_ped}")
                for _, r in sub.iterrows():
                    valor_txt = f"{r['pendente']:.2f}".replace(".", ",")
                    linhas_msg.append(f"{int(r['quantidade'])} {r['produto']} {valor_txt}")
            total_aberto = itens_cli["pendente"].sum()

            saudacao = f"Paz {cli_cobrar}!\nBoa tarde!\n\nSua conta se encontra em aberto do consumo:"
            corpo = "\n".join(linhas_msg)
            fecho = f"\n\nTotal em aberto: R$ {total_aberto:.2f}".replace(".", ",")
            if pix_chave:
                fecho += (f"\n\nSe puder realizar o pix na chave {pix_chave}"
                          + (f" ({pix_nome})" if pix_nome else "")
                          + " e mandar o comprovante, agradecemos.\nDeus abençoe!!")
            mensagem = saudacao + "\n" + corpo + fecho

            mensagem_editada = st.text_area("Mensagem (pode editar antes de enviar)", value=mensagem, height=300)

            tel = telefone_do_cliente(cli_cobrar)
            col_w1, col_w2 = st.columns([1, 3])
            if tel:
                col_w1.link_button("📲 Abrir no WhatsApp", link_whatsapp(tel, mensagem_editada), use_container_width=True)
            else:
                col_w1.caption("Sem telefone")
                col_w2.caption("Cadastre o telefone do cliente na aba ⚙️ Configurações para liberar o botão. Você ainda pode copiar o texto acima.")
