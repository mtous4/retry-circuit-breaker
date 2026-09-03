# Retry & Circuit Breaker Policy Engine

**One week. Graded out of 10 against `RUBRIC_final_projects.md`. This is the last one.**

## What is different about this one

Project 1 gave you a complete specification. Project 2 gave you a stakeholder to interrogate. **This one gives you neither.**

There is no correct answer waiting in a file I'm holding. **You decide what correct means**, you write it down, and then you have to prove it — to me, on data you have never seen, a week from now.

That means I cannot grade this by comparing your output to mine. So I'm grading it three other ways, and I'm telling you all three now, because knowing them is supposed to change how you build.

---

## The goal

Our gateway calls upstream model providers. They fail — sometimes an error, sometimes a timeout, sometimes they're just slow. Right now we hammer them regardless, which makes a bad outage worse.

I want a **policy engine** that reads a log of call outcomes and, for every call, tells me what our policy *should* have done: attempt it, retry it, give up on it, or refuse it outright because we'd already decided that provider was unhealthy.

And I want to be able to see, over the whole log, when we would have stopped calling each provider and when we would have started again.

That is the goal. **Everything else is yours to decide.**

Things you will have to make a call on, none of which I am going to answer for you:

- What counts as a failure. Is a slow success a failure? A timeout — same as an error, or worse?
- How many failures before you stop calling a provider, and measured over what — a count, a window, a rate?
- Once stopped, how long before you try again, and how do you try? One probe, or resume fully?
- What happens if that probe fails. What if it succeeds.
- How many retries per call, how long between them, and how do you keep that deterministic when real backoff uses jitter.
- Per provider, or global? What about a provider you've never seen before?
- What do you do with a record whose status you don't recognise, or whose timestamps are out of order.

There are defensible answers and indefensible ones. There is no single right one. **What I am grading is whether your answer is coherent, written down, and yours.**

---

## Fixed interface

I fix the shape so I can run your code on my data. I do not fix the behaviour.

**Input — `outcomes.jsonl`**, one call per line:

```json
{"id":"c001","provider":"alpha","started_at":"2026-09-01T10:00:00.000Z",
 "status":"ok","latency_ms":420}
```

`status` is one of `ok`, `error`, `timeout` — and you should assume you will eventually be handed something that isn't.

**Config — one file**, format your choice, but every threshold, window and duration lives in it. Nothing tunable hardcoded in logic.

**Output — `decisions.jsonl`**, exactly one line per input record, in input order. Each line must contain at least:

```json
{"id":"c001","action":"...","provider_state":"...","reason":"..."}
```

You define the vocabulary for `action`, `provider_state` and `reason`. You must document it. Once documented, it must not change — I will be predicting against it.

**Plus** a second output showing, per provider, the periods during which you would have stopped calling it. Name and shape are yours.

**Requirements for me to be able to grade you:**

- `pip install -r requirements.txt` then `pytest` from the repo root runs your entire test suite.
- One documented command turns an `outcomes.jsonl` plus your config into your outputs.
- Both must work on a clean clone. I will clone it fresh.

---

## How this is graded — all three, announced in advance

### 1. Mutation testing — does your test suite actually work?

I will take your implementation and **introduce small defects into it**: flip a `>=` to a `>`, change a threshold by one, remove a `not`, invert a boolean. Then I run **your** test suite.

Every defect your tests fail to catch is a hole in your verification. I will show you the survivors.

This is the whole reason a test suite exists, and it is the thing you have never yet been asked to demonstrate. A suite of thirty tests that catches none of these is worth less than four tests that catch all of them.

### 2. Prediction — do you understand your own system?

At the walkthrough I will hand you **ten input scenarios you have never seen.** For each, before running anything, you write down what your system will output and why.

Then we run it.

Where your prediction and your system disagree, one of them is wrong, and either way you did not own it. **This is the closest thing to a direct measurement of whether you built this or approved it.**

I'd rather you predicted "I'm not certain, but I think X because of rule 4" and were wrong, than that you predicted nothing.

### 3. Third-party reproduction — can anyone else run it?

I clone your repo fresh, follow your README exactly, and try to regenerate every number in your `EVIDENCE.md`.

No help from you. No "ah, you need to also…". Either the document is sufficient or it isn't.

---

## What you deliver

1. **`UNDERSTANDING.md`** — the problem in your own words, and what you judge actually matters here versus what merely sounds important.
2. **`POLICY.md`** — your specification. Every decision above, answered, with your reasoning. This is the central document of the project. Someone else should be able to implement your policy from it and get the same answers you get.
3. **Your test suite**, written before the implementation.
4. **The implementation.**
5. **`EVIDENCE.md`** — what you measured, what counts as correct *by your own definition*, and the command that regenerates every number.
6. **`AI_LOG.md`** and **`QUESTIONS.md`**.
7. **`README.md`** that works on a clean clone.

---

## Hard rules

1. No implementation code before `POLICY.md` exists.
2. **Determinism.** Same input, same output, every run. If you want jitter, seed it and document the seed. A non-deterministic engine cannot be graded and cannot be trusted.
3. All thresholds and durations in config, not in logic.
4. Files in, files out. No network, no database.
5. Every number in `EVIDENCE.md` regenerable by a command.

---

## The one thing worth understanding before you start

In Project 1 the way through was reading carefully. In Project 2 it was asking.

Here, nobody is going to tell you the answer and there is nothing to read — so the only thing that can make this project good is that **you decided, deliberately, and can say why.** A policy you chose for a reason and documented beats a better policy you can't account for. Every time.

You may use AntiGravity for all of it. But note what the three tests above are actually measuring: whether your tests can fail, whether you can predict your own system, and whether a stranger can run it. None of those improve by generating more code.
