# 词根管理助手

用于 CET-4、CET-6 词汇学习的 Dify Agent 与本地 Flask 工具。学习流程保留词源和词根分析，并增加学习卡、语境填空及间隔复习。

## 仓库内容

- `agent-config.yml`：从已发布 Agent 导出的 Dify DSL。导入后需要在自己的 Dify 中重新配置模型和工具连接。
- `skills/`：词根管理与词源历史两项 Skill 的源码和可上传 ZIP。
- `English1.py`、`word_learning.py`：词根家族、词源查询、学习卡和复习接口。
- `word_root_api.json`：在 Dify 中作为 Swagger API 工具导入的 OpenAPI 定义。
- `cet_etymology.db`：项目当前使用的本地 CET 词源资料；`CET4.txt`、`CET6.txt` 与 `build_cet_db.py` 用于重新构建。

## 本地运行

需要 Python 3.10+。在仓库目录安装依赖后启动服务：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python English1.py
```

服务默认仅监听本机 `127.0.0.1:5000`。打开 `http://localhost:5000/openapi.json` 可查看 API 定义。`word_learning.db` 和 `data/` 会在使用时创建，保存个人学习卡与词族笔记，不纳入 Git。

可选环境变量：

| 变量 | 用途 |
| --- | --- |
| `CET_DB_PATH` | 指定 CET 词源数据库路径，默认使用仓库内的 `cet_etymology.db` |
| `WORD_ROOT_DATA_DIR` | 指定词族笔记和词源缓存目录，默认使用仓库内的 `data/` |
| `WORD_ROOT_HOST` | 服务监听地址，默认 `127.0.0.1`；只有在受信任网络且配置了访问限制时才改为 `0.0.0.0` |
| `WORD_ROOT_PROXY` | 在线词源查询需要代理时设置代理 URL；默认直连 |
| `CET4_PATH`、`CET6_PATH` | 重新构建数据库时指定词表路径 |
| `CET_BUILD_LOG_PATH` | 重新构建数据库时指定日志路径，默认写入仓库目录 |

## 接入 Dify

1. 在 Dify 中导入 `agent-config.yml`，并为自己的账号配置模型供应商。
2. 保持 Flask 服务运行。在「集成 → 工具 → Swagger API 作为工具」中导入 `http://host.docker.internal:5000/openapi.json`。本地 Dify 使用 Docker Desktop 时，这个地址指向宿主机；此时可能需要将 `WORD_ROOT_HOST` 设为 Docker 可访问的宿主机网卡地址，并只允许本机 Docker 网络访问 5000 端口。服务没有内置鉴权，切勿直接暴露到公网或不可信局域网。其他部署方式需要修改 `word_root_api.json` 中的 `servers.url`。
3. 检查 Agent 已启用学习卡、复习、词根和词源相关动作，再发布 Agent。两项 Skill 也可分别从 `skills/*.zip` 上传。

可以试问“acquire 的词源是什么”“学 acquire 并保存”“今天学四级”“复习”。只查词源和挑选候选词不会写入学习卡；真正学习并保存后才会进入复习队列。

## 数据说明

`cet_etymology.db` 的词源文本取自 Wiktionary；重新构建会请求其公开接口。使用或再发布这些内容时，请保留来源信息并核对 Wiktionary 的许可条款。仓库不包含 Dify 登录凭据、DeepSeek API key、个人学习卡或运行日志。
