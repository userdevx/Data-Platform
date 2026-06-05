import { getSearchProvider } from "../providers/providerRouter";
import { searchSearxng, type SearchResult } from "../providers/searxngProvider";
import { searchDuckDuckGoHtml } from "../providers/duckduckgoHtmlProvider";

export async function internetSearch(query: string): Promise<SearchResult[]> {
  const searchQuery = query.trim();

  if (!searchQuery) {
    return [];
  }

  const provider = getSearchProvider();

  try {
    if (provider === "searxng") {
      return await searchSearxng(searchQuery);
    }

    return await searchDuckDuckGoHtml(searchQuery);
  } catch {
    return await searchDuckDuckGoHtml(searchQuery);
  }
}
