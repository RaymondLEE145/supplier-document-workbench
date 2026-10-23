# 供应商单证工作台 · GitHub Pages 展示页

这是可直接分享到微信的 **HTTPS 静态展示页**（`github.io`），不依赖本机、不会触发非标准端口风控。

## 它能做什么

- 介绍工作台能力、5-Sheet 模板回填、ChAFTA/ABF/中国 HS 归类逻辑
- 交互式查询 11 个挖掘机附件的澳洲参考税号 / ChAFTA / PSR / 最终中国编码
- 下载当前 11 行导出样例 `excavator_11_rows.xlsx`
- 查看门禁、导出页、澳洲参考卡片截图

## 它不能做什么

GitHub Pages 只能托管静态 HTML/CSS/JS，**不能运行 FastAPI/Python 后端**，所以：

- 不能真实上传 PDF/图片/Excel 并解析
- 不能调用中国海关/ABF 接口、运行 OCR、WPS 重算
- 不能生成新的 Excel

完整交互工具需要后端：本地运行、GitHub Codespaces，或 Render 等容器平台。展示页会明确标注这一点，避免误导。

## 部署

仓库根目录的 `.github/workflows/pages.yml` 会在 push `main` 后发布 `pages/` 目录到 GitHub Pages。公开地址：

```text
https://<github-user>.github.io/supplier-document-workbench/
```
