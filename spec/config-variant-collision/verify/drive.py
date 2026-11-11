"""Gate: drive the configuration core, against the base and against a model of the rule.

    python -I drive.py run PHASE > OUT.json
        Run inside the profile's environment for one tree (the gate runs it once on the base and
        once on the index, each in a fresh interpreter). Before importing cmdkit it replaces
        `subprocess.check_output` and `os.getenv` with spies that record every call and return a
        marker, so nothing runs and nothing is read. It then runs two corpora and prints JSON.

        same    scenarios with no variant collision, which must behave exactly as on the base:
                layers with depth-first merges, a mapping and a scalar under one key, keys that
                are not strings, a name whose every layer sets the same two variants, plain
                Namespace updates and attribute access, `update` with a mapping, keywords or a
                one-shot iterable of pairs, attribute assignment of a present name or of a name
                with no variant present, item assignment and `del` (which bypass `_`), a layer
                added after an in-place change, and `Configuration(_=...)`. After every step it
                records repr(), the merged view, the instance attributes, `which` and item access
                for every path any layer or the merged view holds (and absent ones), `whereis` and
                `duplicates`, attribute access, and the spies' calls. Fixed cases come first, then
                seeded random ones.
        model   scenarios built from keys that collide freely (`a`, `a_env`, `a_eval`, `b`, ...,
                `a_env_eval`, and a key that is not a string), each checked in the run against an
                independent model of the rule: for every name the highest mapping sets a variant
                of, only the variants it sets survive, at every level where the merge descends.
                Checked: the merged view, `_`, the instance attributes, every layer still equal to
                its input, item access and `which` for every path (where the model holds the path,
                the highest source holding it literally; where a source sets another variant of a
                key on the path above a source holding it and item access raises KeyError,
                KeyError; elsewhere an error, except beneath a key an in-place change dropped or
                replaced wholesale, where `which` may name a layer as it does today), attribute
                access, and no spy call outside attribute access. Layers arrive through the
                constructor and through `extend`, one or two at a time. At P2 the scenarios add
                `update` with a mapping, with keywords and with a one-shot iterable of pairs (which
                reaches `_` only, as today, so `which` is not graded beneath its keys), and
                attribute assignment; at P1 they hold layers only.

    python -I drive.py compare PHASE BASE.json HEAD.json
        `same`: every scenario's record is identical on both trees. `model`: no scenario has a
        problem on HEAD, and at least half of them have one on the base (the corpus bites).

Footprint: one Python process, under 100 MB; a few seconds per run.
"""

# type annotations
from __future__ import annotations

# standard libs
import copy
import json
import os
import random
import subprocess
import sys

CALLS: list = []
STATE = {'phase': 'import'}
SAME_RANDOM, MODEL_RANDOM = 400, 400


def spy_check_output(cmd, *args, **kwargs) -> bytes:
    CALLS.append((STATE['phase'], 'eval', str(cmd)))
    return f'EVAL[{cmd}]\n'.encode()


def spy_getenv(name, default=None):
    CALLS.append((STATE['phase'], 'env', str(name)))
    return f'ENV[{name}]'


def attempt(fn) -> str:
    try:
        return 'ok ' + repr(fn())
    except Exception as exc:
        return f'{type(exc).__name__}: {exc}'


def plain(value):
    """A mapping as nested plain dicts, anything else as it is."""
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


def paths_of(mapping, prefix=()) -> list:
    out = []
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            out.append(prefix + (key,))
            out.extend(paths_of(value, prefix + (key,)))
    return out


def lookup(mapping, path):
    for key in path:
        mapping = mapping[key]
    return mapping


def model_lookup(mapping, path):
    """Look up `path` in plain dicts; a step through anything else is a TypeError."""
    for key in path:
        if not isinstance(mapping, dict):
            raise TypeError(f'{type(mapping).__name__} is not a mapping')
        mapping = mapping[key]
    return mapping


def failure(exc: Exception) -> str:
    """KeyError, or 'scalar' for a step through a value that is not a mapping."""
    return 'KeyError' if isinstance(exc, KeyError) else 'scalar'


