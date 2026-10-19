import type * as React from 'react';
import { cx } from './util';

export interface DataTableProps { columns: { key: string; label: string; num?: boolean; mono?: boolean }[]; rows: Record<string, React.ReactNode>[]; caption?: string }

export function DataTable({ columns, rows, caption }: DataTableProps) {
  return (
    <table className="mm-table">
      {caption ? <caption className="mm-overline" style={{ textAlign: 'left', padding: '0 0 6px' }}>{caption}</caption> : null}
      <thead>
        <tr>
          {columns.map((c) => <th key={c.key} scope="col" className={c.num ? 'mm-num' : undefined}>{c.label}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={typeof r.id === 'string' || typeof r.id === 'number' ? r.id : i}>
            {columns.map((c) => <td key={c.key} className={cx(c.num && 'mm-num', c.mono && 'mm-mono')}>{r[c.key]}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
