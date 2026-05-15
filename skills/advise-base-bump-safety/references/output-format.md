# Advice doc output format

Each run of the skill emits `advice.md` (always) and, when `--json`
is passed, `advice.json` (structured findings, one entry per FROM,
with classification + indicators recorded).

## advice.md structure

Per-FROM section template, one per finding, grouped under the owning
chart (matches the audit's grouping):

```markdown
## <image>:<tag>  ·  stage: <stage>

- **Classification**: <safe-mechanical | requires-migration | …>
- **Before**: `<original FROM>`
- **After**:  `<proposed FROM>`  (source: <audit-table | user-override>)
- **Indicators**:
  - <indicator-1>
  - <indicator-2>
- **Recommended action**: <one sentence>
- **Notes** (optional): <any caveats, license citations, etc.>
```

## Top-of-file summary panel

```
Classification counts (n findings):
  safe-mechanical       N
  requires-migration    N
  license-aware         N
  interim-caution       N
  not-recommended       N
  no-action-needed      N
```

The summary is a sanity check: every FROM in the audit must be
accounted for in one of the buckets. Silent omission breaks the
user's expectation that the advice covers the whole audit.
