window.__ModuleLoader__.load({
  id: 'dsh-socratic',
  factory(require) {
    const React = require('react');
    const h = React.createElement;

    function useSocratic(sessionId, open) {
      const [state, setState] = React.useState(null);
      const [citations, setCitations] = React.useState([]);
      const [error, setError] = React.useState('');
      React.useEffect(() => {
        if (!open || !sessionId) return undefined;
        let alive = true;
        const base = localStorage.getItem('socratic_sidecar') || 'http://127.0.0.1:8765';
        const load = async () => {
          try {
            const [s, c] = await Promise.all([
              fetch(base + '/v1/state/' + encodeURIComponent(sessionId)),
              fetch(base + '/v1/citations/' + encodeURIComponent(sessionId) + '?limit=8'),
            ]);
            if (!alive) return;
            if (s.ok) setState(await s.json());
            else if (s.status === 404) setState(null);
            if (c.ok) setCitations((await c.json()).citations || []);
            setError('');
          } catch (e) {
            if (alive) setError(String(e && e.message || e));
          }
        };
        load();
        const timer = setInterval(load, 5000);
        return () => { alive = false; clearInterval(timer); };
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
        fetch(base + '/v1/citations/' + encodeURIComponent(sessionId) + '?turn=' + encodeURIComponent(turn))
          .then((r) => r.ok ? r.json() : { citations: [] })
          .then((d) => { if (alive) setItems(d.citations || []); })
          .catch(() => {});
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

    return {
      inject: ['slots'],
      apply(ctx) {
        ctx.slots.inject('conversation.composer.dock', () => ctx.slots.register({
          name: 'conversation.composer.dock',
          id: 'socratic-panel',
          order: 200,
        }, Panel));
        ctx.slots.inject('conversation.chat.turnTail', () => ctx.slots.register({
          name: 'conversation.chat.turnTail',
          id: 'socratic-turn-citations',
          order: 300,
        }, TurnCitations));
      },
    };
  },
});
