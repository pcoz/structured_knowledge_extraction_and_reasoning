"""Load a JSON knowledge graph and run multi-hop / path / chain queries."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


KB_PATH = Path(__file__).resolve().parent / "kb_1000_articles.json"


@dataclass
class Triple:
    # Core schema — unchanged since v1. Every triple has these five
    # fields and the existing JSON KBs round-trip them losslessly.
    subject: str
    relation: str
    object: str
    source_article: str
    source_sentence_idx: int

    # Production schema extensions. All optional with defaults that
    # match the original semantics: a triple with no temporal slots
    # and confidence 1.0 behaves exactly like a v1 triple, so old
    # JSON files load unchanged and old rules need no edits.
    #
    # valid_from / valid_to: ISO-8601 date strings ("YYYY-MM-DD",
    # "YYYY-MM", "YYYY", or BC forms like "356 BC"). None means
    # unbounded on that side ("valid from forever" / "still valid").
    # See src/kb/temporal.py for interval operations.
    #
    # confidence: noisy-AND combined through derivation chains
    # (see src/kb/confidence.py). 1.0 = asserted as certain. Rules
    # propagate confidence automatically via the dispatcher when
    # `propagate_confidence=True` (the default).
    valid_from: str | None = None
    valid_to: str | None = None
    confidence: float = 1.0


@dataclass
class KB:
    # The serialised state — what gets read from / written to the
    # JSON artifact. Everything below is rebuilt at construction time.
    triples: list[Triple]
    alias_map: dict[str, str]
    n_articles: int

    # Optional source-authority ranking, consumed by the
    # AuthorityWinsPolicy in src/kb/conflict.py. Maps source name
    # (matching Triple.source_article) to a float in [0.0, 1.0]
    # where higher = more authoritative. Empty by default — policies
    # that don't use authority work unchanged.
    source_authority: dict[str, float] = field(default_factory=dict)

    # Adjacency indexes built in __post_init__. Index by entity for
    # O(1) neighbour lookups and BFS traversal. Each entry stores
    # (relation, other_entity, triple_idx) so callers can recover the
    # full Triple by indexing back into self.triples — saves memory
    # vs storing the Triple itself in every adjacency entry.
    out_edges: dict[str, list] = field(default_factory=lambda: defaultdict(list))
    in_edges: dict[str, list] = field(default_factory=lambda: defaultdict(list))
    by_relation: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))

    def __post_init__(self):
        # Single pass over triples populates all three indexes. Called
        # automatically by the dataclass after __init__, and re-runs
        # whenever the reasoner constructs a new KB with extended
        # triples — that's how derived facts become queryable.
        for idx, t in enumerate(self.triples):
            self.out_edges[t.subject].append((t.relation, t.object, idx))
            self.in_edges[t.object].append((t.relation, t.subject, idx))
            self.by_relation[t.relation].append(idx)

    @classmethod
    def load(cls, path: Path) -> "KB":
        """Load a KB from JSON. Backward-compatible with v1 schemas:
        unknown keys are dropped, missing optional keys (valid_from /
        valid_to / confidence) default to the v1-equivalent values.
        Lets old kb_*.json files load unchanged after schema changes."""
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        # Filter to known Triple fields so a newer JSON written with
        # extra keys doesn't blow up an older codebase, and an older
        # JSON written without the new keys defaults cleanly.
        known = {
            "subject", "relation", "object",
            "source_article", "source_sentence_idx",
            "valid_from", "valid_to", "confidence",
        }
        triples = [
            Triple(**{k: v for k, v in t.items() if k in known})
            for t in payload["triples"]
        ]
        return cls(
            triples=triples,
            alias_map=payload.get("alias_map", {}),
            n_articles=payload.get("n_articles", 0),
            source_authority=payload.get("source_authority", {}),
        )

    def entities(self) -> set[str]:
        return set(self.out_edges.keys()) | set(self.in_edges.keys())

    def canonicalize(self, name: str) -> str:
        return self.alias_map.get(name, name)

    def out_facts(self, entity: str, relation: str | None = None) -> list[Triple]:
        ent = self.canonicalize(entity)
        return [
            self.triples[idx]
            for rel, _, idx in self.out_edges.get(ent, [])
            if relation is None or rel == relation
        ]

    def in_facts(self, entity: str, relation: str | None = None) -> list[Triple]:
        ent = self.canonicalize(entity)
        return [
            self.triples[idx]
            for rel, _, idx in self.in_edges.get(ent, [])
            if relation is None or rel == relation
        ]

    def neighbours(self, entity: str) -> set[str]:
        ent = self.canonicalize(entity)
        out: set[str] = set()
        for _, obj, _ in self.out_edges.get(ent, []):
            out.add(obj)
        for _, subj, _ in self.in_edges.get(ent, []):
            out.add(subj)
        return out

    def find_paths(
        self, start: str, end: str, max_hops: int = 4, max_paths: int = 5,
    ) -> list[list[Triple]]:
        """BFS from start to end (edges undirected for connectivity).

        Treats the graph as undirected — both out_edges and in_edges are
        followed at each hop. This matches user intent for "how are X
        and Y connected?" where the answer reads naturally as a chain
        regardless of the relation direction at each link."""
        start = self.canonicalize(start)
        end = self.canonicalize(end)
        if start == end:
            return [[]]
        results: list[list[Triple]] = []
        # `visited` prevents revisiting an entity. Standard BFS — but
        # note we don't visit `end` itself, so multiple distinct paths
        # to `end` can still be discovered.
        visited = {start}
        frontier = [(start, [])]
        for _hop in range(max_hops):
            next_frontier = []
            for current, path in frontier:
                # Forward edges first, then incoming — when we report
                # results, the relation arrows in fmt_path will reflect
                # which direction we traversed.
                for rel, obj, idx in self.out_edges.get(current, []):
                    t = self.triples[idx]
                    if obj == end:
                        results.append(path + [t])
                        if len(results) >= max_paths:
                            return results
                    elif obj not in visited:
                        visited.add(obj)
                        next_frontier.append((obj, path + [t]))
                for rel, subj, idx in self.in_edges.get(current, []):
                    t = self.triples[idx]
                    if subj == end:
                        results.append(path + [t])
                        if len(results) >= max_paths:
                            return results
                    elif subj not in visited:
                        visited.add(subj)
                        next_frontier.append((subj, path + [t]))
            # Return early at the first hop that produced results so
            # we don't keep expanding past the shortest-path layer.
            if results:
                return results
            frontier = next_frontier
        return results

    def chain_query(
        self, start: str, relations: list[str],
    ) -> list[tuple[str, list[Triple]]]:
        """Follow a fixed sequence of relations from start.

        Each relation is followed in BOTH directions (out_facts and
        in_facts) for connectivity. Returns (end_entity, path) pairs.
        """
        start = self.canonicalize(start)
        frontiers = [[(start, [])]]
        for rel in relations:
            next_layer = []
            for entity, path in frontiers[-1]:
                for t in self.out_facts(entity, rel):
                    next_layer.append((t.object, path + [t]))
                for t in self.in_facts(entity, rel):
                    next_layer.append((t.subject, path + [t]))
            frontiers.append(next_layer)
            if not next_layer:
                break
        return frontiers[-1]


def fmt_path(path: list[Triple]) -> str:
    """Render a Triple chain as an arrow string.

    Each relation arrow points in the direction the relation was
    originally stated, regardless of which direction the BFS
    traversal followed. `Aristotle --TUTORED_BY--> Plato` reads the
    same way whether we walked the path Aristotle→Plato or
    Plato→Aristotle."""
    if not path:
        return "(empty path)"
    nodes = [path[0].subject]
    for t in path:
        # Whether we're moving forward or backward through this edge
        # depends on whether the previous node matches the current
        # triple's subject or object — that determines arrow direction.
        if nodes[-1] == t.subject:
            nodes.append(t.object)
            nodes[-2] = f"{nodes[-2]} --{t.relation}--> "
        else:
            nodes.append(t.subject)
            nodes[-2] = f"{nodes[-2]} <--{t.relation}-- "
    return "".join(nodes)


def main() -> None:
    print("=" * 78)
    print("Knowledge graph query session")
    print("=" * 78)
    print()

    if not KB_PATH.exists():
        print(f"  KB file not found: {KB_PATH}")
        return

    kb = KB.load(KB_PATH)
    print(f"  Loaded: {KB_PATH.name}")
    print(f"  Triples:  {len(kb.triples):,}")
    print(f"  Entities: {len(kb.entities()):,}")
    print(f"  Aliases:  {len(kb.alias_map):,}")
    print()

    # Entity cards
    print("ENTITY CARDS")
    print("-" * 78)
    for ent in ["Aristotle", "Alexander the Great", "Albert Einstein",
                "Plato", "Socrates"]:
        out_facts = kb.out_facts(ent)
        in_facts = kb.in_facts(ent)
        print(f"\n  {ent}")
        if not out_facts and not in_facts:
            print(f"    (not in KB)")
            continue
        for t in out_facts[:8]:
            print(f"    {t.relation}: {t.object}")
        if len(out_facts) > 8:
            print(f"    ... + {len(out_facts) - 8} more outgoing")
        if in_facts:
            print(f"    Incoming:")
            for t in in_facts[:3]:
                print(f"      ← {t.relation} ← {t.subject}")
    print()

    # Multi-hop chains
    print("MULTI-HOP QUERIES")
    print("-" * 78)

    print(f"\n  Q: Who did Aristotle tutor?")
    for r in [t.object for t in kb.out_facts("Aristotle", "TUTORED")]:
        print(f"    → {r}")

    print(f"\n  Q: Aristotle's tutor's tutor?")
    for tutor in [t.object for t in kb.out_facts("Aristotle", "TUTORED_BY")]:
        for t in kb.out_facts(tutor, "TUTORED_BY"):
            print(f"    → Aristotle ← {tutor} ← {t.object}")

    print(f"\n  Q: What did Aristotle's student conquer?")
    for end, path in kb.chain_query("Aristotle", ["TUTORED", "CONQUERED"]):
        print(f"    → {path[0].object} conquered {end}")

    print(f"\n  Q: Connection between Alexander the Great and Socrates?")
    paths = kb.find_paths("Alexander the Great", "Socrates", max_hops=4)
    for p in paths[:3]:
        print(f"    → {fmt_path(p)}")

    # Filter queries
    print()
    print("FILTER QUERIES")
    print("-" * 78)
    print(f"\n  Q: Entities born in the 4th-5th century BC")
    for t in kb.triples:
        if t.relation == "BORN_DATE":
            m = re.match(r"(\d+)\s*BC", t.object)
            if m and 300 < int(m.group(1)) <= 500:
                print(f"    → {t.subject} ({t.object})")

    print(f"\n  Q: Entities born in the 19th century")
    seen = set()
    for t in kb.triples:
        if t.relation == "BORN_DATE":
            try:
                year = int(re.match(r"\d+", t.object).group(0))
                if 1800 <= year <= 1899 and t.subject not in seen:
                    seen.add(t.subject)
                    print(f"    → {t.subject} ({t.object})")
                    if len(seen) >= 10:
                        break
            except (AttributeError, ValueError):
                pass

    # Graph stats
    print()
    print("GRAPH STATS")
    print("-" * 78)
    mention_counts = Counter()
    for t in kb.triples:
        mention_counts[t.subject] += 1
        mention_counts[t.object] += 1
    print(f"\n  Top 10 most-connected entities:")
    for ent, n in mention_counts.most_common(10):
        print(f"    {ent}: {n} mentions")

    rel_counts = Counter(t.relation for t in kb.triples)
    print(f"\n  Top 10 relations:")
    for rel, n in rel_counts.most_common(10):
        print(f"    {rel}: {n}")
    print()


if __name__ == "__main__":
    main()
