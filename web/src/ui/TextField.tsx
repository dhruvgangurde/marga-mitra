import { useId } from 'react';
import type * as React from 'react';
import { cx } from './util';

export interface TextFieldProps extends React.InputHTMLAttributes<HTMLInputElement> { label?: string; hint?: string; error?: string; multiline?: boolean }

export function TextField({ label, hint, error, multiline, className, ...rest }: TextFieldProps) {
  const id = useId();
  const control = {
    id,
    className: 'mm-input',
    'aria-invalid': error ? ('true' as const) : undefined,
    'aria-describedby': error || hint ? id + '-hint' : undefined,
  };
  return (
    <div className={cx('mm-field', error && 'mm-field--error', className)}>
      {label ? <label className="mm-field__label" htmlFor={id}>{label}</label> : null}
      {multiline
        ? <textarea {...control} {...(rest as React.TextareaHTMLAttributes<HTMLTextAreaElement>)} />
        : <input {...control} {...rest} />}
      {error || hint ? <div className="mm-field__hint" id={id + '-hint'}>{error || hint}</div> : null}
    </div>
  );
}
