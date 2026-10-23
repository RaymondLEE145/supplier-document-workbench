# testdata — supplier-document fixture set

Synthetic source documents for end-to-end testing of the supplier-document
automation platform (import → extract → normalize → de-duplicate → map onto
`repo/assets/template.xlsx`).

**Disclaimer:** every company, address, contract, price and contact below is
fictional. The data is realistic for a China → Australia furniture/hardware
shipment (April 2026, CIF Melbourne) but is not copied from a real shipment.

## File tree

```
repo/testdata/
├── README-testdata.md
├── manifest.json                                  # expected values + per-document expectations
├── supplier_a_ningbo_homeline/
│   ├── packing_list.pdf                           # reportlab PDF, real text layer, EN+ZH
│   └── commercial_invoice.pdf                     # reportlab PDF, real text layer, EN+ZH
├── supplier_b_foshan_sunrise/
│   ├── packing_list.xlsx                          # openpyxl, 2 title rows, reordered columns
│   └── commercial_invoice.xlsx                    # openpyxl, 2 title rows, reordered columns
├── supplier_c_guangzhou_evergreen/
│   └── packing_list_scan.png                      # Pillow raster, OCR-friendly, 1800×1150
└── _build/
    ├── fixture_data.py                            # single source of truth for all values
    ├── build_fixtures.py                          # (re)generates the five documents + manifest.json
    ├── verify_fixtures.py                         # reads every file back and asserts against manifest.json
    ├── build_report.json                           # written by build_fixtures.py
    └── verify_report.json                          # written by verify_fixtures.py
```

All document paths inside `manifest.json` are relative to the repository root
(`testdata/...`); `workspace_path` is relative to the DSH workspace root
(`repo/testdata/...`).

## Regenerate / verify

```powershell
$py = "C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
& $py repo/testdata/_build/build_fixtures.py      # writes the 5 documents + manifest.json
& $py repo/testdata/_build/verify_fixtures.py     # reads them back, writes verify_report.json
```

`verify_fixtures.py` exits `0` and prints `VERIFY OK` when every assertion
passes; it checks PDF text extraction with **PyMuPDF and pypdf**, XLSX cell
values with **openpyxl**, PNG pixels/dimensions with **Pillow**, and all
manifest arithmetic (pieces, amount, CBM, supplier totals, grand totals, the
duplicate pair and the one intentionally missing HS code).

## Suppliers and document formats

| Supplier | Company | Documents | Format quirks |
|---|---|---|---|
| A | NINGBO HOMELINE IMP.&EXP. CO., LTD / 宁波豪迈进出口有限公司 | `packing_list.pdf`, `commercial_invoice.pdf` | single-page A4 landscape, EN + ZH headers, real text layer, contract `HL-2026-0408`, invoice `HL-INV-260408`, date 2026-04-08, Ningbo → Melbourne |
| B | FOSHAN SUNRISE FURNITURE CO., LTD / 佛山市日出家具有限公司 | `packing_list.xlsx`, `commercial_invoice.xlsx` | 2 title rows, reordered columns (cartons before description; model before HS; cartons/pieces reordered), contract `FSF-2026-0415`, invoice `FSF-INV-260415`, date 2026-04-15, Shenzhen/Shekou → Melbourne |
| C | GUANGZHOU EVERGREEN HARDWARE CO., LTD / 广州常青五金制品有限公司 | `packing_list_scan.png` | raster PNG, no text layer (OCR required), compact table, contract `GEG-2026-0420`, invoice `GEG-INV-260420`, date 2026-04-20, Guangzhou/Nansha → Melbourne |

All three buyers are different Australian companies; destination is
`MELBOURNE, AUSTRALIA`, incoterm `CIF`, payment `T/T`, origin `CHINA`.
Supplier C has only a packing list; its unit prices/amounts exist only as
expected values in `manifest.json` (`price_source = "manifest_only_no_invoice"`).

### Supplier A — line items (3)

| Key | Product (EN / ZH) | HS code | Cartons | Pcs/ctn | Total pcs | Unit USD | Amount USD | G.W. kg | N.W. kg | L×W×H cm | CBM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A-1 | Metal Dining Chair / 金属餐椅 | 9401790000 | 120 | 6 | 720 | 18.50 | 13,320.00 | 2,340 | 2,100 | 62×48×92 | 32.86 |
| A-2 | Wooden Side Table / 木制边几 | 9403600000 | 80 | 4 | 320 | 24.00 | 7,680.00 | 1,180 | 1,050 | 55×45×70 | 13.86 |
| A-3 | Steel Storage Rack / 钢制储物架 | 7326909000 | 65 | 2 | 130 | 46.00 | 5,980.00 | 3,250 | 3,100 | 120×40×15 | 4.68 |