# ---------------------------------------------------------------- the `same` corpus

FAMILIES = ['a', 'b', 'c', 'k']


def same_forms(rng: random.Random) -> dict:
    forms = {}
    for name in FAMILIES:
        forms[name] = rng.choice([(name,), (name,), (f'{name}_env',), (f'{name}_eval',),
                                  (name, f'{name}_env'), (f'{name}_env', f'{name}_eval')])
    forms['int'] = (7,)
    forms['str7'] = ('7_env',)
    return forms


def same_value(rng: random.Random, forms: dict, depth: int):
    r = rng.random()
    if depth < 2 and r < 0.35:
        return same_mapping(rng, forms, depth + 1)
    if r < 0.6:
        return rng.randint(0, 9)
    if r < 0.9:
        return rng.choice(['x', 'y', 'echo v'])
    return [rng.randint(0, 3)]


def same_mapping(rng: random.Random, forms: dict, depth: int = 0) -> dict:
    out = {}
    for family in rng.sample(sorted(forms), rng.randint(1, 3)):
        for key in forms[family]:
            out[key] = same_value(rng, forms, depth)
    return out


def same_ops(seed: int) -> list:
    rng = random.Random(seed)
    forms = same_forms(rng)
    layers = [(f'l{i}', same_mapping(rng, forms)) for i in range(rng.randint(1, 4))]
    local = same_mapping(rng, forms) if rng.random() < 0.2 else None
    ops = [('new', layers, local)]
    singles = [form[0] for form in forms.values() if len(form) == 1 and isinstance(form[0], str)]
    for _ in range(rng.randint(0, 4)):
        kind = rng.choice(['update', 'update', 'update_iter', 'update_kw', 'setattr', 'setattr',
                           'fresh', 'setitem', 'delitem', 'extend'])
        if kind in ('update', 'update_iter'):
            ops.append((kind, same_mapping(rng, forms)))
        elif kind == 'update_kw':
            ops.append((kind, {k: v for k, v in same_mapping(rng, forms).items() if isinstance(k, str)}))
        elif kind == 'setattr':
            ops.append(('setattr_present', rng.choice(singles) if singles else 'a', same_value(rng, forms, 1)))
        elif kind == 'fresh':
            ops.append(('setattr_fresh', 'fresh', same_value(rng, forms, 1)))
        elif kind == 'setitem':
            key = rng.choice(singles) if singles else 'a'
            ops.append(('setitem', key, same_value(rng, forms, 1)))
        elif kind == 'delitem':
            ops.append(('delitem_present',))
        else:
            ops.append(('extend', f'x{len(ops)}', same_mapping(rng, forms)))
    return ops


FIXED = [
    # depth-first blending, a mapping and a scalar under one key, both ways
    [('new', [('a', {'x': {'y': 1, 'z': 2}, 'w': 1}), ('b', {'x': {'y': 3}}), ('c', {'w': {'q': 1}})], None)],
    [('new', [('a', {'x': {'y': 1}}), ('b', {'x': 5})], None)],
    [('new', [('a', {'x': 5}), ('b', {'x': {'z': 1}})], None)],
    # keys that are not strings, beside a string key that looks like their variant
    [('new', [('a', {1: 'a', 'k': {2: 'b'}}), ('b', {1: 'c', '1_env': 'V', 'k': {'2_eval': 'echo'}})], None)],
    # one name, the same two variants in every layer; a lone variant in one layer
    [('new', [('a', {'t': 1, 't_env': 'V'}), ('b', {'t': 2, 't_env': 'W', 'u_eval': 'echo u'})], None)],
    # update with a one-shot iterable of pairs, keywords, a mapping
    [('new', [('a', {'x': 1})], None), ('update_iter', {'y': 2}), ('update_kw', {'z': 3}),
     ('update', {'x': {'n': 1}})],
    # attribute assignment: a present name, a name with no variant present
    [('new', [('a', {'x': 1, 'token_env': 'V'})], None), ('setattr_present', 'x', 2),
     ('setattr_present', 'token_env', 'W'), ('setattr_fresh', 'fresh', 3)],
    # a layer added after an in-place change
    [('new', [('a', {'x': {'y': 1}})], None), ('update', {'x': {'y': 2}}), ('extend', 'late', {'x': 5})],
    # item assignment and del bypass `_`
    [('new', [('a', {'x': 1, 'w': 2})], None), ('delitem', 'x'), ('setitem', 'w', {'q': 1})],
    # Configuration(_=...)
    [('new', [('a', {'x': 1})], {'q': 3})],
]

