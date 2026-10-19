-- ============================================================
-- App Mobile da Lanchonete (Caixa EMB) — FASE 3 da migração
-- Abatimento/Reembolso, Despesas, Usuários, chave Pix
-- e a Cobrança descontando os abatimentos.
-- Projeto Supabase: Diversos
--
-- Tudo exige login + perfil administrador (Administrador e Meiry).
-- Usuários: só perfil 'admin' (igual ao Streamlit: gestor não gerencia).
-- ============================================================

-- ============================================================
-- ABATIMENTO / REEMBOLSO
-- ============================================================
create or replace function public.mob_abatimentos(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_admin(p_token);
  return json_build_object(
    'total', (select round(coalesce(sum(valor), 0), 2) from public.abatimentos where not excluido),
    'lista', (select coalesce(json_agg(json_build_object(
                'id', id, 'data', data, 'cliente', cliente, 'valor', valor,
                'observacao', observacao, 'lancado_por', lancado_por
              ) order by data desc, id desc), '[]')
              from public.abatimentos where not excluido)
  );
end $$;

create or replace function public.mob_salvar_abatimento(
  p_token uuid, p_data date, p_cliente text, p_valor numeric, p_observacao text
) returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_cli text := btrim(coalesce(p_cliente, ''));
begin
  u := public._mob_admin(p_token);
  if v_cli = '' then raise exception 'Escolha o cliente'; end if;
  if coalesce(p_valor, 0) <= 0 then raise exception 'Informe um valor maior que zero'; end if;
  if p_data is null then raise exception 'Informe a data'; end if;
  -- o nome fica exatamente como nos lançamentos, para o desconto bater
  insert into public.abatimentos (data, cliente, valor, observacao, lancado_por)
  values (p_data, v_cli, round(p_valor, 2), nullif(btrim(coalesce(p_observacao, '')), ''), u.nome);
end $$;

create or replace function public.mob_excluir_abatimento(p_token uuid, p_id bigint, p_motivo text)
returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_n int;
begin
  u := public._mob_admin(p_token);
  if nullif(btrim(coalesce(p_motivo, '')), '') is null then raise exception 'Informe o motivo da exclusão'; end if;
  update public.abatimentos set excluido = true, motivo_exclusao = btrim(p_motivo),
         excluido_por = u.nome, excluido_em = now()
  where id = p_id and not excluido;
  get diagnostics v_n = row_count;
  if v_n = 0 then raise exception 'Abatimento não encontrado'; end if;
end $$;

-- ============================================================
-- DESPESAS
-- ============================================================
create or replace function public.mob_despesas(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_admin(p_token);
  return json_build_object(
    'total', (select round(coalesce(sum(valor), 0), 2) from public.despesas where not excluido),
    'lista', (select coalesce(json_agg(json_build_object(
                'id', id, 'data', data, 'descricao', descricao, 'valor', valor, 'lancado_por', lancado_por
              ) order by data desc, id desc), '[]')
              from public.despesas where not excluido)
  );
end $$;

-- p_itens: [{"descricao":"Gás","valor":120.5}, ...]
create or replace function public.mob_salvar_despesas(p_token uuid, p_data date, p_itens jsonb)
returns json language plpgsql security definer set search_path = public as $$
declare u public.usuarios; it jsonb; v_n int := 0; v_total numeric := 0; v_desc text; v_valor numeric;
begin
  u := public._mob_admin(p_token);
  if p_data is null then raise exception 'Informe o dia das despesas'; end if;
  if jsonb_typeof(coalesce(p_itens, '[]'::jsonb)) <> 'array' then raise exception 'Itens inválidos'; end if;
  for it in select * from jsonb_array_elements(coalesce(p_itens, '[]'::jsonb)) loop
    v_desc := btrim(coalesce(it->>'descricao', ''));
    v_valor := round(coalesce((it->>'valor')::numeric, 0), 2);
    continue when v_desc = '' or v_valor <= 0;
    insert into public.despesas (data, descricao, valor, lancado_por) values (p_data, v_desc, v_valor, u.nome);
    v_n := v_n + 1; v_total := v_total + v_valor;
  end loop;
  if v_n = 0 then raise exception 'Adicione ao menos uma linha com descrição e valor'; end if;
  return json_build_object('n', v_n, 'total', v_total);
end $$;

create or replace function public.mob_excluir_despesa(p_token uuid, p_id bigint, p_motivo text)
returns void language plpgsql security definer set search_path = public as $$
declare u public.usuarios; v_n int;
begin
  u := public._mob_admin(p_token);
  if nullif(btrim(coalesce(p_motivo, '')), '') is null then raise exception 'Informe o motivo da exclusão'; end if;
  update public.despesas set excluido = true, motivo_exclusao = btrim(p_motivo),
         excluido_por = u.nome, excluido_em = now()
  where id = p_id and not excluido;
  get diagnostics v_n = row_count;
  if v_n = 0 then raise exception 'Despesa não encontrada'; end if;
end $$;

-- ============================================================
-- CHAVE PIX (mensagem de cobrança)
-- ============================================================
create or replace function public.mob_pix(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_admin(p_token);
  return json_build_object(
    'chave', (select valor from public.config where chave = 'pix_chave'),
    'nome',  (select valor from public.config where chave = 'pix_nome'));
end $$;

create or replace function public.mob_salvar_pix(p_token uuid, p_chave text, p_nome text)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_admin(p_token);
  insert into public.config (chave, valor) values ('pix_chave', btrim(coalesce(p_chave, '')))
    on conflict (chave) do update set valor = excluded.valor;
  insert into public.config (chave, valor) values ('pix_nome', btrim(coalesce(p_nome, '')))
    on conflict (chave) do update set valor = excluded.valor;
end $$;

-- ============================================================
-- USUÁRIOS (só perfil admin)
-- ============================================================
create or replace function public._mob_admin_usuarios(p_token uuid)
returns public.usuarios
language plpgsql security definer set search_path = public as $$
declare u public.usuarios;
begin
  u := public._mob_usuario(p_token);
  if u.perfil <> 'admin' then raise exception 'Somente o perfil admin gerencia usuários'; end if;
  return u;
end $$;

create or replace function public.mob_usuarios_listar(p_token uuid)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform public._mob_admin_usuarios(p_token);
  return (select coalesce(json_agg(json_build_object('id', id, 'nome', nome, 'perfil', perfil, 'ativo', ativo)
                                   order by ativo desc, nome), '[]') from public.usuarios);
end $$;

-- p_id nulo = novo (senha obrigatória). p_senha preenchida em usuário existente = reset de senha.
create or replace function public.mob_salvar_usuario(
  p_token uuid, p_id bigint, p_nome text, p_perfil text, p_ativo boolean, p_senha text
) returns void language plpgsql security definer set search_path = public, extensions as $$
declare
  u public.usuarios;
  alvo public.usuarios;
  v_nome text := initcap(btrim(coalesce(p_nome, '')));
  v_pepper text;
  v_hash text;
begin
  u := public._mob_admin_usuarios(p_token);
  if p_perfil not in ('operador', 'gestor', 'admin') then raise exception 'Perfil inválido'; end if;
  select valor into v_pepper from public.mob_segredos where chave = 'senha_pepper';
  if coalesce(p_senha, '') <> '' then
    v_hash := encode(extensions.digest(v_pepper || p_senha, 'sha256'), 'hex');
  end if;

  if p_id is null then
    if v_nome = '' then raise exception 'Informe o nome'; end if;
    if v_hash is null then raise exception 'Informe a senha inicial'; end if;
    if exists (select 1 from public.usuarios where lower(nome) = lower(v_nome)) then
      raise exception 'Já existe um usuário com esse nome';
    end if;
    insert into public.usuarios (nome, senha_hash, perfil, ativo) values (v_nome, v_hash, p_perfil, coalesce(p_ativo, true));
    return;
  end if;

  select * into alvo from public.usuarios where id = p_id;
  if not found then raise exception 'Usuário não encontrado'; end if;
  if alvo.nome = 'Administrador' and (not coalesce(p_ativo, true) or p_perfil <> 'admin') then
    raise exception 'O usuário Administrador não pode ser inativado nem rebaixado';
  end if;
  if alvo.id = u.id and (not coalesce(p_ativo, true) or p_perfil <> 'admin') then
    raise exception 'Você não pode inativar nem rebaixar o seu próprio usuário';
  end if;

  update public.usuarios set perfil = p_perfil, ativo = coalesce(p_ativo, true),
         senha_hash = coalesce(v_hash, senha_hash)
  where id = p_id;

  -- inativou ou trocou a senha: derruba as sessões abertas dessa pessoa (menos a de quem está mexendo)
  if not coalesce(p_ativo, true) or v_hash is not null then
    delete from public.mob_sessoes where usuario = alvo.nome and token <> p_token;
  end if;
end $$;

-- ============================================================
-- COBRANÇA: agora desconta os abatimentos/reembolsos do cliente
-- (substitui a versão da fase 1; mesmo formato + campos bruto/abatido)
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
      'pix_chave', (select valor from public.config where chave = 'pix_chave'),
      'pix_nome',  (select valor from public.config where chave = 'pix_nome'),
      'devedores', (select coalesce(json_agg(d order by d.total desc), '[]') from d where total > 0.001)
    )
  );
end $$;

-- ---------- permissões ----------
revoke execute on function public._mob_admin_usuarios(uuid) from public, anon, authenticated;
grant execute on function
  public.mob_abatimentos(uuid),
  public.mob_salvar_abatimento(uuid, date, text, numeric, text),
  public.mob_excluir_abatimento(uuid, bigint, text),
  public.mob_despesas(uuid),
  public.mob_salvar_despesas(uuid, date, jsonb),
  public.mob_excluir_despesa(uuid, bigint, text),
  public.mob_pix(uuid),
  public.mob_salvar_pix(uuid, text, text),
  public.mob_usuarios_listar(uuid),
  public.mob_salvar_usuario(uuid, bigint, text, text, boolean, text)
to anon, authenticated;