Totals A: **265 cartons, 1,170 pcs, USD 26,980.00, G.W. 6,770 kg, N.W. 6,250 kg, 51.40 CBM**

### Supplier B — line items (3)

| Key | Product (EN / ZH) | HS code | Cartons | Pcs/ctn | Total pcs | Unit USD | Amount USD | G.W. kg | N.W. kg | L×W×H cm | CBM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B-1 | Outdoor Bench / 户外长椅 | 9401690000 | 50 | 3 | 150 | 58.00 | 8,700.00 | 1,680 | 1,500 | 155×45×40 | 13.95 |
| B-2 | Aluminum Folding Chair / 铝合金折叠椅 | **missing** | 40 | 8 | 320 | 12.50 | 4,000.00 | 560 | 480 | 58×38×105 | 9.26 |
| B-3 | Metal Dining Chair / 金属餐椅 | 9401790000 | 120 | 6 | 720 | 18.50 | 13,320.00 | 2,340 | 2,100 | 62×48×92 | 32.86 |

Totals B: **210 cartons, 1,190 pcs, USD 26,020.00, G.W. 4,580 kg, N.W. 4,080 kg, 56.07 CBM**

### Supplier C — line items (3, PNG packing list only)

| Key | Product (EN / ZH) | HS code | Cartons | Pcs/ctn | Total pcs | Unit USD | Amount USD | G.W. kg | N.W. kg | L×W×H cm | CBM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C-1 | Wrought Iron Plant Stand / 铁艺花架 | 7326209000 | 30 | 4 | 120 | 9.80 | 1,176.00 | 300 | 240 | 42×32×68 | 2.74 |
| C-2 | Teak Outdoor Bench / 柚木户外长椅 | 9401690000 | 25 | 2 | 50 | 74.00 | 3,700.00 | 1,010 | 900 | 150×60×45 | 10.13 |
| C-3 | Aluminum Folding Table / 铝合金折叠桌 | 9403200000 | 60 | 5 | 300 | 15.60 | 4,680.00 | 1,020 | 900 | 70×25×55 | 5.78 |

Totals C: **115 cartons, 470 pcs, USD 9,556.00, G.W. 2,330 kg, N.W. 2,040 kg, 18.65 CBM**

### Grand totals (all fixtures)

**9 line items · 5 documents · 3 suppliers · 590 cartons · 2,830 pcs ·
USD 62,556.00 · G.W. 13,680 kg · N.W. 12,370 kg · 126.12 CBM**

CBM convention: per-line CBM = round-half-up(`L*W*H / 1,000,000 * cartons`, 2);
supplier/grand totals are sums of the rounded line values (so tests can add the
manifest line values and match the totals exactly).

## Intentionally seeded test cases

1. **Cross-supplier duplicate** — `A-1` and `B-3` are deliberately identical:
   same product EN/ZH, model `DC-2018`, HS `9401790000`, 120 cartons × 6 pcs,
   720 pcs, USD 18.50, USD 13,320.00, weights, dimensions and CBM. The platform
   should extract both source lines but collapse them to one canonical item and
   keep both source occurrences. Definition: `manifest.duplicates[0]`
   (`dup-metal-dining-chair`, match fields listed there).
2. **Missing HS code** — `B-2` (Aluminum Folding Chair) has an empty HS cell in
   **both** Supplier B files. It must still be extracted with `hs_code: null`
   and flagged by validation; definition: `manifest.data_quality_cases.missing_hs_code`.
3. **Layout heterogeneity** — Supplier A PDFs (merged-looking multi-line header,
   one header row), Supplier B XLSX (two title rows, reordered columns), Supplier C
   PNG (raster, no text layer, OCR required).
4. **Text PDF vs scanned image** — Supplier A PDFs have a real text layer
   (reportlab + embedded SimHei TTF with ToUnicode); Supplier C PNG has no text
   layer. `manifest.documents[*].extraction_expectations.text_layer` states which
   is which.
5. **Mixed EN/ZH** — every document carries both English and Simplified Chinese
   labels plus bilingual product names.

