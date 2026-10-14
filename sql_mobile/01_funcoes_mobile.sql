-- ============================================================
-- App Mobile da Lanchonete (Caixa EMB) — funções seguras
-- Projeto Supabase: Diversos
--
-- O app do celular usa a chave PÚBLICA (anon). Ela não enxerga
-- nenhuma tabela (RLS ligado, sem policies). Tudo passa por estas
-- funções mob_*, que conferem a sessão do usuário antes de ler
-- ou gravar. O Streamlit continua com a SERVICE_KEY, sem mudança.
-- ============================================================

-- ---------- tabelas de apoio (privadas) ----------
create table if not exists public.mob_sessoes (
  token      uuid primary key default gen_random_uuid(),
  usuario    text not null,
  criado_em  timestamptz not null default now(),
  expira_em  timestamptz not null
);
create table if not exists public.mob_segredos (
  chave text primary key,
  valor text not null
);
create table if not exists public.mob_tentativas (
  id      bigserial primary key,
  usuario text,
  em      timestamptz not null default now(),
  ok      boolean not null
);
alter table public.mob_sessoes    enable row level security;
alter table public.mob_segredos   enable row level security;
alter table public.mob_tentativas enable row level security;
revoke all on public.mob_sessoes, public.mob_segredos, public.mob_tentativas from anon, authenticated;

-- mesmo "pepper" do st.secrets["SENHA_PEPPER"] do Streamlit
-- (se no secrets estiver outro valor, é só atualizar esta linha)
insert into public.mob_segredos (chave, valor)
values ('senha_pepper', 'emb-lanchonete-2026')
on conflict (chave) do nothing;

-- ---------- helper interno: valida a sessão ----------
create or replace function public._mob_usuario(p_token uuid)
returns public.usuarios
language plpgsql security definer set search_path = public as $$
declare u public.usuarios;
begin
  select us.* into u
  from public.mob_sessoes s
  join public.usuarios us on us.nome = s.usuario and us.ativo
  where s.token = p_token and s.expira_em > now();
  if not found then
    raise exception 'SESSAO_INVALIDA';
  end if;
  return u;
end $$;

create or replace function public._mob_eh_admin(u public.usuarios)
returns boolean language sql immutable as $$
  select u.perfil in ('admin', 'gestor')
$$;

-- ---------- helper interno: fecha uma comanda ----------
-- Mesma regra do fechar_comanda() do Streamlit.
create or replace function public._mob_fechar(
  p_pedido_id text, p_situacao text, p_valor_pago numeric,
  p_forma text, p_observacao text, p_usuario text
) returns numeric
language plpgsql security definer set search_path = public as $$
declare
  r record;
  v_total numeric;
  v_restante numeric;
  v_valor numeric;
  v_obs text;
  v_n int;
  v_i int := 0;
  v_hoje date := (now() at time zone 'America/Sao_Paulo')::date;
begin
  if p_situacao not in ('pago', 'pendente', 'parcial') then
    raise exception 'Situação inválida';
  end if;
  if p_situacao in ('pago', 'parcial') and
     (p_forma is null or p_forma not in ('Dinheiro','Pix','Cartão Débito','Cartão Crédito','Bonificação')) then
    raise exception 'Escolha a forma de pagamento';
  end if;

  select count(*), coalesce(sum(quantidade * preco_unitario), 0)
    into v_n, v_total
  from public.lancamentos
  where pedido_id = p_pedido_id and status = 'aberta' and not excluido;
  if v_n = 0 then
    raise exception 'Comanda não encontrada ou já fechada';
  end if;

  if p_situacao = 'parcial' and (coalesce(p_valor_pago, 0) <= 0 or p_valor_pago > v_total) then
    raise exception 'Valor parcial deve ser maior que zero e até o total';
  end if;

  -- nota digitada agora tem prioridade; senão reaproveita a última registrada
  v_obs := nullif(btrim(coalesce(p_observacao, '')), '');
  if v_obs is null then
    select observacao into v_obs from public.lancamentos
    where pedido_id = p_pedido_id and status = 'aberta' and not excluido and observacao is not null
    order by id limit 1;
  end if;

  v_restante := round(coalesce(p_valor_pago, 0), 2);
  for r in
    select id, round(quantidade * preco_unitario, 2) as tot
    from public.lancamentos
    where pedido_id = p_pedido_id and status = 'aberta' and not excluido
    order by id
  loop
    v_i := v_i + 1;
    if p_situacao = 'pago' then
      v_valor := r.tot;
    elsif p_situacao = 'parcial' then
      if v_i = v_n then
        v_valor := v_restante;
      else
        v_valor := round(least(r.tot, v_restante), 2);
        v_restante := round(v_restante - v_valor, 2);
      end if;
    else
      v_valor := 0;
    end if;

    update public.lancamentos set
      status          = 'fechada',
      pago            = (p_situacao = 'pago'),
      valor_pago      = v_valor,
      forma_pagamento = case when p_situacao in ('pago','parcial') then p_forma end,
      data_pagamento  = case when p_situacao = 'pago' then v_hoje end,
      observacao      = v_obs,
      alterado_por    = p_usuario,
      alterado_em     = now()
    where id = r.id;
  end loop;

  return round(v_total, 2);
