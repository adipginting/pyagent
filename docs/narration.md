# pyagent — talk narration

A script for a **20–30 minute** talk around
`pyagent-presentation-large.odp`. The deck and this doc are kept in sync: the
spoken lines live in the ODP's speaker notes, and this file is generated from
them. (The deck file now has **18 pages** — the ten topics below, with the
dense ones split across two pages so the 25%-larger type fits.)

Pace is roughly 130 words/minute. The times total ~28 minutes, leaving room
for a live demo and Q&A.

| Slide | Topic | Time |
| --- | --- | --- |

| 1 | The thesis | 0:00–2:00 |
| 2 | Why build one instead of just using one? | 2:00–5:30 |
| 3 | Events are the contract | 5:30–8:30 |
| 4 | Four modules, one job each | 8:30–11:30 |
| 5 | Harness vs. chatbot vs. agent | 11:30–14:30 |
| 6 | The loop, step by step | 14:30–18:30 |
| 7 | Python, in four tiers | 18:30–21:30 |
| 8 | The CLI call chain | 21:30–24:00 |
| 9 | Skin in the game | 24:00–26:30 |
| 10 | Get started / close | 26:30–28:30 |

The `>` lines are spoken. Bracketed, bold lines are delivery notes. Backup material at the end is for Q&A.

---

## Slide 1 — The thesis (0:00–2:00)

> Most agent talks go one of two ways. Either they stay in the clouds — 'the model reasons' — or they drop you into forty files of glue with no map. This one does neither.
>
> pyagent is the smallest coding agent I could build and still call an agent: four modules, one loop, three tools. And it rests on a single split. The model is probabilistic — ask it twice, get two answers. The harness is deterministic — same events, same rules, every time. The model decides what; the harness decides how.
>
> If you're an engineer, that second half is the interesting half, because it's the part you can read, test, and cap. Over the next twenty-five minutes I'll draw that line, walk the loop, and finish with the Python you need to read every line of it.

**Aside.** State the thesis in the first ninety seconds — this is a talk about scaffolding, not about the model.

**Transition.** So why build one at all, instead of just calling an API?

---

## Slide 2 — Why build one instead of just using one? (2:00–5:30)

> Four reasons, and none of them is 'because it's fun.'
>
> One — the model brings flexibility. The same prompt can produce different answers or different tool choices. That's a feature, not flakiness.
>
> Two — engineering supplies the foundation. Code defines how a request becomes an action and how the result comes back. That's the part you own.
>
> Three — the harness makes the rules explicit. Tool interfaces, event handling, loop limits — all in code, all reviewable.
>
> Four — building it makes you a better engineer. You learn where to trust the model and where to write a test instead.
>
> The panel on the right is the mental model worth stealing: yin and yang. The model proposes an action; the harness executes it and returns the observed result. A predictable control structure still allows nondeterministic outcomes. That's not a bug; that's the contract.

**Aside.** If the room will take it: an advisor who bears no consequences is dangerous. A model with no harness can propose anything and lose nothing. The feedback loop is what gives its proposals weight.

**Takeaway.** 'Trust the model' is not an architecture. 'Constrain the model's interface, then test everything around it' is.

**Transition.** The thing that makes that possible is a very small idea.

---

## Slide 3 — Events are the contract (5:30–8:30)

> If you remember one sentence from this talk, make it this: events are the contract.
>
> The model's output is variable, so the harness reduces it to a small set of typed events — TextDelta, ToolCallStarted, ToolResult, Usage, Done. Every frontend subscribes to the same stream and decides what to show.
>
> llm.py streams from the provider and never prints. agent.py is the coded control flow. cli.py subscribes and prints. tools.py holds three JSON-schema tools. One interface, four consumers. Because the interface is typed, a printer, a browser, and a test can all consume the same run.

**Aside.** This is 'program to an interface,' applied to a nondeterministic component. You can't pin the model's output, so you pin the event contract — and then everything around the model is testable without a network.

