# App do celular (pasta docs)

App instalável (PWA) para lançar pedidos e comandas da lanchonete pelo celular.
Usa o **mesmo banco** do sistema do navegador (o `app.py` deste repositório), então tudo
que é lançado aqui aparece lá na hora, e vice-versa.

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `index.html` | As telas (login, Lançar, Comandas, Hoje, Config.) |
| `style.css` | Visual (cores Molicenter, layout de celular) |
| `app.js` | A lógica: chama o banco, monta as listas, carrinho, pagamento |
| `config.js` | Endereço do Supabase e a chave **pública** |
| `manifest.json` | Nome, ícone e cores do app instalado |
| `sw.js` | Service worker: permite instalar e abrir com internet ruim |
| `icons/` | Ícones e logo |
| `../sql_mobile/01_funcoes_mobile.sql` (fora do docs, não é publicado) | Funções do banco que o app usa (já aplicado no projeto Diversos) |

## Segurança

A chave em `config.js` é a pública (publishable). Ela **não lê nenhuma tabela** (RLS ligado, sem
policies). Tudo passa pelas funções `mob_*` do banco, que exigem login com usuário e senha (os mesmos
do sistema do navegador). Operador não altera preço nem remove itens; Config. só para admin.

## Como atualizar

1. Edite o arquivo aqui no GitHub (ícone de lápis) e clique em **Commit changes**.
2. Em ~1 minuto o GitHub Pages publica. No celular, feche e abra o app (às vezes 2 vezes).
3. Ao mexer no visual ou na lógica, aumente a `VERSAO` em `config.js` e o `CACHE` em `sw.js`
   (ex.: `caixa-emb-v2`) para forçar o celular a pegar a versão nova.