NS_FIXED = [
    ({'t': 1}, {'t_env': 'V'}),
    ({'s': {'t': 1}}, {'s': {'t_eval': 'echo t'}}),
    ({'t_env': 'V', 'u': {'v': 1}}, {'t': 2, 'u': 3}),
]


def build(op, cfg):
    from cmdkit.config import Configuration
    from cmdkit.namespace import Namespace
    kind = op[0]
    if kind == 'new':
        layers = {label: Namespace(mapping) for label, mapping in op[1]}
        if op[2] is not None:
            layers['_'] = Namespace(op[2])
        return Configuration(**layers)
    if kind == 'extend':
        cfg.extend(**{op[1]: Namespace(op[2])})
    elif kind == 'extend_many':
        cfg.extend(**{label: Namespace(mapping) for label, mapping in op[1]})
    elif kind == 'update':
        cfg.update(op[1])
    elif kind == 'update_iter':
        cfg.update(iter(list(op[1].items())))
    elif kind == 'update_kw':
        cfg.update(**op[1])
    elif kind in ('setattr_present', 'setattr_fresh', 'setattr'):
        setattr(cfg, op[1], op[2])
    elif kind == 'setitem':
        cfg[op[1]] = op[2]
    elif kind == 'delitem':
        del cfg[op[1]]
    elif kind == 'delitem_present':
        if cfg:
            del cfg[next(iter(cfg))]
    return cfg


def observe_same(cfg, tag: str, lines: list) -> None:
    STATE['phase'] = 'read'
    sources = [cfg.namespaces[label] for label in cfg.namespaces] + [cfg.local, cfg]
    paths = {p for source in sources for p in paths_of(source)}
    paths |= {p + ('absent',) for p in list(paths)} | {('absent',)}
    lines.append(f'{tag} repr {cfg!r}')
    lines.append(f'{tag} merged {dict(cfg)!r}')
    lines.append(f'{tag} attrs {sorted((k, repr(v)) for k, v in vars(cfg).items())!r}')
    for path in sorted(paths, key=repr):
        lines.append(f'{tag} which {path!r} {attempt(lambda: cfg.which(*path))}')
        lines.append(f'{tag} item {path!r} {attempt(lambda: lookup(cfg, path))}')
    lines.append(f'{tag} which unhashable {attempt(lambda: cfg.which(["x"]))}')
    leaves = sorted({p[-1] for p in paths}, key=repr)
    for leaf in leaves:
        lines.append(f'{tag} whereis {leaf!r} {attempt(lambda: cfg.whereis(leaf))}')
    lines.append(f'{tag} duplicates {attempt(cfg.duplicates)}')
    lines.append(f'{tag} calls {CALLS!r}')
    CALLS.clear()
    STATE['phase'] = 'attr'
    names = set()
    for key in list(cfg):
        if isinstance(key, str):
            names |= {key, key.rsplit('_', 1)[0]}
    for name in sorted(names):
        lines.append(f'{tag} attr {name} {attempt(lambda: getattr(cfg, name))}')
        value = cfg.get(name)
        if isinstance(value, dict):
            for sub in sorted(k for k in value if isinstance(k, str)):
                for nm in sorted({sub, sub.rsplit('_', 1)[0]}):
                    lines.append(f'{tag} attr {name}.{nm} {attempt(lambda: getattr(getattr(cfg, name), nm))}')
    lines.append(f'{tag} attr-calls {CALLS!r}')
    CALLS.clear()