**Transition.** Now the four modules that produce those events.

---

## Slide 4 — Four modules, one job each (8:30–11:30)

> Everything lives under src/pyagent, and each module does exactly one thing.
>
> llm.py streams an OpenAI-compatible API and parses SSE into typed events. agent.py is AgentHarness — the prompt, tool-call, re-prompt loop. It emits events and never prints. tools.py is three tools, each a JSON schema plus an async function: read, write, bash. cli.py is print mode — it subscribes to the event stream and renders it to the terminal.
>
> If you can hold those four sentences, you can hold the codebase.

**Aside.** Most agent projects tangle streaming, looping, tools, and presentation into one blob — and then nothing is testable. Keeping 'emit' separate from 'print' is the cheapest architectural win here.

**Aside.** Notice what makes this a harness and not a chatbot. AgentHarness is the harness; llm.py is the model boundary; tools.py is the action surface. Delete the tools and you have a chatbot. Remove the model and you have an inert harness.

**Transition.** Let's walk the loop.

---

## Slide 5 — Harness vs. chatbot vs. agent (11:30–14:30)

> These three words get used for the same demo, but they are different.
>
> A chatbot is a model plus a turn loop: text in, text out, no side effects.
>
> An agent adds tools and feedback: the model acts, the world answers, and the answer changes what it does next.
>
> The harness is the deterministic code around the model — the loop, the tool schemas, the limits, the event contract.
>
> The test: can you point at the code that decides what the model may do? AgentHarness is the harness; llm.py is the model boundary; tools.py is the action surface. Delete the tools and you have a chatbot.

**Transition.** Which brings us back to the loop.

---

## Slide 6 — The loop, step by step (14:30–18:30)

> Here's the loop, and it's boring in the best way.
>
> One — append the prompt. The user's message joins the running conversation as a plain dict, OpenAI wire format.
>
> Two — stream a completion. The loop streams from the LLM, yielding TextDelta events as text arrives.
>
> Three — run a tool if asked. Yield ToolCallStarted, execute the tool, yield ToolResult, append it, and loop back to step two.
>
> Four — stop when done. If the model asks for nothing more, yield Done and stop.
>
> Two things to notice. First: tools are called by the harness, not by the frontend. The CLI only prints the events it receives; it never knows what a tool actually does. Second: the coded boundary. MAX_ITERATIONS is 25. A limit bounds execution — it does not guarantee a correct answer.

**Aside.** That's avoiding ruin, not seeking certainty, and it's the right framing. You can't promise the model is right. You can promise it never runs forever. Ship the guarantee you can actually make.

**Aside.** Same idea in the tools: a failed tool returns an 'Error: ...' string. That string becomes context the model can act on, instead of a stack trace that kills the process. Errors become data.

**Transition.** Which is enough to run it.

---

## Slide 7 — Python, in four tiers (18:30–21:30)

> People hear ‘we built an agent’ and picture a mountain of Python. It is a hill.
>
> Tier one: values and names — variables, types, f-strings. The agent's memory is a list of dictionaries.
>
> Tier two: functions and data — parameters, type hints, defaults, unpacking, comprehensions.
>
> Tier three: objects and failure — classes and self, dataclasses, modules, JSON, and try/except. That last one is the reliability pattern: errors become data the model can act on.
>
> Tier four: streaming — async and await, generators and yield, async for, async with, isinstance and union types.

**Aside.** Use the tier the room needs; do not walk all four. Tiers one and four carry the most weight.

---

## Slide 8 — The CLI call chain (21:30–24:00)

> Where does it actually start? Follow the stack.
>
> The pyagent command calls main. main asks the environment for a provider, hands the loop a pre-wired streaming function, then asyncio.run drives _print_events.
>
> _print_events walks the events the harness yields. The harness gets them from stream_chat, which gets them from parse_sse.
>
> Tools are called from inside the loop, never by the CLI. The CLI only prints ToolCallStarted and ToolResult; it never knows what a tool does.

