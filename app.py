# ============================================================
# Lanchonete da Igreja - Lançamento de Cobranças
# Streamlit + Supabase
# ============================================================
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from supabase import create_client, Client

TZ = ZoneInfo("America/Sao_Paulo")

st.set_page_config(
    page_title="Lanchonete da Igreja",
    page_icon="🍔",
    layout="wide",
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
    st.markdown("## 🍔 Lanchonete da Igreja")
    st.caption("Sistema de lançamento de cobranças")

    # st.form evita race condition no login (lição aprendida no Despesas-Comp)
    with st.form("login_form"):
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", use_container_width=True, type="primary")

    if entrar:
        if senha == st.secrets["APP_SENHA"]:
            st.session_state["logado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")


if not st.session_state.get("logado"):
    tela_login()
    st.stop()

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


def carregar_lancamentos(
    data_ini: date, data_fim: date, cliente: str | None, situacao: str = "Todos"
) -> pd.DataFrame:
    q = (
        sb.table("lancamentos")
        .select("*")
        .gte("data_lancamento", data_ini.isoformat())
        .lte("data_lancamento", data_fim.isoformat())
        .order("criado_em", desc=True)
    )
    if cliente and cliente != "Todos":
        q = q.eq("cliente", cliente)
    if situacao == "⏳ Pendentes":
        q = q.eq("pago", False)
    elif situacao == "✅ Pagos":
        q = q.eq("pago", True)
    return pd.DataFrame(q.execute().data)


def clientes_existentes() -> list[str]:
    dados = sb.table("lancamentos").select("cliente").execute().data
    return sorted({d["cliente"] for d in dados})


# ------------------------------------------------------------
# Navegação
# ------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🍔 Lanchonete")
    pagina = st.radio(
        "Menu",
        ["🧾 Lançamento", "📋 Extrato", "🛒 Produtos"],
        label_visibility="collapsed",
    )
    st.divider()
    if st.button("Sair", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ============================================================
# TELA: CADASTRO DE PRODUTOS
# ============================================================
if pagina == "🛒 Produtos":
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

            if st.button("💾 Salvar alterações", type="primary"):
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

# ============================================================
# TELA: LANÇAMENTO
# ============================================================
elif pagina == "🧾 Lançamento":
    st.markdown("### 🧾 Novo Lançamento")

    df_prod = carregar_produtos(somente_ativos=True)
    if df_prod.empty:
        st.warning("Cadastre pelo menos um produto na tela **Produtos** antes de lançar.")
        st.stop()

    precos = dict(zip(df_prod["nome"], df_prod["preco"].astype(float)))

    if "carrinho" not in st.session_state:
        st.session_state["carrinho"] = []

    # --- dados do cliente ---
    clientes = clientes_existentes()
    col_a, col_b = st.columns([2, 1])
    with col_a:
        opcao_cliente = st.selectbox(
            "Cliente",
            ["✏️ Digitar novo cliente..."] + clientes,
            help="Escolha um cliente já usado ou digite um novo.",
        )
        if opcao_cliente == "✏️ Digitar novo cliente...":
            cliente = st.text_input("Nome do cliente")
        else:
            cliente = opcao_cliente
    with col_b:
        data_lanc = st.date_input("Data", value=hoje_br(), format="DD/MM/YYYY")

    st.divider()

    # --- adicionar itens ao pedido ---
    st.markdown("**Adicionar produto ao pedido**")
    c1, c2, c3, c4 = st.columns([3, 1, 1.5, 1.5])
    with c1:
        produto_sel = st.selectbox("Produto", df_prod["nome"].tolist(), key="sel_produto")
    with c2:
        qtde = st.number_input("Qtde", min_value=0.5, value=1.0, step=0.5, key="inp_qtde")
    with c3:
        preco_padrao = precos.get(produto_sel, 0.0)
        preco_unit = st.number_input(
            "Preço unit. (R$)",
            min_value=0.0,
            value=preco_padrao,
            step=0.50,
            format="%.2f",
            key=f"inp_preco_{produto_sel}",  # muda a key -> recarrega o preço do cadastro
            help="Vem do cadastro, mas pode alterar.",
        )
    with c4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Adicionar", use_container_width=True):
            st.session_state["carrinho"].append(
                {
                    "produto": produto_sel,
                    "quantidade": qtde,
                    "preco_unitario": preco_unit,
                    "total": round(qtde * preco_unit, 2),
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
            ic1.write(item["produto"])
            ic2.write(f"x {item['quantidade']:g}")
            ic3.write(f"R$ {item['preco_unitario']:.2f}")
            ic4.write(f"**R$ {item['total']:.2f}**")
            if ic5.button("🗑️", key=f"del_{i}"):
                carrinho.pop(i)
                st.rerun()

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
                if not cliente or not cliente.strip():
                    st.error("Informe o nome do cliente.")
                else:
                    pedido_id = uuid.uuid4().hex[:8]
                    esta_pago = situacao == "✅ Pago"
                    linhas = [
                        {
                            "pedido_id": pedido_id,
                            "cliente": cliente.strip().title(),
                            "produto": it["produto"],
                            "quantidade": it["quantidade"],
                            "preco_unitario": it["preco_unitario"],
                            "data_lancamento": data_lanc.isoformat(),
                            "pago": esta_pago,
                            "data_pagamento": data_lanc.isoformat() if esta_pago else None,
                        }
                        for it in carrinho
                    ]
                    try:
                        sb.table("lancamentos").insert(linhas).execute()
                        st.session_state["carrinho"] = []
                        st.success(f"Lançamento salvo para **{cliente.strip().title()}**! 🎉")
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

    f1, f2, f3, f4 = st.columns([1, 1, 1.5, 1.2])
    with f1:
        data_ini = st.date_input("De", value=hoje_br() - timedelta(days=30), format="DD/MM/YYYY")
    with f2:
        data_fim = st.date_input("Até", value=hoje_br(), format="DD/MM/YYYY")
    with f3:
        cliente_filtro = st.selectbox("Cliente", ["Todos"] + clientes_existentes())
    with f4:
        situacao_filtro = st.selectbox("Situação", ["Todos", "⏳ Pendentes", "✅ Pagos"])

    df = carregar_lancamentos(data_ini, data_fim, cliente_filtro, situacao_filtro)

    if df.empty:
        st.info("Nenhum lançamento encontrado nesse período.")
    else:
        df["data_lancamento"] = pd.to_datetime(df["data_lancamento"]).dt.strftime("%d/%m/%Y")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total no período", f"R$ {df['total'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        m2.metric("Lançamentos (itens)", len(df))
        m3.metric("Clientes", df["cliente"].nunique())

        st.dataframe(
            df[["data_lancamento", "cliente", "produto", "quantidade", "preco_unitario", "total", "pedido_id"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "data_lancamento": st.column_config.TextColumn("Data"),
                "cliente": st.column_config.TextColumn("Cliente"),
                "produto": st.column_config.TextColumn("Produto"),
                "quantidade": st.column_config.NumberColumn("Qtde", format="%g"),
                "preco_unitario": st.column_config.NumberColumn("Preço Unit.", format="R$ %.2f"),
                "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                "pedido_id": st.column_config.TextColumn("Pedido", width="small"),
            },
        )

        # resumo por cliente
        if cliente_filtro == "Todos":
            with st.expander("📊 Resumo por cliente"):
                resumo = (
                    df.groupby("cliente", as_index=False)["total"]
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

        # exclusão de lançamento (correção de erro)
        with st.expander("🗑️ Excluir um lançamento (correção)"):
            ids = df["id"].tolist()
            id_excluir = st.selectbox("ID do lançamento", ids)
            linha = df.loc[df["id"] == id_excluir].iloc[0]
            st.caption(
                f"{linha['data_lancamento']} — {linha['cliente']} — {linha['produto']} "
                f"x{linha['quantidade']:g} — R$ {linha['total']:.2f}"
            )
            if st.button("Confirmar exclusão", type="secondary"):
                sb.table("lancamentos").delete().eq("id", int(id_excluir)).execute()
                st.success("Lançamento excluído.")
                st.rerun()
