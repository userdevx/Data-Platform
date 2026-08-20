import { open } from "@tauri-apps/plugin-dialog";

type AttachmentPickerProps = {
  attachmentPaths: string[];
  disabled?: boolean;
  onChange: (paths: string[]) => void;
};

function getFileName(path: string): string {
  const normalizedPath = path
    .split("\\")
    .join("/");

  const parts = normalizedPath
    .split("/")
    .filter((part) => part.length > 0);

  if (parts.length === 0) {
    return path;
  }

  return parts[parts.length - 1];
}

export default function AttachmentPicker({
  attachmentPaths,
  disabled = false,
  onChange,
}: AttachmentPickerProps) {
  async function selectFiles(): Promise<void> {
    const selected = await open({
      multiple: true,
      directory: false,
      filters: [
        {
          name: "Photos and files",
          extensions: [
            "png",
            "jpg",
            "jpeg",
            "webp",
            "gif",
            "bmp",
            "pdf",
            "txt",
            "md",
            "json",
            "csv",
            "docx",
          ],
        },
      ],
    });

    if (!selected) {
      return;
    }

    const paths = Array.isArray(selected)
      ? selected
      : [selected];

    const cleanPaths = paths.filter(
      (path): path is string =>
        typeof path === "string"
        && path.trim().length > 0,
    );

    onChange([
      ...attachmentPaths,
      ...cleanPaths.filter(
        (path) => !attachmentPaths.includes(path),
      ),
    ]);
  }

  return (
    <>
      <button
        type="button"
        className="composer-plus-button"
        aria-label="Add photos or files"
        title="Add photos or files"
        disabled={disabled}
        onClick={() => {
          void selectFiles();
        }}
      >
        <span aria-hidden="true">+</span>
      </button>

      {attachmentPaths.length > 0 ? (
        <div className="composer-file-list">
          {attachmentPaths.map((path) => (
            <span
              className="composer-file-chip"
              key={path}
              title={path}
            >
              <span className="composer-file-name">
                {getFileName(path)}
              </span>

              <button
                type="button"
                aria-label={`Remove ${getFileName(path)}`}
                disabled={disabled}
                onClick={() => {
                  onChange(
                    attachmentPaths.filter(
                      (currentPath) =>
                        currentPath !== path,
                    ),
                  );
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : null}
    </>
  );
}
