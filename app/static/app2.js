/* Supplier Document Workbench — Vue 3 SPA (no build step) */
const { createApp } = Vue;

const API = {
  async get(path) {
    const sep = path.includes("?") ? "&" : "?";
    const r = await fetch(path + sep + "_t=" + Date.now(), { headers: { "Accept": "application/json", "Cache-Control": "no-cache" } });
    if (!r.ok) {
      let detail = "";
      try { detail = (await r.json()).detail || ""; } catch (e) {}
      throw new Error(detail || `HTTP ${r.status}`);
    }
    return r.json();
  },
  async send(path, method, body) {
    const r = await fetch(path, {
      method,
      headers: body instanceof FormData ? {} : { "Content-Type": "application/json" },
      body: body instanceof FormData ? body : JSON.stringify(body || {}),
    });
    if (!r.ok) {
      let detail = "";
      try { const j = await r.json(); detail = j.detail || j.error || JSON.stringify(j); } catch (e) {}
      throw new Error(detail || `HTTP ${r.status}`);
    }
    return r.json();
  },
};

createApp({
  data() {
    return {
      scope: "supplier",
      supplierId: null,
      activeId: null,
      step: 1,
      steps: [
        { id: 1, n: "01", zh: "上传单证", en: "UPLOAD" },
        { id: 2, n: "02", zh: "识别结果", en: "IDENTIFY" },
        { id: 3, n: "03", zh: "人工校对", en: "REVIEW" },
        { id: 4, n: "04", zh: "汇总导出", en: "EXPORT" },
      ],
      suppliers: [],
      files: [],
      documents: [],
      analysis: null,
      compliance: { records: [], summary: {}, gate: {}, attempts: [] },
      template: {},
      llm: {},
      exports: [],
      mapping: null,
      healthOk: false,
      dragOver: false,
      uploadJob: null,
      uploadError: "",
      exportJob: null,
      exportBusy: false,
      supplementJob: null,
      supplementBusy: false,
      autoSupplemented: false,
      reidentifyBusy: false,
      supplementConfirming: false,
      cardsLoading: false,
      modal: { supplier: false, rename: false, supplement: false, settings: false, selfCheck: false, manual: false },
      newSupplierName: "",
      renameName: "",
      renameTarget: null,
      docFilter: "all",
      expandedDoc: null,
      supplementFilter: "all",
      lastExport: null,
      showScript: false,
      outputName: "",
      ackUnsupported: false,
      settings: { llm: { base_url: "https://api.deepseek.com/v1", model: "deepseek-chat", api_key: "" } },
      manual: { item_id: "", hs_code: "", source_url: "", matched_evidence: "" },
      selfCheck: { loading: false, checks: [] },
      toasts: [],
      pollTimer: null,
      jobKind: "",
      pollCount: 0,
    };
  },
  computed: {
    activeSupplier() {
      return this.suppliers.find((s) => s.id === this.supplierId) || null;
    },
    currentFiles() {
      if (this.scope === "all") return this.files;
      return this.files.filter((f) => f.supplier_id === this.supplierId);
    },
    analysisItems() {
      return (this.analysis && this.analysis.items) || [];
    },
    totals() {
      return (this.analysis && this.analysis.totals) || {};
    },
    gate() {
      return (this.compliance && this.compliance.gate) || (this.analysis && this.analysis.gate) || {
        ok: false, needs_run: true, unconfirmed: [], missing_hs: [], supported: 0, confirmed: 0, unsupported: 0,
      };
    },
    coverage() {
      return (this.analysis && this.analysis.doc && this.analysis.doc.coverage) || {};
    },
    missingSheetLabels() {
      const labels = { packing_list: "装箱单", invoice: "发票", sales_confirmation: "销售合同", customs_declaration: "报关单", declaration_elements: "申报要素" };
      return Object.entries(labels).filter(([k]) => !this.coverage[k]).map(([, v]) => v);
    },
    mappingSheets() {
      if (!this.mapping || !this.mapping.sheets) return [];
      return this.mapping.sheets.filter((s) => s.role && s.role !== "unmapped");
    },
    displayDocuments() {
      let docs = this.documents || [];
      if (this.scope === "supplier") docs = docs.filter((d) => d.supplier_id === this.supplierId);
      const mapped = docs.map((d) => ({ ...d, supplier_name: this.supplierName(d.supplier_id) }));
      const failedFiles = (this.currentFiles || []).filter((f) => f.status === "failed");
      const haveFiles = new Set(mapped.map((d) => d.file_id).filter(Boolean));
      for (const f of failedFiles) {
        if (!haveFiles.has(f.id)) {
          mapped.push({
            id: "failed_" + f.id, file_id: f.id, supplier_id: f.supplier_id, filename: f.filename,
            type: f.type, format: f.ext, status: "failed", fields: {}, items: [], structure: {}, error: f.error,
            supplier_name: this.supplierName(f.supplier_id),
          });
        }
      }
      return mapped;
    },
    filteredDocs() {
      if (this.docFilter === "all") return this.displayDocuments;
      return this.displayDocuments.filter((d) => {
        if (this.docFilter === "image") return d.format === "image" || /\.(png|jpe?g|webp|bmp)$/i.test(d.filename || "");
        return d.type === this.docFilter;
      });
    },
    documentFilters() {
      const all = this.displayDocuments;
      const count = (fn) => all.filter(fn).length;
      return [
        { key: "all", label: "全部", count: all.length },
        { key: "packing_list", label: "装箱单", count: count((d) => d.type === "packing_list") },
        { key: "invoice", label: "发票", count: count((d) => d.type === "invoice") },
        { key: "combined", label: "合并单据", count: count((d) => d.type === "combined") },
        { key: "image", label: "扫描件", count: count((d) => d.format === "image" || /\.(png|jpe?g|webp)$/i.test(d.filename || "")) },
      ];
    },
    stats() {
      const files = this.currentFiles || [];
      return {
        files: files.length,
        failed: files.filter((f) => f.status === "failed").length,
        docs: this.displayDocuments.length,
      };
    },
    gateClass() {
      if (this.gate.ok) return "ok";
      if (this.gate.needs_run) return "warn";
      if ((this.gate.unconfirmed || []).length || (this.gate.missing_hs || []).length) return "bad";
      return "warn";
    },
    gateLabel() {
      if (this.gate.ok) return "PASSED";
      if (this.gate.needs_run) return "NOT RUN";
      if ((this.gate.missing_hs || []).length) return "MISSING HS";
      if ((this.gate.unconfirmed || []).length) return "UNCONFIRMED";
      return "REVIEW";
    },
    gateTitle() {
      if (this.gate.ok) return "合规门禁已通过";
      if (this.gate.needs_run) return "尚未运行智能补充";
      if ((this.gate.missing_hs || []).length) return "缺少 HS 编码，导出已阻断";
      if ((this.gate.unconfirmed || []).length) return "存在未确认的溯源数据";
      return "请检查合规字段";
    },
    gateDescription() {
      if (this.gate.ok) return "所有 supported 字段均已人工确认；可以生成代码并回填模板。";
      if (this.gate.needs_run) return "先运行智能补充，获取中国海关 / ABF 官方证据；未确认的补充数据不会进入导出。";
      if ((this.gate.missing_hs || []).length) return "至少一个商品项没有 10 位 HS 编码。可运行智能补充或人工补充官方证据。";
      if ((this.gate.unconfirmed || []).length) return "请打开溯源卡片，确认全部 supported 值；未确认前导出按钮不会执行。";
      return "请检查模板映射与补充状态。";
    },
    confirmedCount() {
      return (this.compliance.records || []).filter((r) => r.confirmed).length;
    },
    pendingRecords() {
      return (this.compliance.records || []).filter((r) => r.status === "supported" && !r.confirmed);
    },
    supplementFilters() {
      const all = this.compliance.records || [];
      return [
        { key: "all", label: "全部", count: all.length },
        { key: "pending", label: "待确认", count: all.filter((r) => r.status === "supported" && !r.confirmed).length },
        { key: "supported", label: "已支持", count: all.filter((r) => r.status === "supported").length },
        { key: "unsupported", label: "未支持", count: all.filter((r) => r.status === "unsupported").length },
      ];
    },
    filteredSupplementRecords() {
      let rows = this.compliance.records || [];
      if (this.supplementFilter === "pending") rows = rows.filter((r) => r.status === "supported" && !r.confirmed);
      else if (this.supplementFilter === "supported") rows = rows.filter((r) => r.status === "supported");
      else if (this.supplementFilter === "unsupported") rows = rows.filter((r) => r.status === "unsupported");
      return rows;
    },
    reviewJson() {
      const data = { document: (this.analysis && this.analysis.doc) || {}, items: this.analysisItems };
      let s = JSON.stringify(data, null, 2);
      if (s.length > 9000) s = s.slice(0, 9000) + "\n… (truncated)";
      return s;
    },
    stepEyebrow() {
      return ["", "UPLOAD DOCUMENTS", "IDENTIFY · STRUCTURE", "HUMAN REVIEW", "EXPORT · TEMPLATE FILL"][this.step];
    },
    stepTitle() {
      if (this.step === 4) return this.scope === "all" ? "集货汇总导出" : "当前供应商导出";
      return ["", "上传单证", "识别结果", "人工校对", "导出"][this.step];
    },
    stepSubtitle() {
      return [
        "",
        "把不同供应商的 PDF / 图片 / Excel 单证拖进来，后台静默完成结构解析、配对与去重。",
        "查看文件级结构元数据、标准化货物行与目标模板映射；需要时运行官方溯源补充。",
        "逐行核对标准字段与原始 JSON，确认无误后进入导出。",
        "读取你的 5-Sheet 模板，生成并执行 Python 回填脚本，校验样式、公式与数据后下载。",
      ][this.step];
    },
    canUpload() {
      return this.scope === "supplier" && !!this.supplierId;
    },
  },
  async mounted() {
    // Do not block the supplier list on template inspection (openpyxl can take seconds cold).
    this.loadMapping();
    this.scope = "all";
    await this.loadState();
    if (this.suppliers.length && this.scope !== "supplier") {
      this.scope = "supplier";
      this.supplierId = this.activeId || this.suppliers[0].id;
      await this.loadState();
    }
    if (!this.autoSupplemented && this.analysisItems.some(i => !i.hs_code)) {
      this.autoSupplemented = true;
      setTimeout(() => this.runSupplement(), 300);
    }
    this.step = 1;
    this.fetchHealth();
    setInterval(() => this.fetchHealth(), 30000);
  },
  methods: {
    async fetchHealth() {
      try { const h = await API.get("/api/health"); this.healthOk = !!h.ok; } catch (e) { this.healthOk = false; }
    },
    async loadState(silent = false) {
      let s = null;
      let lastErr = null;
      for (let attempt = 0; attempt < 3 && !s; attempt++) {
        try {
          let q = `/api/state?scope=${encodeURIComponent(this.scope)}`;
          if (this.scope === "supplier" && this.supplierId) q += `&supplier_id=${encodeURIComponent(this.supplierId)}`;
          s = await API.get(q);
        } catch (e) {
          lastErr = e;
          await new Promise((r) => setTimeout(r, 650));
        }
      }
      if (!s) {
        if (!silent) this.toast(`读取工作台状态失败：${lastErr ? lastErr.message : "网络错误"}`, "error");
        return;
      }
      try {
        this.suppliers = s.suppliers || [];
        this.files = s.files || [];
        this.documents = s.documents || [];
        this.analysis = s.analysis || null;
        this.compliance = s.compliance || { records: [], summary: {}, gate: {} };
        this.template = s.template || {};
        this.llm = s.llm || {};
        this.exports = s.exports || [];
        this.healthOk = true;
        // The backend resolves a single-supplier aggregate request to that
        // supplier, so one request is enough for the first paint.
        if (s.scope) this.scope = s.scope;
        if (s.scope === "supplier" && s.supplier_id) this.supplierId = s.supplier_id;
        this.activeId = s.active_supplier_id || this.activeId;
        if (this.scope === "supplier" && !this.supplierId && this.suppliers.length) {
          this.supplierId = this.suppliers[0].id;
        }
        if (this.supplierId && !this.suppliers.some((x) => x.id === this.supplierId)) {
          this.supplierId = this.suppliers[0] ? this.suppliers[0].id : null;
        }
        if (this.suppliers.length && !this.supplierId) this.supplierId = this.suppliers[0].id;
        if (this.template && this.template.filename) {
          // keep mapping in sync after template replacement
          if (!this.mapping || (this.mapping.template && this.mapping.template.hash !== this.template.hash)) this.loadMapping();
        }
      } catch (e) {
        if (!silent) this.toast(`读取工作台状态失败：${e.message}`, "error");
      }
    },
    async loadMapping() {
      try {
        const m = await API.get("/api/template/inspect");
        this.mapping = m.mapping || null;
        if (!this.template || !this.template.filename) this.template = m.template || {};
      } catch (e) {
        // template may not be ready during first boot
      }
    },
    async selectSupplier(s) {
      this.scope = "supplier";
      this.supplierId = s.id;
      this.autoSupplemented = false;
      await this.loadState();
      this.step = (s.items || 0) > 0 ? 2 : 1;
    },
    scopeSupplier() {
      const pick = this.suppliers.find((s) => s.id === this.supplierId)
        || this.suppliers.find((s) => s.id === this.activeId) || this.suppliers[0];
      if (pick) this.selectSupplier(pick);
      else this.toast("还没有供应商，请先新建", "error");
    },
    async scopeAll() {
      this.scope = "all";
      this.supplierId = null;
      this.autoSupplemented = false;
      await this.loadState();
      this.step = this.analysisItems.length ? 2 : 1;
    },
    async exportScopeSupplier() {
      const pick = this.suppliers.find((s) => s.id === this.supplierId)
        || this.suppliers.find((s) => s.id === this.activeId) || this.suppliers[0];
      if (!pick) { this.toast("还没有供应商，请先新建", "error"); return; }
      this.scope = "supplier";
      this.supplierId = pick.id;
      this.autoSupplemented = false;
      await this.loadState();
      this.step = 4;
    },
    async exportScopeAll() {
      this.scope = "all";
      this.supplierId = null;
      this.autoSupplemented = false;
      await this.loadState();
      this.step = 4;
    },
    goUpload() {
      if (this.scope !== "supplier") this.scopeSupplier();
      this.step = 1;
    },
    canGo(n) {
      if (n === 1) return true;
      if (n === 2) return this.analysisItems.length > 0 || this.displayDocuments.length > 0;
      return this.analysisItems.length > 0;
    },
    setStep(n) {
      if (!this.canGo(n)) { this.toast("请先完成上一步：上传并识别单证", "error"); return; }
      this.step = n;
    },
    goReview() {
      if (!this.analysisItems.length) { this.toast("还没有可校对的数据", "error"); return; }
      this.step = 3;
    },
    pickFiles() {
      if (!this.canUpload) { this.toast("请先选择具体供应商，再上传单证", "error"); return; }
      this.$refs.fileInput && this.$refs.fileInput.click();
    },
    onDrop(e) {
      this.dragOver = false;
      if (!this.canUpload) { this.toast("请先选择具体供应商，再上传单证", "error"); return; }
      const files = Array.from((e.dataTransfer && e.dataTransfer.files) || []);
      if (files.length) this.uploadFiles(files);
    },
    onFileInput(e) {
      const files = Array.from((e.target && e.target.files) || []);
      e.target.value = "";
      if (files.length) this.uploadFiles(files);
    },
    uploadFiles(files) {
      if (!this.canUpload) return;
      const allowed = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".xlsx", ".xlsm", ".xls"];
      const bad = files.find((f) => !allowed.some((x) => f.name.toLowerCase().endsWith(x)));
      if (bad) { this.uploadError = `不支持的文件类型：${bad.name}`; this.toast(this.uploadError, "error"); return; }
      this.uploadError = "";
      this.uploadJob = { status: "running", progress: 0, phase: "上传中", message: `正在上传 ${files.length} 份单证…`, logs: [] };
      const fd = new FormData();
      fd.append("supplier_id", this.supplierId);
      for (const f of files) fd.append("files", f, f.name);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/upload");
      xhr.upload.onprogress = (ev) => {
        if (ev.lengthComputable) {
          const p = Math.max(2, Math.min(18, Math.round((ev.loaded / ev.total) * 18)));
          this.uploadJob.progress = Math.max(this.uploadJob.progress, p);
          this.uploadJob.message = `正在上传单证 ${(ev.loaded / 1024 / 1024).toFixed(1)} MB / ${(ev.total / 1024 / 1024).toFixed(1)} MB`;
        }
      };
      xhr.onload = async () => {
        try {
          const data = JSON.parse(xhr.responseText || "{}");
          if (xhr.status >= 200 && xhr.status < 300 && data.job_id) {
            this.uploadJob.message = "文件已接收，后台启动结构解析…";
            this.pollJob(data.job_id, "upload");
          } else {
            const detail = data.detail && typeof data.detail === "object" ? JSON.stringify(data.detail) : (data.detail || data.error);
            throw new Error(detail || `上传失败 HTTP ${xhr.status}`);
          }
        } catch (e) {
          this.uploadJob.status = "failed";
          this.uploadError = e.message;
          this.toast(`上传失败：${e.message}`, "error");
        }
      };
      xhr.onerror = () => {
        this.uploadJob.status = "failed";
        this.uploadError = "网络错误：无法连接本地服务";
        this.toast(this.uploadError, "error");
      };
      xhr.send(fd);
    },
    pollJob(jobId, kind) {
      this.jobKind = kind;
      this.pollCount = 0;
      if (this.pollTimer) clearInterval(this.pollTimer);
      const maxSeconds = kind === "upload" ? 240 : (kind === "export" ? 240 : 150);
      const started = Date.now();
      this.pollTimer = setInterval(async () => {
        this.pollCount += 1;
        try {
          const j = await API.get(`/api/jobs/${jobId}`);
          if (kind === "upload") this.uploadJob = j;
          else if (kind === "compliance") this.supplementJob = j;
          else if (kind === "export") this.exportJob = j;
          if (j.status === "done" || j.status === "failed") {
            clearInterval(this.pollTimer); this.pollTimer = null;
            await this.onJobFinished(j, kind);
          }
          if ((Date.now() - started) / 1000 > maxSeconds) {
            clearInterval(this.pollTimer); this.pollTimer = null;
            const err = `任务超时（${maxSeconds} 秒）：${j.phase || "处理中"}。请检查服务日志后重试。`;
            if (kind === "upload") { this.uploadJob = { ...j, status: "failed", message: err }; this.uploadError = err; }
            if (kind === "compliance") { this.supplementBusy = false; this.supplementJob = { ...j, status: "failed", message: err }; }
            if (kind === "export") { this.exportBusy = false; }
            this.toast(err, "error");
          }
        } catch (e) {
          if (this.pollCount > 4) {
            clearInterval(this.pollTimer); this.pollTimer = null;
            if (kind === "upload") { this.uploadJob = { ...(this.uploadJob || {}), status: "failed", message: e.message }; this.uploadError = `轮询任务失败：${e.message}`; }
            if (kind === "compliance") this.supplementBusy = false;
            if (kind === "export") this.exportBusy = false;
            this.toast(`任务状态读取失败：${e.message}`, "error");
          }
        }
      }, 700);
    },
    async onJobFinished(job, kind) {
      if (job.status === "failed") {
        if (kind === "upload") {
          this.uploadError = job.error || job.message || "解析失败：后台任务异常";
          this.toast(this.uploadError, "error");
        } else if (kind === "compliance") {
          this.supplementBusy = false;
          this.supplementJob = job;
          this.modal.supplement = true;
          this.toast(job.error || "智能补充失败", "error");
        } else if (kind === "export") {
          this.exportBusy = false;
          this.toast(job.error || "导出失败", "error");
        }
        await this.loadState(true);
        return;
      }
      if (kind === "upload") {
        this.uploadError = "";
        await this.loadState();
        this.step = 2;
        if (!this.autoSupplemented && this.analysisItems.some(i => !i.hs_code)) {
          this.autoSupplemented = true;
          setTimeout(() => this.runSupplement(), 250);
        }
        const r = job.result || {};
        this.toast(`识别完成：${r.items || 0} 行货物${r.duplicates_removed ? `，去重 ${r.duplicates_removed} 行` : ""}`, "success");
      } else if (kind === "compliance") {
        this.supplementBusy = false;
        this.supplementJob = job;
        await this.loadState();
        this.modal.supplement = true;
        this.supplementFilter = "all";
        this.loadSupplementCards();
        this.toast(`智能补充完成：${this.compliance.summary?.supported || 0} 条有官方证据，需人工确认`, "success");
      } else if (kind === "export") {
        this.exportBusy = false;
        await this.loadState();
        if (job.result && job.result.export) {
          this.lastExport = job.result.export;
          this.showScript = false;
          this.step = 4;
          this.toast(`导出成功：${job.result.export.filename}`, "success");
        } else if (job.result && job.result.blocked) {
          this.toast(job.result.error || "合规门禁阻断导出", "error");
          this.modal.supplement = true;
        } else {
          this.toast("导出任务完成，但未返回文件记录", "error");
        }
      }
    },
    async runSupplement() {
      if (!this.analysisItems.length) { this.toast("当前视图没有可补充的货物行", "error"); return; }
      if (this.supplementBusy) return;
      this.supplementBusy = true;
      this.modal.supplement = true;
      this.supplementJob = { status: "running", progress: 3, phase: "准备", message: "正在登记官方取证任务…", logs: [] };
      try {
        const data = await API.send("/api/compliance/run", "POST", { scope: this.scope, supplier_id: this.scope === "supplier" ? this.supplierId : null });
        if (!data.job_id) throw new Error("未返回任务 ID");
        this.pollJob(data.job_id, "compliance");
      } catch (e) {
        this.supplementBusy = false;
        this.supplementJob = { status: "failed", progress: 100, phase: "失败", message: e.message, logs: [] };
        this.toast(`智能补充启动失败：${e.message}`, "error");
      }
    },
    openSupplement() {
      this.modal.supplement = true;
      if (!this.compliance.records || !this.compliance.records.length) this.runSupplement();
      else this.loadSupplementCards();
    },
    async loadSupplementCards() {
      if (this.cardsLoading) return;
      // already have full cards (reason field) → no extra request
      if ((this.compliance.records || []).some((r) => r.reason)) return;
      this.cardsLoading = true;
      try {
        let q = `/api/compliance/records?scope=${encodeURIComponent(this.scope)}`;
        if (this.scope === "supplier" && this.supplierId) q += `&supplier_id=${encodeURIComponent(this.supplierId)}`;
        const data = await API.get(q);
        this.compliance.records = data.records || [];
        if (data.summary) this.compliance.summary = data.summary;
        if (data.gate) this.compliance.gate = data.gate;
      } catch (e) {
        this.toast(`读取溯源卡片失败：${e.message}`, "error");
      } finally {
        this.cardsLoading = false;
      }
    },
    closeSupplement() {
      this.modal.supplement = false;
      if (!this.supplementBusy) this.supplementJob = null;
    },
    async toggleRecord(r) {
      const next = !r.confirmed;
      r.confirmed = next;
      try {
        let res = null, last = null;
        for (let attempt = 0; attempt < 3 && !res; attempt++) {
          try {
            res = await API.send("/api/compliance/confirm", "POST", {
              ids: [r.id], confirmed: next, scope: this.scope, supplier_id: this.scope === "supplier" ? this.supplierId : null,
            });
          } catch (e) {
            last = e;
            if (!/50[234]/.test(e.message) && !/network|Failed to fetch/i.test(e.message)) throw e;
            await new Promise((ok) => setTimeout(ok, 650));
          }
        }
        if (!res) throw last || new Error("网络错误");
        if (res.gate) this.compliance.gate = res.gate;
        this.loadState(true);
      } catch (e) {
        r.confirmed = !next;
        this.toast(`确认失败：${e.message}`, "error");
      }
    },
    async confirmAll() {
      const ids = this.pendingRecords.map((r) => r.id);
      if (!ids.length) { this.toast("没有待确认的记录", "error"); return; }
      this.supplementConfirming = true;
      try {
        let res = null, last = null;
        for (let attempt = 0; attempt < 3 && !res; attempt++) {
          try {
            res = await API.send("/api/compliance/confirm", "POST", {
              ids, confirmed: true, scope: this.scope, supplier_id: this.scope === "supplier" ? this.supplierId : null,
            });
          } catch (e) {
            last = e;
            if (!/50[234]/.test(e.message) && !/network|Failed to fetch/i.test(e.message)) throw e;
            await new Promise((ok) => setTimeout(ok, 650));
          }
        }
        if (!res) throw last || new Error("网络错误");
        for (const r of this.compliance.records || []) {
          if (ids.includes(r.id)) r.confirmed = true;
        }
        if (res.gate) this.compliance.gate = res.gate;
        this.compliance.summary = { ...(this.compliance.summary || {}), confirmed: this.confirmedCount };
        this.toast(`已确认并应用 ${ids.length} 条溯源记录`, "success");
        if (this.gate.ok) this.modal.supplement = false;
        setTimeout(() => { this.loadState(true); }, 300);
      } catch (e) {
        this.toast(`确认失败：${e.message}`, "error");
      } finally {
        this.supplementConfirming = false;
      }
    },
    async reidentify() {
      if (this.reidentifyBusy) return;
      this.reidentifyBusy = true;
      try {
        await API.send("/api/identify", "POST", { scope: this.scope, supplier_id: this.scope === "supplier" ? this.supplierId : null });
        await this.loadState();
        this.step = 2;
        this.toast("已重新识别并重建标准模型", "success");
      } catch (e) {
        this.toast(`重新识别失败：${e.message}`, "error");
      } finally {
        this.reidentifyBusy = false;
      }
    },
    async startExport() {
      if (this.exportBusy) return;
      if (this.gate.needs_run) { this.runSupplement(); return; }
      if ((this.gate.unconfirmed || []).length) { this.openSupplement(); this.toast("请先确认全部溯源数据", "error"); return; }
      if ((this.gate.missing_hs || []).length) { this.openManualHs(); this.toast("请先补齐缺失的 HS 编码", "error"); return; }
      this.exportBusy = true;
      this.exportJob = { status: "running", progress: 3, phase: "准备", message: "正在校验合规门禁与模板…" };
      try {
        const data = await API.send("/api/export", "POST", {
          scope: this.scope, supplier_id: this.scope === "supplier" ? this.supplierId : null,
          acknowledge_unsupported: this.ackUnsupported, output_name: this.outputName || "",
        });
        if (!data.job_id) throw new Error("未返回任务 ID");
        this.pollJob(data.job_id, "export");
      } catch (e) {
        this.exportBusy = false;
        this.toast(`导出启动失败：${e.message}`, "error");
      }
    },
    downloadExport(id) {
      if (!id) return;
      window.location.href = `/api/download/${id}`;
    },
    downloadTemplate() {
      window.location.href = "/api/template/download";
    },
    async uploadTemplate(e) {
      const f = e.target.files && e.target.files[0];
      e.target.value = "";
      if (!f) return;
      const fd = new FormData();
      fd.append("file", f, f.name);
      try {
        await API.send("/api/template", "POST", fd);
        await this.loadMapping();
        await this.loadState();
        this.toast("目标模板已替换并通过 5-Sheet 校验", "success");
      } catch (err) {
        this.toast(`模板上传失败：${err.message}`, "error");
      }
    },
    openNewSupplier() { this.newSupplierName = ""; this.modal.supplier = true; },
    async createSupplier() {
      const name = (this.newSupplierName || "").trim();
      if (!name) { this.toast("请输入供应商名称", "error"); return; }
      try {
        const r = await API.send("/api/suppliers", "POST", { name });
        this.modal.supplier = false;
        this.scope = "supplier";
        this.supplierId = r.supplier.id;
        await this.loadState();
        this.step = 1;
        this.toast(`已创建供应商：${name}`, "success");
      } catch (e) {
        this.toast(`创建失败：${e.message}`, "error");
      }
    },
    openRename(s) { this.renameTarget = s; this.renameName = s.name; this.modal.rename = true; },
    async renameSupplier() {
      const name = (this.renameName || "").trim();
      if (!name || !this.renameTarget) { this.toast("名称不能为空", "error"); return; }
      try {
        await API.send(`/api/suppliers/${this.renameTarget.id}`, "PATCH", { name });
        this.modal.rename = false;
        await this.loadState();
        this.toast("供应商名称已更新", "success");
      } catch (e) {
        this.toast(`重命名失败：${e.message}`, "error");
      }
    },
    async removeSupplier(s) {
      if (!window.confirm(`确定删除「${s.name}」及其 ${s.files} 份单证？此操作不可撤销。`)) return;
      try {
        await API.send(`/api/suppliers/${s.id}`, "DELETE");
        if (this.supplierId === s.id) this.supplierId = null;
        await this.loadState();
        this.toast("供应商已删除", "success");
      } catch (e) {
        this.toast(`删除失败：${e.message}`, "error");
      }
    },
    openSettings() {
      this.settings = {
        llm: {
          base_url: (this.llm && this.llm.base_url) || "https://api.deepseek.com/v1",
          model: (this.llm && this.llm.model) || "deepseek-chat",
          api_key: "",
        },
      };
      this.modal.settings = true;
    },
    async saveSettings() {
      try {
        await API.send("/api/settings", "POST", { llm: this.settings.llm });
        this.toast("设置已保存", "success");
      } catch (e) {
        this.toast(`保存失败：${e.message}`, "error");
      }
    },
    async openSelfCheck() {
      this.modal.selfCheck = true;
      this.selfCheck = { loading: true, checks: [] };
      try {
        const r = await API.send("/api/self-check", "POST", {});
        this.selfCheck = { loading: false, checks: r.checks || [] };
      } catch (e) {
        this.selfCheck = { loading: false, checks: [{ name: "自查失败", ok: false, detail: e.message }] };
      }
    },
    openManualHs() {
      const missing = this.analysisItems.find((i) => !i.hs_code);
      this.manual = {
        item_id: missing ? missing.id : (this.analysisItems[0] ? this.analysisItems[0].id : ""),
        hs_code: "",
        source_url: "https://online.customs.gov.cn/ociswebserver/pages/jckspsl/index.html",
        matched_evidence: "",
      };
      this.modal.manual = true;
    },
    async submitManual() {
      if (!this.manual.item_id || !this.manual.hs_code || !this.manual.source_url || !this.manual.matched_evidence) {
        this.toast("请填写货物行、HS 编码、官方 URL 与逐字证据", "error"); return;
      }
      try {
        await API.send("/api/compliance/manual", "POST", this.manual);
        this.modal.manual = false;
        await this.loadState();
        this.toast("人工证据已通过官网校验并写入", "success");
      } catch (e) {
        this.toast(`人工补充失败：${e.message}`, "error");
      }
    },
    async demoLoad() {
      try {
        const r = await API.get("/api/demo/load");
        await this.loadState();
        if (r.suppliers && r.suppliers.length) {
          this.scope = "supplier";
          this.supplierId = r.suppliers[r.suppliers.length - 1];
          await this.loadState();
        }
        this.step = 2;
        this.toast("演示单证已通过真实解析管线载入", "success");
      } catch (e) {
        this.toast(`载入演示失败：${e.message}`, "error");
      }
    },
    toast(message, type = "info") {
      const id = Date.now() + Math.random();
      this.toasts.push({ id, message, type });
      setTimeout(() => { this.toasts = this.toasts.filter((t) => t.id !== id); }, 4600);
    },
    supplierName(id) {
      const s = this.suppliers.find((x) => x.id === id);
      return s ? s.name : "—";
    },
    initials(name) {
      const s = String(name || "").replace(/[（）()]/g, "");
      return s.slice(0, 2) || "供";
    },
    number(v, digits = 0) {
      if (v === null || v === undefined || v === "" || isNaN(Number(v))) return "0";
      return Number(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
    },
    money(v) {
      if (v === null || v === undefined || v === "" || isNaN(Number(v))) return "0.00";
      return Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
    money4(v) {
      if (v === null || v === undefined || v === "" || isNaN(Number(v))) return "0.0000";
      return Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    },
    moneyShort(v) {
      const n = Number(v) || 0;
      if (n >= 1000000) return "$" + (n / 1000000).toFixed(2) + "M";
      if (n >= 1000) return "$" + (n / 1000).toFixed(1) + "K";
      return "$" + n.toFixed(0);
    },
    sizeText(bytes) {
      const n = Number(bytes) || 0;
      if (n > 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
      if (n > 1024) return (n / 1024).toFixed(0) + " KB";
      return n + " B";
    },
    cleanFileName(name) {
      return String(name || "").replace(/^file_[a-f0-9]{12}_/, "");
    },
    fileKind(f) {
      if (!f) return "file";
      const ext = String(f.ext || f.filename || "").toLowerCase();
      if (ext.includes("pdf")) return "pdf";
      if (ext.includes("xls")) return "xlsx";
      if (ext.includes("png") || ext.includes("jpg") || ext.includes("jpeg") || ext.includes("webp")) return "image";
      return "file";
    },
    fileStatusClass(f) {
      if (!f) return "neutral";
      if (f.status === "parsed") return "ok";
      if (f.status === "failed") return "danger";
      if (f.status === "duplicate") return "gold";
      return "neutral";
    },
    fileStatusLabel(s) {
      return { parsed: "已解析", failed: "解析失败", duplicate: "重复跳过", queued: "排队中", running: "解析中" }[s] || (s || "未知");
    },
    docTypeLabel(t) {
      return { packing_list: "装箱单", invoice: "发票", combined: "装箱单 + 发票", declaration: "报关单", unknown: "未分类" }[t] || (t || "未分类");
    },
    docPages(d) {
      const st = d.structure || {};
      const pages = st.pages || st.sheets;
      if (pages && pages.length) return pages.length + " / " + (st.table_count || pages.length);
      return "1 / 1";
    },
    structureSummary(d) {
      const st = d.structure || {};
      const out = {
        format: st.format || d.format, engine: st.coordinate_engine || st.ocr || "—",
        tables: st.table_count || (st.sheets ? st.sheets.length : 0),
        pages: (st.pages || []).map((p) => ({ page: p.page, w: p.width, h: p.height, tables: (p.tables || []).length })),
        sheets: (st.sheets || []).map((s) => ({ title: s.title, dim: s.dim, merges: (s.merges || []).length, header: s.header_row })),
        warnings: d.warnings || [],
      };
      return JSON.stringify(out, null, 2);
    },
    compactFields(fields) {
      const out = {};
      for (const k of ["invoice_no", "contract_no", "date", "supplier_name", "consignee", "loading_port", "destination", "incoterm", "currency", "total_amount", "container_no"]) {
        if (fields && fields[k]) out[k] = String(fields[k]).slice(0, 100);
      }
      return out;
    },
    fieldLabel(k) {
      return {
        no: "序号", name_en: "英文品名", name_zh: "中文品名", hs_code: "HS CODE", material: "材质",
        cartons: "箱数", pieces_per_carton: "每箱件数", pieces: "计价件数", unit_price: "单价", amount: "金额",
        gross_weight: "毛重", net_weight: "净重", cbm: "CBM", length: "L", width: "W", height: "H",
        packing: "包装类型", model: "型号", brand: "品牌", origin: "原产地", usage: "用途", processing: "加工工艺",
        scenario: "适用场景", preference: "优惠关税", preference_eligible: "优惠资格", origin_criterion: "原产地标准",
        invoice_no: "发票号", contract_no: "合同号", date: "日期", supplier_name: "供应商", consignee: "收货人",
        loading_port: "起运港", destination: "目的地", incoterm: "成交方式", currency: "币种", total_amount: "总金额",
        container_no: "集装箱号", declaration_elements: "申报要素", product_name_en: "英文品名", product_name_zh: "中文品名",
        picture: "产品图", preference: "优惠关税", unit: "单位", amount_currency: "总价/币制",
        source: "境内货源地", exemption: "征免", destination_country: "目的国", origin: "原产地",
        au_hs_code: "澳洲参考税号", au_tariff: "澳洲参考税号",
      }[k] || k;
    },
  },
}).mount("#app");
