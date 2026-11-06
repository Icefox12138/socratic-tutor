window.__ModuleLoader__.load({
  id: 'dsh-socratic',
  factory(require) {
    const React = require('react');
    const h = React.createElement;

    function useSocratic(sessionId, open) {
      const [state, setState] = React.useState(null);
      const [citations, setCitations] = React.useState([]);
      const [error, setError] = React.useState('');
      const misses = React.useRef(0);
      React.useEffect(() => {
        if (!open || !sessionId) return undefined;
        let alive = true;
        const base = localStorage.getItem('socratic_sidecar') || 'http://127.0.0.1:8765';
        // 404 是正常答案（sidecar 还没有这个会话的状态）；其余非 ok 才算该端点失败。
        const getJson = async (url) => {
          const res = await fetch(url, { cache: 'no-store' });
          if (res.status === 404) return { notFound: true };
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        };
        const load = async () => {
          // 两个端点各自成败：一个失败不该把另一个的结果也丢掉。
          const [s, c] = await Promise.allSettled([
            getJson(base + '/v1/state/' + encodeURIComponent(sessionId)),
            getJson(base + '/v1/citations/' + encodeURIComponent(sessionId) + '?limit=8'),
          ]);
          if (!alive) return;
          if (s.status === 'fulfilled') setState(s.value.notFound ? null : s.value);
          if (c.status === 'fulfilled') setCitations((c.value && c.value.citations) || []);
          const failed = [s, c].filter((r) => r.status === 'rejected');
          if (!failed.length) { misses.current = 0; setError(''); return; }
          // 偶发一次多半是连接层的瞬断；连续两次才提示，且保留上一次数据。
          misses.current += 1;
          if (misses.current >= 2) {
            const why = failed[0].reason;
            const name = (why && why.name) || 'Error';
            const text = (why && why.message) || String(why);
            const where = (typeof location !== 'undefined' ? location.origin : '?') + ' → ' + base;
            setError(name + ': ' + text
              + '（已连续 ' + misses.current + ' 次；' + where + '）');
          }
        };
        const tick = () => {
          // 后台标签页不必轮询；回到前台会立刻补一次。
          if (typeof document !== 'undefined' && document.hidden) return;
          load();
        };
        load();
        const timer = setInterval(tick, 15000);
        const onVisible = () => { if (!document.hidden) load(); };
        document.addEventListener('visibilitychange', onVisible);
        return () => {
          alive = false;
          clearInterval(timer);
          document.removeEventListener('visibilitychange', onVisible);
        };
      }, [sessionId, open]);
      return { state, citations, error };
    }

    function Panel(props) {
      const hookId = props.useSession
        ? props.useSession((s) => s && (s.id || s.sessionId))
        : undefined;
      const sessionId = props.sessionId || hookId
        || (typeof localStorage !== 'undefined' ? localStorage.getItem('socratic_session') : '')
        || '';
      const [open, setOpen] = React.useState(false);
      const [img, setImg] = React.useState('');
      const { state, citations, error } = useSocratic(sessionId, open);
      const base = (typeof localStorage !== 'undefined' && localStorage.getItem('socratic_sidecar'))
        || 'http://127.0.0.1:8765';
      const st = state && state.state ? state.state : null;
      const level = st ? (st.mastery < 0.35 ? '未掌握' : st.mastery <= 0.75 ? '在学' : '已掌握') : '—';

      const chip = {
        display: 'inline-flex', alignItems: 'center', gap: 6,
        border: '1px solid rgba(127,127,127,.35)', borderRadius: 8,
        padding: '4px 8px', fontSize: 12, cursor: 'pointer',
        background: 'rgba(127,127,127,.06)', color: 'inherit',
      };
      const box = {
        marginTop: 6, border: '1px solid rgba(127,127,127,.3)', borderRadius: 10,
        padding: 10, fontSize: 12, background: 'rgba(127,127,127,.04)',
        maxHeight: 300, overflow: 'auto',
      };
      const row = { display: 'flex', justifyContent: 'space-between', gap: 8, margin: '2px 0' };
      const link = { color: 'inherit', textDecoration: 'underline', cursor: 'pointer' };

      return h('div', { style: { margin: '4px 0' } },
        h('div', { style: { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' } },
          h('button', { style: chip, onClick: () => setOpen(!open), title: '苏格拉底教学台' },
            '教学台', st ? ' · ' + st.phase : '', open ? ' ▾' : ' ▸'),
          h('span', { style: { fontSize: 11, opacity: 0.65 } },
            '引用卡 / 提示级别 / 页图'),
        ),
        open && h('div', { style: box },
          error && h('div', { style: { color: '#b42318' } }, 'sidecar: ' + error),
          !sessionId && h('div', { style: { opacity: 0.7 } }, '当前会话没有 sessionId，无法读取状态。'),
          sessionId && !st && !error && h('div', { style: { opacity: 0.7 } },
            'sidecar 里还没有这个会话的状态；先让导师调用 socratic_init。'),
          st && h('div', null,
            h('div', { style: row }, h('span', null, '阶段'), h('b', null, st.phase)),
            h('div', { style: row }, h('span', null, '概念'), h('b', null, st.concept || '未设定')),
            h('div', { style: row }, h('span', null, '提示'), h('b', null, 'L' + (st.hint_level || 0))),
            h('div', { style: row }, h('span', null, '尝试/连对'),
              h('b', null, (st.attempts || 0) + ' / ' + (st.correct_streak || 0))),
            h('div', { style: row }, h('span', null, '掌握'), h('b', null, level)),
          ),
          h('div', { style: { marginTop: 8, fontWeight: 600 } }, '最近引用'),
          !citations.length && h('div', { style: { opacity: 0.65 } }, '还没有引用；让导师调用 kb_search。'),
          citations.map((c) => h('div', {
            key: c.id,
            style: { borderTop: '1px dashed rgba(127,127,127,.25)', padding: '6px 0' },
          },
            h('div', { style: { fontWeight: 600, wordBreak: 'break-all' } }, c.locator || ''),
            c.url && h('a', {
              style: link, href: c.url, target: '_blank', rel: 'noreferrer',
            }, '原文 ↗'),
            h('div', { style: { opacity: 0.75, margin: '2px 0' } },
              (c.snippet || '').slice(0, 120)),
            c.page_image && h('span', { style: link, onClick: () => setImg(c.page_image) }, '查看页图'),
          )),
          h('div', { style: { marginTop: 8 } },
            h('a', {
              style: link,
              href: base + '/ui?session=' + encodeURIComponent(sessionId),
              target: '_blank', rel: 'noreferrer',
            }, '打开完整教学台 ↗'),
          ),
        ),
        img && h('div', {
          style: { position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,.62)',
            display: 'flex', alignItems: 'center', justifyContent: 'center' },
          onClick: () => setImg(''),
        },
          h('img', { src: base + img, style: { maxWidth: '92vw', maxHeight: '88vh', background: '#fff' } }),
        ),
      );
    }

    function TurnCitations(props) {
      const turn = props.turn && typeof props.turn === 'object' ? props.turn.turn : props.turn;
      const hookId = props.useSession
        ? props.useSession((s) => s && (s.id || s.sessionId))
        : undefined;
      const sessionId = props.sessionId || hookId
        || (typeof localStorage !== 'undefined' ? localStorage.getItem('socratic_session') : '')
        || '';
      const [items, setItems] = React.useState([]);
      const [img, setImg] = React.useState('');
      const base = (typeof localStorage !== 'undefined' && localStorage.getItem('socratic_sidecar'))
        || 'http://127.0.0.1:8765';
      React.useEffect(() => {
        if (!sessionId || turn == null) return undefined;
        let alive = true;
        const url = base + '/v1/citations/' + encodeURIComponent(sessionId)
          + '?turn=' + encodeURIComponent(turn);
        const pull = (attempt) => {
          fetch(url, { cache: 'no-store' })
            .then((r) => r.ok ? r.json() : { citations: [] })
            .then((d) => { if (alive) setItems(d.citations || []); })
            .catch(() => {
              // 连接层瞬断值得一次安静的重试；两次都失败就按"本轮无引用"处理。
              if (alive && attempt === 0) setTimeout(() => { if (alive) pull(1); }, 1500);
            });
        };
        pull(0);
        return () => { alive = false; };
      }, [sessionId, turn]);
      if (!items.length) return null;
      return h('div', {
        style: { margin: '8px 0 2px', borderTop: '1px solid rgba(127,127,127,.22)', paddingTop: 6 },
      },
        h('div', { style: { fontSize: 11, opacity: 0.65, marginBottom: 4 } }, '本轮引用'),
        items.map((c) => {
          const greek = c.lang === 'greek';
          const pageOnly = c.lang === 'page';
          return h('div', {
            key: c.id,
            style: { display: 'flex', gap: 8, alignItems: 'center', fontSize: 12,
              padding: '2px 0', flexWrap: 'wrap' },
          },
            h('span', { style: { fontWeight: 600, wordBreak: 'break-all' } }, c.locator || ''),
            c.url && h('a', {
              style: { color: 'inherit', textDecoration: 'underline' },
              href: c.url, target: '_blank', rel: 'noreferrer',
            }, '原文 ↗'),
            pageOnly
              ? h('span', { style: { opacity: 0.75 } }, '扫描本：章回页图')
              : (greek
                ? h('span', { style: { opacity: 0.75 } }, '希腊原文：OCR 不可用，仅页图')
                : h('span', { style: { opacity: 0.7 } }, (c.snippet || '').slice(0, 80))),
            pageOnly && c.page_image && c.book
              ? h('a', {
                style: { color: 'inherit', textDecoration: 'underline', cursor: 'pointer' },
                onClick: () => {
                  window.open(base + '/browse?book=' + encodeURIComponent(c.book)
                    + '&page=' + encodeURIComponent(c.page), '_blank', 'noreferrer');
                },
              }, '打开章回 ↗')
              : null,
            (greek || pageOnly) && c.page_image
              ? h('img', {
                src: base + c.page_image,
                style: { maxHeight: 120, maxWidth: 240, cursor: 'zoom-in',
                  border: '1px solid rgba(127,127,127,.3)', background: '#fff' },
                onClick: () => setImg(c.page_image),
              })
              : c.page_image && h('a', {
                style: { color: 'inherit', textDecoration: 'underline', cursor: 'pointer' },
                onClick: () => setImg(c.page_image),
              }, '页图'),
          );
        }),
        img && h('div', {
          style: { position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,.62)',
            display: 'flex', alignItems: 'center', justifyContent: 'center' },
          onClick: () => setImg(''),
        }, h('img', { src: base + img, style: { maxWidth: '92vw', maxHeight: '88vh', background: '#fff' } })),
      );
    }

    // PolicyCard: read-only diagnostics over /v1/policy and /v1/channels.
    // Answers "why did this citation come from that source" — the sidecar side
    // of that question already exists (M0/M1); this is only the view.
    function PolicyCard() {
      const [open, setOpen] = React.useState(false);
      const [data, setData] = React.useState(null);
      const [error, setError] = React.useState('');
      const [busy, setBusy] = React.useState(false);
      const base = (typeof localStorage !== 'undefined' && localStorage.getItem('socratic_sidecar'))
        || 'http://127.0.0.1:8765';

      const getJson = async (url) => {
        const res = await fetch(url, { cache: 'no-store' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      };

      const load = async () => {
        setBusy(true);
        const [p, c] = await Promise.allSettled([
          getJson(base + '/v1/policy'),
          getJson(base + '/v1/channels'),
        ]);
        setBusy(false);
        if (p.status === 'rejected' && c.status === 'rejected') {
          setError(String((p.reason && p.reason.message) || p.reason));
          return;
        }
        setError('');
        setData({
          policy: p.status === 'fulfilled' ? p.value : null,
          channels: c.status === 'fulfilled' ? (c.value.channels || []) : [],
        });
      };

      React.useEffect(() => {
        if (open && !data && !busy) load();
      }, [open]);

      const chip = {
        display: 'inline-flex', alignItems: 'center', gap: 6,
        border: '1px solid rgba(127,127,127,.35)', borderRadius: 8,
        padding: '4px 8px', fontSize: 12, cursor: 'pointer',
        background: 'rgba(127,127,127,.06)', color: 'inherit',
      };
      const box = {
        marginTop: 6, border: '1px solid rgba(127,127,127,.3)', borderRadius: 10,
        padding: 10, fontSize: 12, background: 'rgba(127,127,127,.04)',
        maxHeight: 320, overflow: 'auto',
      };
      const row = { display: 'flex', justifyContent: 'space-between', gap: 8, margin: '2px 0' };
      const th = { opacity: 0.6, fontWeight: 600 };
      const policy = data && data.policy;
      const channels = (data && data.channels) || [];
      const dot = (a) => (a === 'ready' ? '#12b76a' : a === 'missing' ? '#b42318' : '#98a2b3');
      const parts = policy && policy.enforced_parts
        ? Object.keys(policy.enforced_parts).map((k) => (
          policy.enforced_parts[k] ? k : k + '(未开)')).join(' · ')
        : '';

      return h('div', { style: { margin: '4px 0' } },
        h('div', { style: { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' } },
          h('button', { style: chip, title: '引用策略与语料通道（只读）',
            onClick: () => setOpen(!open) },
            '策略', policy && policy.policy_version ? ' · v' + policy.policy_version : '',
            open ? ' ▾' : ' ▸'),
          h('span', { style: { fontSize: 11, opacity: 0.65 } }, '来源 / 通道 / 生效范围'),
        ),
        open && h('div', { style: box },
          error && h('div', { style: { color: '#b42318' } }, 'sidecar: ' + error),
          busy && !policy && h('div', { style: { opacity: 0.7 } }, '读取中…'),
          policy && !policy.enforced && h('div', { style: { opacity: 0.75, marginBottom: 6 } },
            '排序尚未由策略接管（' + parts + '）'),
          policy && policy.last_reload_error && h('div', { style: { color: '#b42318' } },
            '上次重载失败：' + policy.last_reload_error),
          policy && h('div', null,
            h('div', { style: { marginTop: 6, fontWeight: 600 } }, '源'),
            Object.keys(policy.sources || {}).map((sid) => {
              const s = policy.sources[sid] || {};
              return h('div', { key: 's-' + sid, style: row },
                h('span', { style: { wordBreak: 'break-all' } }, sid),
                h('b', null, (s.tier || '—') + (s.tier_estimated ? '*' : '')
                  + ' · ' + (s.role || '?')),
              );
            }),
            h('div', { style: { marginTop: 8, fontWeight: 600 } }, '通道'),
            h('div', { style: { ...row, ...th } },
              h('span', null, 'kind'), h('span', null, '状态')),
            channels.map((c, i) => h('div', { key: 'c-' + i, style: row },
              h('span', { style: { display: 'inline-flex', gap: 6, alignItems: 'center' } },
                h('span', { style: { width: 8, height: 8, borderRadius: 4,
                  background: dot(c.availability) } }),
                c.source + ' · ' + c.kind),
              h('span', { style: { opacity: 0.8 } },
                c.availability + (c.in_use ? ' · 在用' : '')),
            )),
            h('div', { style: { marginTop: 8 } },
              h('a', { style: { color: 'inherit', textDecoration: 'underline', cursor: 'pointer' },
                onClick: () => { setData(null); load(); } }, busy ? '刷新中…' : '刷新'),
            ),
          ),
          !policy && !error && !busy && h('div', { style: { opacity: 0.7 } },
            'sidecar 未返回策略；确认它已在 8765 运行。'),
        ),
      );
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        ctx.slots.inject('conversation.composer.dock', () => ctx.slots.register({
          name: 'conversation.composer.dock',
          id: 'socratic-panel',
          order: 200,
        }, Panel));
        ctx.slots.inject('conversation.composer.dock', () => ctx.slots.register({
          name: 'conversation.composer.dock',
          id: 'socratic-policy',
          order: 210,
        }, PolicyCard));
        ctx.slots.inject('conversation.chat.turnTail', () => ctx.slots.register({
          name: 'conversation.chat.turnTail',
          id: 'socratic-turn-citations',
          order: 300,
        }, TurnCitations));
      },
    };
  },
});
