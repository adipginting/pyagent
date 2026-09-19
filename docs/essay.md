# How pyagent works, in plain language

An essay version of the talk: no timings, no stage directions, just the ideas
and the code behind them. If you can read Python `if` statements and loops,
you can read all of it.

## The one idea

A language model is a machine for predicting text. Ask it the same question
twice and you may get two different answers. That is what people mean when
they call it **probabilistic**: it deals in likelihoods, not certainties.

Ordinary software is the opposite. A `for` loop does the same thing every
time. Push the same input in, get the same output out. That is
**deterministic**.

pyagent is built on the seam between those two worlds. The model decides
*what* to do; a program calls a **harness** that decides *how* that is allowed
to happen. The model is the creative part. The harness is the part you can
read, test, and put a limit on. Almost everything interesting about a coding
agent lives in the harness, not the model. That is the whole thesis.

## Why build one instead of just using one?

Four reasons.

First, the model brings flexibility. The same prompt can produce a different
plan or choose different tools. That variety is the point, not a defect.

Second, engineering supplies the foundation. A model can suggest "read
config.py," but something has to turn that suggestion into an actual file
read and then hand the result back. That "something" is ordinary code you
write and own.

Third, the harness makes the rules explicit. Which tools exist, what each one
accepts, how long it may run, how many times the loop may repeat — all of
that is written down in code, so it can be reviewed and argued about.

Fourth, building one makes you a better engineer. You quickly learn where the
model is reliable and where you should write a test instead. Trust stops being
a feeling and becomes something you can measure.

## Events are the contract

The model's output is messy and variable. If the rest of the program had to
deal with that mess directly, every part would be fragile.

So the harness translates the model's output into a small, fixed set of
**events**. In pyagent there are five: `TextDelta` (a chunk of text),
`ToolCallStarted` (the model wants to run a tool), `ToolResult` (what the tool
returned), `Usage` (how many tokens were used), and `Done` (the run is over).

Think of a **contract**: both sides agree on the shape of what will be
exchanged. The model produces unpredictable content, but it always comes out
wrapped in the same predictable envelopes. A program that prints to the
terminal can subscribe to those events. So can a web browser. So can a test.
None of them need to know how the model works; they only need to know the
events.

That is why pyagent's core rule is: **emit events, never print**. The moment
the core starts printing, it is tied to one screen. By emitting events
instead, it stays free, and each frontend decides how to present them.

## Four small modules

The whole agent is four files, each with one job.

`llm.py` talks to the model. It sends the conversation and the tool list to an
OpenAI-compatible web API and reads the response as it streams back, turning
the raw wire format into those typed events.

`agent.py` is the harness. Its central object, `AgentHarness`, runs the loop:
send the conversation, see what the model wants, run any tools, feed the
results back, and repeat. It emits events and never prints.

`tools.py` holds the three things the agent can actually *do*: `read` a file,
`write` a file, and `bash` (run a shell command). Each tool is described by a
small JSON schema plus a function that performs it.

`cli.py` is the front door for the command line. It subscribes to the event
stream and renders it to your terminal.

If you can remember those four sentences, you can navigate the codebase.

## A harness, not a chatbot

These three words get used for the same demo, but they are not the same thing.

A **chatbot** is a model plus a turn loop. Text goes in, text comes out. It
can be wrong, but it cannot *do* anything: no files touched, no commands
run, no side effects.

An **agent** adds tools and feedback. The model chooses an action, the world
answers, and that answer changes what the model does next. That feedback loop
is what makes it an agent — not the cleverness of the model.

A **harness** is the deterministic code around the model: the loop, the tool
schemas, the limits, the event contract. It does not decide anything. It
executes what the model asks for and enforces what the model is allowed to do.

Put together: **an agent is a model plus a harness.** A chatbot is an agent
with the tools taken away. The harness is where all the engineering lives.
If you cannot point at the part of your "agent" that is deterministic and
testable, you do not have an agent yet.

## The loop

Here is the whole thing, step by step.

One: append the user's message to the conversation. Internally the
conversation is just a list of dictionaries — plain data, the same format the
API expects.

Two: stream a reply from the model. As text arrives, the harness emits
`TextDelta` events, which is why the output appears to type itself out.

Three: if the model asked to use a tool, run that tool, emit a `ToolResult`
with what came back, append that result to the conversation, and go back to
step two. Notice the loop: the model sees the real result and can react.

Four: if the model asks for nothing more, emit `Done` and stop.

Two details matter. The first is that tools are run by the *harness*, not by
the command-line program. The CLI only prints the events it receives; it never
knows what a tool does. That separation keeps the loop reusable.

The second is the limit. The loop may repeat at most `MAX_ITERATIONS` times
(25). This is a safety rail, not a guarantee. A limit makes sure the agent
always terminates; it does nothing to make the answer correct. Those are two
different promises, and good systems are honest about which one they are
making.

There is a matching idea inside the tools. If a tool fails, it does not crash
the program. It returns a string that starts with `Error:`. That string gets
appended to the conversation, so the model sees the failure and can try
something else. Failures become information rather than a dead process.

## The Python you need, in plain language

You do not need to know all of Python to read this agent. Here are the pieces,
in four levels, with the plain-English meaning of each.

### Level 1 — values and names

A **variable** is just a name pointing at a value. `prompt = "hello"` stores
the text `hello` under the name `prompt`.

Every value has a **type**, which is simply "what kind of thing is this?":

