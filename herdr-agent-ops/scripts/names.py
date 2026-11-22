"""Name pool parser for herdr-agent-ops.

Parses references/names.md into NAMES: {group: {theme, keywords_zh, keywords_en, names}.
Also exports RESERVED (hao/herdr reserved words) and GRAY (sensitive words).
"""
import os
import re

_RESERVED_STR = (
    "wait done list read test agent name ask clear doctor suggest status export import "
    "restore pane idle working blocked unknown hat hao herdr task token scope label role "
    "machine session tab workspace terminal send prompt focus split close attach config "
    "input layout move resize server start swap update open report view watch cancel abort say result"
)
RESERVED = set(_RESERVED_STR.split())

_GRAY_STR = (
    "corona coven chapel censer bless karma creed faith oath angel spirit grace mercy "
    "pardon lamb dove revere saint fairy genie magic spell combat bruise attack harm hurt "
    "abuse evil vice cull clash claw crack cringe crook crush diet beard brawn greek roman "
    "latin kanji hanzi pinyin hangul kana hira hebrew arabic cyril thai hindi urdu farsi "
    "tamil telugu zulu maori"
)
GRAY = set(_GRAY_STR.split())


def _load(path=None):
    if path is None:
        try:
            here = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            here = os.getcwd()
        for cand in (os.path.join(here, "..", "references", "names.md"),
                     os.path.join(os.getcwd(), "references", "names.md")):
            if os.path.exists(cand):
                path = cand
                break
    names = {}
    group = theme = kw_zh = kw_en = None
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line = line.rstrip("\n")
        if line.startswith("## "):
            group = line[3:].strip()
            names[group] = {"names": [], "keywords_zh": [], "keywords_en": [], "theme": ""}
        elif line.startswith("主题："):
            names[group]["theme"] = line[3:].strip()
        elif line.startswith("关键词（中文）："):
            names[group]["keywords_zh"] = [k.strip() for k in line[8:].split("/") if k.strip()]
        elif line.startswith("关键词（英文）："):
            names[group]["keywords_en"] = [k.strip() for k in line[8:].split("/") if k.strip()]
        elif line.startswith("- `"):
            m = re.match(r"- `([a-z]{4,6})`", line)
            if m:
                names[group]["names"].append(m.group(1))
    return names


NAMES = _load()
