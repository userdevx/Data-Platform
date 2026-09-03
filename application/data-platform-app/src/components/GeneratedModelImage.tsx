type GeneratedModelImageProps = {
  response: unknown;
};


function asRecord(
  value: unknown,
): Record<string, unknown> | null {
  if (
    typeof value !== "object"
    || value === null
    || Array.isArray(value)
  ) {
    return null;
  }

  return value as Record<
    string,
    unknown
  >;
}


function stringValue(
  value: unknown,
): string {
  return (
    typeof value === "string"
      ? value
      : ""
  );
}


function getImageDataUrl(
  response: unknown,
): string | null {
  const responseRecord =
    asRecord(response);

  if (!responseRecord) {
    return null;
  }

  const raw = asRecord(
    responseRecord.raw,
  );

  if (!raw) {
    return null;
  }

  // Automatic Intelligence Runtime response:
  //
  // raw.data.output.data_url

  const data = asRecord(
    raw.data,
  );

  const output = asRecord(
    data?.output,
  );

  const automaticDataUrl =
    stringValue(
      output?.data_url,
    );

  if (
    automaticDataUrl.startsWith(
      "data:image/",
    )
  ) {
    return automaticDataUrl;
  }

  // Manual model-selection response:
  //
  // raw.metadata.image_data_url

  const metadata = asRecord(
    raw.metadata,
  );

  const manualDataUrl =
    stringValue(
      metadata?.image_data_url,
    );

  if (
    manualDataUrl.startsWith(
      "data:image/",
    )
  ) {
    return manualDataUrl;
  }

  return null;
}


export default function GeneratedModelImage({
  response,
}: GeneratedModelImageProps) {
  const imageDataUrl =
    getImageDataUrl(
      response,
    );

  if (!imageDataUrl) {
    return null;
  }

  return (
    <figure
      className="generated-model-image"
      style={{
        margin: "1rem 0 0",
        width: "100%",
      }}
    >
      <img
        src={imageDataUrl}
        alt="Generated output"
        style={{
          borderRadius: "12px",
          display: "block",
          height: "auto",
          maxHeight: "640px",
          maxWidth: "100%",
          objectFit: "contain",
        }}
      />
    </figure>
  );
}
