import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Tag } from '../ui';

export type RoleId = 'ward_engineer' | 'department_officer' | 'field_crew' | 'resident' | 'visitor';

export const ROLES: { id: RoleId; label: string; home: string }[] = [
  { id: 'ward_engineer', label: 'Ward engineer', home: '/command' },
  { id: 'department_officer', label: 'Department officer', home: '/approvals' },
  { id: 'field_crew', label: 'Field crew', home: '/field' },
  { id: 'resident', label: 'Resident', home: '/report' },
  { id: 'visitor', label: 'Visitor', home: '/record' },
];

const KEY = 'mm-role';

function readRole(): RoleId {
  try {
    const v = sessionStorage.getItem(KEY);
    if (ROLES.some((r) => r.id === v)) return v as RoleId;
  } catch {
    // storage can be blocked; fall through to the default
  }
  return 'ward_engineer';
}

interface RoleValue { role: RoleId; setRole: (r: RoleId) => void }

const RoleContext = createContext<RoleValue>({ role: 'ward_engineer', setRole: () => {} });

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<RoleId>(readRole);
  const setRole = (r: RoleId) => {
    setRoleState(r);
    try {
      sessionStorage.setItem(KEY, r);
    } catch {
      // not saved; the choice still works for this page
    }
  };
  return <RoleContext.Provider value={{ role, setRole }}>{children}</RoleContext.Provider>;
}

export function useRole(): RoleValue {
  return useContext(RoleContext);
}

export function roleLabel(id: RoleId): string {
  return ROLES.find((r) => r.id === id)?.label ?? 'Ward engineer';
}

export function RoleMenu({ onClose }: { onClose: () => void }) {
  const { role, setRole } = useRole();
  const navigate = useNavigate();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      // The drawer and the copilot card close first.
      if (e.key === 'Escape' && !document.querySelector('.mm-app-drawer, .mm-app-copilot__steps')) onClose();
    };
    const onDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (ref.current && !ref.current.contains(target) && !(target as HTMLElement).closest?.('.mm-role')) onClose();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
      opener?.focus();
    };
  }, [onClose]);

  return (
    <div ref={ref} className="mm-app-rolemenu" role="dialog" aria-label="Choose your role">
      <Card soft>
        {ROLES.map((r) => (
          <div key={r.id} className="mm-app-rolemenu__row">
            <Button
              variant="ghost"
              block
              onClick={() => {
                setRole(r.id);
                onClose();
                navigate(r.home);
              }}
            >
              {r.label}
            </Button>
            {r.id === role ? <Tag tone="lime" flat>Current</Tag> : null}
          </div>
        ))}
      </Card>
    </div>
  );
}