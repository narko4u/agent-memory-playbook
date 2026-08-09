# Twelve Agents, One Memory: Persistent Recall for an Autonomous Agent Fleet

*Architecture deep-dive by the team that runs a 12-agent autonomous fleet in production.*

---

We run twelve autonomous AI agents in production. They generate leads, parse tenders, monitor compliance, review code, and keep each other honest. They run on a cron scheduler, work from the same codebase, and - until we built it properly - they **forgot everything between runs**.

Ask any agent "what were we working on last?" and you'd get a blank stare. Each run was a fresh context window, a fresh identity, a fresh amnesia. The first time one of our agents lost track of an external thread (a vendor application, an email sequence, a live finding), we learned the hard way that **"I'll remember that" is not a memory architecture**.

This is the memory stack we built instead - four layers, each with a specific job, plus the discipline rule that makes the whole thing hold together. It's what lets an agent pick up a thread days later and say, "Here's where we left off, here's what's changed, here's the blocker."

## The Failure Mode

The incident that started it: an agent had submitted an integration brief to an external platform. A week later, a team member asked about status. The agent checked its context - nothing. It checked its files - nothing. The submission had happened in a session that no longer existed, and no state had been written anywhere durable.

The damage wasn't the lost brief. It was the **false confidence**. The agent *believed* the thread was handled. It wasn't. "This approach works until it doesn't - and when it doesn't, the damage is already done."

Three things were missing:

1. **Durable state** - the thread existed only in a dead context window
2. **A recall path** - no way to search what past sessions actually did
3. **A commit discipline** - no rule forcing state to be written at the moment of action

Each missing piece became a layer.

## Layer 0 - Hot Memory: What the Agent Knows

Every agent starts with a compact, curated memory block injected into its system prompt. It's the agent's *knows* layer: identity, chain of command, environment quirks, hard rules, active threads.

The discipline is **smallness**. Hot memory is a scarce resource - it's paid for on every single token of every single turn. So it holds only:

- Facts that will still matter in a month (preferences, conventions, hard rules)
- Current-state pointers (where the ledger lives, which thread is active)
- **Never** task logs, run results, or completed-work records

```markdown
# MEMORY (hot tier - injected every turn)
- Current: 4,460 / 10,000 chars - compact facts only
- [COMPANY] websites: [TEST_DOMAIN] = TEST; [PROD_DOMAIN] = MAIN
- State files live in ~/.state/ - one file per external thread

# USER PROFILE
- Communicates in short, direct messages
- Wants decisions -> reasoning -> action steps, not essays
```

Anything bigger, or anything with a shelf life shorter than a month, gets evicted. Where does it go? The next layer.

## Layer 1 - State Files: What the Agent Did

Every external thread gets a **state file** on disk. One file per thread, with a `CURRENT STATUS` line at the top, updated in the **same turn** as any state-changing action.

```markdown
# Thread: [EXTERNAL_THREAD_NAME]
CURRENT STATUS: SUBMITTED - awaiting validation

- [DATE] - Application form completed
- [DATE] - Content pack attached, terms signed
- [DATE] - Pre-requisite course completed (95/100)
- [DATE] - Marketing blackout active until confirmed

Next action: follow up if no contact within 2 weeks
```

Why files and not just memory? Because files are **searchable, diffable, and survive context death**. Memory is what the agent knows; state files are what the agent *did* - the durable, verifiable record. When a fresh context window starts, the first thing it does is read the state file and the live system *before* asserting anything.

The rule that makes this work - **the commit rule**:

> Any state-changing action in an external system (email sent, access granted, finding submitted, credential issued) MUST be committed to the state file **in the same turn**. Never "I'll log it later." Later is where threads die.

This is a discipline, not a feature. It costs one file write. It saves entire investigations.

## Layer 2 - Session Search: What Was Said

State files record actions. But half of what matters is *conversation* - decisions, reasoning, rejected alternatives. For that, we index every session into a **searchable message store**.

The workhorse is SQLite with FTS5. Every message from every agent session lands in a virtual table; recall is a full-text query that returns the session, the hit, and the surrounding context.

