# speedyindex — Python client for the SpeedyIndex API

`speedyindex` is a small, dependency-free Python client and command-line tool for SpeedyIndex, a service for link indexing and Google, Bing and Yandex index checking. It wraps the public [SpeedyIndex API](https://en.speedyindex.com/api.php) v2, so you can check whether a list of URLs is indexed, submit links for indexing and pull reports from scripts, cron jobs or CI.

- Standard library only (`urllib`), Python 3.8+
- Index checks for Google, Bing and Yandex
- Link indexing tasks for Google and Yandex, with optional drip-feed
- Task status, task list and full reports
- Backlink checks: find links to your domains on donor pages
- `speedyindex` CLI for quick jobs from the shell

## Install

```bash
pip install speedyindex
```

## API key

Every request needs an API key. You can find it in your SpeedyIndex dashboard or in the SpeedyIndex Telegram bot settings. The client reads it from the `SPEEDYINDEX_API_KEY` environment variable:

```bash
export SPEEDYINDEX_API_KEY="your-key"
```

Keep the key out of source code and commit history; use environment variables or your CI secret store.

## Quick start (Python)

```python
from speedyindex import SpeedyIndex

si = SpeedyIndex()  # reads SPEEDYINDEX_API_KEY

print(si.balance())

# Check which URLs are in Google's index
task = si.create_task(
    ["https://example.com/", "https://example.com/blog/post-1"],
    engine="google",
    task_type="checker",
    title="blog check",
)
print(task)

# Later: progress and the full report
task_id = si.list_tasks(engine="google")["result"][0]["id"]  # newest task
status = si.task_status([task_id], engine="google", task_type="checker")
report = si.full_report(task_id, engine="google", task_type="checker")
```

Submit links for indexing, spread over several days:

```python
si.create_task(urls, engine="google", task_type="indexer", drip_feed=True, drip_feed_days=7)
```

Check donor pages for links to your site:

```python
si.create_backlink_check(["https://donor.example/page"], target_domains=["mysite.com"])
```

## Command line

```bash
speedyindex balance
speedyindex check urls.txt --engine google --title "weekly check"
speedyindex check urls.txt --engine bing
speedyindex index urls.txt --engine google --drip-feed-days 5
speedyindex status 65f8c7315752853b9171860a --type checker
speedyindex report 65f8c7315752853b9171860a --type checker > report.json
speedyindex tasks --engine google --page 0
speedyindex backlinks donors.txt --target mysite.com
```

`urls.txt` holds one URL per line; empty lines and lines starting with `#` are skipped, duplicates are removed. Use `-` to read URLs from stdin:

```bash
cat sitemap-urls.txt | speedyindex check - --engine google
```

## Limits the client enforces

| Rule | Value |
|---|---|
| URLs per task | up to 10,000 |
| Task IDs per status request | up to 1,000 |
| Drip-feed days | 2–30, and at least as many URLs as days |
| Bing | `checker` tasks only |
| Google `indexer` | always sent with `pay_per_indexed: true` (the only mode the API accepts) |

API error codes are raised as `SpeedyIndexError` with `.code`: `1` means the balance is too low, `2` means a validation error.

## Tips before you run an index check

- Clean the list first: remove UTM parameters, fragments and duplicates.
- Check status codes and `noindex` before submitting: a 404 or a `noindex` page will not be indexed whatever you do.
- Google's own [URL Inspection tool](https://support.google.com/webmasters/answer/9012289) remains the reference for a single URL on a site you own.

## License

MIT
