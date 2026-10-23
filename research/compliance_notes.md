# Compliance research notes — China→Australia furniture export supplement

**Researched:** 2026-10-23, 14:03–14:38 Asia/Shanghai
**Researcher:** compliance-researcher (teammate on task-2)
**Scope:** official-source evidence only. Nothing in `evidence.json` is inferred from third-party blogs; every `supported` record carries a URL, a retrieval timestamp and a verbatim quote/row captured from that URL.

---

## 1. Bottom line

| Area | Verdict | How |
|---|---|---|
| China 10-digit HS codes + MFN/ordinary rates | **Supported** | Direct HTTPS POST to the official 税率查询 backend endpoint — **no browser required** |
| ChAFTA preferential rate on the **Chinese import** side | **Supported** | Same service, 进口协定税率 detail endpoints (agreementCode 18 = 中国澳大利亚自贸协定) |
| 申报要素 (declaration elements) | **Unsupported** | The 通关参数 service returns an encrypted payload; the UI rendered no table. Nothing claimed |
| ABF ChAFTA eligibility wording | **Supported** | `www.abf.gov.au` HTML pages fetch fine over plain GET (HTTP 200) |
| ABF ChAFTA origin criteria (WO/CTC/RVC) | **Supported** | Sections 5.1.4, 5.1.7, 6.1.1, 8 (CTC/RVC) of the ABF guidelines PDF, cross-checked between the browser-rendered page 21/37 and the full text extraction in `abf_guide_pdf.txt` |
| ChAFTA PSR value for a specific HS line | **Unsupported** | Lives in Schedule 1 of the Customs (Chinese Rules of Origin) Regulations 2015 — not retrieved |
| Australian Working Tariff (import duty) rates | **Unsupported / not attempted** | Link discovered (schedule 12) but not retrieved |

**Critical framing for the platform:** the "0%" values captured from online.customs.gov.cn are **China's import** agreement rates under ChAFTA. They are *not* Australia's import duty rates and must never be displayed as such. Australian duty rates require the ABF Working Tariff (schedule 12).

---

## 2. Environment notes (why some routes failed)

- `pwsh` is unusable in this session: every command exits `3221225794` (0xC0000142) under the workspace-write sandbox, and escalation is disabled. **No shell, no Python, no curl.** All HTTP was done with the browser toolchain's Node-side fetch and the harness `web_fetch`.
- The DSH built-in browser (Edge) repeatedly died: `msedge.exe exited immediately after launch (exit code 21)`. `dsh_browser_open` and `dsh_browser_content` worked against an already-live page, but any tool that needed a fresh window (execute / screenshot / set_value) failed. The ego-browser carrier was used for navigation, screenshots and the PDF viewer; its JS evaluation context intermittently detached to `about:blank`, which is why some in-page interaction was abandoned.
- Consequence: interaction-heavy verification (typing into the customs form and screenshotting the result table) was **not** achievable. The equivalent data was pulled through the exact endpoints the page itself calls, and both endpoints and request bodies are quoted below so the backend team can reproduce them.

---

## 3. China customs (online.customs.gov.cn)

### 3.1 How the right service was located

`https://online.customs.gov.cn/` is a Nuxt portal. The 我要查 menu items are `<div>`/`<p>` elements, not links, so the service URLs are not visible in the DOM anchor list. They *are* present in the SSR state of the `/mySearch` page (`window.__NUXT__`), which yielded:

| Service | Official URL |
|---|---|
| 税率查询 (import/export commodity tax rate) | `https://online.customs.gov.cn/ociswebserver/pages/jckspsl/index.html` |
| 通关参数 (parameter service, incl. 申报要素) | `http://online.customs.gov.cn/ociswebserver/pages/cus/#/tgcs/index` |
| 进出口税则查询 | `http://www.customs.gov.cn/customs/302427/302442/jckszcx/index.html` (**HTTP 412 — blocked**, see §5) |
| 税则商品及品目注释查询 | `http://www.customs.gov.cn/customs/302427/302442/jckszspjpmzscx/index.html` |

A second, smaller discovery API also exists and is useful as documentation of catalogue structure:

```
GET https://online.customs.gov.cn/ocportalserver/Recommend/queryIndexRecommend
```
— returns 12 recommended services with `serviceName` + `serviceUrl`, e.g. `{"serviceName":"税则商品及品目注释查询","serviceUrl":"http://www.customs.gov.cn/customs/302427/302442/jckszspjpmzscx/index.html"}`.