**Aside.** For a non-Python room: the CLI starts the loop, the loop calls the model, the model calls tools, the CLI prints events.

---

## Slide 9 — Skin in the game (24:00–26:30)

> If the room has read Taleb, use this framing. His rule: never take advice from someone who does not bear the consequences.
>
> A language model is the ultimate advisor with no skin in the game: it can propose anything and lose nothing. The harness is the fix.
>
> Skin in the game: a proposal becomes a ToolCallStarted, and the real outcome returns as a ToolResult on the same conversation.
>
> Avoiding ruin: MAX_ITERATIONS and the bash timeout cap the downside. You cannot guarantee correct; you can guarantee terminates.

**Caveat.** Taleb writes about people taking risks. This is a metaphor for a software boundary, not a claim about machine intent.

---

## Slide 10 — Get started / close (26:30–28:30)

> It runs in four commands: create a virtualenv, install the package, export a provider key, and ask it to explain this repo.
>
> Four modules, three tools, a test suite, and three providers — OpenRouter, Kimi, or DeepSeek. The docs cover setup and the architecture module by module; the source is on GitHub.
>
> The closing line is why you'd build it at all: learning to code lets you build, inspect, and test the foundation the model stands on.
>
> The interesting engineering in an AI agent isn't the model call. It's the deterministic scaffolding: a typed event contract, tools that fail safely, and a loop with an explicit limit. Model probabilistic, harness deterministic — the harness is what makes the agent shippable. Thanks — questions?

**Aside.** The slide's stats graphic still reads '2 providers / 15 tests'; the repo is now three providers and 18 tests. Say the numbers out loud, or update the graphic.

**Aside.** If there's time, run `make dev` and ask it to list the files — the live tool call is the best thirty seconds of the talk.

---

## Backup — if the questions go deep

**The Python this agent assumes, in four tiers.**

1. Values and names — variables, types (`str`, `int`, `bool`, `None`, `list`,
   `dict`), f-strings (`tools.py:43`). The whole conversation is a list of
   dicts (`agent.py:80`).
2. Functions and data — parameters/returns, type hints, defaults and keyword
   args, `**` unpacking (`tools.py:132`), comprehensions (`agent.py:86`).
3. Objects and failure — classes and `self` (`agent.py:65`), dataclasses
   (`tools.py:20`), modules, dicts ↔ JSON, `try`/`except` turning failures
   into `"Error: ..."` data (`tools.py:125`).
4. Streaming — `async`/`await`, generators and `yield` (`agent.py:90`),
   `async for` (`agent.py:87`), `async with` (`llm.py:98`), `isinstance` and
   union types (`agent.py:88`).

**The call chain when you type `pyagent`.**

```
console script -> main (cli.py:26)
  -> provider_from_env (cli.py:32 -> llm.py:37)
  -> AgentHarness(partial(stream_chat, ...)) (cli.py:36)
  -> asyncio.run(_print_events(...)) (cli.py:45)
  -> harness.run (agent.py:78)
  -> stream_chat (llm.py:78) -> parse_sse (llm.py:110)
  -> execute_tool (agent.py:104 -> tools.py:125) -> tool.execute (tools.py:132)
```

**Harness vs. chatbot vs. agent.** An agent is a model plus a harness. A
chatbot is an agent minus the tools. The harness is the deterministic code:
the loop, the tool schemas, the limits, the event contract. Tools are called
by the harness, never by the CLI.

**Where the Taleb angle lands.** Skin in the game = the `ToolResult` comes
back to the context that proposed the action. Avoiding ruin = `MAX_ITERATIONS`
and the bash timeout cap the downside. The Intellectual Yet Idiot = a model
with no tools: fluent advice, zero exposure.

---

## The bottom line

Model probabilistic, harness deterministic. The harness turns variable output
into a typed event contract, tools that fail as data, and a loop with an
explicit limit. It's small enough to read, test, and run locally — and that
is the whole point.
