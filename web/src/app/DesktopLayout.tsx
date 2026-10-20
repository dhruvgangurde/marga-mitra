import { useCallback, useEffect, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useConnectionLost } from '../api/live';
import { TopBar } from '../ui';
import type { TopBarProps } from '../ui';
import { RoleMenu, roleLabel, useRole } from './role';

const NAV: { id: TopBarProps['active']; label: string; href: string }[] = [
  { id: 'command', label: 'Command centre', href: '/command' },
  { id: 'approvals', label: 'Approvals', href: '/approvals' },
  { id: 'field', label: 'Field', href: '/field' },
  { id: 'record', label: 'Public record', href: '/record' },
  { id: 'impact', label: 'Impact', href: '/impact' },
];

const DOTGRID = ['/', '/record', '/impact'];

export function DesktopLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { role } = useRole();
  const [menu, setMenu] = useState(false);
  const lost = useConnectionLost();
  const closeMenu = useCallback(() => setMenu(false), []);

  const first = pathname.split('/')[1] ?? '';
  const known = NAV.some((n) => n.id === first);
  // On the landing page and unknown paths no link is active; TopBar wants a valid id, so cast once.
  const active = (known ? first : '') as TopBarProps['active'];

  useEffect(() => {
    const dots = DOTGRID.includes(pathname);
    document.body.classList.toggle('mm-dotgrid', dots);
    return () => document.body.classList.remove('mm-dotgrid');
  }, [pathname]);

  const shownRole = pathname === '/record' || pathname === '/impact' ? 'Visitor' : roleLabel(role);

  return (
    <>
      <TopBar
        active={active}
        links={NAV.map((n) => ({ id: n.id, label: n.label, href: n.href, onClick: () => navigate(n.href) }))}
        place={lost ? 'Reconnecting \u00b7 Surathkal' : 'Live \u00b7 Surathkal'}
        role={shownRole}
        onRole={() => setMenu((m) => !m)}
        homeHref="/"
      />
      {menu ? <RoleMenu onClose={closeMenu} /> : null}
      <Outlet />
    </>
  );
}