---
name: morning-brief
description: Generate a live GitHub briefing every morning — open PRs, pending reviews, issue updates, and prioritized tasks for the day.
version: 1.0.1
author: BlutAgent
license: MIT
metadata:
  hermes:
    tags: [github, daily, briefing, pr, issues, priorities]
    related_skills: [github-pr-workflow, github-issues, pulse-todo, wake-up]
---

# Morning Brief

## Overview

Morning Brief generates a daily GitHub status report with live data on your open PRs, pending reviews, issue updates, and prioritized tasks. It replaces the "what was I working on?" scramble with a clear, actionable briefing.

**Core philosophy:** Start every day with context. Know what's blocked, what needs your attention, and what to work on next — before you write a single line of code.

## Briefing Structure

Every morning brief includes:

### 1. Open PRs (Your Contributions)

```markdown
## My Open PRs (3)

| PR | Repo | Status | Age | Action |
|----|------|--------|-----|--------|
| #42 | owner/repo | ✅ CI passed, 1 approval | 2 days | Ping @reviewer |
| #45 | org/lib | ⏳ CI running | 1 day | Wait |
| #48 | company/app | ❌ CI failed | 4 hours | Fix tests |
```

### 2. PRs Awaiting Your Review

```markdown
## Pending My Review (2)

| PR | Repo | Author | Age | Priority |
|----|------|--------|-----|----------|
| #103 | team/api | @alice | 3 days | 🔴 High (stale) |
| #107 | team/web | @bob | 1 day | 🟡 Medium |
```

### 3. Issue Updates

```markdown
## Issue Activity (Last 24h)

- **#34** (owner/repo): Maintainer responded — awaiting your reply
- **#89** (org/lib): Issue closed as duplicate — no action needed
- **#102** (company/app): New comment from @maintainer — review requested changes
```

### 4. Today's Priorities

```markdown
## Today's Focus

### Must Do
1. Fix CI on PR #48 (blocking merge)
2. Review PR #103 (3 days stale — team blocked)

### Should Do
3. Reply to maintainer on issue #34
4. Update PR #42 based on feedback

### Nice to Do
5. Investigate issue #156 for potential contribution
6. Run repo-scout for new opportunities
```

### 5. Blockers & Waiting

```markdown
## Waiting On

| What | Who | Since | Follow-up |
|------|-----|-------|-----------|
| PR #42 approval | @reviewer | 2 days | Ping today |
| Issue #34 response | Me | 1 day | Reply today |
| CI fix | External | 4 hours | Monitor |
```

## Data Sources

### GitHub API Endpoints

```bash
# Your open PRs
gh api "/search/issues?q=author:@me+type:pr+state:open"

# PRs awaiting your review
gh api "/search/issues?q=review-requested:@me+type:pr+state:open"

# Issues you're subscribed to (last 24h)
gh api "/search/issues?q=involves:@me+updated:>=YYYY-MM-DD"

# Your open issues
gh api "/search/issues?q=author:@me+type:issue+state:open"
```

### Pulse Todo Integration

```bash
# Load your task list
# Cross-reference with GitHub status
# Update task statuses based on PR/issue state
```

## Generation Script

Save as `~/.hermes/skills/github/morning-brief/scripts/generate_brief.py`:

