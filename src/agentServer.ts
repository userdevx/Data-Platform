import express from "express";
import path from "path";
import { runAgent } from "./intelligence/agents/mainAgent";

const app = express();
const PORT = 3333;

app.use(express.json());
app.use("/agent-ui", express.static(path.join(process.cwd(), "app_ui", "agent")));

app.post("/agent/message", async (req, res) => {
  try {
    const userInput = String(req.body.userInput ?? "");

    if (!userInput.trim()) {
      return res.status(400).json({
        ok: false,
        error: "userInput is required",
      });
    }

    const decision = await runAgent({
      contactName: "Data Engineer",
      description: "Data Platform software UI user",
      userInput,
    });

    return res.json({
      ok: true,
      decision,
    });
  } catch (error) {
    return res.status(500).json({
      ok: false,
      error: error instanceof Error ? error.message : "Unknown server error",
    });
  }
});

app.get("/agent/health", (_req, res) => {
  res.json({
    ok: true,
    service: "Data Platform Intelligence Agent",
  });
});

app.listen(PORT, () => {
  console.log(`Intelligence Agent API running on http://localhost:${PORT}`);
});
