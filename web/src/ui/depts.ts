import type { IconName } from './icons';

export const DEPTS = {
  water: { icon: 'drop', name: 'Water', token: '--dept-water' },
  drainage: { icon: 'waves', name: 'Drainage', token: '--dept-drainage' },
  gas: { icon: 'flame', name: 'Gas', token: '--dept-gas' },
  power: { icon: 'lightning', name: 'Power', token: '--dept-power' },
  telecom: { icon: 'wifi', name: 'Telecom', token: '--dept-telecom' },
  roads: { icon: 'road', name: 'Roads', token: '--dept-roads' },
  coordinator: { icon: 'handshake', name: 'Coordinator', token: '--ink' },
  solver: { icon: 'gear', name: 'Scheduler', token: '--lime' },
} as const satisfies Record<string, { icon: IconName; name: string; token: string }>;

export type Dept = keyof typeof DEPTS;