```python
#!/usr/bin/env python3
"""Generate daily GitHub morning brief."""

import json, subprocess, sys
from datetime import datetime, timedelta, timezone

def gh_api(endpoint):
    result = subprocess.run(['gh', 'api', endpoint], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    data = json.loads(result.stdout)
    return data.get('items', []) if 'items' in data else [data] if data else []

def get_my_open_prs():
    """Get PRs I opened that are still open."""
    prs = gh_api("/search/issues?q=author:@me+type:pr+state:open")
    result = []
    for pr in prs:
        # Derive owner/repo once; avoid interpolating a list into the f-string
        repo = '/'.join(pr['repository_url'].split('/')[-2:])

        # Fetch PR details for head SHA
        pr_detail = gh_api(f"/repos/{repo}/pulls/{pr['number']}")
        if isinstance(pr_detail, list):
            pr_detail = pr_detail[0] if pr_detail else {}

        # Check CI status via commit status endpoint
        head_sha = pr_detail.get('head', {}).get('sha', '') if isinstance(pr_detail, dict) else ''
        status = gh_api(f"/repos/{repo}/commits/{head_sha}/status") if head_sha else {}
        ci_state = status.get('state', 'unknown') if isinstance(status, dict) else 'unknown'

        # Fetch reviews separately (not embedded in PR detail)
        reviews = gh_api(f"/repos/{repo}/pulls/{pr['number']}/reviews")
        approvals = len([r for r in reviews if isinstance(r, dict) and r.get('state') == 'APPROVED'])

        result.append({
            'number': pr['number'],
            'repo': repo,
            'title': pr['title'],
            'url': pr['html_url'],
            'created': pr['created_at'],
            'ci_status': ci_state,
            'approvals': approvals
        })
    return result

def get_pending_reviews():
    """Get PRs awaiting my review."""
    prs = gh_api("/search/issues?q=review-requested:@me+type:pr+state:open")
    result = []
    now = datetime.now(timezone.utc)
    for pr in prs:
        created = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
        age_days = (now - created).days
        result.append({
            'number': pr['number'],
            'repo': '/'.join(pr['repository_url'].split('/')[-2:]),
            'title': pr['title'],
            'url': pr['html_url'],
            'author': pr['user']['login'],
            'age_days': age_days,
            'priority': '🔴 High' if age_days >= 3 else '🟡 Medium' if age_days >= 1 else '🟢 Low'
        })
    return result

def get_recent_activity():
    """Get issues/PRs with activity in last 24h."""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    items = gh_api(f"/search/issues?q=involves:@me+updated:>={yesterday}")
    result = []
    for item in items:
        result.append({
            'number': item['number'],
            'repo': '/'.join(item['repository_url'].split('/')[-2:]),
            'title': item['title'],
            'url': item['html_url'],
            'type': 'PR' if 'pull_request' in item else 'Issue',
            'updated': item['updated_at']
        })
    return result

def generate_brief():
    """Generate the full morning brief."""
    my_prs = get_my_open_prs()
    pending_reviews = get_pending_reviews()
    recent = get_recent_activity()
    now = datetime.now(timezone.utc)

    print(f"# Morning Brief — {now.strftime('%Y-%m-%d %H:%M')}\n")

    # My Open PRs
    print(f"## My Open PRs ({len(my_prs)})\n")
    if my_prs:
        print("| PR | Repo | Status | Age | Action |")
        print("|----|------|--------|-----|--------|")
        for pr in my_prs:
            created = datetime.fromisoformat(pr['created'].replace('Z', '+00:00'))
            age = (now - created).days
            ci_icon = {'success': '✅', 'failure': '❌', 'pending': '⏳'}.get(pr['ci_status'], '❓')

            if pr['ci_status'] == 'failure':
                action = "Fix tests"
            elif pr['ci_status'] == 'pending':
                action = "Wait"
            elif pr['approvals'] >= 1 and pr['ci_status'] == 'success':
                action = "Ready to merge"
            elif age >= 2 and pr['approvals'] < 1:
                action = "Ping reviewer"
            else:
                action = "Monitor"

            print(f"| #{pr['number']} | {pr['repo']} | {ci_icon} {pr['approvals']} approval(s) | {age}d | {action} |")
    else:
        print("_No open PRs_ ✓\n")

    # Pending Reviews
    print(f"\n## Pending My Review ({len(pending_reviews)})\n")
    if pending_reviews:
        print("| PR | Repo | Author | Age | Priority |")
        print("|----|------|--------|-----|----------|")
        for pr in pending_reviews:
            print(f"| #{pr['number']} | {pr['repo']} | @{pr['author']} | {pr['age_days']}d | {pr['priority']} |")
    else:
        print("_No pending reviews_ ✓\n")

    # Recent Activity
    print(f"\n## Issue Activity (Last 24h, {len(recent)})\n")
    if recent:
        for item in recent[:10]:
            print(f"- **#{item['number']}** ({item['repo']}): {item['type']} updated — {item['title']}")
    else:
        print("_No recent activity_\n")

    # Today's Priorities
    print(f"\n## Today's Focus\n")
    print("### Must Do")
    must_do = []
    for pr in my_prs:
        if pr['ci_status'] == 'failure':
            must_do.append(f"Fix CI on PR #{pr['number']} ({pr['repo']})")
    for pr in pending_reviews:
        if pr['age_days'] >= 3:
            must_do.append(f"Review PR #{pr['number']} ({pr['repo']}) — stale")
    if must_do:
        for i, task in enumerate(must_do, 1):
            print(f"{i}. {task}")
    else:
        print("_No critical tasks_")

    print("\n### Should Do")
    should_do = []
    for pr in my_prs:
        if pr['approvals'] >= 1 and pr['ci_status'] == 'success':
            should_do.append(f"Follow up on / merge PR #{pr['number']} ({pr['repo']})")
    for pr in pending_reviews:
        if 1 <= pr['age_days'] < 3:
            should_do.append(f"Review PR #{pr['number']} ({pr['repo']})")
    if should_do:
        for i, task in enumerate(should_do, 1):
            print(f"{i}. {task}")
    else:
        print("_No pending tasks_")

    # Blockers
    print(f"\n## Waiting On\n")
    blockers = []
    for pr in my_prs:
        if pr['approvals'] < 1 and pr['ci_status'] != 'failure':
            blockers.append(f"PR #{pr['number']} ({pr['repo']}) — awaiting approval")
    if blockers:
        for b in blockers[:5]:
            print(f"- {b}")
    else:
        print("_No blockers_")

if __name__ == '__main__':
    generate_brief()
```

