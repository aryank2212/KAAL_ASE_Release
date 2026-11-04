#!/usr/bin/env python3
"""Choose which model KAAL ASE uses, from any machine, e.g. the laptop that hosts Ollama or LM Studio.

  kaal-model show                     what is configured and whether the model host is reachable
  kaal-model models                   models available on the host
  kaal-model set qwen2.5:7b           switch the chat model (takes effect immediately)
  kaal-model set llama3 --embed nomic-embed-text
  kaal-model host lmstudio --url http://100.64.0.2:1234 [--api-key KEY]
  kaal-model test                     send a tiny prompt through the configured model

Server and key come from --server/--key or KAAL_SERVER (default http://127.0.0.1:8140) and KAAL_API_KEY.
Needs only Python 3.8+.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def call(server, key, method, path, body=None):
    req = urllib.request.Request(server.rstrip("/") + "/api/v1" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-API-Key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode()).get("detail", e.reason)
        except Exception:
            detail = e.reason
        sys.exit(f"error {e.code}: {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"cannot reach {server}: {e.reason}")


def show(st):
    c = st["config"]
    state = f"reachable, {st.get('latency_ms')} ms" if st["reachable"] else f"UNREACHABLE ({st.get('error')})"
    print(f"provider : {c['provider']}\nhost     : {c['base_url']}  [{state}]\nchat     : {c['model']}"
          f"{'' if st.get('model_available', True) else '   (not installed on the host!)'}\nembedding: {c['embed_model']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default=os.environ.get("KAAL_SERVER", "http://127.0.0.1:8140"))
    ap.add_argument("--key", default=os.environ.get("KAAL_API_KEY", ""))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show"); sub.add_parser("models"); sub.add_parser("test")
    s = sub.add_parser("set"); s.add_argument("model"); s.add_argument("--embed")
    h = sub.add_parser("host"); h.add_argument("provider", choices=["ollama", "lmstudio"]); h.add_argument("--url"); h.add_argument("--api-key")
    a = ap.parse_args(argv)
    if not a.key:
        sys.exit("API key needed: set KAAL_API_KEY or pass --key")
    if a.cmd == "show":
        show(call(a.server, a.key, "GET", "/llm"))
    elif a.cmd == "models":
        for m in call(a.server, a.key, "GET", "/llm/models"):
            print(("embedding  " if m["embedding"] else "chat       ") + m["name"])
    elif a.cmd == "set":
        body = {"model": a.model}
        if a.embed:
            body["embed_model"] = a.embed
        show(call(a.server, a.key, "PUT", "/llm", body))
    elif a.cmd == "host":
        body = {"provider": a.provider, "verify": False}
        if a.url:
            body["base_url"] = a.url
        if a.api_key is not None:
            body["api_key"] = a.api_key
        show(call(a.server, a.key, "PUT", "/llm", body))
        print("Host saved. Run `kaal-model models`, then `kaal-model set <model>`.")
    else:
        r = call(a.server, a.key, "POST", "/llm/test", {})
        print(f"OK: {r['model']} replied: {r['reply']}")


if __name__ == "__main__":
    main()
