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


# ------------------------------------------------------------
# Navegação (menu conforme o perfil)
# ------------------------------------------------------------
MENU_USUARIO = ["🧾 Lançamento", "📋 Extrato"]
MENU_ADMIN = ["🧾 Lançamento", "📋 Extrato", "⚙️ Cadastros"]

with st.sidebar:
    st.markdown("## Lanchonete" if TEM_LOGO else "## 🍔 Lanchonete")
    st.caption(f"👤 Perfil: **{PERFIL}**")
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
if pagina == "⚙️ Cadastros":
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
            salvar_cli = st.form_submit_button("➕ Cadastrar cliente", type="primary", use_container_width=True)
        if salvar_cli:
            if not nome_cli.strip():
                st.warning("Informe o nome do cliente.")
            else:
                try:
                    sb.table("clientes").insert({"nome": nome_cli.strip().title()}).execute()
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
            df_cli_edit = st.data_editor(
                df_cli[["id", "nome", "ativo"]],
                hide_index=True,
                use_container_width=True,
                disabled=["id"],
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "nome": st.column_config.TextColumn("Cliente"),
                    "ativo": st.column_config.CheckboxColumn("Ativo"),
                },
                key="editor_clientes",
            )
            if st.button("💾 Salvar clientes", key="btn_salvar_clientes"):
                alterados = 0
                for _, row in df_cli_edit.iterrows():
                    original = df_cli.loc[df_cli["id"] == row["id"]].iloc[0]
                    if row["nome"] != original["nome"] or bool(row["ativo"]) != bool(original["ativo"]):
                        sb.table("clientes").update(
                            {"nome": str(row["nome"]).strip(), "ativo": bool(row["ativo"])}
                        ).eq("id", int(row["id"])).execute()
                        alterados += 1
                limpar_cache_clientes()
                if alterados:
                    st.success(f"{alterados} cliente(s) atualizado(s)!")
                    st.rerun()
                else:
                    st.info("Nenhuma alteração detectada.")


