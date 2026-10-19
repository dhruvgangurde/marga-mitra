/* MargaMitra Design System: component source, for reference only (not imported by the app).
   web/src/ui/*.tsx rebuild these components with the props in index.d.ts and exactly this DOM and these class names.
   Icons: the design system inlines Phosphor Bold paths as ICONS; the app uses @phosphor-icons/react with weight="bold" instead. */
(function () {
  var React = window.React;
  var h = React.createElement;
  var ICONS = {}; // Phosphor Bold paths, omitted here

  function cx() { return Array.prototype.slice.call(arguments).filter(Boolean).join(' '); }

  // Phosphor Bold icon by short name, inheriting currentColor.
  function Icon(props) {
    var d = ICONS[props.name];
    if (!d) return null;
    return h('svg', { className: cx('mm-icon', props.className), viewBox: d.vb, width: props.size || 20, height: props.size || 20, fill: 'currentColor', 'aria-hidden': props.label ? undefined : 'true', role: props.label ? 'img' : undefined, 'aria-label': props.label, dangerouslySetInnerHTML: { __html: d.inner } });
  }

  // The scalloped edge shared by seals and the arrow badge on primary buttons.
  function scallopPath(size, bumps, inset) {
    var c = size / 2, R = size / 2 - inset, r = R * Math.sin(Math.PI / bumps) * 1.12, d = '';
    for (var i = 0; i < bumps; i++) {
      var a0 = (i / bumps) * Math.PI * 2 - Math.PI / bumps, a1 = a0 + (2 * Math.PI) / bumps;
      var p0 = [c + R * Math.cos(a0), c + R * Math.sin(a0)], p1 = [c + R * Math.cos(a1), c + R * Math.sin(a1)];
      if (i === 0) d += 'M' + p0[0].toFixed(2) + ' ' + p0[1].toFixed(2) + ' ';
      d += 'A' + r.toFixed(2) + ' ' + r.toFixed(2) + ' 0 0 1 ' + p1[0].toFixed(2) + ' ' + p1[1].toFixed(2) + ' ';
    }
    return d + 'Z';
  }

  function ArrowSeal() {
    return h('span', { className: 'mm-btn__seal', 'aria-hidden': 'true' },
      h('svg', { viewBox: '0 0 24 24' },
        h('path', { d: scallopPath(24, 12, 2.2), fill: 'var(--signal)', stroke: 'var(--ink)', strokeWidth: 1.2 }),
        h('path', { d: 'M7.5 12h8.5m-3.4-3.6L16.2 12l-3.6 3.6', fill: 'none', stroke: 'var(--paper)', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' })));
  }

  function Button(p) {
    var variant = p.variant || 'secondary', size = p.size || 'md';
    var rest = Object.assign({}, p); ['variant', 'size', 'icon', 'children', 'className', 'arrow', 'as', 'block'].forEach(function (k) { delete rest[k]; });
    var text = typeof p.children === 'string' ? p.children : '';
    var label = variant === 'primary'
      ? h('span', { className: 'mm-btn__label' }, h('span', { className: 'mm-btn__roll', 'data-text': text }, p.children))
      : h('span', null, p.children);
    var face = h('span', { className: 'mm-btn__face' },
      p.icon && variant !== 'primary' ? h(Icon, { name: p.icon }) : null,
      label,
      variant === 'primary' && p.arrow !== false ? h(ArrowSeal) : null);
    return h(p.as || 'button', Object.assign({ type: p.as ? undefined : 'button' }, rest, { className: cx('mm-btn', 'mm-btn--' + variant, size === 'lg' && 'mm-btn--lg', p.block && 'mm-btn--block', p.className) }), face);
  }

  function IconButton(p) {
    return h('button', { type: 'button', className: cx('mm-iconbtn', p.tone === 'ink' && 'mm-iconbtn--ink', p.size === 'sm' && 'mm-iconbtn--sm', p.className), 'aria-label': p.label, title: p.label, onClick: p.onClick, disabled: p.disabled },
      h(Icon, { name: p.icon, size: p.size === 'sm' ? 16 : 20 }));
  }

  function Tag(p) {
    return h('span', { className: cx('mm-tag', p.tone && p.tone !== 'ink' && 'mm-tag--' + p.tone, p.flat && 'mm-tag--flat', p.className) }, p.icon ? h(Icon, { name: p.icon, size: 14 }) : null, p.children);
  }

  var STATUS_ICON = { ok: 'check', fail: 'x', warn: 'question', pending: 'clock', approved: 'sealCheck', live: null, emergency: 'siren' };
  function StatusBadge(p) {
    var s = p.status || 'pending';
    return h('span', { className: cx('mm-badge', 'mm-badge--' + s, p.className) }, STATUS_ICON[s] ? h(Icon, { name: STATUS_ICON[s], size: 14 }) : null, p.children);
  }

  var DEPTS = {
    water: { icon: 'drop', name: 'Water' }, drainage: { icon: 'waves', name: 'Drainage' }, gas: { icon: 'flame', name: 'Gas' },
    power: { icon: 'lightning', name: 'Power' }, telecom: { icon: 'wifi', name: 'Telecom' }, roads: { icon: 'road', name: 'Roads' },
    coordinator: { icon: 'handshake', name: 'Coordinator' }, solver: { icon: 'gear', name: 'Scheduler' },
  };
  function DeptChip(p) {
    var d = DEPTS[p.dept] || DEPTS.roads;
    return h('span', { className: cx('mm-dept', 'mm-dept--' + p.dept, p.className) },
      h('span', { className: 'mm-dept__icon' }, h(Icon, { name: d.icon, size: 12 })), p.children || d.name);
  }

  function Seal(p) {
    var size = p.size || 96, kind = p.kind || 'verified';
    var path = scallopPath(100, 18, 6);
    return h('span', { className: cx('mm-seal', 'mm-seal--' + kind, p.stamp && 'mm-seal--stamp', p.className), style: { '--seal-size': size + 'px' }, role: 'img', 'aria-label': p.label || (typeof p.children === 'string' ? p.children : kind) },
      h('svg', { viewBox: '0 0 100 100', 'aria-hidden': 'true' },
        h('path', { className: 'mm-seal__shadow', d: path, transform: 'translate(3 3)' }),
        h('path', { className: 'mm-seal__body', d: path })),
      h('span', { className: 'mm-seal__text', 'aria-hidden': 'true' }, p.children));
  }

  function Card(p) {
    return h(p.as || 'div', { className: cx('mm-card', p.tone && 'mm-card--' + p.tone, p.soft && 'mm-card--soft', p.flat && 'mm-card--flat', p.interactive && 'mm-card--interactive', p.className), onClick: p.onClick, tabIndex: p.interactive ? 0 : undefined, style: p.style },
      p.title ? h('h3', { className: 'mm-card__title' }, p.title) : null,
      p.meta ? h('div', { className: 'mm-card__meta' }, p.meta) : null,
      p.children);
  }

  function FolderCard(p) {
    return h('section', { className: cx('mm-folder', p.tone && 'mm-folder--' + p.tone, p.className), style: p.style },
      h('div', { className: 'mm-folder__tab' }, p.icon ? h(Icon, { name: p.icon, size: 16 }) : null, p.tab),
      h('div', { className: 'mm-folder__body' }, p.children));
  }

  var BANNER_ICON = { info: 'info', warn: 'warning', danger: 'warning', ok: 'sealCheck', ink: 'info' };
  function Banner(p) {
    var tone = p.tone || 'info';
    return h('div', { className: cx('mm-banner', tone !== 'info' && 'mm-banner--' + tone, p.className), role: tone === 'danger' ? 'alert' : 'status' },
      h(Icon, { name: p.icon || BANNER_ICON[tone] }),
      h('div', { className: 'mm-banner__body' }, p.title ? h('div', { className: 'mm-banner__title' }, p.title) : null, p.children ? h('div', { className: 'mm-banner__text' }, p.children) : null),
      p.action || null);
  }

  function Toast(p) {
    return h('div', { className: cx('mm-toast', p.fixed && 'mm-toast--fixed', p.className), role: 'status' },
      p.icon ? h(Icon, { name: p.icon }) : null, h('span', null, p.children),
      p.actionLabel ? h('button', { type: 'button', className: 'mm-toast__action', onClick: p.onAction }, p.actionLabel) : null);
  }

  function Tabs(p) {
    var items = p.items || [];
    return h('div', { className: cx('mm-tabs', p.className), role: 'tablist', 'aria-label': p.label },
      items.map(function (it) {
        var sel = it.id === p.value;
        return h('button', { key: it.id, type: 'button', role: 'tab', 'aria-selected': sel ? 'true' : 'false', className: 'mm-tab', onClick: function () { p.onChange && p.onChange(it.id); } },
          it.icon ? h(Icon, { name: it.icon, size: 16 }) : null, it.label, it.count != null ? h('span', { className: 'mm-tab__count' }, it.count) : null);
      }));
  }

  function Toggle(p) {
    var on = !!p.checked;
    return h('button', { type: 'button', role: 'switch', 'aria-checked': on ? 'true' : 'false', 'aria-label': p.label, className: cx('mm-toggle', p.className), onClick: function () { p.onChange && p.onChange(!on); }, style: { background: 'none', border: 0, padding: 0, font: 'inherit' } },
      p.off ? h('span', { className: cx('mm-toggle__side', !on && 'mm-toggle__side--on') }, p.off) : null,
      h('span', { className: 'mm-toggle__track' }, h('span', { className: 'mm-toggle__knob' })),
      p.on ? h('span', { className: cx('mm-toggle__side', on && 'mm-toggle__side--on') }, p.on) : null);
  }

  var fieldSeq = 0;
  function TextField(p) {
    var id = React.useState(function () { fieldSeq += 1; return 'mm-field-' + fieldSeq; })[0];
    var rest = Object.assign({}, p); ['label', 'hint', 'error', 'multiline', 'className'].forEach(function (k) { delete rest[k]; });
    return h('div', { className: cx('mm-field', p.error && 'mm-field--error', p.className) },
      p.label ? h('label', { className: 'mm-field__label', htmlFor: id }, p.label) : null,
      h(p.multiline ? 'textarea' : 'input', Object.assign({ id: id, className: 'mm-input', 'aria-invalid': p.error ? 'true' : undefined, 'aria-describedby': (p.error || p.hint) ? id + '-hint' : undefined }, rest)),
      (p.error || p.hint) ? h('div', { className: 'mm-field__hint', id: id + '-hint' }, p.error || p.hint) : null);
  }

  function decimals(n) { return (String(n).split('.')[1] || '').length; }

  // Counts up from 0 once on mount (600 ms, ease-out); respects reduced motion.
  function useCountUp(target, enabled) {
    var st = React.useState(enabled ? 0 : target), v = st[0], setV = st[1];
    React.useEffect(function () {
      if (!enabled || typeof target !== 'number') { setV(target); return; }
      if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setV(target); return; }
      var t0 = performance.now(), raf, dp = decimals(target);
      function tick(t) { var k = Math.min(1, (t - t0) / 600); setV(k < 1 ? Number((target * (1 - Math.pow(1 - k, 3))).toFixed(dp)) : target); if (k < 1) raf = requestAnimationFrame(tick); }
      raf = requestAnimationFrame(tick);
      return function () { cancelAnimationFrame(raf); };
    }, [target, enabled]);
    return v;
  }

  function MetricTile(p) {
    var v = useCountUp(p.value, p.countUp !== false);
    return h('div', { className: cx('mm-metric', p.className) },
      h('div', { className: 'mm-metric__label' }, p.label),
      h('div', { className: 'mm-metric__value' }, typeof v === 'number' ? v.toLocaleString('en-IN', { minimumFractionDigits: decimals(p.value), maximumFractionDigits: decimals(p.value) }) : v, p.unit ? h('span', { className: 'mm-metric__unit' }, p.unit) : null),
      (p.delta || p.compare) ? h('div', { className: 'mm-metric__foot' },
        p.compare ? h('span', null, p.compare) : h('span'),
        p.delta ? h('span', { className: cx('mm-delta', p.better === false ? 'mm-delta--worse' : 'mm-delta--better') }, p.delta) : null) : null);
  }

  function DataTable(p) {
    var cols = p.columns || [];
    return h('table', { className: cx('mm-table', p.className) },
      p.caption ? h('caption', { className: 'mm-overline', style: { textAlign: 'left', padding: '0 0 6px' } }, p.caption) : null,
      h('thead', null, h('tr', null, cols.map(function (c) { return h('th', { key: c.key, scope: 'col', className: c.num ? 'mm-num' : undefined }, c.label); }))),
      h('tbody', null, (p.rows || []).map(function (r, i) {
        return h('tr', { key: r.id || i }, cols.map(function (c) {
          var val = r[c.key];
          return h('td', { key: c.key, className: cx(c.num && 'mm-num', c.mono && 'mm-mono') }, val);
        }));
      })));
  }

  function NegotiationMessage(p) {
    var type = (p.type || 'NOTICE').toUpperCase();
    return h('article', { className: cx('mm-msg', 'mm-msg--' + type.toLowerCase(), p.fresh && 'mm-msg--fresh', p.className) },
      h('header', { className: 'mm-msg__head' },
        h(DeptChip, { dept: p.sender || p.from }),
        p.to ? h('span', { className: 'mm-msg__to' }, '→ ' + p.to) : null,
        h('span', { className: 'mm-msg__type' }, type),
        h('time', { className: 'mm-msg__time' }, (p.round ? 'R' + p.round + ' · ' : '') + (p.time || ''))),
      p.body ? h('p', { className: 'mm-msg__body' }, p.body) : null,
      p.options && p.options.length ? h('ul', { className: 'mm-msg__opts' }, p.options.map(function (o, i) {
        return h('li', { key: i, className: 'mm-msg__opt' }, h('span', null, o.label), h('span', null, o.cost));
      })) : null);
  }

  function DiffRow(p) {
    var was = p.was != null ? p.was : p.from;
    return h('li', { className: cx('mm-diff', p.className) },
      h(DeptChip, { dept: p.dept }),
      h('div', null,
        h('div', { className: 'mm-diff__title' }, p.title),
        h('div', { className: 'mm-diff__dates' }, was ? h('s', null, was) : null, was ? ' → ' : null, h('b', null, p.to)),
        p.reason ? h('div', { className: 'mm-diff__reason' }, p.reason) : null),
      p.cost ? h('span', { className: cx('mm-diff__cost', p.costDir === 'down' ? 'mm-diff__cost--down' : 'mm-diff__cost--up') }, p.cost) : h('span'));
  }

  function TimelineSlider(p) {
    var days = p.days || 28, value = p.value == null ? 0 : p.value;
    var pct = function (d) { return (d / Math.max(1, days - 1)) * 100 + '%'; };
    var ticks = []; for (var d = 0; d < days; d += 7) ticks.push(d);
    function onKey(e) {
      if (!p.onChange) return;
      if (e.key === 'ArrowRight') p.onChange(Math.min(days - 1, value + 1));
      if (e.key === 'ArrowLeft') p.onChange(Math.max(0, value - 1));
    }
    function onClick(e) {
      if (!p.onChange) return;
      var r = e.currentTarget.getBoundingClientRect();
      p.onChange(Math.round(((e.clientX - r.left) / r.width) * (days - 1)));
    }
    return h('div', { className: cx('mm-timeline', p.className) },
      h(IconButton, { icon: p.playing ? 'pause' : 'play', label: p.playing ? 'Pause' : 'Play the plan', onClick: p.onPlay, tone: 'ink' }),
      h('div', { className: 'mm-timeline__track', onClick: onClick },
        h('span', { className: 'mm-timeline__fill', style: { width: pct(value) } }),
        (p.risks || []).map(function (r, i) { return h('span', { key: i, className: cx('mm-timeline__risk', r.kind && r.kind !== 'rain' && 'mm-timeline__risk--' + r.kind), style: { left: pct(r.start), width: 'calc(' + pct(r.end) + ' - ' + pct(r.start) + ')' }, title: r.label }); }),
        h('span', { className: 'mm-timeline__ticks', 'aria-hidden': 'true' }, ticks.map(function (t) { return h('span', { key: t }, p.tickLabel ? p.tickLabel(t) : 'D' + (t + 1)); })),
        h('span', { className: 'mm-timeline__thumb', role: 'slider', tabIndex: 0, 'aria-label': 'Plan day', 'aria-valuemin': 0, 'aria-valuemax': days - 1, 'aria-valuenow': value, 'aria-valuetext': p.valueLabel, onKeyDown: onKey, style: { left: pct(value) } },
          h('span', { className: 'mm-timeline__bubble' }, p.valueLabel || 'Day ' + (value + 1)))),
      p.range ? h('span', { className: 'mm-timeline__range' }, p.range) : null);
  }

  var LEGEND_DEPTS = ['water', 'drainage', 'gas', 'power', 'telecom', 'roads'];
  function MapLegend(p) {
    var counts = p.counts || {};
    return h('div', { className: cx('mm-legend', p.className), role: 'group', 'aria-label': 'Map legend' },
      h('div', { className: 'mm-overline' }, p.title || 'On the map'),
      LEGEND_DEPTS.map(function (k) {
        return h('div', { key: k, className: 'mm-legend__row' },
          h('span', { className: 'mm-legend__swatch', style: { '--dept': 'var(--dept-' + k + ')' } }),
          h(Icon, { name: DEPTS[k].icon, size: 14 }), DEPTS[k].name, counts[k] != null ? h('span', { className: 'mm-legend__count' }, counts[k]) : null);
      }),
      h('div', { className: 'mm-legend__row' }, h('span', { className: 'mm-legend__swatch mm-legend__swatch--shared' }), 'Shared trench'),
      h('div', { className: 'mm-legend__row' }, h('span', { className: 'mm-legend__swatch mm-legend__swatch--nodig' }), h(Icon, { name: 'lock', size: 14 }), 'No new digs (protected)'),
      h('div', { className: 'mm-legend__row' }, h('span', { className: 'mm-legend__swatch mm-legend__swatch--rain' }), 'Heavy rain forecast'),
      h('div', { className: 'mm-legend__row' }, h('span', { className: 'mm-legend__swatch mm-legend__swatch--air' }), 'Poor air forecast'),
      h('div', { className: 'mm-legend__row' }, h('span', { className: 'mm-legend__swatch mm-legend__swatch--event' }), 'Event route'));
  }

  var STEP_ICON = { done: 'check', running: null, needs: 'hand', waiting: null };
  function StepList(p) {
    return h('ol', { className: cx('mm-steps', p.className) }, (p.steps || []).map(function (s, i) {
      var st = s.status || 'waiting';
      return h('li', { key: i, className: cx('mm-step', 'mm-step--' + st) },
        h('span', { className: 'mm-step__dot', 'aria-hidden': 'true' }, STEP_ICON[st] ? h(Icon, { name: STEP_ICON[st], size: 11 }) : null),
        h('span', null, s.text, s.detail ? h('span', { className: 'mm-step__detail' }, s.detail) : null));
    }));
  }

  function PhotoSlot(p) {
    if (p.src) {
      return h('figure', { className: cx('mm-photo', 'mm-photo--filled', p.className), style: { margin: 0 } },
        h('img', { src: p.src, alt: p.alt || p.label || 'Site photo' }),
        h('figcaption', { className: 'mm-photo__meta' }, h('span', null, p.meta), p.badge || null));
    }
    return h('button', { type: 'button', className: cx('mm-photo', 'mm-photo--empty', p.className), onClick: p.onPick, style: { font: 'inherit', color: 'inherit' } },
      h(Icon, { name: 'camera', size: 28 }),
      h('span', { className: 'mm-photo__title' }, p.label || 'Take photo'),
      p.hint ? h('span', { className: 'mm-photo__hint' }, p.hint) : null);
  }

  function CopilotBar(p) {
    return h('form', { className: cx('mm-copilot', p.fixed && 'mm-copilot--fixed', p.className), onSubmit: function (e) { e.preventDefault(); p.onSubmit && p.onSubmit(p.value); }, role: 'search', 'aria-label': 'Copilot' },
      h('span', { className: 'mm-copilot__badge' }, h(Icon, { name: 'command', size: 16 }), 'Copilot'),
      h('input', { className: 'mm-copilot__input', value: p.value, onChange: function (e) { p.onChange && p.onChange(e.target.value); }, placeholder: p.placeholder || 'Tell MargaMitra what to do, for example: plan next month and keep the procession route clear', 'aria-label': 'Copilot command' }),
      h(Button, { variant: 'primary', type: 'submit', disabled: p.busy }, p.busy ? 'Working' : 'Run'));
  }

  var LINKS = [
    { id: 'command', label: 'Command centre' }, { id: 'approvals', label: 'Approvals' }, { id: 'field', label: 'Field' },
    { id: 'record', label: 'Public record' }, { id: 'impact', label: 'Impact' },
  ];
  function TopBar(p) {
    var links = p.links || LINKS;
    return h('header', { className: cx('mm-topbar', p.className) },
      h('a', { className: 'mm-topbar__brand', href: p.homeHref || '#' }, 'MARGAMITRA'),
      h('nav', { className: 'mm-topbar__nav', 'aria-label': 'Main' }, links.map(function (l) {
        return h('a', { key: l.id, href: l.href || '#', className: 'mm-topbar__link', 'aria-current': l.id === p.active ? 'page' : undefined, onClick: l.onClick }, l.label);
      })),
      h('div', { className: 'mm-topbar__right' },
        h('span', { className: 'mm-live' }, h('span', { className: 'mm-live__dot', 'aria-hidden': 'true' }), p.place || 'Live · Surathkal'),
        h('button', { type: 'button', className: 'mm-role', onClick: p.onRole }, h(Icon, { name: 'hardhat', size: 16 }), p.role || 'Ward engineer', h(Icon, { name: 'caretDown', size: 14 }))));
  }

  var api = { Icon: Icon, Button: Button, IconButton: IconButton, Tag: Tag, StatusBadge: StatusBadge, DeptChip: DeptChip, Seal: Seal, Card: Card, FolderCard: FolderCard, Banner: Banner, Toast: Toast, Tabs: Tabs, Toggle: Toggle, TextField: TextField, MetricTile: MetricTile, DataTable: DataTable, NegotiationMessage: NegotiationMessage, DiffRow: DiffRow, TimelineSlider: TimelineSlider, MapLegend: MapLegend, StepList: StepList, PhotoSlot: PhotoSlot, CopilotBar: CopilotBar, TopBar: TopBar, DEPTS: DEPTS };
  window.MargaMitra = Object.assign(window.MargaMitra || {}, api);
})();