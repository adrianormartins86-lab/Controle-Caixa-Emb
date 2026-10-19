-- ============================================================
-- App Mobile da Lanchonete (Caixa EMB) — FASE 1 da migração
-- Extrato, Pagamentos Pendentes e Gerar Cobrança
-- Projeto Supabase: Diversos
--
-- Todas as funções exigem login E perfil administrador
-- (Administrador e Meiry). Regras copiadas do app.py (Streamlit).
-- ============================================================

-- ---------- helper interno: barra quem não é admin ----------
create or replace function public._mob_admin(p_token uuid)
returns public.usuarios
language plpgsql security definer set search_path = public as $$
declare u public.usuarios;
begin
  u := public._mob_usuario(p_token);
  if not public._mob_eh_admin(u) then
    raise exception 'Somente administrador';
  end if;
  return u;
end $$;

-- ---------- helper interno: grava o total pago de um pedido ----------
-- Mesma regra do registrar_pagamento_pedido() do Streamlit:
-- distribui o valor entre as linhas (mais antiga primeiro), a última
-- linha fica com o restante; data_pagamento = hoje só se quitou tudo.
create or replace function public._mob_pagar(
  p_pedido_id text, p_valor_pago numeric, p_forma text, p_usuario text
) returns numeric
language plpgsql security definer set search_path = public as $$
declare
  r record;
  v_total numeric;
  v_n int;
  v_i int := 0;
  v_restante numeric := round(coalesce(p_valor_pago, 0), 2);
  v_item numeric;
  v_quitou boolean;
  v_hoje date := (now() at time zone 'America/Sao_Paulo')::date;
begin
  if p_forma is not null and p_forma not in ('Dinheiro','Pix','Cartão Débito','Cartão Crédito','Bonificação') then
    raise exception 'Forma de pagamento inválida';
  end if;

  select count(*), round(coalesce(sum(total), 0), 2) into v_n, v_total
  from public.lancamentos
  where pedido_id = p_pedido_id and status = 'fechada' and not excluido;
  if v_n = 0 then raise exception 'Pedido não encontrado'; end if;
  if v_restante < 0 or v_restante > v_total + 0.001 then
    raise exception 'Valor pago deve ficar entre zero e o total do pedido (%)', v_total;
  end if;
  v_quitou := v_restante >= v_total - 0.001;

  for r in
    select id, round(total, 2) as tot from public.lancamentos
    where pedido_id = p_pedido_id and status = 'fechada' and not excluido
    order by id
  loop
    v_i := v_i + 1;
    if v_i = v_n then
      v_item := v_restante;
    else
      v_item := round(least(r.tot, v_restante), 2);
      v_restante := round(v_restante - v_item, 2);
    end if;
    update public.lancamentos set
      valor_pago      = v_item,
      pago            = v_item >= r.tot - 0.001,
      data_pagamento  = case when v_quitou then v_hoje end,
      forma_pagamento = coalesce(p_forma, forma_pagamento),
      alterado_por    = p_usuario,
      alterado_em     = now()
    where id = r.id;
  end loop;
  return v_total;
end $$;

