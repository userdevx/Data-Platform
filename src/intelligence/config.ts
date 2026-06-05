import "dotenv/config";

export const CONFIG = {
  openaiApiKey: process.env.OPENAI_API_KEY,
  openaiModel: process.env.OPENAI_MODEL ?? "gpt-4.1-mini",
};

if (!CONFIG.openaiApiKey) {
  throw new Error("OPENAI_API_KEY is missing from .env");
}
