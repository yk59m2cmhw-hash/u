"""Terminal chat: python3 -m okno [--provider offline|anthropic|gemini|auto] [--model ...]"""
import argparse

from . import kb as kbmod
from .agent import Conversation
from .handoff import sinks_from_env
from .providers import make_provider


def main(argv=None):
    ap = argparse.ArgumentParser(description="Okno demo: chat as a customer of a fictional company")
    ap.add_argument("--provider", default="auto", help="offline | anthropic | gemini | auto (default)")
    ap.add_argument("--model", default=None, help="override the model (or set OKNO_MODEL)")
    ap.add_argument("--kb", default=None, help="path to a company knowledge base JSON")
    args = ap.parse_args(argv)
    kb = kbmod.load(args.kb)
    provider = make_provider(args.provider, kb, args.model)
    conv = Conversation(kb, provider, channel="cli", sinks=sinks_from_env())
    print(f"Okno demo — «{kb['company']}» ({'вымышленная компания' if kb.get('fictional') else kb.get('city', '')}). "
          f"Провайдер: {provider.name} / {provider.model}. Пустая строка — выход.\n")
    while True:
        try:
            text = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        out = conv.handle(text)
        print(f"Okno: {out['reply']}\n")
        if out["status"] in ("handed_off", "closed"):
            if out["card"]:
                print("----- карточка для сотрудника -----\n" + out["card"] + "\n-----------------------------------")
            break
    u = conv.usage
    print(f"\nТокены: вход {u['input_tokens']}, выход {u['output_tokens']}"
          f"{' (оценка офлайн-режима)' if u['estimated'] else ''}; вызовов модели: {u['model_calls']}")


if __name__ == "__main__":
    main()
