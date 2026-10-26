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

## 2. 公网访问

### 已上线：GitHub Pages 展示页（可微信分享）

```text
https://raymondlee145.github.io/supplier-document-workbench/
```

- 由 GitHub Pages 托管，正式 HTTPS，不再是 `bore.pub` 非标准端口。
- 内容：项目介绍、HS 查询、门禁截图、11 行导出样例下载。
- 限制：Pages 只能托管静态页，不能运行 FastAPI/OCR/海关接口/WPS。

### 完整平台：GitHub 仓库 + Render

仓库：<https://github.com/RaymondLEE145/supplier-document-workbench>

**已上线完整平台（Render free）**：

```text
https://supplier-document-workbench.onrender.com
```

- `/api/health` 返回 200；真实上传 2 份 XLSX 后解析出 15 行，测试数据已清理。
- 免费实例会在空闲后休眠，首次打开可能需要 30–60 秒唤醒。
- 免费实例没有持久盘；升级到 starter 并取消 `render.yaml` 里 `disk` 的注释后，`/app/data` 才会持久化。
- Linux 容器没有 WPS COM，公式缓存值由打开 Excel/WPS 时重算；服务端校验会给出 warning，不阻断导出。

Render 一键 Blueprint（重新部署/新环境时用）：

```text
https://render.com/deploy?repo=https://github.com/RaymondLEE145/supplier-document-workbench
```

登录 Render（可用 GitHub 登录）后按页面提示创建：

- 服务名：`supplier-document-workbench`
- 运行环境：Docker（读取仓库 `Dockerfile`）
- 健康检查：`/api/health`
- 当前 `render.yaml` 是 **free** 计划，不带持久盘；升级到 starter 后取消注释 `disk` 即可持久化 `/app/data`
- 部署完成地址：`https://<service>.onrender.com`

> 免费 Render 会休眠，首次访问较慢；Windows WPS COM 在 Linux 容器不可用，公式缓存值需在 Excel/WPS 打开时重算，校验会降级为 warning，不阻断导出。

### 本机调试

```text
http://127.0.0.1:8000
```

`start_public.bat`（bore）只用于本机调试，**不要再发微信**；正式分享用上面的 GitHub Pages 或 Render 地址。

---

## 3. 单文件上传规则

- 只上传装箱单：填「装箱单」；发票/销售合同空白；报关单/申报要素按 HS 自动生成。
- 只上传发票：填「发票」；装箱单/销售合同空白；报关单/申报要素自动生成。
- 只上传合同：填「销售合同」；装箱单/发票空白；报关单/申报要素自动生成。
- 只上传报关单/申报要素：对应表 + 自动生成报关/申报要素。
- 装箱单 + 发票：填这两张，不自动补合同；报关单/申报要素自动生成。
- 申报要素来自中国海关官方 `CusMerchElement` 表；发票/合同金额、材质等没有来源时保持空白，不默认 `USD/CIF/一般贸易/纸箱包装`。
- 导出页显示「本次可填写的单证」和官方申报要素来源。

---

## 4. Docker

```bash
docker build -t supplier-workbench .
docker run -p 8000:8000 -v workbench-data:/app/data supplier-workbench
```

打开 <http://127.0.0.1:8000>。

> Linux 容器没有 WPS COM，公式仍会写回，但缓存值需要在 Excel/WPS 中打开一次重算；校验会把“缓存值不可读”降级为 warning，不会阻断导出。申报要素 `unsupported` 和官方证据逻辑不受影响。

---

## 5. GitHub + Render 一键部署

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

## 6. 公网安全

当前版本是本地单用户工作台，没有登录鉴权。放到公网前建议至少：

- 在反向代理层加 Basic Auth / 访问码；
- 限制上传大小（后端已有 80MB 上限）；
- 使用 HTTPS（localhost.run / Render 默认 HTTPS）；
- 不要把 `data/` 目录暴露为静态文件（当前只暴露 `/static` 与 `/testdata` 测试夹具）。

---

## 7. 关键数据与缓存

- `data/state.json`：供应商、单证、标准模型、合规确认
- `data/uploads/`：原始文件
- `data/outputs/`：已导出 Excel
- `data/scripts/`：每次生成的 Python 回填脚本 + payload
- `assets/au_chafta_tariff.json`：官方 ChAFTA 税则索引（DFAT FTA Portal 下载）
- `data/abf_chapters/`：ABF Schedule 3 章节缓存（按需抓取）
