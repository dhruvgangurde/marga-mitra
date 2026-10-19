import type * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { IconButton } from './IconButton';
import './PhoneScreen.css';

export interface PhoneScreenProps { title: string; badge?: React.ReactNode; backTo: string; footer?: React.ReactNode; children?: React.ReactNode }

export function PhoneScreen({ title, badge, backTo, footer, children }: PhoneScreenProps) {
  const navigate = useNavigate();
  return (
    <div className="mm-dotgrid ph-page">
      <div className="ph-col">
        <header className="ph-bar">
          <IconButton icon="caretLeft" label="Back" onClick={() => navigate(backTo)} />
          <h1 className="display-3 ph-title">{title}</h1>
          {badge}
        </header>
        <main className="ph-main">{children}</main>
        {footer ? <footer className="ph-foot">{footer}</footer> : null}
      </div>
    </div>
  );
}
