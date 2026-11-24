// Contract tests for the client console: slot shape and the lexicon card.
// The bundle evaluates through window.__ModuleLoader__, so the test loads
// client.js with a stub loader and a stub React (no DOM needed).
import assert from 'node:assert/strict';
import { test } from 'node:test';

let factory = null;
const slotted = [];

globalThis.window = {
  __ModuleLoader__: { load(spec) { factory = spec.factory; } },
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() {},
};
globalThis.document = { hidden: false, addEventListener() {}, removeEventListener() {} };
globalThis.localStorage = { getItem: () => null, setItem() {} };
globalThis.CustomEvent = class CustomEvent {
  constructor(type, init) { this.type = type; this.detail = init && init.detail; }
};

const React = {
  useState(init) { return [init, () => {}]; },
  useEffect(fn) { fn(); return undefined; },
  useRef(init) { return { current: init }; },
  useMemo(fn) { return fn(); },
  useCallback(fn) { return fn; },
  createElement(type, props, ...children) {
    return { type, props: props || {}, children };
  },
};

await import('../client.js');
const app = factory((name) => (name === 'react' ? React : undefined));

function texts(node, out = []) {
  if (node == null || typeof node === 'boolean') return out;
  if (typeof node === 'string' || typeof node === 'number') {
    out.push(String(node));
    return out;
  }
  if (Array.isArray(node)) {
    node.forEach((n) => texts(n, out));
    return out;
  }
  (node.children || []).forEach((n) => texts(n, out));
  return out;
}

test('the module exposes slots and registers the four views', () => {
  assert.deepEqual(app.inject, ['slots']);
  const ctx = {
    slots: {
      inject(name, fn) { fn(); },
      register(spec, component) { slotted.push({ spec, component }); },
    },
  };
  app.apply(ctx);
  const ids = slotted.map((row) => row.spec.id).sort();
  assert.deepEqual(ids, [
    'socratic-lexicon', 'socratic-panel', 'socratic-policy', 'socratic-turn-citations',
  ]);
  for (const row of slotted) {
    assert.equal(typeof row.component, 'function', row.spec.id);
  }
  const lexicon = slotted.find((row) => row.spec.id === 'socratic-lexicon');
  assert.equal(lexicon.spec.order, 220);
});

test('the lexicon card renders closed by default', () => {
  const lexicon = slotted.find((row) => row.spec.id === 'socratic-lexicon').component;
  const text = texts(lexicon({})).join(' ');
  assert.ok(text.includes('词条'), 'missing chip');
  assert.ok(text.includes('查词'), 'missing hint');
});

test('the panel and policy cards render their closed chips', () => {
  const panel = slotted.find((row) => row.spec.id === 'socratic-panel').component;
  const policy = slotted.find((row) => row.spec.id === 'socratic-policy').component;
  assert.ok(texts(panel({})).join(' ').includes('教学台'));
  assert.ok(texts(policy({})).join(' ').includes('策略'));
});

test('the turn tail renders nothing without citations', () => {
  const turn = slotted.find((row) => row.spec.id === 'socratic-turn-citations').component;
  assert.equal(turn({}), null);
});
