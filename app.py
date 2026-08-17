# ============================================================
# Gerenciamento de Caixa - Lançamento de Cobranças
# Streamlit + Supabase
# ============================================================
import hashlib
import uuid
from html import escape as escapar_html
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client

TZ = ZoneInfo("America/Sao_Paulo")

LOGO = "EMB.png"  # logo na raiz do repositório
TEM_LOGO = Path(LOGO).exists()

st.set_page_config(
    page_title="Gerenciamento de Caixa",
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
        content: "Embaixada de Cristo";
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

    /* O components.html usado para travar as datas cria um iframe de
       altura zero; isso evita que ele deixe um espaco em branco na tela. */
    .stElementContainer:has(iframe[height="0"]),
    div[data-testid="stElementContainer"]:has(iframe[height="0"]) {{
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }}

    /* No celular, ao trazer um campo para o topo, deixa folga para o cabeçalho */
    @media (max-width: 640px) {{
        [data-testid="stSelectbox"],
        [data-testid="stNumberInput"],
        [data-testid="stTextInput"],
        [data-testid="stDateInput"],
        [data-testid="stTextArea"],
        [data-testid="stRadio"] {{
            scroll-margin-top: 5rem;
        }}
    }}

    /* Linha do carrinho: produto, qtde, unitário e total lado a lado */
    .linha-item {{
        display: flex;
        align-items: center;
        gap: 0.6rem;
        white-space: nowrap;
        line-height: 1.35;
    }}
    .linha-item .li-prod {{
        flex: 1 1 auto;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        font-weight: 600;
    }}
    .linha-item .li-qtd,
    .linha-item .li-uni {{ flex: 0 0 auto; opacity: 0.75; }}
    .linha-item .li-tot {{ flex: 0 0 auto; font-weight: 800; color: {AZUL}; }}
    .obs-item {{
        font-size: 0.78rem;
        opacity: 0.65;
        font-style: italic;
        margin-top: -0.2rem;
    }}

    /* No celular o Streamlit empilha as colunas; aqui força a linha única.
       O :has() mira só nos blocos que contêm um item do carrinho. */
    @media (max-width: 640px) {{
        .linha-item {{ font-size: 0.88rem; gap: 0.4rem; }}
        [data-testid="stHorizontalBlock"]:has(.linha-item) {{
            flex-wrap: nowrap !important;
            gap: 0.3rem !important;
            align-items: center;
        }}
        [data-testid="stHorizontalBlock"]:has(.linha-item) [data-testid="stColumn"] {{
            min-width: 0 !important;
        }}
    }}

    /* Titulo de secao (fica maior no celular) */
    .titulo-seccao {{
        color: {AZUL};
        font-weight: 800;
        font-size: 1.45rem;
        margin: 0.2rem 0 0.6rem 0;
    }}
    @media (max-width: 640px) {{
        .titulo-seccao {{ font-size: 1.75rem; }}
    }}
    .regua-seccao {{
        border: none;
        border-top: 3px solid {MAGENTA};
        margin: 1.4rem 0 0.8rem 0;
    }}

    /* Mascara os campos de senha SEM usar type="password".
       Assim o Chrome / Google Password Manager nao oferece gerar senha. */
    .st-key-campo_senha input,
    .st-key-campo_nova_senha input,
    .st-key-campo_reset_senha input,
    input[aria-label*="Senha de acesso"],
    input[aria-label*="Senha inicial"],
    input[aria-label*="Nova senha"] {{
        -webkit-text-security: disc;
        text-security: disc;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Bloqueio de digitação: TODOS os campos de data + o campo Qtde
#
# Datas: o st.date_input não expõe aria-label no <input>, então a trava é
# aplicada pelo container do widget (data-testid / data-baseweb), o que pega
# todas as datas do app — lançamento, filtros do extrato e edição de pedido.
# Um input readonly não abre o teclado do celular, mas continua recebendo
# clique — por isso o calendário segue funcionando normalmente.
#
# Qtde: identificado pelo aria-label, para NÃO travar Preço unit. / Valor extra.
# Aqui NÃO usamos readonly: o botão "próximo" (→) do teclado do celular pula
# campos readonly, e a equipe precisa que ele caia no Qtde. Sem o readonly o
# campo entra na navegação normalmente, e a digitação continua impossível
# graças ao inputmode='none' (não abre teclado) + bloqueio de keydown.
# ------------------------------------------------------------
SELETORES_DATA = [
    '[data-testid="stDateInput"] input',
    '[data-testid="stDateInputField"] input',
    '[data-baseweb="datepicker"] input',
    '.stDateInput input',
]
ROTULOS_SEM_TECLADO = ["Qtde"]


def bloquear_teclado():
    """Injeta o JS que impede digitação nas datas e na quantidade.
    Chamada uma única vez por execução, logo depois do menu."""
    seletores = ", ".join(f"'{s}'" for s in SELETORES_DATA)
    rotulos = ", ".join(f'"{r}"' for r in ROTULOS_SEM_TECLADO)
    components.html(
        f"""
        <script>
        const doc = window.parent.document;
        const SELETORES = [{seletores}];
        const ROTULOS = [{rotulos}];

        function semTeclado(el, comReadonly) {{
            // reaplicado sempre: o React remove o atributo ao redesenhar
            if (comReadonly) {{
                el.setAttribute('readonly', 'readonly');
            }} else {{
                el.removeAttribute('readonly');
            }}
            el.setAttribute('inputmode', 'none');
            el.setAttribute('autocomplete', 'off');
            el.style.caretColor = 'transparent';

            // Alguns teclados de Android (SwiftKey, Gboard) ignoram o readonly.
            // Barra a digitacao na origem — o clique que abre o calendario passa.
            if (!el.dataset.semDigitacao) {{
                el.addEventListener('keydown', e => {{
                    // libera apenas Tab e Esc, para nao prender a navegacao
                    if (e.key !== 'Tab' && e.key !== 'Escape') e.preventDefault();
                }});
                el.addEventListener('paste', e => e.preventDefault());
                el.addEventListener('drop', e => e.preventDefault());
                el.dataset.semDigitacao = '1';
            }}
        }}

        function travar() {{
            // datas: com readonly (mantem o calendario e nao sobe teclado)
            SELETORES.forEach(sel => {{
                doc.querySelectorAll(sel).forEach(el => semTeclado(el, true));
            }});
            // Qtde: SEM readonly, para nao ser pulada pelo "proximo" do celular
            doc.querySelectorAll('input').forEach(el => {{
                const rot = el.getAttribute('aria-label') || '';
                if (ROTULOS.includes(rot)) semTeclado(el, false);
                el.setAttribute('data-lpignore', 'true');
            }});
        }}

        travar();

        // o Streamlit redesenha a tela a cada interação -> reaplica,
        // com debounce de 1 frame para não pesar
        let agendado = false;
        const obs = new MutationObserver(() => {{
            if (agendado) return;
            agendado = true;
            requestAnimationFrame(() => {{ agendado = false; travar(); }});
        }});
        obs.observe(doc.body, {{childList: true, subtree: true}});
        </script>
        """,
        height=0,
    )


# ------------------------------------------------------------
# UX no celular: o campo que está sendo preenchido sobe para o topo
# ------------------------------------------------------------
LARGURA_MOBILE = 640

BLOCOS_CAMPO = (
    '[data-testid="stSelectbox"], [data-testid="stNumberInput"], '
    '[data-testid="stTextInput"], [data-testid="stDateInput"], '
    '[data-testid="stTextArea"], [data-testid="stRadio"]'
)


def ux_mobile():
    """Sobe para o topo da tela o campo que recebeu foco ou clique.

    Só age em telas estreitas. O clique também é observado porque o campo
    Qtde é readonly e os botões - / + não dão foco ao input.
    Os listeners são registrados uma única vez (marca em document.body).
    """
    components.html(
        f"""
        <script>
        const win = window.parent;
        const doc = win.document;
        const BLOCOS = '{BLOCOS_CAMPO}';

        function ehCelular() {{ return win.innerWidth <= {LARGURA_MOBILE}; }}

        function aoTopo(el) {{
            if (el) el.scrollIntoView({{block: 'start', behavior: 'smooth'}});
        }}

        function tratar(ev) {{
            if (!ehCelular()) return;
            const bloco = ev.target.closest(BLOCOS);
            if (bloco) setTimeout(() => aoTopo(bloco), 150);
        }}

        if (!doc.body.dataset.uxMobile) {{
            doc.addEventListener('focusin', tratar, true);
            doc.addEventListener('click', tratar, true);
            doc.body.dataset.uxMobile = '1';
        }}
        </script>
        """,
        height=0,
    )


def destacar_menu_colapsado():
    """Mostra um rótulo "MENU" ao lado da setinha que abre a barra lateral
    quando ela está fechada (comum no celular, onde a sidebar começa
    colapsada). O botão é interno do Streamlit e sua posição na tela varia
    (o container dele ocupa a altura toda da coluna da sidebar e centraliza
    o botão nela) — por isso usamos JS pra ler a posição real do botão em
    vez de tentar "grudar" nele só com CSS.
    """
    components.html(
        f"""
        <script>
        const win = window.parent;
        const doc = win.document;

        function posicionar() {{
            const barra = doc.querySelector('[data-testid="stSidebar"]');
            const fechada = barra && barra.getAttribute('aria-expanded') === 'false';
            const btn = doc.querySelector('[data-testid="stSidebarCollapsedControl"] button');
            let rotulo = doc.getElementById('rotulo-menu-emb');

            if (!fechada || !btn) {{
                if (rotulo) rotulo.style.display = 'none';
                return;
            }}
            if (!rotulo) {{
                rotulo = doc.createElement('div');
                rotulo.id = 'rotulo-menu-emb';
                rotulo.textContent = 'MENU';
                Object.assign(rotulo.style, {{
                    position: 'fixed',
                    zIndex: '999999',
                    background: '{AZUL_ESCURO}',
                    color: '#FFFFFF',
                    fontFamily: 'inherit',
                    fontSize: '0.72rem',
                    fontWeight: '800',
                    letterSpacing: '0.5px',
                    padding: '3px 10px',
                    borderRadius: '6px',
                    whiteSpace: 'nowrap',
                    pointerEvents: 'none',
                    boxShadow: '0 2px 6px rgba(0, 0, 0, 0.25)',
                }});
                doc.body.appendChild(rotulo);
            }}

            const r = btn.getBoundingClientRect();
            rotulo.style.display = 'block';
            rotulo.style.top = (r.top + r.height / 2 - rotulo.offsetHeight / 2) + 'px';
            rotulo.style.left = (r.right + 6) + 'px';
        }}

        posicionar();
        if (!doc.body.dataset.rotuloMenu) {{
            setInterval(posicionar, 300);
            win.addEventListener('resize', posicionar);
            win.addEventListener('scroll', posicionar, true);
            doc.body.dataset.rotuloMenu = '1';
        }}
        </script>
        """,
        height=0,
    )


def rolar_tela(alvo: str = "topo"):
    """Rola a tela depois de um rerun. alvo: 'topo' ou um seletor CSS."""
    if alvo == "topo":
        destino = "null"
    else:
        destino = f"doc.querySelector('{alvo}')"
    components.html(
        f"""
        <script>
        const win = window.parent;
        const doc = win.document;

        function rolar() {{
            const alvo = {destino};
            if (alvo) {{
                alvo.scrollIntoView({{block: 'start', behavior: 'smooth'}});
                return;
            }}
            // topo: cada versao do Streamlit usa um container de rolagem diferente
            [
                doc.querySelector('section[data-testid="stMain"]'),
                doc.querySelector('section.main'),
                doc.querySelector('[data-testid="stAppViewContainer"]'),
                doc.scrollingElement,
                doc.documentElement,
            ].forEach(el => {{
                if (el && el.scrollTo) el.scrollTo({{top: 0, behavior: 'smooth'}});
            }});
            win.scrollTo({{top: 0, behavior: 'smooth'}});
        }}

        // repete: o Streamlit ainda pode estar desenhando a tela
        setTimeout(rolar, 80);
        setTimeout(rolar, 350);
        </script>
        """,
        height=0,
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


# a conexao precisa existir antes do login, porque o login le a tabela 'usuarios'
sb = get_supabase()

# ------------------------------------------------------------
# Login por usuário (tabela 'usuarios' no Supabase)
# ------------------------------------------------------------
def gerar_hash(senha: str) -> str:
    """SHA-256 da senha + pepper guardado no st.secrets."""
    pepper = st.secrets.get("SENHA_PEPPER", "emb-lanchonete-2026")
    return hashlib.sha256((pepper + senha).encode("utf-8")).hexdigest()


@st.cache_data(ttl=30)
def carregar_usuarios(somente_ativos: bool = True) -> pd.DataFrame:
    q = sb.table("usuarios").select("*").order("nome")
    if somente_ativos:
        q = q.eq("ativo", True)
    return pd.DataFrame(q.execute().data)


def limpar_cache_usuarios():
    carregar_usuarios.clear()


def tela_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_esq, col_meio, col_dir = st.columns([1, 1.1, 1])

    with col_meio:
        with st.container(border=True):
            if TEM_LOGO:
                c_tit, c_logo = st.columns([4, 1])
                with c_tit:
                    st.markdown(
                        f"<h3 style='text-align:center; margin-bottom:0;'>Gerenciamento de Caixa</h3>"
                        f"<p style='text-align:center; color:{AZUL}; font-size:0.8rem;'>"
                        f"Sistema de Lançamento de Cobranças</p>",
                        unsafe_allow_html=True,
                    )
                with c_logo:
                    st.image(LOGO, width=60)
            else:
                st.markdown(
                    f"<h3 style='text-align:center; margin-bottom:0;'>🍔 Gerenciamento de Caixa</h3>"
                    f"<p style='text-align:center; color:{AZUL}; font-size:0.8rem;'>"
                    f"Sistema de Lançamento de Cobranças</p>",
                    unsafe_allow_html=True,
                )

            st.divider()

            try:
                df_users = carregar_usuarios(somente_ativos=True)
            except Exception as e:
                st.error(f"Erro ao ler a tabela de usuários: {e}")
                st.stop()

            if df_users.empty:
                st.error(
                    "Nenhum usuário ativo cadastrado. "
                    "Rode o SQL de criação da tabela `usuarios` no Supabase."
                )
                st.stop()

            with st.form("login_form"):
                nome_sel = st.selectbox("👤 Usuário:", df_users["nome"].tolist())
                senha = st.text_input("🔑 Senha de acesso:", key="campo_senha")
                entrar = st.form_submit_button(
                    "Entrar no Sistema", use_container_width=True, type="primary"
                )

            if entrar:
                linha = df_users.loc[df_users["nome"] == nome_sel]
                if not linha.empty and linha.iloc[0]["senha_hash"] == gerar_hash(senha):
                    st.session_state["logado"] = True
                    st.session_state["usuario"] = nome_sel
                    st.session_state["perfil"] = linha.iloc[0]["perfil"]
                    st.rerun()
                else:
                    st.error("Senha incorreta.")


if not st.session_state.get("logado"):
    tela_login()
    st.stop()

USUARIO = st.session_state.get("usuario", "")
PERFIL = st.session_state.get("perfil", "operador")

# admin  -> tudo, inclusive gerenciar usuários
# gestor -> tudo, menos gerenciar usuários
# operador -> lançamento, extrato e cadastro de clientes
EH_ADMIN = PERFIL in ("admin", "gestor")
PODE_USUARIOS = PERFIL == "admin"

AGORA = lambda: datetime.now(TZ).isoformat()

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

def carregar_abatimentos(somente_ativos: bool = True) -> pd.DataFrame:
    """Abatimentos/reembolsos: crédito lançado direto pro cliente (não é forma
    de pagamento de um pedido específico) — abate do total pendente dele."""
    q = sb.table("abatimentos").select("*")
    if somente_ativos:
        q = q.eq("excluido", False)
    dados = q.order("data", desc=True).execute().data
    return pd.DataFrame(dados)

# Formas de pagamento aceitas
FORMAS_PAGAMENTO = ["Dinheiro", "Pix", "Cartão Débito", "Cartão Crédito", "Bonificação"]

def fmt_moeda(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

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
    """Monta o PDF do fechamento com as visões dispostas em 2 colunas.

    Usa um layout de verdade em 2 colunas (BaseDocTemplate + Frames), em vez de
    empilhar tudo dentro de uma única célula de tabela: isso permite que o
    conteúdo flua e pagine automaticamente quando não cabe em uma página só,
    evitando o erro "Table too large ... too large on page" do ReportLab.
    """
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, FrameBreak,
                                    Table, TableStyle, Paragraph, Spacer, Image as RLImage)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    AZUL_RL = colors.HexColor("#0B3D91")
    MAGENTA_RL = colors.HexColor("#E6007E")
    AZUL_CLARO_RL = colors.HexColor("#EEF3FB")

    def moeda(v):
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    buf = BytesIO()

    margem = 12 * mm
    largura_pag, altura_pag = A4
    largura_util = largura_pag - 2 * margem
    altura_util = altura_pag - 2 * margem

    VAO = 6 * mm
    COL_W = (largura_util - VAO) / 2

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=styles["Title"], textColor=AZUL_RL, fontSize=16)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.grey, fontSize=9)
    sec = ParagraphStyle("sec", parent=styles["Heading3"], textColor=MAGENTA_RL, fontSize=10, spaceBefore=2, spaceAfter=2)

    # cabeçalho (logo + título + período) — monta primeiro para medir a altura
    # real que ele ocupa (o texto do período varia de tamanho conforme os
    # filtros de missão/cliente aplicados, então não dá pra "chutar" um valor
    # fixo aqui: se o cabeçalho não coubesse no espaço reservado, ele
    # transbordaria sozinho para a coluna esquerda e bagunçava o layout).
    if TEM_LOGO:
        try:
            cab = Table([[RLImage(LOGO, width=16 * mm, height=16 * mm),
                          Paragraph("Fechamento — Gerenciamento de Caixa", titulo)]],
                        colWidths=[20 * mm, None])
            cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        except Exception:
            cab = Paragraph("Fechamento — Gerenciamento de Caixa", titulo)
    else:
        cab = Paragraph("Fechamento — Gerenciamento de Caixa", titulo)
    par_periodo = Paragraph(periodo_txt, sub)

    _, altura_cab = cab.wrap(largura_util, altura_util)
    _, altura_periodo = par_periodo.wrap(largura_util, altura_util)
    ALTURA_CABECALHO = altura_cab + altura_periodo + 6 * mm  # + folga de segurança

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=margem, rightMargin=margem,
        topMargin=margem, bottomMargin=margem,
    )

    frame_cabecalho = Frame(
        margem, altura_pag - margem - ALTURA_CABECALHO, largura_util, ALTURA_CABECALHO,
        id="cabecalho", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=2,
    )
    frame_esq = Frame(
        margem, margem, COL_W, altura_util - ALTURA_CABECALHO,
        id="esq", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    frame_dir = Frame(
        margem + COL_W + VAO, margem, COL_W, altura_util - ALTURA_CABECALHO,
        id="dir", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([
        PageTemplate(id="Fechamento", frames=[frame_cabecalho, frame_esq, frame_dir]),
    ])

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
        return [Paragraph(titulo_txt, sec), tabela, Spacer(1, 4)]

    # monta cada seção como uma lista de flowables
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

    # cabeçalho vai no frame do topo; o restante das seções flui normalmente
    # pela coluna esquerda e, quando não couber mais, pela direita — e, se
    # ainda sobrar conteúdo, o ReportLab cria novas páginas sozinho.
    story = [cab, par_periodo, FrameBreak()]
    for s in secoes:
        story.extend(s)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ------------------------------------------------------------
# Navegação (menu conforme o perfil)
# ------------------------------------------------------------
# todos veem "Configurações", mas dentro dela só o cadastro de clientes
# fica liberado para o perfil operador.
MENU_USUARIO = ["🧾 Lançamento", "📋 Extrato", "⚙️ Configurações"]
MENU_ADMIN = ["🧾 Lançamento", "📋 Extrato", "🔄 Abatimento/Reembolso", "📑 Fechamento",
              "📊 Resumo por cliente", "📱 Gerar Cobrança", "⚙️ Configurações"]

with st.sidebar:
    st.caption(f"👤 Conectado como **{USUARIO}**")
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

# vale para todas as telas: nenhum campo de data aceita digitação
bloquear_teclado()
ux_mobile()
destacar_menu_colapsado()

# ============================================================
# TELA: CADASTROS (Produtos, Missões, Clientes)
# ============================================================
if pagina == "⚙️ Configurações":

    # ------------------------------------------------------------
    # Clientes — LIBERADO PARA TODOS OS USUÁRIOS
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # Daqui para baixo: só Administrador / Meiry (perfil admin ou gestor)
    # ------------------------------------------------------------
    if not EH_ADMIN:
        st.stop()

    st.divider()
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
    st.markdown("### 🎯 Missões")
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


    # ------------------------------------------------------------
    # Usuários do sistema (somente perfil admin)
    # ------------------------------------------------------------
    if PODE_USUARIOS:
        st.divider()
        st.markdown("### 👤 Usuários do sistema")

        cu1, cu2 = st.columns([1, 2])

        with cu1:
            st.markdown("**Novo usuário**")
            with st.form("form_usuario", clear_on_submit=True):
                nome_us = st.text_input("Nome")
                senha_us = st.text_input("Senha inicial", key="campo_nova_senha")
                perfil_us = st.selectbox(
                    "Perfil",
                    ["operador", "gestor", "admin"],
                    help="operador: lança, consulta e cadastra clientes  •  "
                         "gestor: tudo, menos gerenciar usuários  •  "
                         "admin: tudo",
                )
                salvar_us = st.form_submit_button(
                    "➕ Cadastrar", type="primary", use_container_width=True
                )
            if salvar_us:
                if not nome_us.strip() or not senha_us:
                    st.warning("Informe o nome e a senha inicial.")
                else:
                    try:
                        sb.table("usuarios").insert({
                            "nome": nome_us.strip().title(),
                            "senha_hash": gerar_hash(senha_us),
                            "perfil": perfil_us,
                        }).execute()
                        limpar_cache_usuarios()
                        st.success(f"Usuário **{nome_us.strip().title()}** criado!")
                        st.rerun()
                    except Exception as e:
                        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                            st.error("Já existe um usuário com esse nome.")
                        else:
                            st.error(f"Erro ao cadastrar: {e}")

        with cu2:
            st.markdown("**Usuários cadastrados**")
            df_us = carregar_usuarios(somente_ativos=False)
            if df_us.empty:
                st.info("Nenhum usuário cadastrado.")
            else:
                df_us_edit = st.data_editor(
                    df_us[["id", "nome", "perfil", "ativo"]],
                    hide_index=True,
                    use_container_width=True,
                    disabled=["id", "nome"],
                    column_config={
                        "id": st.column_config.NumberColumn("ID", width="small"),
                        "nome": st.column_config.TextColumn("Usuário"),
                        "perfil": st.column_config.SelectboxColumn(
                            "Perfil", options=["operador", "gestor", "admin"]
                        ),
                        "ativo": st.column_config.CheckboxColumn("Ativo"),
                    },
                    key="editor_usuarios",
                )
                if st.button("💾 Salvar usuários", key="btn_salvar_usuarios"):
                    alterados = 0
                    for _, row in df_us_edit.iterrows():
                        original = df_us.loc[df_us["id"] == row["id"]].iloc[0]
                        if (row["perfil"] != original["perfil"]
                                or bool(row["ativo"]) != bool(original["ativo"])):
                            if original["nome"] == "Administrador" and (
                                not bool(row["ativo"]) or row["perfil"] != "admin"
                            ):
                                st.warning("O usuário Administrador não pode ser inativado nem rebaixado.")
                                continue
                            sb.table("usuarios").update({
                                "perfil": str(row["perfil"]),
                                "ativo": bool(row["ativo"]),
                            }).eq("id", int(row["id"])).execute()
                            alterados += 1
                    limpar_cache_usuarios()
                    if alterados:
                        st.success(f"{alterados} usuário(s) atualizado(s)!")
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração detectada.")

                st.markdown("**🔑 Resetar senha**")
                cr1, cr2, cr3 = st.columns([2, 2, 1])
                with cr1:
                    us_reset = st.selectbox("Usuário", df_us["nome"].tolist(), key="sel_reset")
                with cr2:
                    nova_senha = st.text_input("Nova senha", key="campo_reset_senha")
                with cr3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Resetar", use_container_width=True, key="btn_reset_senha"):
                        if not nova_senha:
                            st.warning("Informe a nova senha.")
                        else:
                            sb.table("usuarios").update(
                                {"senha_hash": gerar_hash(nova_senha)}
                            ).eq("nome", us_reset).execute()
                            limpar_cache_usuarios()
                            st.success(f"Senha de **{us_reset}** atualizada!")

            st.caption(
                "💡 Prefira **inativar** em vez de excluir — assim o histórico da coluna "
                "*Lançado por* continua fazendo sentido."
            )



# ============================================================
# TELA: LANÇAMENTO
# ============================================================
elif pagina == "🧾 Lançamento":
    st.markdown(
        "<div class='titulo-seccao'>🧾 Novo Lançamento</div>",
        unsafe_allow_html=True,
    )

    df_prod = carregar_produtos(somente_ativos=True)
    if df_prod.empty:
        st.warning("Cadastre pelo menos um produto na aba **⚙️ Configurações** antes de lançar.")
        st.stop()

    precos = dict(zip(df_prod["nome"], df_prod["preco"].astype(float)))

    if "carrinho" not in st.session_state:
        st.session_state["carrinho"] = []

    # Contadores usados para LIMPAR os campos: ao incrementar, os widgets recebem
    # uma key nova e voltam ao valor default (é o jeito de "zerar" no Streamlit).
    st.session_state.setdefault("n_pedido", 0)   # cliente, obs, situação
    st.session_state.setdefault("n_item", 0)     # produto, qtde, preço, extra, obs do item
    NP = st.session_state["n_pedido"]
    NI = st.session_state["n_item"]

    # rolagem pedida pela ação anterior (salvar pedido / adicionar item)
    destino = st.session_state.pop("rolar", None)
    if destino:
        rolar_tela(destino)

    # mensagem do último salvamento (o st.rerun apagaria o st.success)
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))

    # --- dados do pedido ---
    df_ev = carregar_eventos(somente_ativos=True)
    lista_missoes = df_ev["nome"].tolist() if not df_ev.empty else ["Geral"]

    df_clientes = carregar_clientes(somente_ativos=True)
    if df_clientes.empty:
        st.warning("Cadastre pelo menos um cliente na aba **⚙️ Configurações** para prosseguir.")
        st.stop()
    lista_clientes = df_clientes["nome"].tolist()

    # Data primeiro: é o campo que a equipe confere antes de tudo no celular
    col_b, col_ev, col_a = st.columns([1, 1.2, 2])
    with col_b:
        data_lanc = st.date_input("Data", value=hoje_br(), format="DD/MM/YYYY")
    with col_ev:
        missao_sel = st.selectbox("🎯 Missão", lista_missoes)
    with col_a:
        cliente_sel = st.selectbox(
            "Cliente",
            lista_clientes,
            index=None,
            placeholder="Escolha...",
            key=f"sel_cliente_{NP}",
            help="Escolha um cliente previamente cadastrado.",
        )

    # --- adicionar itens ao pedido ---
    st.markdown(
        "<hr class='regua-seccao'>"
        "<div class='titulo-seccao' id='sec-produto'>🛒 Adicionar produto</div>",
        unsafe_allow_html=True,
    )
    
    # Qtde precisa de peso >= 1.1: abaixo disso o Streamlit esconde os botões - e +
    c1, c2, c3, c_extra, c4, c5 = st.columns([1.8, 1.15, 1.15, 1.15, 1.6, 1.15])
    with c1:
        produto_sel = st.selectbox(
            "Produto",
            df_prod["nome"].tolist(),
            index=None,
            placeholder="Escolha...",
            key=f"sel_produto_{NI}",
        )
    with c2:
        # somente os botões - e + (a digitação é bloqueada por bloquear_teclado)
        qtde = st.number_input(
            "Qtde", min_value=1, value=1, step=1, key=f"inp_qtde_{NI}",
            help="Use os botões - e + para ajustar a quantidade.",
        )
    with c3:
        preco_padrao = float(precos.get(produto_sel, 0.0)) if produto_sel else 0.0
        preco_unit = st.number_input(
            "Preço unit. (R$)",
            min_value=0.0,
            value=preco_padrao,
            step=0.50,
            format="%.2f",
            key=f"inp_preco_{NI}_{produto_sel}",
            disabled=not EH_ADMIN,
            help=None if EH_ADMIN
            else "Preço travado. Somente Administrador e Meiry podem alterar.",
        )
    with c_extra:
        # liberado para todos os perfis, por causa das exceções (bacon, borda...)
        preco_extra = st.number_input(
            "Valor extra (R$)",
            min_value=0.0,
            value=0.0,
            step=0.50,
            format="%.2f",
            key=f"inp_extra_{NI}_{produto_sel}",
            help="Bacon, borda recheada, etc."
        )
    with c4:
        obs_item = st.text_input(
            "Obs. do item",
            key=f"inp_obs_item_{NI}",
            placeholder="Ex: com bacon...",
        )
    with c5:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Adicionar", use_container_width=True):
            if not produto_sel:
                st.warning("Escolha um produto antes de adicionar.")
            else:
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
                # o item já foi para a lista abaixo -> limpa os campos de cima
                st.session_state["n_item"] += 1
                # leva a tela direto para a lista do pedido (total, situação e salvar)
                st.session_state["rolar"] = "#sec-itens"
                st.rerun()

    # --- carrinho ---
    carrinho = st.session_state["carrinho"]
    if carrinho:
        st.markdown(
            "<hr class='regua-seccao'>"
            "<div class='titulo-seccao' id='sec-itens'>📦 Itens do pedido</div>",
            unsafe_allow_html=True,
        )
        df_car = pd.DataFrame(carrinho)   # usado no total do pedido, mais abaixo

        for i, item in enumerate(carrinho):
            # duas colunas apenas: a linha completa + a lixeira.
            # o CSS acima impede que elas empilhem no celular.
            ic_linha, ic_lixo = st.columns([9, 1.2])

            extra = (
                f" <span class='li-uni'>(+{item['preco_extra']:.2f})</span>"
                if item.get("preco_extra", 0) > 0
                else ""
            )
            with ic_linha:
                st.markdown(
                    "<div class='linha-item'>"
                    f"<span class='li-prod'>{escapar_html(item['produto'])}</span>"
                    f"<span class='li-qtd'>x{item['quantidade']}</span>"
                    f"<span class='li-uni'>R$ {item['preco_unitario']:.2f}{extra}</span>"
                    f"<span class='li-tot'>R$ {item['total']:.2f}</span>"
                    "</div>"
                    + (
                        f"<div class='obs-item'>{escapar_html(item['obs_item'])}</div>"
                        if item.get("obs_item")
                        else ""
                    ),
                    unsafe_allow_html=True,
                )
            with ic_lixo:
                if st.button("🗑️", key=f"del_{i}", help="Remover este item"):
                    carrinho.pop(i)
                    st.rerun()

        observacao = st.text_input(
            "Observação do pedido (opcional)",
            placeholder="Ex.: pagar na sexta, entregar na mesa 3...",
            key=f"inp_obs_pedido_{NP}",
        )

        total_pedido = df_car["total"].sum()
        st.markdown(f"#### 💰 Total do pedido: R$ {total_pedido:.2f}")

        situacao = st.radio(
            "Situação do pagamento",
            ["✅ Pago", "⏳ Pendente", "💸 Parcial"],
            horizontal=True,
            help="Parcial: cliente pagou só uma parte agora; o restante fica como pendente no extrato.",
            key=f"rad_situacao_{NP}",
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
                key=f"inp_parcial_{NP}",
            )
            falta = total_pedido - valor_pago_input
            st.caption(f"Ficará **devendo R$ {falta:.2f}** deste pedido.")

        # Forma de pagamento aparece quando há recebimento agora (Pago ou Parcial).
        # Pendente não pede forma - ela será escolhida no extrato, na hora de receber.
        if situacao in ("✅ Pago", "💸 Parcial"):
            forma_pgto = st.selectbox(
                "Forma de pagamento", FORMAS_PAGAMENTO, key=f"sel_forma_{NP}"
            )

        @st.dialog("🧹 Limpar itens do pedido?")
        def confirmar_limpar_itens():
            st.write(
                f"Isso vai remover **{len(carrinho)} item(ns)** já adicionados a este "
                "pedido. Essa ação não pode ser desfeita."
            )
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("🧹 Sim, limpar", type="primary", use_container_width=True):
                    st.session_state["carrinho"] = []
                    st.session_state["n_item"] += 1
                    st.rerun()
            with cc2:
                if st.button("Cancelar", use_container_width=True):
                    st.rerun()

        col_s1, col_s2 = st.columns([1, 3])
        with col_s1:
            if st.button("✅ Salvar lançamento", type="primary", use_container_width=True):
                if not cliente_sel:
                    st.error("Selecione um cliente antes de salvar.")
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
                            "lancado_por": USUARIO,
                        }
                        for idx, it in enumerate(carrinho)
                    ]
                    try:
                        sb.table("lancamentos").insert(linhas).execute()
                        # volta a tela ao inicio: sem cliente, sem produto, sem itens
                        st.session_state["carrinho"] = []
                        st.session_state["n_pedido"] += 1
                        st.session_state["n_item"] += 1
                        st.session_state["rolar"] = "topo"
                        st.session_state["flash"] = (
                            f"Lançamento salvo para **{cliente_sel.strip().title()}** "
                            f"— R$ {total_pedido:.2f}. 🎉"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
        with col_s2:
            if st.button("🧹 Limpar itens"):
                confirmar_limpar_itens()
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

    modo_data = st.radio(
        "Filtrar por", ["Período", "Dia único"], horizontal=True, key="extrato_modo_data"
    )

    f1, f2, f3, f4, f5 = st.columns([1, 1, 1.4, 1.1, 1.1])
    if modo_data == "Dia único":
        with f1:
            dia_unico = st.date_input("Dia", value=hoje_br(), format="DD/MM/YYYY")
        data_ini = dia_unico
        data_fim = dia_unico
        with f2:
            st.caption("")  # mantém o alinhamento das colunas abaixo
    else:
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

        # ------------------------------------------------------------
        # Visão AGRUPADA POR PEDIDO (uma linha por pedido) — montada aqui
        # em cima porque as ações rápidas de editar/excluir (mais abaixo)
        # também precisam dela.
        # ------------------------------------------------------------
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
                "lancado_por": sub["lancado_por"].iloc[0] if "lancado_por" in sub.columns else "",
                "situacao": ("✅ Pago" if sub["pendente"].sum() <= 0.001
                             else ("💸 Parcial" if sub["valor_pago"].sum() > 0.001
                                   else "⏳ Pendente")),
            })
        df_ped = pd.DataFrame(grupos).sort_values(["situacao", "cliente"])

        # abatimentos/reembolsos do mesmo período (e cliente, se filtrado)
        # descontam do card "A receber" — não mexem no pendente de cada
        # pedido individual, só no total mostrado aqui.
        df_ab_extrato = carregar_abatimentos(somente_ativos=True)
        if not df_ab_extrato.empty:
            datas_ab_extrato = pd.to_datetime(df_ab_extrato["data"]).dt.date
            df_ab_extrato = df_ab_extrato.loc[
                (datas_ab_extrato >= data_ini) & (datas_ab_extrato <= data_fim)
            ]
            if cliente_filtro != "Todos":
                df_ab_extrato = df_ab_extrato.loc[df_ab_extrato["cliente"] == cliente_filtro]
            total_abatido_extrato = df_ab_extrato["valor"].sum()
        else:
            total_abatido_extrato = 0.0
        total_pendente_ajustado = round(max(total_pendente - total_abatido_extrato, 0.0), 2)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total no período", fmt_moeda(df_validos["total"].sum()))
        m2.metric("⏳ A receber", fmt_moeda(total_pendente_ajustado))
        m3.metric("Pedidos", df_validos["pedido_id"].nunique())
        m4.metric("Clientes", df_validos["cliente"].nunique())
        if total_abatido_extrato > 0.001:
            st.caption(f"(já descontado {fmt_moeda(total_abatido_extrato)} em abatimentos/reembolsos do período)")

        # ------------------------------------------------------------
        # Ações rápidas (editar / excluir pedido) — junto com os filtros,
        # no começo do relatório, pra facilitar correções.
        # ------------------------------------------------------------
        if EH_ADMIN and not df_ped.empty:
            col_ed, col_ex = st.columns(2)
            with col_ed:
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
                            "alterado_por": USUARIO,
                            "alterado_em": AGORA(),
                        }).eq("pedido_id", pid_editar).execute()
                        st.success(f"Pedido de {novo_cliente} atualizado!")
                        st.rerun()

            with col_ex:
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
                                    "excluido_por": USUARIO,
                                    "excluido_em": datetime.now(TZ).isoformat(),
                                }
                            ).eq("pedido_id", pid_excluir).execute()
                            st.success(f"Pedido de {ped_sel['cliente']} excluído (fica guardado com o motivo).")
                            st.rerun()

        # ------------------------------------------------------------
        # Tabela de pedidos do período filtrado
        # ------------------------------------------------------------
        st.markdown("#### 📦 Pedidos")

        st.dataframe(
            df_ped[["data_lancamento", "data_pagamento", "cliente", "evento", "itens",
                    "total", "valor_pago", "pendente", "situacao", "observacao",
                    "lancado_por"]],
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
                "lancado_por": st.column_config.TextColumn("Lançado por", width="small"),
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
                    "alterado_por": USUARIO,
                    "alterado_em": AGORA(),
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


# ============================================================
# TELA: ABATIMENTO/REEMBOLSO — crédito lançado direto no cliente,
# não é forma de pagamento de um pedido específico — só administrador
# ============================================================
elif pagina == "🔄 Abatimento/Reembolso":
    st.markdown("### 🔄 Abatimento / Reembolso")
    st.caption(
        "Use quando o cliente amortizar parte do valor pendente com produto, "
        "serviço ou outra compensação (sem passar pelo caixa). O valor entra "
        "aqui e abate automaticamente do total pendente do cliente nos relatórios."
    )

    cli_historico_ab = clientes_existentes_no_historico()
    df_cli_todos_ab = carregar_clientes(somente_ativos=False)
    cli_cadastrados_ab = df_cli_todos_ab["nome"].tolist() if not df_cli_todos_ab.empty else []
    lista_cli_ab = sorted(list(set(cli_historico_ab + cli_cadastrados_ab)))

    with st.form("form_abatimento", clear_on_submit=True):
        ab1, ab2, ab3 = st.columns([1, 1.6, 1])
        with ab1:
            data_ab = st.date_input("Data", value=hoje_br(), format="DD/MM/YYYY")
        with ab2:
            if lista_cli_ab:
                cliente_ab = st.selectbox("Cliente", lista_cli_ab)
            else:
                cliente_ab = st.text_input("Cliente")
        with ab3:
            valor_ab = st.number_input(
                "Valor do abatimento (R$)", min_value=0.0, step=0.50, format="%.2f"
            )
        obs_ab = st.text_input("Observação (opcional)", placeholder="Ex.: pagou com 2 marmitex")
        salvar_ab = st.form_submit_button("💾 Registrar abatimento", type="primary")

    if salvar_ab:
        if not cliente_ab:
            st.error("Selecione (ou digite) o cliente.")
        elif valor_ab <= 0:
            st.error("Informe um valor maior que zero.")
        else:
            sb.table("abatimentos").insert({
                "data": data_ab.isoformat(),
                "cliente": cliente_ab.strip().title(),
                "valor": round(valor_ab, 2),
                "observacao": obs_ab.strip() or None,
                "lancado_por": USUARIO,
                "criado_em": AGORA(),
            }).execute()
            st.success(f"Abatimento de {fmt_moeda(valor_ab)} registrado para {cliente_ab.strip().title()}.")
            st.rerun()

    st.divider()
    st.markdown("#### 📜 Abatimentos registrados")

    df_ab = carregar_abatimentos(somente_ativos=True)
    if df_ab.empty:
        st.info("Nenhum abatimento registrado ainda.")
    else:
        df_ab_show = df_ab.copy()
        df_ab_show["data_fmt"] = pd.to_datetime(df_ab_show["data"]).dt.strftime("%d/%m/%Y")
        total_abatido = df_ab["valor"].sum()
        st.caption(f"Total abatido (ativo): **{fmt_moeda(total_abatido)}**")

        st.dataframe(
            df_ab_show[["data_fmt", "cliente", "valor", "observacao", "lancado_por"]]
                .sort_values("data_fmt", ascending=False),
            hide_index=True,
            use_container_width=True,
            column_config={
                "data_fmt": st.column_config.TextColumn("Data"),
                "cliente": st.column_config.TextColumn("Cliente"),
                "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "observacao": st.column_config.TextColumn("Observação"),
                "lancado_por": st.column_config.TextColumn("Lançado por", width="small"),
            },
        )

        with st.expander("🗑️ Excluir um abatimento (correção)"):
            def formata_abatimento(row_id):
                r = df_ab.loc[df_ab["id"] == row_id].iloc[0]
                data_fmt = pd.to_datetime(r["data"]).strftime("%d/%m/%Y")
                return f"{data_fmt} | {r['cliente']} | R$ {r['valor']:.2f}"

            id_excluir_ab = st.selectbox(
                "Selecione o abatimento para excluir",
                df_ab["id"].tolist(),
                format_func=formata_abatimento,
                key="sel_excluir_abatimento",
            )
            motivo_ab = st.text_input("Motivo da exclusão (obrigatório)", key="motivo_abatimento")
            if st.button("Confirmar exclusão", type="secondary", key="excluir_abatimento_btn"):
                if not motivo_ab.strip():
                    st.error("Informe o motivo da exclusão.")
                else:
                    sb.table("abatimentos").update({
                        "excluido": True,
                        "motivo_exclusao": motivo_ab.strip(),
                        "excluido_por": USUARIO,
                        "excluido_em": datetime.now(TZ).isoformat(),
                    }).eq("id", int(id_excluir_ab)).execute()
                    st.success("Abatimento excluído (fica guardado com o motivo).")
                    st.rerun()

# ============================================================
# TELA: FECHAMENTO DO PERÍODO (resumos + PDF) — só administrador
# ============================================================
elif pagina == "📑 Fechamento":
    st.markdown("### 📑 Fechamento do período")

    df_ev_todos_fech = carregar_eventos(somente_ativos=False)
    lista_missao_fech = ["Todos"] + (
        df_ev_todos_fech["nome"].tolist() if not df_ev_todos_fech.empty else []
    )

    cli_historico_fech = clientes_existentes_no_historico()
    df_cli_todos_fech = carregar_clientes(somente_ativos=False)
    cli_cadastrados_fech = df_cli_todos_fech["nome"].tolist() if not df_cli_todos_fech.empty else []
    lista_cli_fech = ["Todos"] + sorted(list(set(cli_historico_fech + cli_cadastrados_fech)))

    modo_data_fech = st.radio(
        "Filtrar por", ["Período", "Dia único"], horizontal=True, key="fech_modo_data"
    )

    g1, g2, g3, g4 = st.columns([1, 1, 1.2, 1.2])
    if modo_data_fech == "Dia único":
        with g1:
            dia_fech = st.date_input("Dia", value=hoje_br(), format="DD/MM/YYYY", key="fech_dia")
        data_ini_fech = data_fim_fech = dia_fech
        with g2:
            st.caption("")  # mantém o alinhamento das colunas
    else:
        with g1:
            data_ini_fech = st.date_input(
                "De", value=hoje_br() - timedelta(days=30), format="DD/MM/YYYY", key="fech_de"
            )
        with g2:
            data_fim_fech = st.date_input(
                "Até", value=hoje_br(), format="DD/MM/YYYY", key="fech_ate"
            )
    with g3:
        cliente_filtro_fech = st.selectbox("Cliente", lista_cli_fech, key="fech_cliente")
    with g4:
        missao_filtro_fech = st.selectbox("Missão", lista_missao_fech, key="fech_missao")

    df_fech = carregar_lancamentos(
        data_ini_fech, data_fim_fech, cliente_filtro_fech, "Todos", missao_filtro_fech, False
    )

    if df_fech.empty:
        st.info("Nenhum lançamento encontrado com esses filtros.")
    else:
        if "valor_pago" not in df_fech.columns:
            df_fech["valor_pago"] = 0.0
        df_fech["valor_pago"] = df_fech["valor_pago"].fillna(0.0)
        df_fech["pendente"] = (df_fech["total"] - df_fech["valor_pago"]).round(2).clip(lower=0)
        df_validos_fech = df_fech.loc[~df_fech["excluido"]] if "excluido" in df_fech.columns else df_fech

        # --- período/legenda + botão de PDF logo abaixo dos filtros ---
        if data_ini_fech == data_fim_fech:
            periodo_txt = f"Dia: {data_fim_fech.strftime('%d/%m/%Y')}"
        else:
            periodo_txt = f"Período: {data_ini_fech.strftime('%d/%m/%Y')} a {data_fim_fech.strftime('%d/%m/%Y')}"
        if missao_filtro_fech != "Todos":
            periodo_txt += f"  •  Missão: {missao_filtro_fech}"
        if cliente_filtro_fech != "Todos":
            periodo_txt += f"  •  Cliente: {cliente_filtro_fech}"

        col_legenda, col_pdf = st.columns([4, 1.2])
        with col_legenda:
            st.caption(periodo_txt)

        st.divider()

        # 1) Recebido por forma de pagamento
        st.markdown("**💳 Recebido por forma de pagamento**")
        recebidos = df_validos_fech.loc[df_validos_fech["valor_pago"] > 0.001].copy()
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
            st.caption(f"Total recebido: **{fmt_moeda(total_receb)}**")

        # 2) Consumo por produto
        st.divider()
        st.markdown("**🍔 Consumo por produto**")
        por_produto = df_validos_fech.groupby("produto", as_index=False).agg(
            qtde=("quantidade", "sum"), total=("total", "sum")
        ).sort_values("total", ascending=False)
        total_consumo = df_validos_fech["total"].sum()
        por_produto_pdf = list(por_produto.itertuples(index=False, name=None))
        st.dataframe(
            por_produto, hide_index=True, use_container_width=True,
            column_config={
                "produto": st.column_config.TextColumn("Produto"),
                "qtde": st.column_config.NumberColumn("Qtde", format="%d"),
                "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
            },
        )
        st.caption(f"Total do consumo: **{fmt_moeda(total_consumo)}**")

        # Consumo por missão
        st.divider()
        st.markdown("**🎯 Consumo por missão**")
        por_missao = df_validos_fech.groupby("evento", as_index=False)["total"].sum().sort_values("total", ascending=False)
        total_missao = df_validos_fech["total"].sum()
        por_missao_pdf = list(por_missao.itertuples(index=False, name=None))
        st.dataframe(
            por_missao, hide_index=True, use_container_width=True,
            column_config={
                "evento": st.column_config.TextColumn("Missão"),
                "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
            },
        )
        st.caption(f"Total geral: **{fmt_moeda(total_missao)}**")

        # 3) Clientes que pagaram (total ou parcial)
        st.divider()
        st.markdown("**✅ Clientes que pagaram**")
        pagantes = (
            df_validos_fech.loc[df_validos_fech["valor_pago"] > 0.001]
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
            st.caption(f"Total pago: **{fmt_moeda(total_pago)}**")

        # 4) A receber por cliente (em aberto) — já descontando abatimentos
        # e reembolsos registrados nesse mesmo período/cliente
        st.divider()
        st.markdown("**⏳ A receber por cliente (em aberto)**")
        a_receber = (
            df_validos_fech.groupby("cliente", as_index=False)["pendente"].sum()
        )

        df_ab_fech = carregar_abatimentos(somente_ativos=True)
        if not df_ab_fech.empty:
            datas_ab_fech = pd.to_datetime(df_ab_fech["data"]).dt.date
            df_ab_fech = df_ab_fech.loc[
                (datas_ab_fech >= data_ini_fech) & (datas_ab_fech <= data_fim_fech)
            ]
            if cliente_filtro_fech != "Todos":
                df_ab_fech = df_ab_fech.loc[df_ab_fech["cliente"] == cliente_filtro_fech]
            abatido_por_cliente_fech = df_ab_fech.groupby("cliente")["valor"].sum()
        else:
            abatido_por_cliente_fech = pd.Series(dtype=float)

        a_receber["pendente"] = (
            a_receber["pendente"] - a_receber["cliente"].map(abatido_por_cliente_fech).fillna(0.0)
        ).round(2).clip(lower=0)
        a_receber = a_receber.loc[a_receber["pendente"] > 0.001].sort_values("pendente", ascending=False)

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
            st.caption(f"Total a receber: **{fmt_moeda(total_receber)}**")
            if abatido_por_cliente_fech.sum() > 0.001:
                st.caption(
                    f"(já descontado {fmt_moeda(abatido_por_cliente_fech.sum())} "
                    "em abatimentos/reembolsos do período)"
                )

        # --- gerar PDF com as visões acima ---
        with col_pdf:
            try:
                pdf_bytes = gerar_pdf_fechamento(
                    periodo_txt, por_forma_pdf, total_receb, por_produto_pdf,
                    total_consumo, pagantes_pdf, total_pago, a_receber_pdf, total_receber,
                    por_missao_pdf, total_missao,
                )
                prefixo_arquivo = "fechamento_dia" if data_ini_fech == data_fim_fech else "fechamento_periodo"
                st.download_button(
                    "📄 Baixar PDF",
                    data=pdf_bytes,
                    file_name=f"{prefixo_arquivo}_{data_fim_fech.strftime('%d-%m-%Y')}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Erro no PDF: {e}")

# ============================================================
# TELA: RESUMO POR CLIENTE (todos os períodos)
# ============================================================
elif pagina == "📊 Resumo por cliente":
    st.markdown("### 📊 Resumo por cliente")

    df_ev_todos_resumo = carregar_eventos(somente_ativos=False)
    lista_missao_resumo = ["Todos"] + (
        df_ev_todos_resumo["nome"].tolist() if not df_ev_todos_resumo.empty else []
    )

    col_modo, col_missao = st.columns([3, 1.3])
    with col_modo:
        modo_data_resumo = st.radio(
            "Filtrar por", ["Todos os períodos", "Período", "Dia único"],
            horizontal=True, key="resumo_modo_data",
        )
    with col_missao:
        missao_filtro_resumo = st.selectbox("Missão", lista_missao_resumo, key="resumo_missao")

    if modo_data_resumo == "Todos os períodos":
        data_ini_resumo = data_fim_resumo = None
        legenda_resumo = "Considera todos os lançamentos, de todos os períodos"
    elif modo_data_resumo == "Dia único":
        dia_resumo = st.date_input("Dia", value=hoje_br(), format="DD/MM/YYYY", key="resumo_dia")
        data_ini_resumo = data_fim_resumo = dia_resumo
        legenda_resumo = f"Lançamentos de {dia_resumo.strftime('%d/%m/%Y')}"
    else:
        rc1, rc2 = st.columns(2)
        with rc1:
            data_ini_resumo = st.date_input(
                "De", value=hoje_br() - timedelta(days=30), format="DD/MM/YYYY", key="resumo_de"
            )
        with rc2:
            data_fim_resumo = st.date_input(
                "Até", value=hoje_br(), format="DD/MM/YYYY", key="resumo_ate"
            )
        legenda_resumo = (
            f"Lançamentos de {data_ini_resumo.strftime('%d/%m/%Y')} "
            f"a {data_fim_resumo.strftime('%d/%m/%Y')}"
        )
    if missao_filtro_resumo != "Todos":
        legenda_resumo += f"  •  Missão: {missao_filtro_resumo}"
    st.caption(legenda_resumo + ".")

    if data_ini_resumo is None:
        dados_all = sb.table("lancamentos").select("*").eq("excluido", False).execute().data
        df_all = pd.DataFrame(dados_all)
        if missao_filtro_resumo != "Todos" and not df_all.empty and "evento" in df_all.columns:
            df_all = df_all.loc[df_all["evento"] == missao_filtro_resumo]
    else:
        df_all = carregar_lancamentos(
            data_ini_resumo, data_fim_resumo, "Todos", "Todos", missao_filtro_resumo, False
        )

    if df_all.empty:
        if data_ini_resumo is None and missao_filtro_resumo == "Todos":
            st.info("Nenhum lançamento registrado ainda.")
        else:
            st.info("Nenhum lançamento encontrado com esses filtros.")
    else:
        if "valor_pago" not in df_all.columns:
            df_all["valor_pago"] = 0.0
        df_all["valor_pago"] = df_all["valor_pago"].fillna(0.0)
        df_all["pendente"] = (df_all["total"] - df_all["valor_pago"]).round(2).clip(lower=0)

        def fmt_moeda(v: float) -> str:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        resumo = (
            df_all.groupby("cliente", as_index=False)[["total", "valor_pago", "pendente"]]
            .sum()
        )

        # abate os abatimentos/reembolsos registrados (crédito direto no
        # cliente, fora do fluxo de pagamento de um pedido específico)
        df_ab_resumo = carregar_abatimentos(somente_ativos=True)
        if not df_ab_resumo.empty:
            if data_ini_resumo is not None:
                datas_ab = pd.to_datetime(df_ab_resumo["data"]).dt.date
                df_ab_resumo = df_ab_resumo.loc[
                    (datas_ab >= data_ini_resumo) & (datas_ab <= data_fim_resumo)
                ]
            abatido_por_cliente = df_ab_resumo.groupby("cliente")["valor"].sum()
        else:
            abatido_por_cliente = pd.Series(dtype=float)

        resumo["abatido"] = resumo["cliente"].map(abatido_por_cliente).fillna(0.0).round(2)
        resumo["pendente"] = (resumo["pendente"] - resumo["abatido"]).round(2).clip(lower=0)
        resumo = resumo.sort_values("pendente", ascending=False)

        m1, m2, m3 = st.columns(3)
        m1.metric("Total geral", fmt_moeda(df_all["total"].sum()))
        m2.metric("Recebido", fmt_moeda(df_all["valor_pago"].sum()))
        m3.metric("⏳ A receber", fmt_moeda(resumo["pendente"].sum()))
        if resumo["abatido"].sum() > 0.001:
            st.caption(f"(já descontado {fmt_moeda(resumo['abatido'].sum())} em abatimentos/reembolsos)")

        st.dataframe(
            resumo[["cliente", "total", "valor_pago", "abatido", "pendente"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "cliente": st.column_config.TextColumn("Cliente"),
                "total": st.column_config.NumberColumn("Total (R$)", format="R$ %.2f"),
                "valor_pago": st.column_config.NumberColumn("Pago (R$)", format="R$ %.2f"),
                "abatido": st.column_config.NumberColumn("Abatido (R$)", format="R$ %.2f"),
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

            saudacao = f"Paz, {cli_cobrar}!\n\nSua conta se encontra em aberto do consumo:"
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
