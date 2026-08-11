<p align="center">
  <img src="og-cover.png" alt="Agent Memory Playbook - Empire Labs" width="100%">
</p>

<p align="center">
  <b>The memory stack that keeps a 12-agent autonomous fleet from forgetting.</b><br>
  Hot memory. State files. Session search. Verify-before-assert. One commit rule.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/production-12%20agents-22c55e" alt="Production">
  <a href="https://dev.to/narko4u/twelve-agents-one-memory-persistent-recall-for-an-autonomous-agent-fleet-57j6"><img src="https://img.shields.io/badge/dev.to-full%20article-0A0A0A?logo=devdotto&logoColor=white" alt="Dev.to full article"></a>
  <a href="https://github.com/narko4u/agent-memory-playbook"><img src="https://img.shields.io/github/stars/narko4u/agent-memory-playbook?style=social" alt="Stars"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> &middot;
  <a href="#the-problem">The problem</a> &middot;
  <a href="#the-four-layers">The four layers</a> &middot;
  <a href="#the-commit-rule">The commit rule</a> &middot;
  <a href="#what-we-learned">What we learned</a>
</p>

---

We run twelve autonomous AI agents in production. They generate leads, parse tenders, monitor compliance, review code, and keep each other honest. They run on a cron scheduler, work from the same codebase, and - until we built this - they **forgot everything between runs**.

This repository is the memory architecture we built to fix that. It is copy-pasteable into any agent stack, from a single agent on a laptop to a fleet on a scheduler. MIT-licensed. Take it.

## Quick Start

Three moving parts, one rule:

```bash
# 1. The store - SQLite + FTS5 full-text session search
sqlite3 agent-memory.db \
  "CREATE VIRTUAL TABLE messages USING fts5(session_id, role, content);"

# 2. The state files - one per external thread, on disk
mkdir -p ~/.state

# 3. The discipline - commit after every external action, in the same turn
echo "- $(date -Iseconds) - action taken, logged same-turn" >> ~/.state/thread.md
```

That is the whole thing. Now an agent can pick up a thread days later and say: *"Here's where we left off, here's what's changed, here's the blocker."*

## The Problem

Ask any agent "what were we working on last?" and you get a blank stare. Each run is a fresh context window, a fresh identity, a fresh amnesia. The first time one of our agents lost track of an external thread - a vendor application, an email sequence, a live finding - we learned the hard way that **"I'll remember that" is not a memory architecture**.

The damage was not the lost thread. It was the **false confidence**. The agent *believed* the work was handled. It was not. "This approach works until it doesn't - and when it doesn't, the damage is already done."

Three things were missing:

1. **Durable state** - the thread existed only in a dead context window
2. **A recall path** - no way to search what past sessions actually did
3. **A commit discipline** - no rule forcing state to be written at the moment of action

Each missing piece became a layer.

## The Four Layers

### Layer 0 - Hot Memory: What the Agent Knows

A compact, curated memory block injected into the system prompt every turn. The discipline is **smallness** - it is paid for on every token of every turn, so it holds only facts that will still matter in a month, plus pointers to where the durable state lives.

```markdown
# MEMORY (hot tier - injected every turn)
- Compact facts only: preferences, conventions, hard rules
- State files live in ~/.state/ - one file per external thread
```

Anything bigger, or anything with a shelf life shorter than a month, gets evicted to the next layer.

### Layer 1 - State Files: What the Agent Did

One file per external thread, with a `CURRENT STATUS` line at the top, updated in the **same turn** as any state-changing action.

```markdown
# Thread: [EXTERNAL_THREAD_NAME]
CURRENT STATUS: SUBMITTED - awaiting validation

- [DATE] - Application form completed
- [DATE] - Content pack attached, terms signed
```

Why files and not memory? Files are **searchable, diffable, and survive context death**. Memory is what the agent knows; state files are what the agent *did* - the durable, verifiable record.

### Layer 2 - Session Search: What Was Said

State files record actions. Half of what matters is *conversation* - decisions, reasoning, rejected alternatives. Every message from every session lands in a SQLite FTS5 index; recall is a full-text query.

```sql
-- Discovery: "which session dealt with X?"
SELECT session_id, snippet(messages, 3, '[', ']') AS hit
FROM messages
WHERE messages MATCH 'memory AND (prune OR recall)'
ORDER BY rank
LIMIT 5;
```

The *bookend* recall pattern: grab the first three messages of a session, the window around the hit, and the last three, and you reconstruct the whole thread - goal, decision, resolution - at roughly 10% of the token cost of replaying it.

### Layer 3 - Verify Before Assert: What Was Actually Done

Agents self-report. Self-reports lie - not from malice, but from stale context, partial reads, and hallucinated confidence. **Never trust a self-report without evidence.**

```python
# Anti-pattern: assert from memory
# if agent_says("email sent"): proceed()

# Pattern: verify the artifact, then assert
import requests, subprocess

def verify_repo_pushed(owner, repo, sha):
    r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}")
    return r.status_code == 200

assert verify_repo_pushed("[GITHUB_ORG]", "agent-memory-playbook", "HEAD")
```

If an agent claims "email sent," the email must be visible in the sent folder. If it claims "service up," the health check must return 200. Memory without verification is just confident hallucination with extra steps.

## The Commit Rule

Four layers, one rule: **commit in the same turn, verify before you assert, and never let a thread exist only inside a context window.**

The checklist every agent run follows:

1. **On start** - read state files + hot memory *before* answering anything about the past
2. **On action** - write the state file in the same turn as the external change
3. **On recall** - search the session store, don't guess; use bookends, don't replay whole threads
4. **On claim** - verify the artifact (sent folder, remote commit, live HTTP) before asserting success
5. **On memory** - keep hot memory small; evict to state files and search, never bloat the prompt

## What We Learned

1. **Context windows are disposable; state files are forever.** Design for context death - it *will* happen mid-thread.
2. **"I'll remember that" is not a memory architecture.** The first failure costs an investigation; the discipline costs a file write.
3. **Hot memory is a budget, not a diary.** Every char in the system prompt is paid for every turn. Curate ruthlessly.
4. **Full-text search beats perfect structure.** We tried nested folders and taxonomy first. FTS5 over everything won - search scales, structure rots.
5. **Bookend recall beats replay.** First three + hit window + last three reconstruct a thread at ~10% of the token cost.
6. **Self-reports need evidence.** "Verify the artifact, then assert" turned false confidence into checkable fact.
7. **The commit rule is the keystone.** Layers 0-2 are architecture; layer 3 and the rule are culture. You need both.

## Read the Full Story

The deep-dive write-up is live on Dev.to:

**[Twelve Agents, One Memory: Persistent Recall for an Autonomous Agent Fleet](https://dev.to/narko4u/twelve-agents-one-memory-persistent-recall-for-an-autonomous-agent-fleet-57j6)**

---

*Empire Labs Pty Ltd, Security Division*
*[www.empirelabs.com.au](https://www.empirelabs.com.au)*

*Building open infrastructure for autonomous AI agents. MIT-licensed.*
