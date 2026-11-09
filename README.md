# speedyindex — Python client for the SpeedyIndex API

`speedyindex` is a small, dependency-free Python client and command-line tool for SpeedyIndex, a service for link indexing, Google, Bing and Yandex index checking and Google rank tracking. It wraps the [SpeedyIndex API](https://en.speedyindex.com/api.php) v2, so you can check whether URLs are indexed, submit links for indexing, track keyword positions and react to webhooks from scripts, cron jobs or CI.

- Standard library only (`urllib`), Python 3.8+
- **Index checks** for Google, Bing and Yandex, with reports that list indexed and unindexed URLs
- **Link indexing** tasks for Google and Yandex, single-URL submission and drip-feed
- **Rank Tracker**: projects, keywords, regions, checks, positions, history, AI Overview citations, CSV export
- **Webhooks**: verify `X-SpeedyIndex-Signature` and parse `check.finished` events
- **Backlink checks**: find links to your domains on donor pages
- `speedyindex` CLI for quick jobs from the shell

## Install

```bash
pip install speedyindex
```

## API key

Every request needs an API key from your SpeedyIndex dashboard or the SpeedyIndex Telegram bot settings. The client reads it from the `SPEEDYINDEX_API_KEY` environment variable:

```bash
export SPEEDYINDEX_API_KEY="your-key"
```

Keep the key out of source code and commit history; use environment variables or your CI secret store.

## Index checks and indexing

```python
from speedyindex import SpeedyIndex

si = SpeedyIndex()  # reads SPEEDYINDEX_API_KEY

# Which URLs are in Google's index?
task = si.create_task(
    ["https://example.com/", "https://example.com/blog/post-1"],
    engine="google", task_type="checker", title="blog check",
)
task_id = task["task_id"]

print(si.task_status([task_id], engine="google", task_type="checker"))

report = si.report(task_id, engine="google", task_type="checker")
print(report["unindexed_links"])          # plain URL lists

full = si.full_report(task_id, engine="google", task_type="checker")
# indexed_links: [{url, title}] - title as shown in the search results
# unindexed_links: [{url, error_code}] - -1: noindex found, 0: no error, otherwise the HTTP status
```

Bing supports `checker` tasks only. Submit links for indexing, spread over several days (drip feed is for Google indexing tasks):

```python
si.create_task(urls, engine="google", task_type="indexer", drip_feed=True, drip_feed_days=7)
si.index_url("https://example.com/new-page", engine="yandex")
```

## Rank Tracker

Projects created through the API are the same projects you see in the dashboard.

```python
rt = si.rank

loc = rt.locations("new york", gl="us")[0]
project = rt.create_project(
    "example.com",
    regions=[{"location": loc["canonical_name"], "gl": loc["country_code"]}],
    keywords=["pizza delivery", "best pizza near me"],
    depth=30,
    ref="my-project-1",            # safe to repeat after a timeout
)["project"]

check = rt.run_check(project["id"])
check = rt.wait(check["id"])          # polls every 30 s; or use a webhook

for row in rt.positions(project["id"], check_id=check["id"]):
    print(row["q"], row["position"] if row["found"] else "not found")

open("positions.csv", "wb").write(rt.export(project["id"]))
```

Also available: `update_project`, `bulk`, `add_region`, `add_keywords`, `replace_keywords`, `edit_keywords`, `keyword_history`, `trend`, `keyword_in_check` (top 10 and AI Overview: present, cited, sources), `cost`, `limits`, `usage`. Lists are iterators that follow `next_cursor` for you.

## Webhooks

Set an account webhook with `rt.set_webhook("https://hooks.example.com/speedyindex")`; the first answer contains the signing secret. Verify each delivery over the raw body before parsing it:

```python
from speedyindex import parse_event

# Flask example
@app.post("/speedyindex")
def hook():
    event = parse_event(request.get_data(), request.headers.get("X-SpeedyIndex-Signature"),
                        os.environ["SPEEDYINDEX_WEBHOOK_SECRET"])
    # event["event"]: check.finished / check.failed / check.skipped
    # a delivery may repeat: process each event["event_id"] once
    return "", 200
```

During secret rotation the header carries two signatures; either one is accepted.

## Command line

```bash
speedyindex balance
speedyindex check urls.txt --engine google --title "weekly check"
speedyindex check urls.txt --engine bing
speedyindex index urls.txt --engine google --drip-feed-days 5
speedyindex status 65f8c7315752853b9171860a --type checker
speedyindex report 65f8c7315752853b9171860a --type checker --unindexed > not-indexed.txt
speedyindex report 65f8c7315752853b9171860a --type checker --full > report.json
speedyindex tasks --engine google --type indexer

speedyindex rank locations "new york" --gl us
speedyindex rank create example.com --location "New York,New York,United States" --gl us --keywords kw.txt
speedyindex rank check PROJECT_ID --wait
speedyindex rank positions PROJECT_ID --changed-only
speedyindex rank export PROJECT_ID --format csv > positions.csv

speedyindex backlinks donors.txt --target mysite.com
```

Input files hold one item per line; empty lines and lines starting with `#` are skipped. Use `-` to read from stdin.

## Errors and limits

Errors raise `SpeedyIndexError` with `.code` (API code), `.status` (HTTP status), `.error` (machine-readable name from the Rank Tracker API, e.g. `rows_expired`) and `.retry_after` on HTTP 429. The client checks the documented request limits before sending:

| Rule | Value |
|---|---|
| URLs per task | up to 10,000 |
| Task IDs per status request | up to 1,000 |
| Drip-feed days | 2–30, at least as many URLs as days, Google indexing only |
| Bing | `checker` tasks only |
| Google `indexer` tasks | sent with `pay_per_indexed: true` (the mode the API accepts now) |

## Tips before you run an index check

- Clean the list first: remove UTM parameters, fragments and duplicates.
- Check status codes and `noindex` before submitting: a 404 or a `noindex` page will not be indexed whatever you do.
- Google's own [URL Inspection tool](https://support.google.com/webmasters/answer/9012289) remains the reference for a single URL on a site you own.

## License

MIT