# ============================================================
# TELA: LANÇAMENTO
# ============================================================
elif pagina == "🧾 Lançamento":
    st.markdown("### 🧾 Novo Lançamento")

    df_prod = carregar_produtos(somente_ativos=True)
    if df_prod.empty:
        st.warning("Cadastre pelo menos um produto na aba **⚙️ Cadastros** antes de lançar.")
        st.stop()

    precos = dict(zip(df_prod["nome"], df_prod["preco"].astype(float)))

    if "carrinho" not in st.session_state:
        st.session_state["carrinho"] = []

    # --- dados do pedido ---
    df_ev = carregar_eventos(somente_ativos=True)
    lista_missoes = df_ev["nome"].tolist() if not df_ev.empty else ["Geral"]

    df_clientes = carregar_clientes(somente_ativos=True)
    if df_clientes.empty:
        st.warning("Cadastre pelo menos um cliente na aba **⚙️ Cadastros** para prosseguir.")
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
            ["✅ Pago", "⏳ Pendente"],
            horizontal=True,
            help="Se ficar pendente, dá pra marcar como pago depois, na tela de Extrato.",
        )

        col_s1, col_s2 = st.columns([1, 3])
        with col_s1:
            if st.button("✅ Salvar lançamento", type="primary", use_container_width=True):
                if not cliente_sel or not cliente_sel.strip():
                    st.error("Selecione um cliente.")
                else:
                    pedido_id = uuid.uuid4().hex[:8]
                    esta_pago = situacao == "✅ Pago"
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
                            "data_pagamento": data_lanc.isoformat() if esta_pago else None,
                            "lancado_por": PERFIL,
                        }
                        for it in carrinho
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

    ver_excluidos = False
    if EH_ADMIN:
        ver_excluidos = st.checkbox("Mostrar também os lançamentos excluídos")

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
            
        df["situacao"] = df["pago"].map({True: "✅ Pago", False: "⏳ Pendente"})
        if "excluido" in df.columns:
            df.loc[df["excluido"], "situacao"] = "🚫 Excluído"

        def fmt_moeda(v: float) -> str:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        df_validos = df.loc[~df["excluido"]] if "excluido" in df.columns else df
        total_pendente = df_validos.loc[~df_validos["pago"], "total"].sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total no período", fmt_moeda(df_validos["total"].sum()))
        m2.metric("⏳ Pendente", fmt_moeda(total_pendente))
        m3.metric("Lançamentos (itens)", len(df_validos))
        m4.metric("Clientes", df_validos["cliente"].nunique())

        st.dataframe(
            df[["data_lancamento", "data_pagamento", "cliente", "evento", "produto", "obs_item", "quantidade",
                "preco_unitario", "total", "situacao", "observacao", "motivo_exclusao", "pedido_id"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "data_lancamento": st.column_config.TextColumn("Data Lanç."),
                "data_pagamento": st.column_config.TextColumn("Data Pgto"),
                "cliente": st.column_config.TextColumn("Cliente"),
                "evento": st.column_config.TextColumn("Missão"),
                "produto": st.column_config.TextColumn("Produto"),
                "obs_item": st.column_config.TextColumn("Obs. Item"),
                "quantidade": st.column_config.NumberColumn("Qtde", format="%d"),
                "preco_unitario": st.column_config.NumberColumn("Preço Unit.", format="R$ %.2f"),
                "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                "situacao": st.column_config.TextColumn("Situação"),
                "observacao": st.column_config.TextColumn("Obs. Pedido"),
                "motivo_exclusao": st.column_config.TextColumn("Motivo Exclusão"),
                "pedido_id": st.column_config.TextColumn("Pedido", width="small"),
            },
        )

        # --- marcar pendentes como pagos (somente administrador) ---
        df_pend = df_validos.loc[~df_validos["pago"]]
        if EH_ADMIN and not df_pend.empty:
            st.markdown("#### ⏳ Pendentes — marcar como pago")
            pedidos_pend = (
                df_pend.groupby(["pedido_id", "cliente", "data_lancamento"], as_index=False)
                .agg(itens=("produto", lambda s: ", ".join(s)), total=("total", "sum"))
                .sort_values("cliente")
            )
            for _, ped in pedidos_pend.iterrows():
                p1, p2, p3, p4, p5 = st.columns([1.5, 1.2, 3, 1.2, 1.5])
                p1.write(f"**{ped['cliente']}**")
                p2.write(ped["data_lancamento"])
                p3.write(ped["itens"])
                p4.write(f"**{fmt_moeda(ped['total'])}**")
                if p5.button("✔️ Marcar pago", key=f"pg_{ped['pedido_id']}"):
                    sb.table("lancamentos").update(
                        {"pago": True, "data_pagamento": hoje_br().isoformat()}
                    ).eq("pedido_id", ped["pedido_id"]).execute()
                    st.success(f"Pedido de {ped['cliente']} marcado como pago!")
                    st.rerun()

            if cliente_filtro != "Todos":
                if st.button(f"✅ Marcar TODOS os pendentes de {cliente_filtro} como pagos", type="primary"):
                    sb.table("lancamentos").update(
                        {"pago": True, "data_pagamento": hoje_br().isoformat()}
                    ).eq("cliente", cliente_filtro).eq("pago", False).eq("excluido", False).execute()
                    st.success(f"Todos os pendentes de {cliente_filtro} foram quitados!")
                    st.rerun()

        # resumo por cliente
        if cliente_filtro == "Todos":
            with st.expander("📊 Resumo por cliente"):
                resumo = (
                    df_validos.groupby("cliente", as_index=False)["total"]
                    .sum()
                    .sort_values("total", ascending=False)
                )
                st.dataframe(
                    resumo,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "cliente": st.column_config.TextColumn("Cliente"),
                        "total": st.column_config.NumberColumn("Total (R$)", format="R$ %.2f"),
                    },
                )

        # exclusão LÓGICA de lançamento
        if EH_ADMIN and not df_validos.empty:
            with st.expander("🗑️ Excluir um lançamento (correção)"):
                ids = df_validos["id"].tolist()
                id_excluir = st.selectbox("ID do lançamento", ids)
                linha = df_validos.loc[df_validos["id"] == id_excluir].iloc[0]
                st.caption(
                    f"{linha['data_lancamento']} — {linha['cliente']} — {linha['produto']} "
                    f"x{linha['quantidade']:g} — R$ {linha['total']:.2f}"
                )
                motivo = st.text_input("Motivo da exclusão (obrigatório)")
                if st.button("Confirmar exclusão", type="secondary"):
                    if not motivo.strip():
                        st.error("Informe o motivo da exclusão.")
                    else:
                        sb.table("lancamentos").update(
                            {
                                "excluido": True,
                                "motivo_exclusao": motivo.strip(),
                                "excluido_por": PERFIL,
                                "excluido_em": datetime.now(TZ).isoformat(),
                            }
                        ).eq("id", int(id_excluir)).execute()
                        st.success("Lançamento excluído (o registro fica guardado com o motivo).")
                        st.rerun()
