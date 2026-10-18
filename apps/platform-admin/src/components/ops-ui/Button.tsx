import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'destructive' | 'ghost';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-ops-accent text-white border border-transparent hover:bg-ops-accent-hover active:bg-ops-accent-active',
  secondary:
    'bg-white text-ops-text-primary border border-ops-border hover:bg-ops-canvas active:bg-ops-canvas',
  destructive:
    'bg-white text-ops-error border border-ops-status-critical-bg hover:bg-ops-status-critical-bg active:bg-ops-status-critical-bg',
  ghost:
    'bg-transparent text-ops-text-secondary border border-transparent hover:bg-ops-canvas hover:text-ops-text-primary active:bg-ops-canvas',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  className = '',
  type = 'button',
  disabled,
  children,
  ...rest
}) => (
  <button
    type={type}
    disabled={disabled}
    className={`inline-flex h-8 items-center justify-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-colors duration-100 ease-in-out focus:outline-none focus:ring-2 focus:ring-ops-accent-focus focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 ${variantClasses[variant]} ${className}`}
    {...rest}
  >
    {children}
  </button>
);
