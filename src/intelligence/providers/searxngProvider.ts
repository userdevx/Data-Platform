export type SearchResult = {
  title: string;
  url: string;
  snippet: string;
  provider: string;
};

export async function searchSearxng(query: string): Promise<SearchResult[]> {
  const baseUrl = process.env.SEARXNG_URL ?? "http://localhost:8080";
  const url = `${baseUrl}/search?q=${encodeURIComponent(query)}&format=json`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`SearXNG search failed with status ${response.status}`);
  }

  const data = await response.json();

  return (data.results ?? []).slice(0, 8).map((result: any) => ({
    title: result.title ?? "Untitled Result",
    url: result.url ?? "",
    snippet: result.content ?? "",
    provider: "searxng",
  })).filter((result: SearchResult) => result.url);
}
