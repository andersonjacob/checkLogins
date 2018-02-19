create table if not exists restricted_users (
  username varchar primary key,
  last_active datetime,
  minutes_remaining integer,
  manual_enable integer
);
  
create table if not exists user_log (
  username varchar,
  logged_at datetime,
  active varchar
);

create index if not exists logged_date_idx on user_log(logged_at);
