import re
from dataclasses import dataclass
from typing import List, Dict

@dataclass(frozen=True)
class SkillDef:
    weight: float
    patterns: List[re.Pattern]

def _rx(p: str) -> re.Pattern:
    return re.compile(p, re.I)

# Canonical skill -> (weight, regex patterns to detect variants/synonyms)
CATALOG: Dict[str, SkillDef] = {
    "python": SkillDef(3.0, [_rx(r"\bpython\b")]),
    "java": SkillDef(2.5, [_rx(r"\bjava(?!script)\b")]),
    "c++": SkillDef(2.5, [_rx(r"\bc\+\+\b")]),
    "c#": SkillDef(2.2, [_rx(r"\bc#\b"), _rx(r"\b\.net\b")]),
    "javascript": SkillDef(2.8, [_rx(r"\bjavascript\b"), _rx(r"\bjs\b")]),
    "typescript": SkillDef(2.4, [_rx(r"\btypescript\b"), _rx(r"\bts\b")]),
    "react": SkillDef(2.3, [_rx(r"\breact(\.js)?\b")]),
    "node": SkillDef(2.2, [_rx(r"\bnode(\.js)?\b")]),
    "sql": SkillDef(2.6, [_rx(r"\bsql\b"), _rx(r"\bpostgres(q|ql)?\b"), _rx(r"\bmysql\b")]),
    "mongodb": SkillDef(1.6, [_rx(r"\bmongo(db)?\b")]),
    "git": SkillDef(1.8, [_rx(r"\bgit\b"), _rx(r"\bversion control\b")]),
    "linux": SkillDef(1.7, [_rx(r"\blinux\b"), _rx(r"\bbash\b"), _rx(r"\bshell\b")]),
    "docker": SkillDef(1.9, [_rx(r"\bdocker\b")]),
    "kubernetes": SkillDef(1.7, [_rx(r"\bkubernetes\b"), _rx(r"\bk8s\b")]),
    "aws": SkillDef(2.0, [_rx(r"\baws\b"), _rx(r"\bamazon web services\b")]),
    "gcp": SkillDef(1.6, [_rx(r"\bgcp\b"), _rx(r"\bgoogle cloud\b")]),
    "azure": SkillDef(1.6, [_rx(r"\bazure\b")]),
    "pandas": SkillDef(1.9, [_rx(r"\bpandas\b")]),
    "numpy": SkillDef(1.6, [_rx(r"\bnumpy\b")]),
    "pytorch": SkillDef(2.0, [_rx(r"\bpytorch\b")]),
    "tensorflow": SkillDef(1.8, [_rx(r"\btensorflow\b")]),
    "sklearn": SkillDef(1.7, [_rx(r"\bscikit[- ]?learn\b"), _rx(r"\bsklearn\b")]),
    "flask": SkillDef(1.6, [_rx(r"\bflask\b")]),
    "django": SkillDef(1.8, [_rx(r"\bdjango\b")]),
    "fastapi": SkillDef(1.6, [_rx(r"\bfastapi\b")]),
    "rest": SkillDef(1.6, [_rx(r"\brest(\s*api)?\b")]),
    "graphql": SkillDef(1.5, [_rx(r"\bgraphql\b")]),
    "redis": SkillDef(1.2, [_rx(r"\bredis\b")]),
    "kafka": SkillDef(1.2, [_rx(r"\bkafka\b")]),
    "data structures": SkillDef(2.2, [_rx(r"\bdata structures?\b")]),
    "algorithms": SkillDef(2.2, [_rx(r"\balgorithms?\b")]),
    "oop": SkillDef(1.3, [_rx(r"\boop\b"), _rx(r"\bobject[- ]oriented\b")]),
}

JR_POS_RX = re.compile(r"\b(intern|new grad|junior|entry|graduate)\b", re.I)
SENIOR_NEG_RX = re.compile(r"\b(senior|sr\.?|staff|principal|lead)\b", re.I)
REMOTE_RX = re.compile(r"\bremote\b", re.I)