```sql
-- Every turn lands here, indexed for recall
CREATE VIRTUAL TABLE IF NOT EXISTS messages USING fts5(
    session_id,
    role,          -- 'user' | 'assistant' | 'tool'
    content,
    tokenize = 'porter'
);

-- Discovery: "which session dealt with X?"
SELECT session_id, snippet(messages, 3, '[', ']') AS hit
FROM messages
WHERE messages MATCH 'memory AND (prune OR recall)'
ORDER BY rank
LIMIT 5;

-- Scroll: once you find the session, read the window around the hit
-- (session_id, anchor_message_id) -> +/-N messages of context
```

The recall pattern has three shapes, and using the right one matters:

1. **Discovery** - search across all sessions for a topic ("which session did the memory prune?")
2. **Scroll** - once you've found the session, walk forward/backward around a message to reconstruct goal -> action -> resolution
3. **Browse** - no query at all, just "what have we been doing lately?" for a status check

One query can reconstruct an entire thread: the goal (first messages), the decision (around the hit), the resolution (last messages). We call it the *bookend* pattern - grab the first three messages, the hit window, and the last three, and you have 90% of the context at a fraction of the token cost.

## Layer 3 - Verify Before Assert: What Was Actually Done

The final layer is the one that prevents self-deception. Agents self-report. Self-reports lie - not out of malice, but out of stale context, partial reads, and hallucinated confidence.

The rule: **never trust a self-report without evidence**. If an agent claims "email sent," the email must be visible in the sent folder. If it claims "repo pushed," the commit must exist on the remote. If it claims "service up," the health check must return 200.

```python
# Anti-pattern: assert from memory
# if agent_says("email sent"): proceed()

# Pattern: verify the artifact, then assert
import requests, subprocess

def verify_email_sent(sender, subject_fragment):
    # check the real sent folder, don't trust the claim
    out = subprocess.run(
        ["himalaya", "-a", sender, "envelope", "list"],
        capture_output=True, text=True,
    ).stdout
    return subject_fragment in out

def verify_repo_pushed(owner, repo, sha):
    r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}")
    return r.status_code == 200

assert verify_email_sent("[EMAIL_ACCOUNT]", "[SUBJECT_FRAGMENT]")
assert verify_repo_pushed("[GITHUB_ORG]", "agent-memory-playbook", "HEAD")
```

This isn't paranoia - it's the difference between an agent that *remembers* and an agent that *knows*. Memory without verification is just confident hallucination with extra steps.

## The Discipline Rule That Holds It Together

Four layers, one rule: **commit in the same turn, verify before you assert, and never let a thread exist only inside a context window.**

The practical checklist every agent run follows:

1. **On start** - read state files + hot memory *before* answering anything about the past
2. **On action** - write the state file in the same turn as the external change
3. **On recall** - search the session store, don't guess; use bookends, don't replay whole threads
4. **On claim** - verify the artifact (sent folder, remote commit, live HTTP) before asserting success
5. **On memory** - keep hot memory small; evict to state files and search, never bloat the prompt

## What We Learned

1. **Context windows are disposable; state files are forever.** Design for the context death - it *will* happen mid-thread.
2. **"I'll remember that" is not a memory architecture.** The first failure costs an investigation; the discipline costs a file write.
3. **Hot memory is a budget, not a diary.** Every char in the system prompt is paid for every turn. Curate ruthlessly.
4. **Full-text search beats perfect structure.** We tried nested folders and taxonomy first. FTS5 over everything won - search scales, structure rots.
5. **Bookend recall beats replay.** First three + hit window + last three messages reconstruct a thread at ~10% of the token cost.
6. **Self-reports need evidence.** "Verify the artifact, then assert" turned false confidence into checkable fact.
7. **The commit rule is the keystone.** Layers 0-2 are architecture; layer 3 and the rule are culture. You need both.

## Try It Yourself

The pattern is copy-pasteable into any agent stack. Minimal viable version:

```bash
# 1. The store - SQLite + FTS5
sqlite3 agent-memory.db \
  "CREATE VIRTUAL TABLE messages USING fts5(session_id, role, content);"

# 2. The state file - one per external thread
mkdir -p ~/.state

# 3. The discipline - a one-line commit after every external action
#    (in whatever language your agent acts in)
echo "- $(date -Iseconds) - action taken, logged same-turn" >> ~/.state/thread.md
```

That's it. Three moving parts, one rule. It scales from a single agent on a laptop to a fleet of twelve running on a cron scheduler - which is exactly where we run it.

---

*- [COMPANY] Security Division*
*[WEBSITE]*

*Building open infrastructure for autonomous AI agents. MIT-licensed.*
