-- ============================================================
-- App Mobile da Lanchonete (Caixa EMB) — texto da mensagem de cobrança
-- editável (abertura e fecho), guardado na tabela config:
--   cob_abertura  (vazio = texto padrão)
--   cob_fecho     (vazio = texto padrão)
-- Marcadores: {cliente} {total} {chave_pix} {nome_pix}
-- Projeto Supabase: Diversos
-- ============================================================

-- leitura da tela "Mensagem de cobrança"
create or replace function public.mob_pix(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_admin(p_token);
  return json_build_object(
    'chave',    (select valor from public.config where chave = 'pix_chave'),
    'nome',     (select valor from public.config where chave = 'pix_nome'),
    'abertura', (select valor from public.config where chave = 'cob_abertura'),
    'fecho',    (select valor from public.config where chave = 'cob_fecho'));
end $$;

create or replace function public.mob_salvar_mensagem(
  p_token uuid, p_chave text, p_nome text, p_abertura text, p_fecho text
) returns void language plpgsql security definer set search_path = public as $$
declare k text; v text;
begin
  perform public._mob_admin(p_token);
  for k, v in select * from (values
      ('pix_chave', btrim(coalesce(p_chave, ''))),
      ('pix_nome',  btrim(coalesce(p_nome, ''))),
      ('cob_abertura', coalesce(p_abertura, '')),
      ('cob_fecho',    coalesce(p_fecho, ''))) x
  loop
    insert into public.config (chave, valor) values (k, v)
      on conflict (chave) do update set valor = excluded.valor;
  end loop;
end $$;

-- cobrança: mesma da fase 3 + os textos editáveis
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
    ), ab as (
      select cliente, round(sum(valor), 2) as valor from public.abatimentos where not excluido group by cliente
    ), d as (
      select p.cliente,
             (select c.telefone from public.clientes c where c.nome = p.cliente order by c.ativo desc limit 1) as telefone,
             round(sum(pend), 2) as bruto,
             coalesce(max(ab.valor), 0) as abatido,
             greatest(round(sum(pend) - coalesce(max(ab.valor), 0), 2), 0) as total,
             json_agg(json_build_object('data', data_lancamento, 'produto', produto,
                                        'quantidade', quantidade, 'pendente', pend)
                      order by data_lancamento, id) as itens
      from p left join ab on ab.cliente = p.cliente
      where pend > 0.001
      group by p.cliente
    )
    select json_build_object(
      'pix_chave',    (select valor from public.config where chave = 'pix_chave'),
      'pix_nome',     (select valor from public.config where chave = 'pix_nome'),
      'cob_abertura', (select valor from public.config where chave = 'cob_abertura'),
      'cob_fecho',    (select valor from public.config where chave = 'cob_fecho'),
      'devedores',    (select coalesce(json_agg(d order by d.total desc), '[]') from d where total > 0.001)
    )
  );
end $$;

grant execute on function public.mob_salvar_mensagem(uuid, text, text, text, text) to anon, authenticated;