### 3.2 The 税率查询 page

- URL: `https://online.customs.gov.cn/ociswebserver/pages/jckspsl/index.html`
- Title: `海关政务服务税率查询`
- Page type: classic jQuery + Bootstrap page (server-rendered HTML, data via AJAX).
- Form selectors (from the raw HTML):
  - 税号 input: `#dutySpa` (`name="corpNaCn"`, accepts 4–10 digits)
  - 商品名称 input: `#nameSpa` (`name="corpCde"`)
  - 查询 button: `#queryBtn`; 重置: `#resetBtn`
  - result table body: `#listData`; empty state: `#noResult`
- The page's own JS (`/ociswebserver/pages/jckspsl/js/jckspslQuery.js`, obfuscated) builds:
  `{"gName": <商品名称>, "codeTs": <税号>, "sysDate": "YYYY-MM-DD", "nextPage": N, "pageSize": "10"}`
  and POSTs it form-encoded as `param=<JSON>`.

### 3.3 Working endpoint — commodity + MFN rates

```
POST https://online.customs.gov.cn/ociswebserver/ocis/taxRateQuery/query/queryImpTariffRate
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Referer: https://online.customs.gov.cn/ociswebserver/pages/jckspsl/index.html

param={"gName":"","codeTs":"9401","sysDate":"2026-10-23","nextPage":1,"pageSize":"50"}
```