- `str` is text — a prompt, a command, a file's contents.
- `int` is a whole number — the loop limit, or a count of tokens.
- `bool` is `True` or `False` — for example, whether a tool succeeded.
- `None` is the special value meaning "nothing yet."
- `list` is an ordered row of things. The conversation is a list.
- `dict` (dictionary) is a set of labelled boxes. A single message is a dict
  like `{"role": "user", "content": "hello"}`.

An **f-string** is text with values dropped into it.
`f"Error: no such file: {path}"` produces a sentence that includes whatever
`path` holds. The `f` stands for "format."

The important realisation here: the agent's entire memory is a list of
dictionaries. Once that clicks, "conversation state" stops being mysterious.

### Level 2 — functions and shaping data

A **function** is a named block of code you can call. It can take inputs
(parameters) and give something back (a return value). For example,
`read(path)` takes a path and returns the file's text.

A **type hint** is a note that says what kind of value goes in or comes out,
like `path: str` or `-> str`. It does not change how the code runs; it is
documentation for humans and editors.

A **default value** lets you call a function without supplying every
parameter. When you call a function by naming its parameters — `api_key=...`,
`model=...` — those are **keyword arguments**.

**Unpacking** with `**` spreads a dictionary into a function's named
parameters. If a tool needs `path="x"`, and you have `{"path": "x"}`, then
`execute(**arguments)` turns one into the other.

A **comprehension** is a loop squeezed into a single expression:
`[tool.schema() for tool in self._tools]` means "build a list of schemas, one
per tool."

### Level 3 — objects and failure

A **class** is a bundle of data and the functions that operate on it. An
**object** is one particular instance of that class. Inside the class, `self`
refers to "this particular object." `AgentHarness` is a class; `self.messages`
is that object's own conversation.

A **dataclass** is a shortcut for writing small classes that mostly just hold
values. pyagent's events are dataclasses, which is why defining a new event
type costs almost nothing.

A **module** is just a file of Python. `import json` brings in a whole toolbox;
`from pyagent.llm import stream_chat` brings in one specific name.

The model speaks **JSON**, which turns out to map neatly onto Python dicts.
`json.loads` converts text into a dict; `json.dumps` converts a dict back into
text. `.get("key", default)` reads a dictionary entry safely even if the key
is missing.

An **exception** is how Python signals that something went wrong. A `try` /
`except` block catches one instead of letting it stop the program. This is the
pattern behind tools returning `"Error: ..."` instead of crashing: the failure
is caught and turned into data.

### Level 4 — streaming

This is the final level, and the heart of the agent.

`async` marks a function that may need to pause while waiting for something
slow, like a network reply. `await` is the spot where it pauses. While one
async function waits, the program can do other things — which is why the
agent can stream text instead of freezing.

A function that contains `yield` is a **generator**. Instead of computing one
big answer and returning it at the end, it hands back results one at a time.
`AgentHarness.run` is such a function: it yields a `TextDelta` each time a
piece of text arrives. The keyword `async for` consumes that stream as it is
produced. That is the whole reason the output feels live.

A **context manager**, written with `with`, sets something up and guarantees
it is cleaned up afterward — even if an error happens in between. The network
client is opened with `async with`, so it always gets closed.

`isinstance(value, SomeType)` asks "is this value of this kind?" pyagent uses
it to decide what to do with each event. And an expression like
`Event = TextDelta | ToolCallStarted | ...` is a **union type**: "one of
these." Together, `isinstance` and the union describe the event contract
exactly.

Two small extras. `partial(stream_chat, api_key=...)` pre-fills some arguments
of a function so it can be passed around as a simpler function. And
`if api_key := os.environ.get(...)` is the **walrus operator**, which assigns
a value and tests it in the same step.

## What happens when you type `pyagent`

When you run the command, control flows like this.

The console script calls `main` in `cli.py`. `main` asks the environment which
provider to use — OpenRouter, Kimi, or DeepSeek — by looking for an API key.
It then creates the harness and tells it how to stream, using `partial` to
pre-fill the key, model, and endpoint.

Next, `main` calls `asyncio.run(_print_events(...))`, which starts the async
machinery. `_print_events` consumes the event stream from `harness.run`,
printing each event as it arrives.

Inside the harness, `run` calls the streaming function, which talks to the
model and returns typed events. When the model asks for a tool, the harness
calls `execute_tool`, which finds the right tool and runs it. The command-line
program never does this itself — it only watches and prints.

So the chain is: command line starts the loop; the loop calls the model; the
model calls tools (through the harness); the command line prints events.

## The skin-in-the-game angle

There is a useful idea from Nassim Taleb's book *Skin in the Game*: never take
advice from someone who does not bear the consequences of that advice.

A language model is the perfect example of an advisor with no skin in the
game. It can propose anything and lose nothing. The harness is the fix,
because it makes the model live with the result: a proposal becomes a
`ToolCallStarted`, the tool actually runs, and the real outcome comes back as
a `ToolResult` in the same conversation. The consequence returns to the thing
that proposed the action.

The same lens explains the limits. You cannot promise the model is *correct*,
but you can promise it never runs forever — that is the iteration cap and the
tool timeouts. It is risk management, not a correctness proof.

Be careful, though: this is a metaphor about a software boundary, not a claim
that the model "cares" or intends anything. The useful part is the design
rule: make the thing that proposes also receive the result.

## What to take away

The interesting engineering in an AI agent is not the model call. It is the
deterministic scaffolding around it: a typed event contract, tools that fail
as data instead of crashing, and a loop with an explicit limit.

pyagent is deliberately small — four modules you can read in an afternoon. But
it is a real agent, not a chatbot, because it acts on the world and feeds the
results back. Model probabilistic, harness deterministic. The harness is what
makes the agent shippable.
