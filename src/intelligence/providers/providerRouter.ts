export type SearchProvider = "searxng" | "duckduckgo_html";

export function getSearchProvider(): SearchProvider {
  const provider = process.env.SEARCH_PROVIDER ?? "searxng";

  if (provider === "duckduckgo_html") {
    return "duckduckgo_html";
  }

  return "searxng";
}