end $$;

-- ============================================================
-- Funções públicas (chamadas pelo app via /rest/v1/rpc/...)
-- ============================================================

-- lista de usuários ativos para a tela de login (só os nomes)
create or replace function public.mob_usuarios()
returns json language sql security definer set search_path = public as $$
  select coalesce(json_agg(nome order by nome), '[]'::json)
  from public.usuarios where ativo
$$;

-- login: confere a senha com o MESMO hash do Streamlit
create or replace function public.mob_login(p_nome text, p_senha text)
returns json language plpgsql security definer set search_path = public, extensions as $$
declare
  u public.usuarios;
  v_pepper text;
  v_falhas int;
  v_token uuid;
begin
  select count(*) into v_falhas from public.mob_tentativas
  where usuario = p_nome and not ok and em > now() - interval '15 minutes';
  if v_falhas >= 5 then
    return json_build_object('erro', 'Muitas tentativas erradas. Aguarde 15 minutos.');
  end if;

  select valor into v_pepper from public.mob_segredos where chave = 'senha_pepper';
  select * into u from public.usuarios where nome = p_nome and ativo;

  if not found or u.senha_hash <> encode(extensions.digest(v_pepper || coalesce(p_senha, ''), 'sha256'), 'hex') then
    insert into public.mob_tentativas (usuario, ok) values (p_nome, false);
    return json_build_object('erro', 'Senha incorreta.');
  end if;

  insert into public.mob_tentativas (usuario, ok) values (p_nome, true);
  delete from public.mob_sessoes where expira_em < now();
  delete from public.mob_tentativas where em < now() - interval '30 days';

  insert into public.mob_sessoes (usuario, expira_em)
  values (u.nome, now() + interval '30 days')
  returning token into v_token;

  return json_build_object('token', v_token, 'usuario', u.nome, 'perfil', u.perfil);
end $$;

create or replace function public.mob_logout(p_token uuid)
returns void language sql security definer set search_path = public as $$
  delete from public.mob_sessoes where token = p_token
$$;

