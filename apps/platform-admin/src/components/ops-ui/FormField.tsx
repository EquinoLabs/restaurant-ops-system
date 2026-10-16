import React from 'react';

export interface FormFieldProps {
  id: string;
  label: string;
  hint?: string;
  error?: string | null;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

export interface FormFieldControlAriaProps {
  id: string;
  'aria-describedby'?: string;
  'aria-invalid'?: boolean;
}

/**
 * Returns the ARIA props a form control should carry for a given FormField id/hint/error.
 * Use this when the child is not a single element FormField can clone.
 */
export function getFormFieldControlAriaProps(
  id: string,
  options: { hint?: string; error?: string | null }
): FormFieldControlAriaProps {
  const describedBy: string[] = [];
  if (options.error) {
    describedBy.push(`${id}-error`);
  } else if (options.hint) {
    describedBy.push(`${id}-hint`);
  }

  return {
    id,
    'aria-describedby': describedBy.length > 0 ? describedBy.join(' ') : undefined,
    'aria-invalid': options.error ? true : undefined,
  };
}

function mergeControlAria(
  element: React.ReactElement<Record<string, unknown>>,
  id: string,
  hint?: string,
  error?: string | null
): Record<string, unknown> {
  const extra = getFormFieldControlAriaProps(id, { hint, error });
  const existingDescribedBy = element.props['aria-describedby'];
  const existingInvalid = element.props['aria-invalid'];
  const controlId = element.props.id ?? extra.id;

  const describedParts = [existingDescribedBy, extra['aria-describedby']]
    .filter((value): value is string => Boolean(value))
    .join(' ');

  return {
    id: controlId,
    'aria-describedby': describedParts.length > 0 ? describedParts : undefined,
    'aria-invalid': error ? true : existingInvalid,
  };
}

export const FormField: React.FC<FormFieldProps> = ({
  id,
  label,
  hint,
  error,
  required,
  children,
  className = '',
}) => {
  const controlAria = getFormFieldControlAriaProps(id, { hint, error });

  let control: React.ReactNode = children;
  if (React.isValidElement(children) && React.Children.count(children) === 1) {
    control = React.cloneElement(
      children as React.ReactElement<Record<string, unknown>>,
      mergeControlAria(children as React.ReactElement<Record<string, unknown>>, id, hint, error)
    );
  }

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={controlAria.id} className="text-xs font-semibold text-ops-text-secondary">
        {label}
        {required && <span className="ml-0.5 text-ops-error">*</span>}
      </label>
      {control}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-[11px] leading-4 text-ops-text-secondary">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="text-[11px] leading-4 text-ops-error">
          {error}
        </p>
      )}
    </div>
  );
};

export const opsInputClass =
  'h-8 w-full rounded-md border border-ops-border bg-white px-2.5 text-[13px] text-ops-text-primary placeholder:text-ops-text-disabled focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus disabled:opacity-50';
