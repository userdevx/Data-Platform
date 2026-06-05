export type ScrapedPage = {
  url: string;
  title: string;
  text: string;
};

function cleanText(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<nav[\s\S]*?<\/nav>/gi, " ")
    .replace(/<footer[\s\S]*?<\/footer>/gi, " ")
    .replace(/<aside[\s\S]*?<\/aside>/gi, " ")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractTitle(html: string): string {
  const match = html.match(/<title>([\s\S]*?)<\/title>/i);
  return match ? cleanText(match[1]) : "Untitled Source";
}

export async function scrapePage(url: string): Promise<ScrapedPage> {
  const parsed = new URL(url);

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Invalid source URL.");
  }

  const response = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 DataPlatformPaige/1.0",
    },
  });

  if (!response.ok) {
    throw new Error(`Page fetch failed with status ${response.status}`);
  }

  const html = await response.text();

  return {
    url,
    title: extractTitle(html),
    text: cleanText(html).slice(0, 4000),
  };
}