## Document layouts

### Supplier A PDFs (`packing_list.pdf`, `commercial_invoice.pdf`)

- A4 landscape, one page.
- Title block: `PACKING LIST` / `装 箱 清 单` or `COMMERCIAL INVOICE` / `商 业 发 票`.
- Supplier block (EN + ZH name/address, tel, email) and a right-hand meta block
  with invoice no, contract no, date, incoterm, port of loading, destination,
  payment; buyer block below.
- Packing list columns: `NO. | DESCRIPTION | HS CODE | MATERIALS | CARTONS |
  PCS/CTN | TOTAL PCS | L | W | H | CBM | G.W. | N.W. | PACKING`; totals row
  `265 | 1,170 | 51.40 | 6,770 | 6,250`.
- Invoice columns: `NO. | DESCRIPTION | HS CODE | MATERIALS | CARTONS |
  PCS/CTN | TOTAL PCS | UNIT PRICE | AMOUNT | REMARKS`; total amount
  `26,980.00`; `SAY TOTAL` in words; a `TOTAL PACKING: 265 CARTONS / 1,170 PCS
  G.W.: 6,770 KGS  N.W.: 6,250 KGS  CBM: 51.40` summary line; bank details.
- Text extraction: all EN/ZH text is in the PDF text layer (no page images).

### Supplier B XLSX

`packing_list.xlsx`, sheet `Packing List`:

- row 1: company name (merged `A1:M1`)
- row 2: `PACKING LIST / 装箱清单` + invoice no + date (merged cells)
- row 3: buyer / contract / destination strip
- row 4: header row — `A NO.`, `B CARTONS`, `C DESCRIPTION`, `D 中文品名`,
  `E HS CODE`, `F MATERIAL`, `G PCS/CTN`, `H TOTAL PCS`, `I N.W.(KGS)`,
  `J G.W.(KGS)`, `K MEAS.(CM)`, `L CBM`, `M PACKING`
- rows 5–7: 3 items (row 6 = `B-2`, HS cell empty)
- row 8: totals (`B 210`, `H 1190`, `I 4080`, `J 4580`, `L 56.07`)
- rows 9–10: packing / shipping-mark notes

`commercial_invoice.xlsx`, sheet `Commercial Invoice`:

- rows 1–2: two title rows (company; `COMMERCIAL INVOICE / 商业发票` + invoice no + date)
- row 3: seller / contract / buyer strip
- row 4: terms / loading port / destination / payment / origin
- row 5: header row — `A NO.`, `B DESCRIPTION`, `C 中文品名`, `D MODEL`,
  `E HS CODE`, `F MATERIAL`, `G CARTONS`, `H PCS/CTN`, `I TOTAL PCS`,
  `J UNIT PRICE(USD)`, `K AMOUNT(USD)`
- rows 6–8: 3 items (row 7 = `B-2`, HS cell empty)
- row 9: totals (`G 210`, `I 1190`, `K 26020.00`)
- rows 10–12: SAY TOTAL, bank details, signature line

All totals are written as static values (no formula cells), so `openpyxl`
`data_only=True` readers see them without recalculation.

### Supplier C PNG (`packing_list_scan.png`)

- 1800×1150 px, RGB, black on white, high contrast; table rules and large
  (≈20 px) text for OCR.
- Compact packing-list table: `NO. | DESCRIPTION | HS CODE | CARTONS |
  PCS/CTN | TOTAL PCS | G.W.(KGS) | CBM`, 3 item rows + `TOTAL 合计` row.
- No embedded text layer — OCR is expected (`text_extractable: false` in
  `manifest.documents[doc_c_packing].extraction_expectations`).

## `manifest.json` schema (version 1.0.0)

Top-level keys:

