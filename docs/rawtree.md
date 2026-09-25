# RawTree: the event mirror

RawTree replaced Tinybird as the analytics sponsor at kickoff on 2026-09-25. It takes events as they are (a
table is created on the first insert) and answers read-only ClickHouse SQL, which is exactly what the ledger
needs: no datafiles, no deploy step.

## Setup

1. Sign in at https://rawtree.com/login and create an API key with the `read_write` permission
   (`rtree key create --name ledger --permission read_write` from the CLI does the same).
2. Put it in `.env`: `RAWTREE_API_KEY=rt_...` (and `RAWTREE_DATABASE=<name>` if not the key's default).
3. `ledger doctor` should show `✓ rawtree`. `ledger sync` posts the backlog; every verb from then on mirrors live.

## What is stored

One table, `ledger_events` by default (`RAWTREE_TABLE` overrides it; on the event's shared cluster we use a name with our handle), one row per verb: `ts` (ISO-8601 with offset), `kind`, `host`, `model`, `gate`,
`text`, `tokens_in`, `tokens_out`, `bytes_discarded`, `ledger` (an id written to `.ledger/id` at init, so two ledgers
sharing a key never mix on the board).

## The two questions

What changed in the last hour, the query a judge can paste into the RawTree UI:

```sql
SELECT ts, kind, host, gate, text FROM ledger_events
WHERE parseDateTimeBestEffort(toString(ts)) >= now() - INTERVAL 1 HOUR
ORDER BY ts DESC LIMIT 200
```

The board, one row per kind and host:

```sql
SELECT kind, host, count() AS events, sum(bytes_discarded) AS bytes_discarded,
       sum(tokens_in) AS tokens_in, sum(tokens_out) AS tokens_out, max(ts) AS last_ts
FROM ledger_events
WHERE parseDateTimeBestEffort(toString(ts)) >= now() - INTERVAL 24 HOUR
GROUP BY kind, host ORDER BY last_ts DESC
```

`ledger board` runs both (scoped to the current ledger) and writes `.ledger/board.html`; without a key it
computes the same tables from `.ledger/events.jsonl`.

## API shape used

- `POST https://api.rawtree.com/v1/tables/ledger_events` with a JSON array, `Authorization: Bearer rt_...`,
  optional `x-rawtree-database` header. Response `{"inserted": n}`.
- `POST https://api.rawtree.com/v1/query` with `{"sql": "..."}`. Response `{"meta", "data", "rows", "statistics", "hints"}`.
- `scripts/hinges.sh H2` runs the sync and the last-hour query and prints the row count: the H2 measurement.