## Usage

### Manual Generation

```bash
# Generate brief
python3 ~/.hermes/skills/github/morning-brief/scripts/generate_brief.py

# Save to file
python3 ~/.hermes/skills/github/morning-brief/scripts/generate_brief.py > /tmp/brief-$(date +%Y-%m-%d).md

# Send to Telegram (or your preferred channel)
cat /tmp/brief-*.md | telegram-cli -W
```

### Cron Job (Daily at 8am)

```python
cronjob(
    action='create',
    name='morning-brief',
    schedule='0 8 * * *',
    prompt='Generate morning GitHub brief using morning-brief skill. Include: open PRs, pending reviews, issue updates, and today priorities. Format for Telegram and send to user.',
    deliver='telegram'
)
```

### Integration with Wake-Up

```python
# In your wake-up routine
skill_view(name='morning-brief')
terminal(command='python3 ~/.hermes/skills/github/morning-brief/scripts/generate_brief.py')

# Then load pulse-todo and cross-reference
skill_view(name='pulse-todo')
```

## Output Example

```markdown
# Morning Brief — 2026-04-23 08:00

## My Open PRs (3)

| PR | Repo | Status | Age | Action |
|-----|------|--------|-----|--------|
| #42 | owner/repo | ✅ 1 approval | 2d | Ping @reviewer |
| #45 | org/lib | ⏳ CI running | 1d | Wait |
| #48 | company/app | ❌ CI failed | 4h | Fix tests |

## Pending My Review (2)

| PR | Repo | Author | Age | Priority |
|-----|------|--------|-----|----------|
| #103 | team/api | @alice | 3d | 🔴 High (stale) |
| #107 | team/web | @bob | 1d | 🟡 Medium |

## Issue Activity (Last 24h, 5)

- **#34** (owner/repo): PR updated — [Link](...)
- **#89** (org/lib): Issue commented — [Link](...)

## Today's Focus

### Must Do
1. Fix CI on PR #48
2. Review PR #103 (stale)

### Should Do
3. Follow up on PR #42
4. Review PR #107

## Waiting On
- PR #42 approval
- PR #45 CI completion
```

## Pitfalls

### `gh pr list` is repo-scoped — use search API for cross-repo discovery

`gh pr list --author @me` **only returns PRs in the current repository**. Even with `--author blut-agent`, it will not find PRs across different repos. For cross-repo PR discovery, always use:

```bash
gh api search/issues -f q="author:blut-agent type:pr state:open"
```

### `GITHUB_TOKEN` env var can shadow keyring tokens

If `GITHUB_TOKEN` is set in the environment, `gh` uses it as the active account even if a keyring token with broader scopes exists. The env var token often has limited scopes (no `addComment`, no `repo` on some repos). Fix:

```bash
unset GITHUB_TOKEN && gh auth switch  # Use keyring token
# or prefix individual commands: unset GITHUB_TOKEN && gh pr view ...
```

### `gh pr view` requires repo + number, not URL paths

`gh pr view "BuilderOSS/nouns-builder/pull/939"` fails with "no pull requests found". Use:
```bash
gh pr view 939 --repo BuilderOSS/nouns-builder
```

### Closed-without-merge PRs silently disappear from open lists

