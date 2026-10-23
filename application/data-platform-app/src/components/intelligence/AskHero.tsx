import type { ReactNode } from "react";
import "./intelligenceHome.css";

export default function AskHero({ children }: { children: ReactNode }) {
  return (
    <section className="dw-ask-hero" aria-label="Ask a question">
      <div className="dw-ask-hero__inner">
        <h2 className="dw-ask-hero__title">What would you like to know?</h2>
        <div className="dw-ask-hero__composer">{children}</div>
      </div>
    </section>
  );
}
