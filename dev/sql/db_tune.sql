-- TaskForce Postgres 调优(幂等)。在 docker compose 重建 postgres 后执行一次。
-- 说明:shared_buffers 等服务器参数在 docker-compose.yml 的 command 里,需要重建容器;
-- 本文件只放可在线执行的 autovacuum 与扩展。

ALTER TABLE checkpoints SET (
    autovacuum_vacuum_scale_factor = 0.02,
    autovacuum_vacuum_threshold = 50
);
ALTER TABLE checkpoint_blobs SET (
    autovacuum_vacuum_scale_factor = 0.02,
    autovacuum_vacuum_threshold = 50
);
ALTER TABLE checkpoint_writes SET (
    autovacuum_vacuum_scale_factor = 0.02,
    autovacuum_vacuum_threshold = 50
);
ALTER TABLE sessions SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

-- 依赖 shared_preload_libraries=pg_stat_statements(compose 已配置,需重建容器)。
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

ANALYZE checkpoints;
ANALYZE checkpoint_blobs;
ANALYZE checkpoint_writes;
ANALYZE sessions;