def run_same() -> dict:
    from cmdkit.namespace import Namespace
    out = {}
    scripts = [(f'fixed-{i}', ops) for i, ops in enumerate(FIXED)]
    scripts += [(f'random-{seed}', same_ops(seed)) for seed in range(SAME_RANDOM)]
    for sid, ops in scripts:
        lines, cfg = [], None
        for step, op in enumerate(ops):
            STATE['phase'] = 'build'
            result = attempt(lambda: build(op, cfg))
            if op[0] == 'new':
                cfg = build(op, None) if result.startswith('ok') else None
            shown = result[:2] if op[0] == 'new' else result
            lines.append(f'{step} {op[0]} {shown}')
            if cfg is None:
                break
            observe_same(cfg, str(step), lines)
        out[sid] = lines
    for i, (first, second) in enumerate(NS_FIXED):
        lines = []
        STATE['phase'] = 'build'
        ns = Namespace(first)
        ns.update(second)
        lines.append(f'repr {ns!r}')
        STATE['phase'] = 'attr'
        for name in ('t', 't_env', 't_eval', 's', 'u'):
            lines.append(f'attr {name} {attempt(lambda: getattr(ns, name))}')
            if isinstance(ns.get(name), dict):
                lines.append(f'attr {name}.t {attempt(lambda: getattr(getattr(ns, name), "t"))}')
        lines.append(f'calls {CALLS!r}')
        CALLS.clear()
        out[f'namespace-{i}'] = lines
    return out


# ---------------------------------------------------------------- the `model` corpus

MODEL_KEYS = ['a', 'a_env', 'a_eval', 'b', 'b_env', 'b_eval', 'a_env_eval', 7]
SETTABLE = ['a', 'a_env', 'a_eval', 'b', 'b_env', 'a_env_eval', 'fresh']


def names_of(key) -> set:
    """The names `key` is a variant of: itself, and the name without its suffix."""
    if not isinstance(key, str):
        return set()
    names = {key}
    for suffix in ('_env', '_eval'):
        if key.endswith(suffix):
            names.add(key[:-len(suffix)])
    return names


def fold(original: dict, new: dict, events: list = None, prefix: tuple = ()) -> dict:
    """
    The model: apply `new` over `original`, both plain dicts, returning a new dict. When `events`
    is a list, the path of every key dropped or replaced wholesale is appended to it.
    """
    decided = set()
    for key in new:
        decided |= names_of(key)
    out = {k: v for k, v in original.items() if k in new or not (names_of(k) & decided)}
    if events is not None:
        events.extend(prefix + (k,) for k in original if k not in out)
    for key, value in new.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = fold(out[key], value, events, prefix + (key,))
        else:
            if events is not None and key in out:
                events.append(prefix + (key,))
            out[key] = copy.deepcopy(value)
    return out


def model_value(rng: random.Random, depth: int):
    r = rng.random()
    if depth < 2 and r < 0.4:
        return model_mapping(rng, depth + 1)
    if r < 0.7:
        return rng.randint(0, 9)
    return rng.choice(['x', 'echo v'])


def model_mapping(rng: random.Random, depth: int = 0) -> dict:
    return {key: model_value(rng, depth) for key in rng.sample(MODEL_KEYS, rng.randint(1, 4))}


def model_ops(seed: int, phase: str) -> list:
    rng = random.Random(10_000 + seed)
    layers = [(f'l{i}', model_mapping(rng)) for i in range(rng.randint(2, 4))]
    first = rng.randint(1, len(layers))
    ops = [('new', layers[:first], None)]
    rest = layers[first:]
    while rest:
        take = rng.randint(1, min(2, len(rest)))
        ops.append(('extend_many', rest[:take]))
        rest = rest[take:]
    if phase == 'P2':
        for _ in range(rng.randint(0, 3)):
            r = rng.random()
            if r < 0.3:
                ops.append(('update', model_mapping(rng)))
            elif r < 0.45:
                ops.append(('update_kw', {k: v for k, v in model_mapping(rng).items() if isinstance(k, str)}))
            elif r < 0.55:
                ops.append(('update_iter', model_mapping(rng)))
            else:
                ops.append(('setattr', rng.choice(SETTABLE), model_value(rng, 1)))
    return ops


