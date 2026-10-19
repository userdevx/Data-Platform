import type { ReactNode } from "react";
import "./intelligenceHome.css";

export type StartIdeasProps = {
  onAsk: () => void;
  onConnect: () => void;
  onBuild?: () => void; // omit to hide "Build something" (Applications flag off)
};

function Card(props: { tone: "blue" | "teal" | "orange"; title: string; text: string; icon: ReactNode; onClick: () => void }) {
  return (
    <button type="button" className="dw-idea" onClick={props.onClick}>
      <span className={`dw-idea__icon dw-idea__icon--${props.tone}`} aria-hidden="true">{props.icon}</span>
      <span className="dw-idea__body">
        <strong>{props.title}</strong>
        <span>{props.text}</span>
      </span>
    </button>
  );
}

const svg = (d: ReactNode) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{d}</svg>
);

export default function StartIdeas({ onAsk, onConnect, onBuild }: StartIdeasProps) {
  return (
    <section className="dw-ideas" aria-labelledby="dw-ideas-title">
      <h2 id="dw-ideas-title" className="dw-ideas__title">Start with an idea</h2>
      <div className="dw-ideas__grid">
        <Card tone="blue" title="Ask a question" text="Get answers from your connected data." onClick={onAsk}
          icon={svg(<><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5M12 16h.01" /></>)} />
        <Card tone="teal" title="Connect a source" text="Bring in files from your computer." onClick={onConnect}
          icon={svg(<><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></>)} />
        {onBuild && (
          <Card tone="orange" title="Build something" text="Turn an idea into a working app." onClick={onBuild}
            icon={svg(<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.4 2.4-2.6-.4-.4-2.6z" />)} />
        )}
      </div>
    </section>
  );
}
