import readline from "readline/promises";
import { stdin as input, stdout as output } from "process";
import { runAgent } from "./intelligence/agents/mainAgent";

const rl = readline.createInterface({ input, output });

async function main() {
  console.log("Data Platform Intelligence Agent");
  console.log("Type 'exit' to stop.\n");

  while (true) {
    const userInput = await rl.question("You: ");

    if (userInput.trim().toLowerCase() === "exit") {
      break;
    }

    const decision = await runAgent({
      contactName: "Data Engineer",
      description: "Data Platform builder",
      userInput,
    });

    console.log("\nAgent Decision:");
    console.log(JSON.stringify(decision, null, 2));
    console.log();
  }

  rl.close();
}

main();