def expected_attr(merged: dict, name: str):
    present = [k for k in (name, f'{name}_env', f'{name}_eval') if k in merged]
    if not present:
        return ('error', f"AttributeError: '{name}' not found")
    if len(present) > 1:
        return ('error', f"AttributeError: '{name}' has more than one variant")
    key, value = present[0], merged[present[0]]
    if key == name:
        return ('value', value)
    if isinstance(value, dict):
        return None
    if key.endswith('_env'):
        return ('value', f'ENV[{value}]')
    return ('value', f'EVAL[{value}]')


def check_model(ops: list) -> list:
    problems = []
    cfg = None
    merged, local, attrs = {}, {}, {}
    sources, stale, desync = [], [], []
    for step, op in enumerate(ops):
        STATE['phase'] = 'build'
        before = copy.deepcopy(op)
        try:
            cfg = build(op, cfg)
        except Exception as exc:
            problems.append(f'{step} {op[0]} raised {type(exc).__name__}: {exc}')
            return problems
        if op[0] in ('new', 'extend_many'):
            for label, mapping in op[1]:
                merged = fold(merged, mapping)
                sources.append((label, mapping))
        elif op[0] in ('update', 'update_kw'):
            merged, local = fold(merged, op[1], stale), fold(local, op[1])
        elif op[0] == 'update_iter':
            # a one-shot iterable reaches `_` only, as today: `_` and the merged view part ways
            local = fold(local, op[1], desync)
            desync.extend(paths_of(op[1]))
        elif op[0] == 'setattr':
            name, value = op[1], op[2]
            if any(names_of(k) & names_of(name) for k in merged):
                merged, local = fold(merged, {name: value}, stale), fold(local, {name: value})
            else:
                attrs[name] = value
        if op != before:
            problems.append(f'{step} {op[0]} changed its input')
        STATE['phase'] = 'read'
        if plain(dict(cfg)) != merged:
            problems.append(f'{step} merged {plain(dict(cfg))!r} != model {merged!r}')
        if plain(dict(cfg.local)) != local:
            problems.append(f'{step} _ {plain(dict(cfg.local))!r} != model {local!r}')
        mine = {k: v for k, v in vars(cfg).items() if k not in ('local', 'namespaces')}
        if mine != attrs:
            problems.append(f'{step} instance attributes {mine!r} != model {attrs!r}')
        for label, mapping in sources:
            if cfg.namespaces[label] != mapping:
                problems.append(f'{step} layer {label} changed')
        order = sources + ([('_', local)] if local else [])
        paths = {p for _, m in order for p in paths_of(m)} | set(paths_of(merged))
        for path in sorted(paths, key=repr):
            try:
                want = ('value', model_lookup(merged, path))
            except (KeyError, TypeError) as exc:
                want = ('error', failure(exc))
            try:
                got = ('value', plain(lookup(cfg, path)))
            except (KeyError, TypeError, IndexError) as exc:
                got = ('error', failure(exc))
            if got != want:
                problems.append(f'{step} item {path!r} {got!r} != model {want!r}')
            holders = [label for label, m in order if _holds(m, path)]
            try:
                which = ('value', cfg.which(*path))
            except (KeyError, TypeError, IndexError) as exc:
                which = ('error', failure(exc))
            apart = any(path[:n] in desync for n in range(1, len(path) + 1))
            excused = apart or any(path[:n] in stale for n in range(1, len(path) + 1))
            if want[0] == 'value':
                if apart:
                    pass
                elif not holders:
                    problems.append(f'{step} item {path!r}: the model holds it, no source does')
                elif which != ('value', holders[-1]):
                    problems.append(f'{step} which {path!r} {which!r} != model {holders[-1]!r}')
            elif want == ('error', 'KeyError') and model_displaced(order, path) and which != want:
                problems.append(f'{step} which {path!r} {which!r} != model KeyError (displaced)')
            elif which[0] != 'error' and not excused:
                problems.append(f'{step} which {path!r} {which!r}: the merged view holds no such path')
        if any(phase != 'attr' for phase, *_ in CALLS):
            problems.append(f'{step} expanded outside attribute access: {CALLS!r}')
        CALLS.clear()
        STATE['phase'] = 'attr'
        for name in sorted({n for k in merged for n in names_of(k)} - set(attrs)):
            want = expected_attr(merged, name)
            if want is None:
                continue
            try:
                got = ('value', plain(getattr(cfg, name)))
            except AttributeError as exc:
                got = ('error', f'AttributeError: {exc}')
            if got != want:
                problems.append(f'{step} attr {name} {got!r} != model {want!r}')
        CALLS.clear()
    return problems


