import type * as React from 'react';
import { Link } from 'react-router-dom';

// In-app paths go through the router so the page never reloads and the mock data stays.
export function AppLink({ href, ...rest }: React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return href?.startsWith('/') ? <Link to={href} {...rest} /> : <a href={href} {...rest} />;
}
