import type {
  NaturalIntelligenceResponse,
} from "../bridge/intelligenceBridge";


export type IntelligenceResponsePanelProps = {
  response:
    | NaturalIntelligenceResponse
    | null;

  onOpenUrl: (
    url: string,
  ) => void | Promise<void>;
};


export default function IntelligenceResponsePanel({
  response,
  onOpenUrl,
}: IntelligenceResponsePanelProps) {
  return (
    <article className="panel response-panel">
      <h2>Response</h2>

      {response ? (
        <div className="natural-response natural-response-only">
          <p>{response.answer}</p>

          {response.results.length > 0 ? (
            <section className="result-section">
              <div className="result-list">
                {response.results.map(
                  (item) => (
                    <article
                      className="result-card"
                      key={item.url}
                    >
                      <strong>
                        {item.title}
                      </strong>

                      <button
                        type="button"
                        className="result-url-button"
                        onClick={() => {
                          void onOpenUrl(
                            item.url,
                          );
                        }}
                      >
                        {item.url}
                      </button>

                      <div className="result-actions">
                        <button
                          type="button"
                          className={
                            "result-action-button "
                            + "primary-result-action"
                          }
                          onClick={() => {
                            void onOpenUrl(
                              item.url,
                            );
                          }}
                        >
                          Open page ↗
                        </button>

                        <button
                          type="button"
                          className="result-action-button"
                          onClick={() => {
                            void onOpenUrl(
                              item.url,
                            );
                          }}
                        >
                          Learn more
                        </button>
                      </div>
                    </article>
                  ),
                )}
              </div>
            </section>
          ) : null}
        </div>
      ) : (
        <div className="empty-response">
          <div className="empty-icon">
            ◌
          </div>

          <p>
            Enter a request to get started.
          </p>
        </div>
      )}
    </article>
  );
}