def model_displaced(order: list, path: tuple) -> bool:
    """A source sets a different variant of a key on `path`, at its prefix, above one holding `path`."""
    for low, (_, lower) in enumerate(order):
        if not _holds(lower, path):
            continue
        for _, upper in order[low + 1:]:
            for i in range(len(path)):
                try:
                    parent = model_lookup(upper, path[:i])
                except (KeyError, TypeError):
                    continue
                if isinstance(parent, dict) and path[i] not in parent \
                        and any(names_of(k) & names_of(path[i]) for k in parent):
                    return True
    return False


def _holds(mapping, path) -> bool:
    try:
        model_lookup(mapping, path)
        return True
    except (KeyError, TypeError):
        return False


def run_model(phase: str) -> dict:
    return {f'model-{seed}': check_model(model_ops(seed, phase)) for seed in range(MODEL_RANDOM)}


# ---------------------------------------------------------------- entry points

def run(phase: str) -> None:
    subprocess.check_output = spy_check_output
    os.getenv = spy_getenv
    import cmdkit.config  # noqa: F401  (imported under the spies)
    CALLS.clear()
    json.dump({'phase': phase, 'same': run_same(), 'model': run_model(phase)}, sys.stdout)


def compare(phase: str, base_path: str, head_path: str) -> None:
    with open(base_path) as stream:
        base = json.load(stream)
    with open(head_path) as stream:
        head = json.load(stream)
    failures = []
    if base['phase'] != phase or head['phase'] != phase:
        failures.append('the runs are not for this phase')
    if sorted(base['same']) != sorted(head['same']):
        failures.append('the runs hold different `same` scenarios')
    for sid in sorted(base['same']):
        old, new = base['same'][sid], head['same'].get(sid, [])
        if old != new:
            diff = next((f'base: {a}\n        head: {b}' for a, b in zip(old, new) if a != b),
                        f'{len(old)} lines on the base, {len(new)} on the index')
            failures.append(f'{sid} differs from the base:\n        {diff}')
    bad = {sid: problems for sid, problems in head['model'].items() if problems}
    for sid, problems in sorted(bad.items())[:20]:
        failures.append(f'{sid}: {problems[0]}' + (f' (+{len(problems) - 1} more)' if len(problems) > 1 else ''))
    if bad:
        failures.append(f'{len(bad)} of {len(head["model"])} model scenarios fail on the index')
    bites = sum(1 for problems in base['model'].values() if problems)
    if bites * 2 < len(base['model']):
        failures.append(f'only {bites} of {len(base["model"])} model scenarios fail on the base: '
                        f'the corpus does not bite')
    for msg in failures[:40]:
        print('FAIL:', msg)
    if failures:
        sys.exit(1)
    print(f'ok drive {phase}: {len(head["same"])} scenarios as on the base, '
          f'{len(head["model"])} model scenarios hold ({bites} fail on the base)')


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == 'run' and sys.argv[2] in ('P1', 'P2'):
        run(sys.argv[2])
    elif len(sys.argv) == 5 and sys.argv[1] == 'compare' and sys.argv[2] in ('P1', 'P2'):
        compare(*sys.argv[2:])
    else:
        print('usage: drive.py run P1|P2 | compare P1|P2 BASE.json HEAD.json')
        sys.exit(2)


if __name__ == '__main__':
    main()
