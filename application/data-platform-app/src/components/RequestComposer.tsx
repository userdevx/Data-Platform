import AttachmentPicker from "./AttachmentPicker";


export type RequestComposerProps = {
  displayName: string;
  requestText: string;
  attachmentPaths: string[];
  runtimeStatus: string;

  onRequestChange: (
    value: string,
  ) => void;

  onAttachmentChange: (
    value: string[],
  ) => void;

  onAsk: () => void;
};


export default function RequestComposer({
  displayName,
  requestText,
  attachmentPaths,
  runtimeStatus,
  onRequestChange,
  onAttachmentChange,
  onAsk,
}: RequestComposerProps) {
  return (
    <>
      <label
        className="field-label"
        htmlFor="request-input"
      >
        Ask {displayName}
      </label>

      <div className="compact-composer">
        <div className="compact-composer-row">
          <AttachmentPicker
            attachmentPaths={
              attachmentPaths
            }
            disabled={
              runtimeStatus === "thinking"
            }
            onChange={
              onAttachmentChange
            }
          />

          <textarea
            id="request-input"
            className={
              "request-input "
              + "compact-composer-input"
            }
            placeholder={
              `Ask ${displayName}...`
            }
            value={requestText}
            onChange={(event) => {
              onRequestChange(
                event.target.value,
              );
            }}
            onKeyDown={(event) => {
              if (
                (
                  event.ctrlKey
                  || event.metaKey
                )
                && event.key === "Enter"
              ) {
                onAsk();
              }
            }}
          />
        </div>
      </div>
    </>
  );
}