-- cadastros para montar a tela (produtos, missões, clientes)
create or replace function public.mob_dados(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
declare u public.usuarios;
begin
  u := public._mob_usuario(p_token);
  return json_build_object(
    'usuario', u.nome,
    'perfil', u.perfil,
    'admin', public._mob_eh_admin(u),
    'hoje', (now() at time zone 'America/Sao_Paulo')::date,
    'produtos', (select coalesce(json_agg(json_build_object('nome', nome, 'preco', preco) order by nome), '[]')
                 from public.produtos where ativo),
    'missoes',  (select coalesce(json_agg(nome order by nome), '[]') from public.eventos where ativo),
    'clientes', (select coalesce(json_agg(nome order by nome), '[]') from public.clientes where ativo),
    'formas',   json_build_array('Dinheiro','Pix','Cartão Débito','Cartão Crédito','Bonificação')
  );
end $$;

-- comandas abertas (com itens)
create or replace function public.mob_comandas(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_usuario(p_token);
  return (
    select coalesce(json_agg(c order by c.aberta_desde), '[]')
    from (
      select pedido_id,
             min(cliente) as cliente,
             min(evento) as evento,
             min(data_lancamento) as data_lancamento,
             min(criado_em) as aberta_desde,
             round(sum(quantidade * preco_unitario), 2) as total,
             json_agg(json_build_object(
               'id', id, 'produto', produto, 'quantidade', quantidade,
               'preco_unitario', preco_unitario, 'obs_item', obs_item,
               'lancado_por', lancado_por,
               'total', round(quantidade * preco_unitario, 2)
             ) order by id) as itens
      from public.lancamentos
      where status = 'aberta' and not excluido
      group by pedido_id
    ) c
  );
end $$;

-- lança itens: entra na comanda aberta do cliente (ou cria uma)
-- p_itens: [{"produto":"X","quantidade":2,"preco_unitario":10,"preco_extra":0,"obs_item":""}]
-- p_fechar (opcional): {"situacao":"pago|pendente|parcial","valor_pago":0,"forma":"Pix"}
create or replace function public.mob_lancar(
  p_token uuid, p_cliente text, p_missao text, p_data date,
  p_observacao text, p_itens jsonb, p_fechar jsonb default null
) returns json
language plpgsql security definer set search_path = public as $$
declare
  u public.usuarios;
  v_admin boolean;
  v_pedido text;
  v_missao text;
  v_data date;
  it jsonb;
  v_preco_cad numeric;
  v_preco numeric;
  v_extra numeric;
  v_qtd int;
  v_total numeric;
begin
  u := public._mob_usuario(p_token);
  v_admin := public._mob_eh_admin(u);

  if not exists (select 1 from public.clientes where nome = p_cliente and ativo) then
    raise exception 'Cliente não encontrado';
  end if;
  if jsonb_typeof(coalesce(p_itens, '[]'::jsonb)) <> 'array' then
    raise exception 'Itens inválidos';
  end if;
  if jsonb_array_length(coalesce(p_itens, '[]'::jsonb)) = 0 and p_fechar is null then
    raise exception 'Nenhum item para lançar';
  end if;

  -- evita duas comandas do mesmo cliente se dois celulares lançarem juntos
  perform pg_advisory_xact_lock(hashtext('mob_cliente:' || p_cliente));

  select pedido_id, evento, data_lancamento into v_pedido, v_missao, v_data
  from public.lancamentos
  where cliente = p_cliente and status = 'aberta' and not excluido
  order by id limit 1;

  if v_pedido is null then
    if not exists (select 1 from public.eventos where nome = p_missao and ativo) then
      raise exception 'Escolha a missão';
    end if;
    v_pedido := substr(replace(gen_random_uuid()::text, '-', ''), 1, 8);
    v_missao := p_missao;
    v_data   := coalesce(p_data, (now() at time zone 'America/Sao_Paulo')::date);
  end if;

  for it in select * from jsonb_array_elements(coalesce(p_itens, '[]'::jsonb)) loop
    select preco into v_preco_cad from public.produtos where nome = it->>'produto' and ativo;
    if not found then
      raise exception 'Produto não encontrado: %', it->>'produto';
    end if;
    v_qtd := (it->>'quantidade')::int;
    if v_qtd is null or v_qtd < 1 then
      raise exception 'Quantidade inválida';
    end if;
    -- operador não altera preço: vale o do cadastro
    v_preco := case when v_admin then coalesce((it->>'preco_unitario')::numeric, v_preco_cad) else v_preco_cad end;
    v_extra := greatest(coalesce((it->>'preco_extra')::numeric, 0), 0);
    if v_preco < 0 then raise exception 'Preço inválido'; end if;

    insert into public.lancamentos (
      pedido_id, cliente, evento, produto, quantidade, preco_unitario,
      obs_item, observacao, data_lancamento, status, pago, valor_pago,
      forma_pagamento, data_pagamento, lancado_por
    ) values (
      v_pedido, p_cliente, v_missao, it->>'produto', v_qtd, v_preco + v_extra,
      nullif(btrim(coalesce(it->>'obs_item', '')), ''),
      nullif(btrim(coalesce(p_observacao, '')), ''),
      v_data, 'aberta', false, 0, null, null, u.nome
    );
  end loop;

  if p_fechar is not null then
    v_total := public._mob_fechar(
      v_pedido, p_fechar->>'situacao', (p_fechar->>'valor_pago')::numeric,
      p_fechar->>'forma', p_observacao, u.nome);
    return json_build_object('pedido_id', v_pedido, 'fechada', true, 'total', v_total);
  end if;

  select round(sum(quantidade * preco_unitario), 2) into v_total
  from public.lancamentos where pedido_id = v_pedido and status = 'aberta' and not excluido;
  return json_build_object('pedido_id', v_pedido, 'fechada', false, 'total', v_total);
end $$;

-- fecha uma comanda já aberta (tela Comandas)
create or replace function public.mob_fechar_comanda(
  p_token uuid, p_pedido_id text, p_situacao text,
  p_valor_pago numeric, p_forma text, p_observacao text
) returns json
language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_total numeric;
begin
  u := public._mob_usuario(p_token);
  v_total := public._mob_fechar(p_pedido_id, p_situacao, p_valor_pago, p_forma, p_observacao, u.nome);
  return json_build_object('pedido_id', p_pedido_id, 'total', v_total);
end $$;

-- remover item / cancelar comanda aberta: só admin (igual ao Streamlit)
create or replace function public.mob_remover_item(p_token uuid, p_item_id bigint)
returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios;
begin
  u := public._mob_usuario(p_token);
  if not public._mob_eh_admin(u) then raise exception 'Somente administrador'; end if;
  delete from public.lancamentos where id = p_item_id and status = 'aberta';
end $$;

create or replace function public.mob_cancelar_comanda(p_token uuid, p_pedido_id text)
returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios;
begin
  u := public._mob_usuario(p_token);
  if not public._mob_eh_admin(u) then raise exception 'Somente administrador'; end if;
  delete from public.lancamentos where pedido_id = p_pedido_id and status = 'aberta';
end $$;

-- cadastro rápido de cliente (operadores também podem, igual ao Streamlit)
create or replace function public.mob_novo_cliente(p_token uuid, p_nome text, p_telefone text)
returns json language plpgsql security definer set search_path = public as $$
declare v_nome text := initcap(btrim(coalesce(p_nome, '')));
begin
  perform public._mob_usuario(p_token);
  if v_nome = '' then raise exception 'Informe o nome do cliente'; end if;
  if exists (select 1 from public.clientes where lower(nome) = lower(v_nome)) then
    raise exception 'Já existe um cliente com esse nome';
  end if;
  insert into public.clientes (nome, telefone) values (v_nome, nullif(btrim(coalesce(p_telefone, '')), ''));
  return json_build_object('nome', v_nome);
end $$;

-- resumo de um dia (só leitura): pedidos fechados naquela data
create or replace function public.mob_resumo_dia(p_token uuid, p_data date)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_usuario(p_token);
  return (
    with l as (
      select * from public.lancamentos
      where data_lancamento = p_data and status = 'fechada' and not excluido
    ), ped as (
      select pedido_id, min(cliente) cliente, min(evento) evento,
             round(sum(quantidade * preco_unitario), 2) total,
             round(sum(coalesce(valor_pago, 0)), 2) pago,
             min(forma_pagamento) forma, min(lancado_por) lancado_por,
             max(criado_em) criado_em,
             string_agg(round(quantidade)::text || 'x ' || produto, ', ' order by id) itens
      from l group by pedido_id
    )
    select json_build_object(
      'data', p_data,
      'total', coalesce((select sum(total) from ped), 0),
      'recebido', coalesce((select sum(pago) from ped), 0),
      'pendente', coalesce((select sum(total - pago) from ped), 0),
      'n_pedidos', (select count(*) from ped),
      'por_forma', (select coalesce(json_agg(json_build_object('forma', forma, 'valor', v) order by v desc), '[]')
                    from (select coalesce(forma_pagamento, 'Pendente') forma,
                                 round(sum(case when forma_pagamento is null then quantidade*preco_unitario - coalesce(valor_pago,0) else coalesce(valor_pago,0) end), 2) v
                          from l group by 1) f),
      'pedidos', (select coalesce(json_agg(ped order by criado_em desc), '[]') from ped)
    )
  );
end $$;

-- ---------- permissões ----------
revoke execute on function public._mob_usuario(uuid) from public, anon, authenticated;
revoke execute on function public._mob_eh_admin(public.usuarios) from public, anon, authenticated;
revoke execute on function public._mob_fechar(text, text, numeric, text, text, text) from public, anon, authenticated;

grant execute on function
  public.mob_usuarios(),
  public.mob_login(text, text),
  public.mob_logout(uuid),
  public.mob_dados(uuid),
  public.mob_comandas(uuid),
  public.mob_lancar(uuid, text, text, date, text, jsonb, jsonb),
  public.mob_fechar_comanda(uuid, text, text, numeric, text, text),
  public.mob_remover_item(uuid, bigint),
  public.mob_cancelar_comanda(uuid, text),
  public.mob_novo_cliente(uuid, text, text),
  public.mob_resumo_dia(uuid, date)
to anon, authenticated;

-- ============================================================
-- Configurações (somente admin: Administrador e Meiry)
-- ============================================================
create or replace function public.mob_config_listar(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
declare u public.usuarios;
begin
  u := public._mob_usuario(p_token);
  if not public._mob_eh_admin(u) then raise exception 'Somente administrador'; end if;
  return json_build_object(
    'produtos', (select coalesce(json_agg(json_build_object('id', id, 'nome', nome, 'preco', preco, 'ativo', ativo) order by nome), '[]') from public.produtos),
    'missoes',  (select coalesce(json_agg(json_build_object('id', id, 'nome', nome, 'ativo', ativo) order by nome), '[]') from public.eventos),
    'clientes', (select coalesce(json_agg(json_build_object('id', id, 'nome', nome, 'telefone', telefone, 'ativo', ativo) order by nome), '[]') from public.clientes)
  );
end $$;

create or replace function public.mob_salvar_produto(p_token uuid, p_id bigint, p_nome text, p_preco numeric, p_ativo boolean)
returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_nome text := btrim(coalesce(p_nome, ''));
begin
  u := public._mob_usuario(p_token);
  if not public._mob_eh_admin(u) then raise exception 'Somente administrador'; end if;
  if v_nome = '' then raise exception 'Informe o nome do produto'; end if;
  if coalesce(p_preco, -1) < 0 then raise exception 'Preço inválido'; end if;
  if exists (select 1 from public.produtos where lower(nome) = lower(v_nome) and id is distinct from p_id) then
    raise exception 'Já existe um produto com esse nome';
  end if;
  if p_id is null then
    insert into public.produtos (nome, preco, ativo) values (v_nome, p_preco, coalesce(p_ativo, true));
  else
    update public.produtos set nome = v_nome, preco = p_preco, ativo = coalesce(p_ativo, true) where id = p_id;
  end if;
end $$;

create or replace function public.mob_salvar_missao(p_token uuid, p_id bigint, p_nome text, p_ativo boolean)
returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_nome text := btrim(coalesce(p_nome, ''));
begin
  u := public._mob_usuario(p_token);
  if not public._mob_eh_admin(u) then raise exception 'Somente administrador'; end if;
  if v_nome = '' then raise exception 'Informe o nome da missão'; end if;
  if p_id is null then v_nome := initcap(v_nome); end if;
  if exists (select 1 from public.eventos where lower(nome) = lower(v_nome) and id is distinct from p_id) then
    raise exception 'Já existe uma missão com esse nome';
  end if;
  if p_id is null then
    insert into public.eventos (nome, ativo) values (v_nome, coalesce(p_ativo, true));
  else
    update public.eventos set nome = v_nome, ativo = coalesce(p_ativo, true) where id = p_id;
  end if;
end $$;

create or replace function public.mob_salvar_cliente(p_token uuid, p_id bigint, p_nome text, p_telefone text, p_ativo boolean)
returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_nome text := btrim(coalesce(p_nome, ''));
begin
  u := public._mob_usuario(p_token);
  if not public._mob_eh_admin(u) then raise exception 'Somente administrador'; end if;
  if v_nome = '' then raise exception 'Informe o nome do cliente'; end if;
  if p_id is null then v_nome := initcap(v_nome); end if;
  if exists (select 1 from public.clientes where lower(nome) = lower(v_nome) and id is distinct from p_id) then
    raise exception 'Já existe um cliente com esse nome';
  end if;
  if p_id is null then
    insert into public.clientes (nome, telefone, ativo) values (v_nome, nullif(btrim(coalesce(p_telefone, '')), ''), coalesce(p_ativo, true));
  else
    update public.clientes set nome = v_nome, telefone = nullif(btrim(coalesce(p_telefone, '')), ''), ativo = coalesce(p_ativo, true) where id = p_id;
  end if;
end $$;

grant execute on function
  public.mob_config_listar(uuid),
  public.mob_salvar_produto(uuid, bigint, text, numeric, boolean),
  public.mob_salvar_missao(uuid, bigint, text, boolean),
  public.mob_salvar_cliente(uuid, bigint, text, text, boolean)
to anon, authenticated;
