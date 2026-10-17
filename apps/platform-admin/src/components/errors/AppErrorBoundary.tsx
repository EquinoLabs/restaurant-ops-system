import React from 'react';
import { ServerErrorPage } from './ServerErrorPage';

interface AppErrorBoundaryProps {
  children: React.ReactNode;
}

interface AppErrorBoundaryState {
  error: Error | null;
}

export class AppErrorBoundary extends React.Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error('Uncaught error in Platform Admin UI:', error);
  }

  render() {
    if (this.state.error) {
      return <ServerErrorPage error={this.state.error} />;
    }
    return this.props.children;
  }
}

export default AppErrorBoundary;
