# 🍔 Lanchonete da Igreja — Lançamento de Cobranças

Sistema simples em **Streamlit + Supabase** para lançar as cobranças da lanchonete.

## Telas
1. **Login** — senha única (definida em `secrets.toml`)
2. **🧾 Lançamento** — escolhe o cliente, adiciona vários produtos (preço vem do cadastro, mas pode ser alterado) e salva o pedido
3. **📋 Extrato** — todos os lançamentos, com filtro por data e cliente, resumo por cliente e exclusão para correção
4. **🛒 Produtos** — cadastro de produtos (nome/preço), edição direto na tabela e inativação sem perder histórico

## Passo a passo para colocar no ar

### 1. Supabase
- Criar um projeto novo (grátis) em https://supabase.com
- Abrir o **SQL Editor** e rodar o conteúdo de `setup_supabase.sql`
- Em **Settings > API**, copiar a `URL` e a `service_role key`

### 2. GitHub
- Criar um repositório e subir: `app.py`, `requirements.txt`, `setup_supabase.sql`, `.gitignore`, `README.md`
- **NÃO subir** o `.streamlit/secrets.toml`

### 3. Streamlit Cloud
- New app → apontar para o repositório → `app.py`
- Em **Advanced settings > Secrets**, colar:

```toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_SERVICE_KEY = "sua-service-role-key"
APP_SENHA = "emb123"
```

### 4. Rodar local (opcional)
```bash
pip install -r requirements.txt
streamlit run app.py
```
(preencher antes o `.streamlit/secrets.toml`)