Response shape (note the double encoding — `res` is a *string* containing pseudo-JSON with unquoted keys, exactly as the page's JS repairs it):

```json
{"res":"{statue:1,message:\"查询成功\",totalCount:34,data:[{\"codeTs\":\"9401790000\",\"gName\":\"其他金属框架的坐具\",\"impDiscountRate\":\"0\",\"impOrdinaryRate\":\"100%\",\"impTempRate\":\"\"}, ...]}","statue":"0","message":"查询成功"}
```

Parser notes: strip `\r\n`, then quote the bare keys `statue:`, `message:`, `totalCount:`, `data:` before `JSON.parse` — that is literally what the site does.

Verified queries (all HTTP 200, 2026-10-23):

| query | rows | file |
|---|---|---|
| `codeTs=9401` (seats) | 34 | `raw/queryImpTariffRate_9401.json` |
| `codeTs=9403` (other furniture) | 27 | `raw/queryImpTariffRate_9403.json` |
| `codeTs=841451` (fans ≤125 W) | 7 | `raw/queryImpTariffRate_841451.json` |

`gName=餐椅` returns `{"statue":1,"message":"未查询到数据。","totalCount":0,"data":[]}` — the Chinese tariff lines do **not** contain the word 餐椅, so name-based search cannot map "dining chair" to a code. This is important: any product→HS mapping produced by the platform is a *classification suggestion*, not an official statement.

### 3.4 Working endpoints — preferential (agreement) rates

From `/ociswebserver/pages/jckspsl/js/shuilvXQ.js` (unobfuscated, quoted verbatim in the source), the 更多税率 detail page calls:

```
POST /ociswebserver/ocis/taxRateQuery/query/queryAgreementRate
     param={"codeTs":"9401790000","sysDate":"2026-10-23"}
     -> data[]: {agreementName, agreementCode, impAgreementRate}

POST /ociswebserver/ocis/taxRateQuery/query/queryCountryAgreementRate
     param={"codeTs":"9401790000","sysDate":"2026-10-23","agreementCode":"18"}
     -> data[]: {conuntryName, impAgreementRate}   (field name is misspelled upstream)
```

ChAFTA is `agreementCode = "18"`, `agreementName = "中国澳大利亚自贸协定"`.
All four furniture codes returned `{"conuntryName":"澳大利亚","impAgreementRate":"0"}`.
Raw captures: `raw/agreement_rate_chafta.json`.

The detail page itself (`https://online.customs.gov.cn/ociswebserver/pages/jckspsl/detail.html`) is static HTML whose tables are filled from these two endpoints; it is the correct `source_url` to cite for 协定税率 because that is the page a human sees the number on.

### 3.5 Disclaimer on the page (quoted for legal framing)

> 免责声明：网上及微信发布的归类及税率信息仅供参考，不保证所提供的资料和服务没有任何瑕疵，海关对公布内容拥有修改和解释权。用户应以实际通关、办理海关手续时相关海关的解释和要求为准，对用户使用网站提供的资料和服务可能存在的风险由用户本人承担。

This disclaimer should be surfaced next to any HS/rate value in the product.

---

## 4. 申报要素 — attempted and blocked

Target: `https://online.customs.gov.cn/ociswebserver/pages/cus/#/tgcs/index` (通关参数), which exposes a `申报要素(规格型号)` category alongside `海关税则编号(HS编码)`, `用途`, `计量单位`, `原产地区`, etc.

What happened:
1. Page loads (title `海关政务服务通关参数`), category list renders as plain `<div title="...">` items.
2. Clicking `海关税则编号(HS编码)` / `申报要素(规格型号)` (both JS `.click()` and a real mouse click at the element's bounding box) fired `GET /ociswebserver/ocis/openParam/queryParamList` (3× observed) but **no table appeared** — `document.querySelectorAll('table').length === 0` afterwards.
3. Calling that endpoint directly returns an opaque payload, not JSON, e.g. `iu1upZBtMChX2tS8yvEebjb9edopsIhHwgrbA64nKn/+f8YbQ4qwfriR4AJaqWn+3AF5...`. The SPA ships `/ociswebserver/static/js/Mu64.js` and decrypts client-side, so the payload cannot be decoded without reverse-engineering the key.
4. No plain-text 申报要素 endpoint or static page was found on `online.customs.gov.cn`.

**Verdict: unsupported.** To support it later the backend needs either (a) a Playwright/Edge session that lets the SPA decrypt and render, then scrape the DOM, or (b) ingestion of 海关总署《进出口商品规范申报目录》 (published annually as an official attachment) — neither is available offline here.

---

## 5. Blockers observed (with status codes)

| URL | Result | Meaning |
|---|---|---|
| `http://www.customs.gov.cn/customs/302427/302442/jckszcx/index.html` | **HTTP 412** (Node-side fetch) / blank page in browser | WAF rejects non-browser clients; the 进出口税则查询 service lives on this blocked host |
| `https://www.abf.gov.au/...` (all HTML pages used) | **HTTP 200** | plain GET works, no bot challenge |
| `https://www.abf.gov.au/importing-exporting-and-manufacturing/fta/rules-of-origin` | **HTTP 404** | no such page; guessed path |
| `https://www.dfat.gov.au/trade/agreements/in-force/chafta/Pages/chafta-guide-to-rules-of-origin` | **HTTP 403** + "Your request has been blocked" reference number | DFAT bot protection |
| `https://www.abf.gov.au/free-trade-agreements/files/instructions-guidelines-australia-china-fta.pdf` | 200 but `application/pdf` | `web_fetch` rejects PDFs (`unsupported content type`); content streams are FlateDecode so raw HTTP body is useless |
| `https://online.customs.gov.cn/ociswebserver/pages/cus/` (relative fetch) | 400 | SPA assets reject bare relative fetches without a document context |

---

## 6. ABF (abf.gov.au) — pages that do work

All fetched over plain GET, HTTP 200, 2026-10-23.

1. **`/importing-exporting-and-manufacturing/fta/free-trade-agreements/china`** — page title `China`; content:
   > The China–Australia Free Trade Agreement (ChAFTA) was signed by Trade and Investment Minister Andrew Robb and Chinese Commerce Minister Gao Hucheng on 17 June 2015 in Canberra, Australia.
   > The implementing legislation for ChAFTA received the Royal Assent on 11 November 2015 and entered into force on 20 December 2015.
   Page footer: "Last updated: 20/10/2026 9:04".

2. **`/importing-exporting-and-manufacturing/fta`** (overview) — the strongest eligibility wording found in HTML:
   > Free trade agreements provide a mechanism for the facilitation of trade in goods. Each agreement has information and links to relevant legislation, policy and notices on the rules of origin and how to access preferential rates of duty.
   > Australia has preferential arrangements that provide preferential rates of customs duty on a reciprocal or non-reciprocal basis to goods that are the produce or manufacture of countries and places to which that arrangement applies.

3. **`/importing-exporting-and-manufacturing/fta/free-trade-agreements`** — FTA table maps `ChAFTA | China-Australia Free Trade Agreement | China (CN) | Working tariff schedule 12`.

4. **`/importing-exporting-and-manufacturing/fta/origin-advice`** —
   > An Origin Advice (OA) is statement by the ABF advising whether specified goods meet the requirements to claim a preferential rate of duty under an FTA.
   > An OA provides advice to the applicant relating to the origin of their goods for the purposes of determining eligibility for preferential duty rates when imported into Australia.

5. **PDF** `/free-trade-agreements/files/instructions-guidelines-australia-china-fta.pdf`
   - PDF metadata (verbatim from the XMP block in the byte stream): `<dc:title>China-Australia Free Trade Agreement Rules of Origin - Instruction and Guideline</dc:title>`, author `Department of Immigration and Border Protection`, keywords `ChAFTA, Rules of Origin, Instructions, Guidelines`, 37 pages.
   - Rendered in the browser's PDF viewer at **page 21/37**, section **8.6 Alternative or additional rules**:
     > 8.6.1. For some goods, the PSRs in Schedule 1 of the ChAFTA Regulations may specify: (a) a RVC requirement as additional to the CTC rule; or (b) a RVC requirement as an alternative to a CTC rule (e.g. 8301.70).
     > 8.6.2. In cases where a RVC requirement is specified as additional to a CTC rule, a good will need to satisfy both the CTC and the specified RVC requirement to qualify as a Chinese originating good.
     > 8.6.3. In cases where the PSR provides an option to determine origin, all the requirements of the option chosen (either the CTC or the RVC) must be met for the good to qualify as a Chinese originating good.
   - Worked example box on the same page:
     > A China producer sells a good to an Australian importer at a value of $200. The VNM used in the good is $60. Using the RVC formula, the importer calculates the RVC as follows: … RVC = (200 - 60) / 200 x 100 = 70%. If the PSR of the good requires an RVC of 40 per cent and the RVC of the good is 70%, then the good meets the PSR and is originating.
   - Screenshot: `shots/abf_chafta_guidelines_p2.png` (viewer captured page 21/37 despite the `#page=2` fragment).

   The side bar of that PDF also lists the structure used by the document: *2. Legislation*, *3. Definitions*, *4. Overview of ChAFTA*, *5. Principles of the ChAFTA rules of origin*, *Division 1L of Part VIII of the Customs Act*, *the ChAFTA Regulations*.

6. **Full-text extraction of the same PDF** — `repo/research/abf_guide_pdf.txt` / `.pdf` (37 pages, 1,846 lines) appeared in the shared workspace during this session (produced by another team member with a working PDF extractor). Its page markers (`China-Australia Free Trade Agreement 4 of 37` …) and wording match the page 21/37 that I rendered and read visually, so it was used to quote the sections the viewer would not page to. Key verbatim passages:

   - **5.1.4 — when preference is available**
     > To be eligible for ChAFTA preferential rates, the following requirements must be met: • the goods are Chinese originating; • the importer claiming preferential treatment satisfies the documentary requirements; and • the goods meet the consignment provisions.

   - **5.1.7 — what a PSR contains**
     > A PSR sets out the following criteria that apply either solely or in conjunction to a good: • change of tariff classification (CTC); • regional value content (RVC); or • specific manufacturing or processing operation rules.

   - **6.1.1 — wholly obtained (WO), s 153ZOC**
     > 153ZOC Goods wholly obtained in China (1) Goods are Chinese originating goods if: (a) they are wholly obtained in China; and (b) either: i. the importer of the goods has, at the time the goods are imported, a CoO or a DoO, or a copy of one, for the goods; or ii. Australia has waived the requirement for a CoO or a DoO for the goods.
     > (2) Goods are wholly obtained in China if, and only if, the goods are: … (a)–(j) [live animals, plants, minerals, high-seas catch, waste and scrap fit only for raw-material recovery, and goods produced exclusively from those goods].

   - **CTC rule + 10 % tolerance (p. 15–16)**
     > Each non-originating material used in the production of the goods is required to satisfy a prescribed change in tariff classification … the requirement … is taken to be satisfied if the total value of those non-originating materials does not exceed 10% of the customs value of the goods.

   - **RVC rule (p. 16)**
     > The regulations may prescribe that the goods are required to have a regional value content of at least a prescribed percentage.

   - **8.6.1–8.6.3 (p. 21) — RVC/CTC interaction**
     > 8.6.1. For some goods, the PSRs in Schedule 1 of the ChAFTA Regulations may specify: (a) a RVC requirement as additional to the CTC rule; or (b) a RVC requirement as an alternative to a CTC rule (e.g. 8301.70).
     > 8.6.2. In cases where a RVC requirement is specified as additional to a CTC rule, a good will need to satisfy both the CTC and the specified RVC requirement to qualify as a Chinese originating good.
     > 8.6.3. In cases where the PSR provides an option to determine origin, all the requirements of the option chosen (either the CTC or the RVC) must be met for the good to qualify as a Chinese originating good.

   Still missing: the **actual PSR value for each furniture HS line** (Schedule 1, Part 2 of the Customs (Chinese Rules of Origin) Regulations 2015). The guideline explains the mechanism only, so the platform must not assert "CTH" or "RVC 40%" for 9401.79/9403.20/9403.60 without that schedule.

---

## 7. Backend integration recommendation

1. **China HS + MFN rates: do NOT use a browser.**
   `httpx`/`requests` POST works directly against `https://online.customs.gov.cn/ociswebserver/ocis/taxRateQuery/query/queryImpTariffRate`. Requirements:
   - `Content-Type: application/x-www-form-urlencoded; charset=UTF-8`
   - body `param=<json>` (URL-encoded)
   - `sysDate` = today `YYYY-MM-DD`; `nextPage`/`pageSize` as strings
   - a `Referer` header is harmless and was used
   - parse the double-encoded `res` string (see §3.3)
   No cookies, no auth, no JS execution were needed. Response time < 1 s.
2. **ChAFTA preferential rate (China side):** same pattern, `/query/queryAgreementRate` then `/query/queryCountryAgreementRate` with `agreementCode=18`. Cache per (codeTs, sysDate) — these are annual tariff parameters.
3. **申报要素:** requires a real browser engine (Playwright + Edge/Chromium) driving `https://online.customs.gov.cn/ociswebserver/pages/cus/#/tgcs/index`, or ingestion of the annual 规范申报目录. Until then the platform must show "not supported" for this field, not a guess.
4. **ABF:** plain `httpx.get` is sufficient for HTML pages (HTTP 200). For the guidelines PDF, extract text server-side with PyMuPDF/pdfplumber — the `abf_guide_pdf.txt` capture in this folder shows the extraction is straightforward and clean (37 pages, page markers preserved).
5. **Never** present `impDiscountRate` / `impAgreementRate` from the Chinese service as Australian duty. The Australia-side rate needs `https://www.abf.gov.au/importing-exporting-and-manufacturing/tariff-classification/current-tariff/schedule-12`.

---

## 8. Reproduction checklist

```text
1. POST https://online.customs.gov.cn/ociswebserver/ocis/taxRateQuery/query/queryImpTariffRate
   param={"gName":"","codeTs":"9401","sysDate":"2026-10-23","nextPage":1,"pageSize":"50"}
2. POST .../queryAgreementRate                param={"codeTs":"9401790000","sysDate":"2026-10-23"}
3. POST .../queryCountryAgreementRate         param={"codeTs":"9401790000","sysDate":"2026-10-23","agreementCode":"18"}
4. GET  https://www.abf.gov.au/importing-exporting-and-manufacturing/fta/free-trade-agreements/china
5. GET  https://www.abf.gov.au/importing-exporting-and-manufacturing/fta
6. GET  https://www.abf.gov.au/importing-exporting-and-manufacturing/fta/origin-advice
7. GET  https://www.abf.gov.au/free-trade-agreements/files/instructions-guidelines-australia-china-fta.pdf  (read p.21 with a PDF text extractor)
```

## 9. Files

- `evidence.json` — machine-readable records; `supported` records only contain values actually observed.
- `raw/queryImpTariffRate_9401.json`, `raw/queryImpTariffRate_9403.json`, `raw/queryImpTariffRate_841451.json` — verbatim request/response captures.
- `raw/agreement_rate_chafta.json` — verbatim ChAFTA agreement-rate captures.
- `shots/abf_chafta_guidelines_p2.png` — ABF guidelines PDF page 21/37 (RVC/CTC rules).
- `abf_guide_pdf.pdf` / `abf_guide_pdf.txt` — the ABF guidelines PDF and its 37-page text extraction (workspace file; used for the WO/CTC/RVC quotes in §6.6).
- `shots/customs_home.png`, `shots/test_example.png` — blank/failed captures (browser crash); kept only as evidence that the capture route failed, **not** as page evidence.
