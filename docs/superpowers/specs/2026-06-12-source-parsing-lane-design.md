# Source Parsing Lane Design

## 1. Goal

Add a source parsing lane that extracts text from the original RFP files under `data/files` and makes parsing quality visible before the parsed text is used for indexing.

The current system remains CSV-first until this lane produces evidence. The new lane should let the project compare:

- CSV text baseline
- parsed source text
- parsed source text with CSV fallback

## 2. Current Evidence

The repository currently loads RFP documents from `data/data_list.csv` through `rfp_rag.corpus.load_corpus()`. The source files are resolved for metadata, but their contents are not used as corpus text.

Observed source-file distribution:

| suffix | count |
|---|---:|
| `.hwp` | 96 |
| `.pdf` | 4 |

Local parser availability:

- `hwp5txt`, `hwp5html`, and `hwp5odt` are available.
- `pdftotext`, PyMuPDF, `pdfplumber`, and `pypdf` are not currently available.
- A sampled HWP parsed successfully with `hwp5txt` and produced non-empty stdout, but stderr was also non-empty. The lane must preserve diagnostics rather than treating all stderr as failure.

## 3. Recommended Approach

Use a parser-manifest-first lane.

Do not immediately replace the corpus loader. First produce parse artifacts and EDA, then add source-aware indexing after the parse quality is known.

This approach is safer because 96 of 100 files are HWP, parser warnings are expected, and source parsing failures should not break the existing CSV baseline.

## 4. Components

### Parser Backends

Create focused parser functions:

- HWP: call `hwp5txt` through `subprocess.run`.
- PDF: leave as explicit unsupported/missing-parser in the first implementation unless a PDF dependency is added deliberately.

HWP parse success condition:

- process exits `0`
- normalized stdout has non-empty text after stripping

Non-empty stderr should be captured as diagnostics, not an automatic failure.

### Parse Manifest

Each CSV row/source file produces one manifest record:

```json
{
  "doc_id": "doc:000",
  "csv_row_id": "000",
  "source_path": "data/files/example.hwp",
  "source_suffix": ".hwp",
  "parser_backend": "hwp5txt",
  "parse_status": "parsed",
  "text_path": "artifacts/parsed_docs/text/doc_000.txt",
  "text_length": 12345,
  "stderr_length": 120,
  "error_reason": null,
  "csv_text_length": 10000,
  "parsed_to_csv_length_ratio": 1.2345
}
```

Allowed `parse_status` values:

- `parsed`
- `empty_text`
- `unsupported_suffix`
- `missing_source_file`
- `parser_error`
- `timeout`

### CLI

Add a parser CLI:

```bash
python3 -m rfp_rag.parse_sources \
  --data data/data_list.csv \
  --files data/files \
  --out artifacts/parsed_docs
```

Expected outputs:

- `artifacts/parsed_docs/manifest.jsonl`
- `artifacts/parsed_docs/summary.json`
- `artifacts/parsed_docs/text/{safe_doc_id}.txt`, where `doc:000` becomes `doc_000`

### EDA Summary

`summary.json` should include:

- row count
- suffix counts
- parse status counts
- parser backend counts
- parsed success rate
- empty parse count
- text length min/median/max
- CSV text length min/median/max
- parsed-to-CSV length ratio min/median/max
- top error reasons

## 5. Source-Aware Indexing Follow-Up

After parse artifacts exist, add source selection to `build_index`:

```bash
python3 -m rfp_rag.build_index ... --source csv
python3 -m rfp_rag.build_index ... --source parsed
python3 -m rfp_rag.build_index ... --source parsed-with-csv-fallback
```

Default remains `csv` until parsed-source evaluation is documented.

The index manifest should record:

- `source_mode`
- `parser_manifest_path`
- `parsed_success_count`
- `csv_fallback_count`
- `empty_parse_count`

## 6. Error Handling

- Missing source file should produce a manifest record, not crash the full run.
- Unsupported suffix should produce a manifest record.
- Parser timeout should produce a manifest record.
- Parser stderr should be preserved by length and optional sample text, but should not leak huge logs into stdout.
- Full CLI should exit `0` if per-document parser failures are recorded successfully; use summary counts to decide whether the output is acceptable.

## 7. Testing

Unit tests should avoid depending on real HWP parser binaries where possible.

Required tests:

- parser backend result mapping for success, empty stdout, nonzero exit, and timeout
- manifest record shape
- summary aggregation
- CLI writes `manifest.jsonl`, `summary.json`, and text files
- PDF/unsupported suffix records a controlled status when no PDF parser is configured
- source-aware indexing remains CSV by default in follow-up work

Integration smoke:

```bash
python3 -m rfp_rag.parse_sources \
  --data data/data_list.csv \
  --files data/files \
  --out artifacts/parsed_docs
```

## 8. Acceptance Criteria

- Parser lane produces artifacts for all 100 CSV rows.
- HWP parser diagnostics are recorded without crashing successful parses.
- PDF files are either parsed with an explicitly added backend or marked unsupported with clear reasons.
- Existing CSV baseline remains unchanged.
- `REPORT.md` records parsing EDA before any claim that source parsing is complete.

## 9. First Implementation Decisions

- PDF parser dependency is not added in the first implementation. The 4 PDF rows are recorded as `unsupported_suffix` unless a local PDF backend is deliberately added in a later PR.
- Store `stderr_length` and a bounded `stderr_sample` of at most 500 characters. Do not write full stderr logs into the main manifest.
- Keep source-aware indexing as a follow-up PR after parse EDA is produced. The first PR only creates parser artifacts and documentation.

## 10. Self-Review

- The design does not claim source parsing is already implemented.
- HWP is prioritized because it is 96% of source files.
- Existing CSV behavior is preserved until parsed-source quality is measured.
- Parser diagnostics and fallback behavior are first-class outputs, not hidden implementation details.
