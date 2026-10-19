import "./intelligenceHome.css";

export type SystemStatusLineProps = {
  ready: boolean;
  items: string[]; // real status text only, e.g. "Data Engine connected"
  onDetails?: () => void;
};

export default function SystemStatusLine({ ready, items, onDetails }: SystemStatusLineProps) {
  return (
    <footer className="dw-status-line">
      <span className={ready ? "dw-status-line__dot" : "dw-status-line__dot is-busy"} aria-hidden="true" />
      <span>{items.join(" · ")}</span>
      {onDetails && (
        <button type="button" className="dw-status-line__link" onClick={onDetails}>System details</button>
      )}
    </footer>
  );
}