| Key | Meaning |
|---|---|
| `schema_version`, `fixture_set`, `created_at` | identification |
| `disclaimer` | fictional-data notice |
| `currency`, `incoterm`, `incoterm_full`, `destination`, `origin_country`, `trade_lane` | shared shipment metadata (USD, CIF, Melbourne, CHINA → AUSTRALIA) |
| `supplier_count`, `document_count`, `item_count` | 3 / 5 / 9 |
| `suppliers` | per supplier: `id`, `code`, `name_en`, `name_zh`, address, tel, email, `contract_no`, `invoice_no`, `doc_date`, `port_of_loading`, `incoterm`, `payment`, buyer, bank, `line_item_keys`, `totals`, `item_count` |
| `documents` | per document: `id`, `supplier_id`, `doc_type`, `doc_type_zh`, `format`, `path`, `workspace_path`, `line_item_keys`, `line_count`, `page_count`, `engine`, `mime_type`, `bytes`, `sha256`, `extraction_expectations` |
| `items` | 9 items; see below |
| `totals_by_supplier` | `supplier_a` / `supplier_b` / `supplier_c` → `cartons`, `total_pieces`, `amount`, `gross_weight_kg`, `net_weight_kg`, `cbm`, `item_count` |
| `grand_totals` | same keys for all suppliers plus `document_count`, `supplier_count` |
| `duplicates` | duplicate definitions; first is `A-1` ≡ `B-3` with `match_fields`, `identical_values`, `expected_behaviour` |
| `data_quality_cases` | missing HS, duplicate, two-title-row, text-PDF-vs-PNG, mixed EN/ZH cases |
| `template_mapping` | template workbook path, exact sheet names (`装箱清单`, `发票`, `申报要素`, `销货确认书`, `报关单 ` — note the trailing space) and how each sheet is populated |
| `aggregation_notes` | rounding conventions |

Each item (9 total) contains:

```
key, supplier_id, supplier_code, line_no, source_documents,
name_en, name_zh, model, hs_code, hs_code_missing,
materials_en, materials_zh, brand,
use_en/use_zh, process_en/process_zh, scenario_en/scenario_zh, preferential_tariff,
cartons, pieces_per_carton, total_pieces,
unit_price, amount, currency,
gross_weight_kg, net_weight_kg,
cbm_per_carton, cbm, dimensions_cm {l,w,h}, dimensions_text,
packing_type_en, packing_type_zh, origin_country, price_source
```

`extraction_expectations` per document records the layout hints tests may need:
PDF → `text_extractable`, `languages`, `page_count`, `required_keywords`,
`expected_item_keys`, `expected_total_strings`; XLSX → `sheet_names`,
`title_rows`, `header_row`, `data_rows`, `totals_row`, `columns` (letter,
header, meaning), `missing_hs_item_keys`; PNG → `image_size_px`, `image_mode`,
`ocr_keywords`, `text_extractable: false`.

## Mapping onto `repo/assets/template.xlsx`

The fixture documents supply the data for the template's five sheets
(exact tab names in the template): `装箱清单`, `发票`, `申报要素`,
`销货确认书`, `报关单 ` (trailing space). See
`manifest.template_mapping.population_expectations` for the field-level intent;
`manifest.items` already carries the declaration-element fields (`brand`,
`model`, `materials`, `use`, `process`, `scenario`, `preferential_tariff`) and
the sales-confirmation fields (`unit_price`, `amount`, `cartons`,
`total_pieces`, `incoterm`).

## Verification results

Last run: **2026-10-23 14:17 (+08:00)**, bundled Python 3.12.14, reportlab 5.0.1,
openpyxl 3.1.5, Pillow 12.3.0, PyMuPDF + pypdf.

| Item | Result |
|---|---|
| `build_fixtures.py` | `BUILD OK` — pdf_engine `reportlab`, 5 documents, 9 items, 590 cartons, USD 62,556.00, 126.12 CBM (2.84 s) |
| `verify_fixtures.py` | **214 checks, 0 failures — `VERIFY OK`** |
| Supplier A PDFs | 1 page each, no page images (real text layer); PyMuPDF extracted 1,512 / 1,535 characters, pypdf independently 1,442 / 1,464 |
| Supplier B XLSX | both sheets read back with expected title rows, headers, 3 data rows and totals; B-2 HS cell is empty in both files |
| Supplier C PNG | 1800×1150 px RGB, 119,573 bytes, dark-pixel fraction 4.8 %, 19 horizontal rule rows detected; no text layer (OCR required) |
| manifest.json | 35,839 bytes; all per-item math, supplier totals, grand totals, duplicate pair and SHA-256 checks pass |

Full evidence: `_build/verify_report.json` (every check + extracted text/statistics)
and `_build/build_report.json` (engine, byte sizes, SHA-256 of `manifest.json`).

Generated document sizes: packing list PDF 27,788 B, invoice PDF 26,240 B,
packing list XLSX 6,782 B, invoice XLSX 6,715 B, PNG 119,573 B.
