# Using a remote model host (for example your laptop)

KAAL ASE does not need a GPU on the server. It calls an **Ollama** or **LM Studio** server over HTTP, so a server like
Anton can run the API while the laptop does the model compute. Choose the provider, address and model in the console
(**Models** tab) or from the laptop with `kaal-model`. Changes apply immediately, no restart.

## On the laptop

**Ollama**: make it listen on the network, not only localhost.

- Linux (systemd): `sudo systemctl edit ollama`, add `Environment="OLLAMA_HOST=0.0.0.0:11434"`, then `sudo systemctl restart ollama`
- macOS: `launchctl setenv OLLAMA_HOST 0.0.0.0:11434`, then restart the app
- Windows: set the user environment variable `OLLAMA_HOST=0.0.0.0:11434`, then restart Ollama
- Pull what you want: `ollama pull qwen2.5:7b` and `ollama pull nomic-embed-text`

**LM Studio**: open the Developer tab, start the server, and switch on **Serve on Local Network** (port 1234). Download
the chat and embedding models you want; they are listed by the server automatically.

Ollama has **no authentication**. Expose it only on a private network (LAN or Tailscale), never the public internet.

## Laptop gateway ("Anton Oracle")

If the laptop runs the Oracle gateway (a small API in front of its Ollama, `GET /health` and `POST /v1/ask`, usually on port 8003), pick
**Laptop gateway (Oracle)** as the provider and enter `http://<laptop>:8003`. It needs no token. Differences from talking to Ollama directly:

- The gateway serves **one** model, the one the laptop is set up with. KAAL follows it automatically; to change model, change it on the laptop.
- There is **no embedding endpoint** through the gateway, so embeddings need Ollama or LM Studio directly.
- KAAL's instruction text is sent as the gateway's `context`, and the question as `message`. Reasoning `<think>` blocks are stripped.

## Connect

In the console: **Models**, pick the provider, enter the laptop address (e.g. `http://100.64.0.2:11434` for Ollama or
`:1234` for LM Studio), **Connect & list models**, choose the chat and embedding model, **Use this model**, then
**Send test prompt**. Models you add later on the laptop show up after another **Connect & list models**.

## From the laptop (change the model from the host machine)

    # kaal-model is a single file using only the Python standard library (no pip install)
    export KAAL_SERVER=http://anton:8140  KAAL_API_KEY=...
    kaal-model host lmstudio --url http://100.64.0.2:1234
    kaal-model models
    kaal-model set qwen2.5-7b-instruct
    kaal-model test

`set` refuses a model the host does not have and tells you what it does have.
