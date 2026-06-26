import { Component, ReactNode } from "react";

import { FallbackMarkdown } from "@/components/FallbackMarkdown";

type Props = {
  resetKey: string;
  content: string;
  children: ReactNode;
};

type State = { failed: boolean; resetKey: string };

export class MarkdownErrorBoundary extends Component<Props, State> {
  state: State = { failed: false, resetKey: this.props.resetKey };

  static getDerivedStateFromError(): Pick<State, "failed"> {
    return { failed: true };
  }

  componentDidCatch(error: Error) {
    if (__DEV__) {
      console.warn("[MarkdownErrorBoundary]", error.message, error.stack);
    }
  }

  static getDerivedStateFromProps(props: Props, state: State): State | null {
    if (props.resetKey !== state.resetKey) {
      return { failed: false, resetKey: props.resetKey };
    }
    return null;
  }

  render() {
    if (this.state.failed) {
      return <FallbackMarkdown content={this.props.content} />;
    }
    return this.props.children;
  }
}
