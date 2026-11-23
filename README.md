# template-openai-agents

[![Deploy to uagents8](https://img.shields.io/badge/Deploy%20to-uagents8-6366f1?style=for-the-badge)](https://app.uagents8.com)

An [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) agent behind
[FastAPI](https://fastapi.tiangolo.com), ready to deploy on
[uAgents8](https://uagents8.com) and to replace with your own agent and tools. One of three
one-click framework templates: LangGraph, CrewAI and this one.

> **Today, the badge opens the dashboard**, where **+ Deploy Agent -> Source -> Templates ->
> OpenAI Agents SDK starter** deploys it in the steps below. **Use this as a GitHub template.**
> Click **Use this template** above to create your own copy in *your* GitHub account - never a
> write back to this repository. Download the code instead if you'd rather redeploy through
> Code Archive.

## What this is

One agent, one tool:

| Route | What it does |
|---|---|
| `GET /` | A friendly status answer: `{"status": "ok", "agent": "template-openai-agents"}`. |
| `POST /ask` | Body `{"question": "..."}`. Answers `{"question", "answer", "mode"}`: the agent can call `word_count` (counts the words and characters in a piece of text), then answers - `mode: "model"` once a key is set, `mode: "stub"` otherwise. |

```bash
curl -X POST https://<your-agent>.uagents8.app/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "how long is this sentence"}'
```

## No API key needed to start

It needs **no API key and no network** to start. With no `OPENAI_API_KEY` set, the agent still
runs its tool for real and answers with the real result, plus exactly what to add next - instead
of refusing to start (see `uagents8.json`'s `env_vars`, and `NO_KEY_MESSAGE` in `main.py`). This
template is OpenAI-only by design: the SDK itself only talks to OpenAI's own API, so there is no
provider choice to make here (unlike the LangGraph template's OpenAI/Anthropic switch).

The place you change to make it your own is `agent` (its `instructions` and `tools`) in `main.py`.

## Run it on your machine

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PORT=8000 python main.py
```

In a second terminal:

```bash
curl http://localhost:8000/
curl -X POST http://localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"question": "how long is this sentence"}'
```

Checks: `pip install -r requirements-dev.txt && ruff check . && pytest`.

## What the platform needs, and where this template does it

- **Listen on the `PORT` environment variable, on `0.0.0.0`.** The last lines of `main.py`. The
  platform only checks that the port accepts connections; an API with only `/ask` would pass too.
- **A `main.py` at the top level that starts the server itself.** The platform runs `python main.py`.
- **A `requirements.txt` at the top level with every package pinned (`==`).** The build uses
  Python 3.12 and has no compiler, so every pin has a ready-made wheel.
- **No `Dockerfile` needed.** The platform writes one from your code.
- **Open the port quickly.** The port has to accept connections within about 150 seconds of the
  container starting.

## Deploy it from uAgents8

1. Press **+ Deploy Agent**.
2. **Details**: give it a name.
3. **Source**: either **GitHub** (this repository, branch `main`) or **Code Archive**: from this
   folder run `zip template-openai-agents.zip main.py requirements.txt` and upload the file.
4. **Configure**: **Execution mode** **Continuous Service**, resource size **T** (256 MB - see
   `uagents8.json`'s `recommended_size`), and your OpenAI key if you have one.
5. **Confirm**, then **Deploy agent**.

When the status screen says **Running**, open the agent's URL and call it the same way as on your
machine.

## Use a real model

1. Set `OPENAI_API_KEY` under **Environment Variables**, **Sensitive** on.
2. Redeploy. A changed variable is only picked up on the next deploy.
3. Optionally override the model with `MODEL_NAME` (default `gpt-4o-mini`).

`ask()` then calls the real model through the Agents SDK and answers with `mode: "model"`. The
model is never exercised by the smoke tests (they cover the offline, no-key path only).

## About this repository

Maintained by the uAgents8 team. CI lints, runs the smoke tests and calls the running server on
every push and once a week (`.github/workflows/ci.yml`); a separate weekly job
(`.github/workflows/deploy-check.yml`) deploys this exact template to the platform's own e2e
sandbox, calls `POST /ask`, and deletes it - so an SDK release or a dependency drift is caught
before a customer meets it, not after.
