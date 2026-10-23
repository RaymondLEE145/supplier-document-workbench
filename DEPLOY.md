# 部署与公网访问

## 1. 本机运行（已验证）

```bat
cd repo
run_server.bat
```

或：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000>。

---

## 2. 公网访问（正式 HTTPS 部署中）

**当前没有可对外分享的正式地址。** 之前用于本地调试的 `bore.pub` HTTP 隧道已停用，不要把它发到微信/群聊：非标准端口 + 明文 HTTP 会被风控当成可疑链接，且任何人都能访问。

正式发布采用 GitHub 仓库 + Render：

1. 推送仓库到 GitHub（或由你授权后由我推送）
2. Render → New → Blueprint → 选择仓库
3. `render.yaml` 自动创建 Docker Web Service + `/api/health` + `/app/data` 持久盘
4. 得到 `https://<service>.onrender.com`，这是可正常分享的 HTTPS 域名

在正式域名完成前，只用本机：

```text
http://127.0.0.1:8000
```

`start_public.bat` 仅作本机调试，不要用于对外分享；正式部署后可删除或加访问控制。

---

## 3. Docker

```bash
docker build -t supplier-workbench .
docker run -p 8000:8000 -v workbench-data:/app/data supplier-workbench
```

打开 <http://127.0.0.1:8000>。

> Linux 容器没有 WPS COM，公式仍会写回，但缓存值需要在 Excel/WPS 中打开一次重算；校验会把“缓存值不可读”降级为 warning，不会阻断导出。申报要素 `unsupported` 和官方证据逻辑不受影响。

---

## 4. GitHub + Render 一键部署

当前环境没有安装 `git`/`gh`，也没有 GitHub Token，因此无法从本机直接 push 到你的 GitHub 账号。仓库已经包含：

- `.github/workflows/ci.yml`（编译 + 澳洲税则索引 + 11 个 HS 回归 + 模板引擎 CI）
- `Dockerfile`
- `render.yaml`（Docker + `/api/health` 健康检查 + 1GB disk 挂载 `/app/data`）
- `requirements.txt`
- 完整 README 与验证报告
- `docs/supplier-workbench-source.zip`（可直接上传的源码包）

拿到 GitHub 权限后执行：

```bash
cd repo
git init
git add .
git commit -m "supplier document workbench"
git branch -M main
git remote add origin https://github.com/<your-account>/<your-repo>.git
git push -u origin main
```

然后在 Render：

1. New + → Blueprint
2. 选择刚推送的 GitHub 仓库
3. Render 会读取 `render.yaml`（Docker + health check + disk）
4. Apply，等待构建完成，得到 `https://<service>.onrender.com`

如果不用 Render，任何支持 Docker 的平台（Fly.io / Railway / 阿里云 / 腾讯云）都可以直接使用 `Dockerfile`。

### GitHub Actions

`ci.yml` 只做构建与回归验证，不会自动推生产。需要自动部署时，在仓库 Secrets 配置目标平台凭据并新增 deploy job。

---

## 5. 公网安全

当前版本是本地单用户工作台，没有登录鉴权。放到公网前建议至少：

- 在反向代理层加 Basic Auth / 访问码；
- 限制上传大小（后端已有 80MB 上限）；
- 使用 HTTPS（localhost.run / Render 默认 HTTPS）；
- 不要把 `data/` 目录暴露为静态文件（当前只暴露 `/static` 与 `/testdata` 测试夹具）。

---

## 6. 关键数据与缓存

- `data/state.json`：供应商、单证、标准模型、合规确认
- `data/uploads/`：原始文件
- `data/outputs/`：已导出 Excel
- `data/scripts/`：每次生成的 Python 回填脚本 + payload
- `assets/au_chafta_tariff.json`：官方 ChAFTA 税则索引（DFAT FTA Portal 下载）
- `data/abf_chapters/`：ABF Schedule 3 章节缓存（按需抓取）
