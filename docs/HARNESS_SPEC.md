# Harness Specification (v1)

> **Status:** updated in Phase 1 (2026-11-09). `generate_exercise`, `evaluate_exercise` and `generate_lesson` were removed; the harness now has two operations. Section numbers are kept so references elsewhere still work. Where this and `docs/BUILD_PLAN.md` disagree, the build plan wins.

The harness is a stateless Python (FastAPI) Cloud Run service. It has **no** database or storage access, no tools, and no MCP. It exposes two operations, each a request in and validated JSON out. Callable only by the API's service account.

## 1. Operations
| Operation | Input | Output |
|---|---|---|
| `transcribe` | photo pages in order | verbatim text per page |
| `evaluate_writing` | scrubbed text and the writing prompt, optional regeneration note | annotations, one overall comment |

Evaluation is one call per submission. The harness never writes exercises or lessons, and never receives teacher notes. Every request carries: operation, opaque student ID, request ID, prompt version. Every response carries: result, token counts (in/out/cache), model, latency.

## 2. Shared code taxonomy (single source of truth)
Lives in one module (`taxonomy`) imported by both the harness prompts and the API validator. 14 codes:

| Code | Meaning | Example |
|---|---|---|
| SP | Spelling | recieve -> receive |
| P | Punctuation (not capitalization) | missing comma, wrong apostrophe |
| CAP | Capitalization | "i" -> "I" |
| S | Sentence boundary: fragment, run-on, comma splice | "I was tired, I went home." |
| VT | Verb tense | "Yesterday I go" -> "went" |
| SV | Subject-verb agreement | "She go" -> "goes" |
| VF | Verb form (participle, gerund vs infinitive, modal + verb) | "have went", "enjoy to swim" |
| ART | Article/determiner: missing, extra, wrong | "I saw elephant" |
| PREP | Preposition | "depends of" -> "on" |
| WF | Word form, plurals, countability | "informations" |
| PRO | Pronoun agreement or reference | "Everyone brought their..." where context requires otherwise |
| WO | Word order | "always I eat" |
| M | Missing word (not article/preposition) | "She going to school" |
| X | Unnecessary word (not article/preposition) | "I did went home" |

Rules given to the model:
- Exactly one code per error, the most specific that fits. ART and PREP take priority over M and X.
- Scope is grammar, punctuation, spelling, capitalization only. Do **not** flag word choice, awkward phrasing, style, content, or organization.
- Never flag `[?]` (illegible) tokens.
- Do not flag a span unless confident it is an error; when unsure, stay silent.
- Each annotation: `code`, `span_text` (exact substring), `occurrence` (1-based index of that substring in the text), `correction` (teacher-only), `explanation` (one line, teacher-only). The student sees only the code on the span.

## 3. Span handling
Models are unreliable at counting offsets, so the harness returns `span_text` + `occurrence`; the **API** computes character offsets against the exact scrubbed text version. A span not found, an unknown code, or overlapping spans means the annotation set is rejected (after one repair attempt in the harness). Changing the scrubbed text invalidates the draft.

## 4. Writing exercise schema
Written by the teacher, never by the harness. The API validates it with the shared schema:
```json
{"kind": "writing", "title": "string", "prompt": "string", "min_words": null, "max_words": null}
```
Validation: `min_words` and `max_words` are optional, at least 1, and `min_words` is not more than `max_words`.

## 5. Evaluation schema
`evaluate_writing` output:
```json
{"annotations": [{"code": "VT", "span_text": "go", "occurrence": 1, "correction": "went", "explanation": "..."}],
 "comment": "One short overall comment on grammar/punctuation."}
```
No scores. Always a draft; the teacher can edit it.

## 6. Lesson schema
Removed in Phase 1: there are no lessons.

## 7. Transcription rules
Copy text **exactly** as written. Do not correct spelling, grammar, punctuation, or capitalization. Mark illegible words as `[?]`. Preserve line breaks and paragraph breaks. Output page by page in order. Never infer missing text. Validation: exactly one result per page sent, numbered 1, 2, 3, ... in order. (Language models tend to silently fix errors; the prompt must forbid this explicitly and the golden set includes a test for it.)

## 8. Prompt, safety, and model client
- One versioned prompt template per operation, stored in the repo; the version is recorded on every job.
- Static prefix (instructions + taxonomy) is separated from dynamic content to allow prompt caching — confirmed supported on Vertex (in-memory cache, 24-hour TTL, cached-token rate ~1/10th of input rate).
- Student text and the teacher's regeneration notes are wrapped in clearly delimited data blocks and labeled as data, never instructions. Output is forced into a JSON schema via structured output/tool-use for format only (no real tools).
- Validation pipeline: schema parse -> semantic checks -> one automatic repair attempt -> else error. The API re-validates independently.
- Model client: Vertex wrapper (`us` multi-region endpoint) with timeouts, one retry on transient errors, low temperature for evaluation/transcription, model name per operation read from `settings`/config. **Decided:** `claude-sonnet-5` for both operations (transcribe, evaluate_writing) — the scope is narrow enough (fixed 14-code taxonomy, verbatim transcription, forced JSON schema) that Sonnet should be sufficient. Upgrade either to `claude-opus-5` only if the golden set (section 9) shows Sonnet missing or miscoding errors it shouldn't.
- **Gemini fallback (teacher decision 2026-10-08, while the Claude quota is pending):** if Claude is unavailable (HTTP 403/404/408/429/5xx/529, connection error or timeout — not 400), the same prompt and schema go to `gemini-3.8-flash` on the same `us` endpoint (`harness/app/gemini_ops.py`), with the same validation and one repair attempt. Thinking level `medium` for both operations. Thinking tokens are billed as output and counted in `tokens_out`. The job record's `model` field shows which model answered; Claude takes over automatically once its quota works. Observed latency on the `us` endpoint: 15–95s per call (the `global` endpoint was 3–4x faster but doesn't keep processing in the US). Vertex in-memory data caching for Gemini is **disabled** for the project (`cacheConfig.disableCache=true`); Google's terms: no training on customer data; prompts may be logged for abuse monitoring unless an exception is requested.
- Logging: job ID, operation, tokens, latency, validation outcome only. No student text, no images.
- Cost reporting: return token counts; the API owns the cap.
- **Mock mode**: env flag returns canned schema-valid responses so the entire app can be built and tested without Claude calls.

## 9. Golden set and regression
- The teacher supplies 8 to 10 short student-style passages (names removed) with their own annotations using the 14 codes, plus 2 transcription samples with known verbatim text.
- A script runs `evaluate_writing` and `transcribe` on the set and reports annotation agreement (exact-span match, code match, missed, extra) and transcription exactness. Run on every prompt or model change.
- Target: tune prompts until the teacher judges output trustworthy; aim to favor precision over recall (stay silent when unsure).
- Until the teacher provides the set, the agent creates a small synthetic placeholder set and clearly labels it as synthetic.
