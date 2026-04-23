#!/usr/bin/env python3
"""Generate daily GitHub morning brief.

Security hardened v1.1.0:
- Endpoint validation for API calls
- Owner/repo validation
- No sensitive data exposure
"""

import json, subprocess, sys, re
from datetime import datetime, timedelta

GITHUB_API_BASE = 'https://api.github.com'

def validate_endpoint(endpoint):
    """Validate GitHub API endpoint format."""
    if not isinstance(endpoint, str):
        raise ValueError("Endpoint must be a string")
    if not endpoint.startswith('/repos/') and not endpoint.startswith('/search/'):
        raise ValueError(f"Invalid endpoint format")
    return endpoint

def validate_owner_repo(owner, repo):
    """Validate owner/repo format."""
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$'
    if not re.match(pattern, owner) or not re.match(pattern, repo):
        raise ValueError(f"Invalid owner/repo format")
    return True

def gh_api(endpoint):
    """Make GitHub API call with validated endpoint."""
    endpoint = validate_endpoint(endpoint)
    result = subprocess.run(['gh', 'api', endpoint], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    data = json.loads(result.stdout)
    return data.get('items', []) if 'items' in data else [data] if data else []

def get_my_open_prs():
    prs = gh_api("/search/issues?q=author:@me+type:pr+state:open")
    result = []
    for pr in prs:
        try:
            repo_parts = pr['repository_url'].split('/')[-2:]
            owner, repo = repo_parts
            validate_owner_repo(owner, repo)
            
            pr_detail = gh_api(f"/repos/{owner}/{repo}/pulls/{pr['number']}")
            if isinstance(pr_detail, list): pr_detail = pr_detail[0] if pr_detail else {}
            
            sha = pr_detail.get('head', {}).get('sha', '')
            if sha and re.match(r'^[a-f0-9]{40}$', sha):
                status = gh_api(f"/repos/{owner}/{repo}/commits/{sha}/status")
                ci_state = status.get('state', 'unknown') if status else 'unknown'
            else:
                ci_state = 'unknown'
            
            result.append({
                'number': pr['number'],
                'repo': '/'.join(repo_parts),
                'title': pr['title'],
                'url': pr['html_url'],
                'created': pr['created_at'],
                'ci_status': ci_state,
                'approvals': len([r for r in pr_detail.get('reviews', []) if r['state'] == 'APPROVED']) if pr_detail else 0
            })
        except (ValueError, KeyError, IndexError):
            continue
    return result

def get_pending_reviews():
    prs = gh_api("/search/issues?q=review-requested:@me+type:pr+state:open")
    result = []
    for pr in prs:
        try:
            created = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
            age_days = (datetime.now() - created).days
            result.append({
                'number': pr['number'],
                'repo': '/'.join(pr['repository_url'].split('/')[-2:]),
                'title': pr['title'],
                'url': pr['html_url'],
                'author': pr['user']['login'],
                'age_days': age_days,
                'priority': '🔴 High' if age_days >= 3 else '🟡 Medium' if age_days >= 1 else '🟢 Low'
            })
        except (ValueError, KeyError):
            continue
    return result

def get_recent_activity():
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    items = gh_api(f"/search/issues?q=involves:@me+updated:>={yesterday}")
    result = []
    for item in items:
        try:
            result.append({
                'number': item['number'],
                'repo': '/'.join(item['repository_url'].split('/')[-2:]),
                'title': item['title'],
                'url': item['html_url'],
                'type': 'PR' if 'pull_request' in item else 'Issue',
                'updated': item['updated_at']
            })
        except (KeyError, ValueError):
            continue
    return result

def generate_brief():
    my_prs = get_my_open_prs()
    pending_reviews = get_pending_reviews()
    recent = get_recent_activity()
    
    print(f"# Morning Brief — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    
    print(f"## My Open PRs ({len(my_prs)})\n")
    if my_prs:
        print("| PR | Repo | Status | Age | Action |")
        print("|-----|------|--------|-----|--------|")
        for pr in my_prs:
            created = datetime.fromisoformat(pr['created'].replace('Z', '+00:00'))
            age = (datetime.now() - created).days
            ci_icon = {'success': '✅', 'failure': '❌', 'pending': '⏳'}.get(pr['ci_status'], '❓')
            action = "Ping reviewer" if age >= 2 and pr['approvals'] < 1 else "Wait" if pr['ci_status'] == 'pending' else "Fix tests" if pr['ci_status'] == 'failure' else "Ready"
            print(f"| #{pr['number']} | {pr['repo']} | {ci_icon} {pr['approvals']} approval(s) | {age}d | {action} |")
    else:
        print("_No open PRs_ ✓\n")
    
    print(f"\n## Pending My Review ({len(pending_reviews)})\n")
    if pending_reviews:
        print("| PR | Repo | Author | Age | Priority |")
        print("|-----|------|--------|-----|----------|")
        for pr in pending_reviews:
            print(f"| #{pr['number']} | {pr['repo']} | @{pr['author']} | {pr['age_days']}d | {pr['priority']} |")
    else:
        print("_No pending reviews_ ✓\n")
    
    print(f"\n## Issue Activity (Last 24h, {len(recent)})\n")
    if recent:
        for item in recent[:10]:
            print(f"- **#{item['number']}** ({item['repo']}): {item['type']} updated — [Link]({item['url']})")
    else:
        print("_No recent activity_\n")
    
    print(f"\n## Today's Focus\n")
    print("### Must Do")
    must_do = []
    for pr in my_prs:
        if pr['ci_status'] == 'failure':
            must_do.append(f"Fix CI on PR #{pr['number']}")
    for pr in pending_reviews:
        if pr['age_days'] >= 3:
            must_do.append(f"Review PR #{pr['number']} (stale)")
    if must_do:
        for i, task in enumerate(must_do, 1):
            print(f"{i}. {task}")
    else:
        print("_No critical tasks_\n")
    
    print("\n### Should Do")
    should_do = []
    for pr in my_prs:
        if pr['approvals'] >= 1 and pr['ci_status'] == 'success':
            should_do.append(f"Follow up on PR #{pr['number']}")
    for pr in pending_reviews:
        if 1 <= pr['age_days'] < 3:
            should_do.append(f"Review PR #{pr['number']}")
    if should_do:
        for i, task in enumerate(should_do, 1):
            print(f"{i}. {task}")
    else:
        print("_No pending tasks_\n")
    
    print(f"\n## Waiting On\n")
    blockers = []
    for pr in my_prs:
        if pr['approvals'] < 1:
            blockers.append(f"PR #{pr['number']} approval")
    if blockers:
        for b in blockers[:5]:
            print(f"- {b}")
    else:
        print("_No blockers_\n")

if __name__ == '__main__':
    generate_brief()
