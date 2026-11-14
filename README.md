# 包装线节拍对照实验

Welch 实验检验的真实业务分析小型项目。完整模拟客户、痛点、上下游、算法公式与一天工作剧本见 [BUSINESS.md](BUSINESS.md)。

## 模块与业务流程
数据接入（JSON/CSV、字段验证、批次指纹）→ 参数化分析（异步 Python worker）→ 结果复核（指标、图形、明细、解释、批准）→ 定时分发（本地收件箱、CSV/JSON、SHA256）；另有业务总览和审计轨迹。
三个贯穿全栈的实体：Dataset 数据批次、Job 分析任务、Report 分发计划；辅助 User、Audit、Delivery。

## 快速启动
```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```
访问 http://localhost:18203；后端文档 http://localhost:19203/docs；数据库宿主端口 17703。
`SEED_DEMO=true` 自动幂等 seed；不覆盖用户修改。手动 seed 命令可重复执行。

## 演示账号与权限
|账号|密码|真实权限|
|---|---|---|
|admin@demo.local|Demo123!|接入、执行、批准、分发、暂停、读取与下载|
|analyst@demo.local|Demo123!|接入、执行、读取与下载；不能批准或安排分发|
|viewer@demo.local|Demo123!|只读与下载|

## 技术与本地开发
Python 3.12 / FastAPI / SQLAlchemy / NumPy / SciPy / scikit-learn；MySQL 8.0；Redis 7；Nginx；原生 HTML CSS JavaScript ES modules（用户指定）。后端所有校验、持久化和算法在服务端。无前端打包步骤。
后端：安装 backend/requirements.txt，设置 DATABASE_URL、REDIS_URL、JWT_SECRET、ARTIFACT_DIR 后在 backend/ 执行 `python -m migrations.initial`、`python -m scripts.seed_demo`、`uvicorn src.main:app`，另开 `python -m src.worker`。前端使用带 /api 反向代理的 Nginx，直接打开 index.html 不支持 API。

## 目录与工程约定
backend/src/{models,schemas,services,routes,controllers,middlewares,constants,config,utils}；backend/scripts/seed_demo.py；backend/migrations/initial.py。
frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}。
Role 枚举：admin/analyst/viewer；JobStatus：queued/running/completed/failed。后端 backend/src/constants/enums.py，前端 frontend/src/constants/enums.js；路由权限在 middlewares/auth.py；页面按相同角色控制操作入口。

## 环境变量与 Docker
COMPOSE_PROJECT_NAME=pack-welch；FRONTEND_PORT=18203；BACKEND_PORT=19203；DB_PORT=17703；DB_PASSWORD、JWT_SECRET 见 .env.example；SEED_DEMO 默认 true。共享命名产物卷供后端下载与 worker 写入，数据库/Redis 各持久卷。
恰好五服务均有健康检查。Redis 队列加 SQL 排队状态兜底；worker 按 next_run 生成本地收件箱文件。周期 60 秒至 30 天。分发结果为批准分析的固定快照；若需新数据重新计算并建立新计划。当前不连接邮件或企业聊天。
错误响应、请求编号、Redis 每 IP 每分钟 240 次限流、JWT 和数据库操作审计。演示密钥与密码仅供本机模拟；生产部署前配置独立密钥与账号。

## 故障片段隔离与统一重算

秒表故障片段在「数据接入」页登记原因后隔离（仅 admin 可操作，支持恢复并保留历史）。影响范围不按批次整体判断，而是给每个分析保存其**实际使用样本的指纹**（有效片段再按班次参数筛选），隔离/恢复时逐任务比对：

- 隔离立即生效：实际用到该片段的分析标记 `invalid` 并写明原因；排队或运行中的旧计算不允许再落为可用结果（运行中的任务在落库前二次校验输入指纹）。未使用这些片段的分析与简报照常运行。
- 关联定时简报自动暂停分发；已发出的 CSV/JSON 文件保留不删，仅标记失效与原因，仍可下载查阅；旧分析结论同样保留可查阅，但不能再批准或安排分发。
- 「统一重算」按原参数、原批次为每个失效分析建立重算任务，归入同一 `recompute_key` 批次（同一来源在途重算不重复创建，也不漏掉计划）。中途失败可在批次内重试，接着完成而不新建分析。
- 同批次重算**全部完成并逐一获批准**后，关联简报才统一切换到新结果并恢复分发；此前分发持续暂停。片段恢复且样本指纹重新匹配时，对应分析自动恢复有效并解除暂停。
- 隔离、恢复、重算、重试、切换均写入审计轨迹；接入页提供隔离前的受影响分析预览。


## 数据与验收
所有数据为固定随机种子生成的模拟业务数据，不能作为实际生产决策证据。项目独立算法、输入边界及业务局限详见 BUSINESS.md。测试与截图统一存放 ../../test-artifacts/gb-1004/，源码不含日志/截图/测试报告。
清理本项目演示数据：`docker compose down -v --remove-orphans`（会删除本项目命名卷）。

## License
MIT，见 LICENSE。
