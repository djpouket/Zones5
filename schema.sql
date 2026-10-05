create table if not exists zones (
  id text primary key,
  symbol text not null,
  tf text not null,
  side text not null,
  stars int not null,
  bottom float8 not null,
  top float8 not null,
  criteres text,
  t0 timestamptz,
  t_imp timestamptz,
  outcome text not null default 'pending',
  entry_alerted boolean not null default false,
  created_at timestamptz not null default now()
);
alter table zones enable row level security;