PRs can be closed without merge between check-ins (e.g., yamada-ui #6921 and simpler-grants-gov #9820 closed on the same day). Always check closed PRs that were open in the last follow-up:
```bash
gh pr view NUM --repo OWNER/REPO --json state,mergedAt,closedAt
```

### Merge conflicts show as `mergeable: CONFLICTING`, `mergeState: DIRTY`

Detect this via `gh pr view --json mergeable,mergeStateStatus`. PRs with `CONFLICTING/DIRTY` need a rebase before they can be merged.

### Timezone-aware datetime subtraction
GitHub API returns ISO-8601 timestamps with `Z` (UTC). `datetime.now()` is offset-naive; subtracting it from an offset-aware timestamp raises `TypeError: can't subtract offset-naive and offset-aware datetimes`. **Fix:** always use `datetime.now(timezone.utc)`.

### Interpolating a list into an f-string URL
`pr['repository_url'].split('/')[-2:]` returns `['owner', 'repo']`. Passing that list directly into an f-string produces `.../['owner', 'repo']/...` and breaks the API call. **Fix:** join first: `repo = '/'.join(pr['repository_url'].split('/')[-2:])`.

### Reviews are not embedded in PR detail
The `/repos/{owner}/{repo}/pulls/{number}` endpoint does **not** include reviews. You must call `/repos/{owner}/{repo}/pulls/{number}/reviews` separately to count approvals.

### Missing script file
The skill references `scripts/generate_brief.py`, but the file may not exist on disk if the skill was installed without linked files. **Fix:** write the script to `~/.hermes/skills/github/morning-brief/scripts/generate_brief.py` before running.

## Anti-Patterns

### ❌ Generating Without Acting

**Bad:** Reading the brief and doing nothing different
**Good:** Using the brief to drive your task list and priorities

### ❌ Skipping Days

**Bad:** "I'll just check GitHub manually today"
**Good:** Running the brief every day — consistency builds the habit

### ❌ Ignoring Stale Items

**Bad:** Letting 3+ day old reviews sit indefinitely
**Good:** Treating stale items as priority — they block others

### ❌ No Cross-Reference with Tasks

**Bad:** Brief and pulse-todo are separate
**Good:** Brief informs pulse-todo updates every morning

## Metrics

Track weekly:

| Metric | Target |
|--------|--------|
| Briefs generated | 7/7 days |
| Stale reviews cleared | < 2 per week |
| PR cycle time | Decreasing trend |
| Morning clarity | Subjective 1-10 |

## Remember

```
Generate every morning at 8am
Include: PRs, reviews, issues, priorities
Cross-reference with pulse-todo
Act on the brief — don't just read it
Stale items = priority
```

**Morning Brief turns GitHub noise into a clear daily plan.**

## Lessons Learned (Week of 2026-04-23)

### What Worked
- **Live API queries over script execution** — calling `gh api` directly in-session produces more reliable, contextual output than running `generate_brief.py`. The script is useful for cron jobs but direct API calls are better for interactive use.
- **CodeRabbit as a review signal** — when CodeRabbit comments on a PR, it's a reliable indicator that the PR is being actively reviewed. Treat CodeRabbit comments as higher priority than silent PRs.
- **Vercel CI "Authorization required" is expected** — for fork PRs, Vercel failing with "Authorization required to deploy" is normal and not a code issue. Don't waste time investigating.
- **PR age tracking is useful** — tracking how long PRs have been open (2+ days = ping reviewer, 4+ days = escalate) is the right cadence for OSS contributions.

### What Didn't Work
- **Notifications API returns 403** — `gh api /notifications` consistently fails with 403 Forbidden because the `GITHUB_TOKEN` env var overrides the keyring token. The workaround (`unset GITHUB_TOKEN`) must be applied before every notifications call.
- **`gh pr view` with URL paths fails** — `gh pr view "BuilderOSS/nouns-builder/pull/939"` returns "no pull requests found". Must use `gh pr view 939 --repo BuilderOSS/nouns-builder`.
- **`gh pr list --json reviewThreads` is invalid** — `reviewThreads` is not a valid field for `gh pr list --json`. Use `reviewRequests`, `reviews`, and `comments` instead.
- **Timezone-aware datetime subtraction** — `datetime.now()` (naive) subtracted from GitHub timestamps (offset-aware with `Z`) raises `TypeError`. Must always use `datetime.now(timezone.utc)`.
- **Interpolating lists into f-string URLs** — `pr['repository_url'].split('/')[-2:]` returns a list. Passing it directly into an f-string produces `.../['owner', 'repo']/...`. Must join first: `'/'.join(...)`.
- **Reviews not embedded in PR detail** — `/repos/{owner}/{repo}/pulls/{number}` does not include reviews. Must call `/reviews` endpoint separately to count approvals.

### Concrete Fixes Applied
- Added `Missing script file` pitfall — skill may be installed without linked files
- Added `Interpolating a list into an f-string URL` pitfall
- Added `Reviews are not embedded in PR detail` pitfall
- Added `Timezone-aware datetime subtraction` pitfall

## Changelog

### v1.2.0 (2026-04-30)
- Added `Lessons Learned` section — comprehensive week-of-2026-04-23 review
- Added `Missing script file` pitfall
- Added `Interpolating a list into an f-string URL` pitfall
- Added `Reviews are not embedded in PR detail` pitfall
- Added `Timezone-aware datetime subtraction` pitfall

### v1.1.0 (2026-04-26)
- Added `metadata:` block to YAML frontmatter
- Added `related_skills: [repo-scout, github-issues, wake-up]`
- Added changelog section