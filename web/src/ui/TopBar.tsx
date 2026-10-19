import { AppLink } from './AppLink';
import { Icon } from './Icon';

type TopBarLink = { id: string; label: string; href?: string; onClick?: () => void };

export interface TopBarProps {
  active: 'command' | 'approvals' | 'field' | 'record' | 'impact';
  links?: TopBarLink[];
  place?: string;
  role?: string;
  onRole?: () => void;
  homeHref?: string;
}

const LINKS: TopBarLink[] = [
  { id: 'command', label: 'Command centre' }, { id: 'approvals', label: 'Approvals' }, { id: 'field', label: 'Field' },
  { id: 'record', label: 'Public record' }, { id: 'impact', label: 'Impact' },
];

export function TopBar({ active, links = LINKS, place, role, onRole, homeHref }: TopBarProps) {
  return (
    <header className="mm-topbar">
      <AppLink className="mm-topbar__brand" href={homeHref ?? '#'}>MARGAMITRA</AppLink>
      <nav className="mm-topbar__nav" aria-label="Main">
        {links.map((l) => {
          const { onClick } = l;
          return (
            <AppLink
              key={l.id}
              href={l.href || '#'}
              className="mm-topbar__link"
              aria-current={l.id === active ? 'page' : undefined}
              onClick={onClick ? (e) => { e.preventDefault(); onClick(); } : undefined}
            >
              {l.label}
            </AppLink>
          );
        })}
      </nav>
      <div className="mm-topbar__right">
        <span className="mm-live"><span className="mm-live__dot" aria-hidden="true" />{place ?? 'Live · Surathkal'}</span>
        <button type="button" className="mm-role" onClick={onRole}>
          <Icon name="hardhat" size={16} />
          {role ?? 'Ward engineer'}
          <Icon name="caretDown" size={14} />
        </button>
      </div>
    </header>
  );
}
