-- ============================================================
-- App Mobile da Lanchonete (Caixa EMB) — FASE 2 da migração
-- Fechamento do período, Resumo por cliente e Resumo por produto
-- Projeto Supabase: Diversos
--
-- Só leitura. Todas exigem login E perfil administrador.
-- Regras copiadas do app.py (Streamlit). Usa _mob_admin() da fase 1.
-- ============================================================

-- listas dos filtros: agora também com os produtos (cadastrados + histórico)
create or replace function public.mob_admin_listas(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_admin(p_token);
  return json_build_object(
    'clientes', (select coalesce(json_agg(nome order by nome), '[]') from (
                   select cliente as nome from public.lancamentos where not excluido and cliente is not null
                   union
                   select nome from public.clientes) c),
    'missoes',  (select coalesce(json_agg(nome order by nome), '[]') from public.eventos),
    'produtos', (select coalesce(json_agg(nome order by nome), '[]') from (
                   select produto as nome from public.lancamentos where not excluido and produto is not null
                   union
                   select nome from public.produtos) p)
  );
end $$;

-- ============================================================
-- FECHAMENTO DO PERÍODO
-- ============================================================
create or replace function public.mob_fechamento(
  p_token uuid, p_ini date, p_fim date, p_cliente text, p_missao text
) returns json language plpgsql security definer set search_path = public as $$
declare
  v_cli text := nullif(btrim(coalesce(p_cliente, '')), '');
  v_mis text := nullif(btrim(coalesce(p_missao, '')), '');
begin
  perform public._mob_admin(p_token);
  return (
    with l as (
      select cliente, evento, produto, quantidade, total,
             coalesce(valor_pago, 0) as valor_pago, forma_pagamento,
             greatest(round(total - coalesce(valor_pago, 0), 2), 0) as pendente
      from public.lancamentos
      where status = 'fechada' and not excluido
        and data_lancamento between p_ini and p_fim
        and (v_cli is null or cliente = v_cli)
        and (v_mis is null or evento = v_mis)
    ),
    -- abatimentos/reembolsos do período (e do cliente, se filtrado)
    ab as (
      select cliente, sum(valor) as valor from public.abatimentos
      where not coalesce(excluido, false) and data between p_ini and p_fim
        and (v_cli is null or cliente = v_cli)
      group by cliente
    ),
    fp as (
      select coalesce(forma_pagamento, '(não informado)') as forma, round(sum(valor_pago), 2) as valor
      from l where valor_pago > 0.001 group by 1
    ),
    prod as (
      select produto, sum(quantidade) as qtde, round(sum(total), 2) as total from l group by produto
    ),
    mis as (
      select evento as missao, round(sum(total), 2) as total from l group by evento
    ),
    pag as (
      select cliente, round(sum(valor_pago), 2) as valor from l where valor_pago > 0.001 group by cliente
    ),
    rec as (
      select r.cliente, greatest(round(r.pend - coalesce(ab.valor, 0), 2), 0) as valor
      from (select cliente, sum(pendente) as pend from l group by cliente) r
      left join ab on ab.cliente = r.cliente
    )
    select json_build_object(
      'n_linhas',      (select count(*) from l),
      'por_forma',     (select coalesce(json_agg(fp order by fp.forma), '[]') from fp),
      'total_receb',   (select coalesce(sum(valor), 0) from fp),
      'por_produto',   (select coalesce(json_agg(prod order by prod.total desc, produto), '[]') from prod),
      'total_consumo', (select round(coalesce(sum(total), 0), 2) from l),
      'por_missao',    (select coalesce(json_agg(mis order by mis.total desc), '[]') from mis),
      'pagantes',      (select coalesce(json_agg(pag order by pag.valor desc, cliente), '[]') from pag),
      'total_pago',    (select coalesce(sum(valor), 0) from pag),
      'a_receber',     (select coalesce(json_agg(rec order by rec.valor desc, cliente), '[]') from rec where valor > 0.001),
      'total_receber', (select coalesce(sum(valor), 0) from rec where valor > 0.001),
      'abatido',       (select round(coalesce(sum(valor), 0), 2) from ab)
    )
  );
end $$;

-- ============================================================
-- RESUMO POR CLIENTE
-- p_ini/p_fim nulos = todos os períodos
-- ============================================================
create or replace function public.mob_resumo_clientes(
  p_token uuid, p_ini date, p_fim date, p_cliente text, p_missao text
) returns json language plpgsql security definer set search_path = public as $$
declare
  v_cli text := nullif(btrim(coalesce(p_cliente, '')), '');
  v_mis text := nullif(btrim(coalesce(p_missao, '')), '');
begin
  perform public._mob_admin(p_token);
  return (
    with l as (
      select cliente, total, coalesce(valor_pago, 0) as valor_pago,
             greatest(round(total - coalesce(valor_pago, 0), 2), 0) as pendente
      from public.lancamentos
      where status = 'fechada' and not excluido
        and (p_ini is null or data_lancamento between p_ini and p_fim)
        and (v_cli is null or cliente = v_cli)
        and (v_mis is null or evento = v_mis)
    ),
    ab as (
      select cliente, sum(valor) as valor from public.abatimentos
      where not coalesce(excluido, false)
        and (p_ini is null or data between p_ini and p_fim)
      group by cliente
    ),
    r as (
      select g.cliente, round(g.total, 2) as total, round(g.valor_pago, 2) as valor_pago,
             round(coalesce(ab.valor, 0), 2) as abatido,
             greatest(round(g.pend - coalesce(ab.valor, 0), 2), 0) as pendente
      from (select cliente, sum(total) total, sum(valor_pago) valor_pago, sum(pendente) pend
            from l group by cliente) g
      left join ab on ab.cliente = g.cliente
    )
    select json_build_object(
      'total',     (select round(coalesce(sum(total), 0), 2) from l),
      'recebido',  (select round(coalesce(sum(valor_pago), 0), 2) from l),
      'a_receber', (select coalesce(sum(pendente), 0) from r),
      'abatido',   (select coalesce(sum(abatido), 0) from r),
      'clientes',  (select coalesce(json_agg(r order by r.pendente desc, r.total desc, cliente), '[]') from r)
    )
  );
end $$;

-- ============================================================
-- RESUMO POR PRODUTO
-- p_ini/p_fim nulos = todos os períodos; p_produto nulo = todos
-- ============================================================
create or replace function public.mob_resumo_produto(
  p_token uuid, p_ini date, p_fim date, p_produto text
) returns json language plpgsql security definer set search_path = public as $$
declare
  v_prod text := nullif(btrim(coalesce(p_produto, '')), '');
begin
  perform public._mob_admin(p_token);
  return (
    with l as (
      select id, data_lancamento, cliente, produto, quantidade, round(total, 2) as total,
             coalesce(valor_pago, 0) as valor_pago,
             greatest(round(total - coalesce(valor_pago, 0), 2), 0) as pendente
      from public.lancamentos
      where status = 'fechada' and not excluido
        and (p_ini is null or data_lancamento between p_ini and p_fim)
        and (v_prod is null or produto = v_prod)
    ),
    prod as (
      select produto, sum(quantidade) as qtde, round(sum(total), 2) as total,
             round(sum(pendente), 2) as pendente
      from l group by produto
    )
    select json_build_object(
      'total',     (select round(coalesce(sum(total), 0), 2) from l),
      'recebido',  (select round(coalesce(sum(valor_pago), 0), 2) from l),
      'a_receber', (select round(coalesce(sum(pendente), 0), 2) from l),
      'qtde',      (select coalesce(sum(quantidade), 0) from l),
      'por_produto', (select coalesce(json_agg(prod order by prod.total desc, produto), '[]') from prod),
      'linhas', (select coalesce(json_agg(json_build_object(
                   'data', data_lancamento, 'cliente', cliente, 'produto', produto,
                   'quantidade', quantidade, 'total', total,
                   'situacao', case when pendente <= 0.001 then 'Pago'
                                    when valor_pago > 0.001 then 'Parcial' else 'Pendente' end)
                 order by data_lancamento desc, cliente, id), '[]') from l)
    )
  );
end $$;

grant execute on function
  public.mob_fechamento(uuid, date, date, text, text),
  public.mob_resumo_clientes(uuid, date, date, text, text),
  public.mob_resumo_produto(uuid, date, date, text)
to anon, authenticated;