-- ============================================================
-- Listas para os filtros (clientes do histórico + cadastrados, todas as missões)
-- ============================================================
create or replace function public.mob_admin_listas(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_admin(p_token);
  return json_build_object(
    'clientes', (select coalesce(json_agg(nome order by nome), '[]') from (
                   select cliente as nome from public.lancamentos where not excluido and cliente is not null
                   union
                   select nome from public.clientes) c),
    'missoes',  (select coalesce(json_agg(nome order by nome), '[]') from public.eventos)
  );
end $$;

-- ============================================================
-- EXTRATO: pedidos fechados do período, agrupados
-- p_situacao: 'todos' | 'pendentes' | 'pagos'  (filtro por linha, igual ao Streamlit)
-- ============================================================
create or replace function public.mob_extrato(
  p_token uuid, p_ini date, p_fim date, p_cliente text, p_missao text, p_situacao text
) returns json language plpgsql security definer set search_path = public as $$
declare
  v_cli text := nullif(btrim(coalesce(p_cliente, '')), '');
  v_mis text := nullif(btrim(coalesce(p_missao, '')), '');
  v_sit text := coalesce(nullif(p_situacao, ''), 'todos');
  v_abat numeric;
begin
  perform public._mob_admin(p_token);

  -- abatimentos/reembolsos do período (e do cliente, se filtrado)
  -- descontam só do card "A receber"
  select round(coalesce(sum(valor), 0), 2) into v_abat
  from public.abatimentos
  where not coalesce(excluido, false) and data between p_ini and p_fim
    and (v_cli is null or cliente = v_cli);

  return (
    with l as (
      select * from public.lancamentos
      where status = 'fechada' and not excluido
        and data_lancamento between p_ini and p_fim
        and (v_cli is null or cliente = v_cli)
        and (v_mis is null or evento = v_mis)
        and (v_sit = 'todos' or (v_sit = 'pendentes' and not pago) or (v_sit = 'pagos' and pago))
    ), ped as (
      select pedido_id,
             (array_agg(cliente order by id))[1] as cliente,
             (array_agg(evento order by id))[1] as evento,
             min(data_lancamento) as data_lancamento,
             max(data_pagamento) as data_pagamento,
             min(criado_em) as criado_em,
             round(sum(total), 2) as total,
             round(sum(coalesce(valor_pago, 0)), 2) as valor_pago,
             round(sum(greatest(round(total - coalesce(valor_pago, 0), 2), 0)), 2) as pendente,
             (array_agg(observacao order by id))[1] as observacao,
             (array_agg(lancado_por order by id))[1] as lancado_por,
             string_agg(distinct forma_pagamento, ', ') as formas,
             json_agg(json_build_object(
               'id', id, 'produto', produto, 'quantidade', quantidade,
               'preco_unitario', preco_unitario, 'total', round(total, 2),
               'valor_pago', round(coalesce(valor_pago, 0), 2), 'obs_item', obs_item
             ) order by id) as itens
      from l group by pedido_id
    )
    select json_build_object(
      'total',      coalesce((select sum(total) from ped), 0),
      'pendente',   coalesce((select sum(pendente) from ped), 0),
      'abatido',    v_abat,
      'a_receber',  greatest(coalesce((select sum(pendente) from ped), 0) - v_abat, 0),
      'n_pedidos',  (select count(*) from ped),
      'n_clientes', (select count(distinct cliente) from ped),
      'pedidos',    (select coalesce(json_agg(ped order by criado_em), '[]') from ped)
    )
  );
end $$;

-- editar cliente / missão / data / observação de um pedido fechado
create or replace function public.mob_editar_pedido(
  p_token uuid, p_pedido_id text, p_cliente text, p_missao text, p_data date, p_observacao text
) returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_n int;
begin
  u := public._mob_admin(p_token);
  if nullif(btrim(coalesce(p_cliente, '')), '') is null then raise exception 'Informe o cliente'; end if;
  if nullif(btrim(coalesce(p_missao, '')), '') is null then raise exception 'Informe a missão'; end if;
  if p_data is null then raise exception 'Informe a data'; end if;
  update public.lancamentos set
    cliente = btrim(p_cliente), evento = btrim(p_missao), data_lancamento = p_data,
    observacao = nullif(btrim(coalesce(p_observacao, '')), ''),
    alterado_por = u.nome, alterado_em = now()
  where pedido_id = p_pedido_id and status = 'fechada' and not excluido;
  get diagnostics v_n = row_count;
  if v_n = 0 then raise exception 'Pedido não encontrado'; end if;
end $$;

-- excluir pedido (exclusão lógica, com motivo obrigatório)
create or replace function public.mob_excluir_pedido(p_token uuid, p_pedido_id text, p_motivo text)
returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_n int;
begin
  u := public._mob_admin(p_token);
  if nullif(btrim(coalesce(p_motivo, '')), '') is null then raise exception 'Informe o motivo da exclusão'; end if;
  update public.lancamentos set
    excluido = true, motivo_exclusao = btrim(p_motivo), excluido_por = u.nome, excluido_em = now()
  where pedido_id = p_pedido_id and status = 'fechada' and not excluido;
  get diagnostics v_n = row_count;
  if v_n = 0 then raise exception 'Pedido não encontrado'; end if;
end $$;

-- ============================================================
-- PAGAMENTOS PENDENTES
-- ============================================================
-- grava o total pago de UM pedido (p_valor_pago = total acumulado, não o valor de agora)
create or replace function public.mob_registrar_pagamento(
  p_token uuid, p_pedido_id text, p_valor_pago numeric, p_forma text
) returns json language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_total numeric;
begin
  u := public._mob_admin(p_token);
  if p_forma is null then raise exception 'Escolha a forma de pagamento'; end if;
  v_total := public._mob_pagar(p_pedido_id, p_valor_pago, p_forma, u.nome);
  return json_build_object('total', v_total, 'valor_pago', round(p_valor_pago, 2),
                           'resta', greatest(round(v_total - p_valor_pago, 2), 0));
end $$;

-- liquidar por valor: quita os pedidos mais antigos do cliente primeiro,
-- respeitando os mesmos filtros da tela (período e missão)
create or replace function public.mob_liquidar_cliente(
  p_token uuid, p_cliente text, p_valor numeric, p_forma text,
  p_ini date, p_fim date, p_missao text
) returns json language plpgsql security definer set search_path = public as $$
declare
  u public.usuarios;
  v_mis text := nullif(btrim(coalesce(p_missao, '')), '');
  v_restante numeric := round(coalesce(p_valor, 0), 2);
  v_aplicado numeric;
  r record;
  v_det jsonb := '[]'::jsonb;
begin
  u := public._mob_admin(p_token);
  if nullif(btrim(coalesce(p_cliente, '')), '') is null then raise exception 'Escolha o cliente'; end if;
  if v_restante <= 0 then raise exception 'Informe o valor recebido'; end if;
  if p_forma is null then raise exception 'Escolha a forma de pagamento'; end if;

  perform pg_advisory_xact_lock(hashtext('mob_cliente:' || p_cliente));

  for r in
    select pedido_id, min(data_lancamento) data_lancamento, min(criado_em) criado_em,
           round(sum(coalesce(valor_pago, 0)), 2) valor_pago,
           round(sum(greatest(round(total - coalesce(valor_pago, 0), 2), 0)), 2) pendente,
           string_agg(round(quantidade)::text || 'x ' || produto, ', ' order by id) itens
    from public.lancamentos
    where status = 'fechada' and not excluido and cliente = p_cliente
      and data_lancamento between p_ini and p_fim
      and (v_mis is null or evento = v_mis)
    group by pedido_id
    having round(sum(greatest(round(total - coalesce(valor_pago, 0), 2), 0)), 2) > 0.001
    order by min(criado_em), pedido_id
  loop
    exit when v_restante <= 0.001;
    v_aplicado := round(least(r.pendente, v_restante), 2);
    perform public._mob_pagar(r.pedido_id, round(r.valor_pago + v_aplicado, 2), p_forma, u.nome);
    v_restante := round(v_restante - v_aplicado, 2);
    v_det := v_det || jsonb_build_object('data', r.data_lancamento, 'itens', r.itens,
                                         'aplicado', v_aplicado, 'quitado', v_aplicado >= r.pendente - 0.001);
  end loop;

  return json_build_object('detalhes', v_det, 'sobra', v_restante,
                           'aplicado', round(coalesce(p_valor, 0) - v_restante, 2));
end $$;

-- ============================================================
-- GERAR COBRANÇA: todos os clientes com valor em aberto (todos os dias)
-- ============================================================
create or replace function public.mob_cobranca(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_admin(p_token);
  return (
    with p as (
      select id, cliente, data_lancamento, produto, quantidade,
             round(greatest(total - coalesce(valor_pago, 0), 0), 2) as pend
      from public.lancamentos
      where status = 'fechada' and not excluido
    ), d as (
      select cliente,
             (select c.telefone from public.clientes c where c.nome = p.cliente order by c.ativo desc limit 1) as telefone,
             round(sum(pend), 2) as total,
             json_agg(json_build_object('data', data_lancamento, 'produto', produto,
                                        'quantidade', quantidade, 'pendente', pend)
                      order by data_lancamento, id) as itens
      from p where pend > 0.001
      group by cliente
    )
    select json_build_object(
      'pix_chave', (select valor from public.config where chave = 'pix_chave'),
      'pix_nome',  (select valor from public.config where chave = 'pix_nome'),
      'devedores', (select coalesce(json_agg(d order by d.total desc), '[]') from d)
    )
  );
end $$;

-- ---------- permissões ----------
revoke execute on function public._mob_admin(uuid) from public, anon, authenticated;
revoke execute on function public._mob_pagar(text, numeric, text, text) from public, anon, authenticated;

grant execute on function
  public.mob_admin_listas(uuid),
  public.mob_extrato(uuid, date, date, text, text, text),
  public.mob_editar_pedido(uuid, text, text, text, date, text),
  public.mob_excluir_pedido(uuid, text, text),
  public.mob_registrar_pagamento(uuid, text, numeric, text),
  public.mob_liquidar_cliente(uuid, text, numeric, text, date, date, text),
  public.mob_cobranca(uuid)
to anon, authenticated;
