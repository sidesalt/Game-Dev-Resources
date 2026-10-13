"""Adds Cinder's free cloud models to an Odysseus install (any device).

Run it with Odysseus's own Python, from the Odysseus folder:

    cd <odysseus folder>
    <its venv python> <this file> [--ollama-key KEY]

Adds (once; running it again changes nothing):
  - "OVHcloud Free (no account)"  free models with no key at all
  - "Cinder (voxel monsters)"     the cinder chat model on 127.0.0.1:8740
  - "Ollama Cloud"                only with --ollama-key, or keeps an existing one

On every cloud endpoint only the models that really answer for free are shown
(a paid one answers 402/403), so Odysseus never offers a model that costs money.
Local endpoints are never added: the AI runs in the cloud, not on this GPU.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.getcwd())
from core.database import ModelEndpoint, SessionLocal  # noqa: E402  (Odysseus's own tables)

OVH = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"
OVH_MODELS = ["gpt-oss-120b", "Qwen3.5-397B-A17B", "Qwen3.8-27B", "Meta-Llama-3_3-70B-Instruct", "gpt-oss-20b",
              "Mistral-Small-3.2-24B-Instruct-2506"]
OLLAMA = "https://ollama.com/api"
OLLAMA_MODELS = ["gpt-oss:120b", "gpt-oss:20b", "nemotron-3-ultra", "nemotron-3-super", "nemotron-3-nano:30b",
                 "gemma4:31b"]


def answers_free(base, key, model):
    url = base.replace("/api", "/v1") if base.endswith("/api") else base
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "OK"}], "max_tokens": 5}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url + "/chat/completions", data=body, headers=headers), timeout=90)
        return True
    except urllib.error.HTTPError as error:
        return error.code == 429  # busy right now, but free
    except (urllib.error.URLError, OSError):
        return False


def upsert(db, ep_id, name, base, key, kind, models, check):
    row = db.query(ModelEndpoint).filter(ModelEndpoint.base_url == base).first()
    if check:
        models = [m for m in models if answers_free(base, key or (row.api_key if row else ""), m)]
        print("  free models on %s: %s" % (name, ", ".join(models) or "none answered right now"))
    if row is None:
        row = ModelEndpoint(id=ep_id, name=name, base_url=base, api_key=key or "", is_enabled=True, model_type="llm",
                            endpoint_kind=kind, supports_tools=kind == "api", owner=None)
        db.add(row)
        print("added   " + name)
    else:
        if key:
            row.api_key = key
        print("updated " + row.name)
    if models:
        row.pinned_models = json.dumps(models)
        row.cached_models = json.dumps(models)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama-key", default="", help="an ollama.com API key (optional)")
    args = parser.parse_args()
    db = SessionLocal()
    upsert(db, "ovhfree0", "OVHcloud Free (no account)", OVH, "", "api", OVH_MODELS, True)
    upsert(db, "cinder00", "Cinder (voxel monsters)", "http://127.0.0.1:8740/v1", "cinder", "local", ["cinder"], False)
    has_ollama = db.query(ModelEndpoint).filter(ModelEndpoint.base_url == OLLAMA).first()
    if args.ollama_key or has_ollama:
        upsert(db, "ollamac0", "Ollama Cloud", OLLAMA, args.ollama_key, "api", OLLAMA_MODELS, True)
    db.commit()
    print("Done. Restart Odysseus to see the new models in the picker.")


if __name__ == "__main__":
    main()
