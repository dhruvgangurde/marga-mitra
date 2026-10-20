import type * as React from 'react';
import { Card } from './Card';
import { Icon } from './Icon';
import type { IconName } from './icons';

export interface EmptyStateProps { icon: IconName; text: string; action: React.ReactNode }

export function EmptyState({ icon, text, action }: EmptyStateProps) {
  return (
    <Card soft>
      <div
        className="mm-dotgrid"
        style={{
          borderRadius: 'var(--radius-xl)', padding: 'var(--space-6)', display: 'flex', flexDirection: 'column',
          alignItems: 'center', gap: 12, textAlign: 'center',
        }}
      >
        <Icon name={icon} size={24} />
        <p className="body-l" style={{ margin: 0 }}>{text}</p>
        {action}
      </div>
    </Card>
  );
}
