// Claude Desktop runs this (Node, bundled with the app). It starts the real MCP server, mcp_server/server.py, inside the WSL
// distribution and passes the stdio JSON-RPC stream through unchanged in both directions.
const { spawn } = require("child_process");

const distro = process.env.DPL_DISTRO || "";          // empty: the default WSL distribution
const repo = process.env.DPL_REPO_WSL;
const python = process.env.DPL_PYTHON || "/opt/de/bin/python";
const role = process.env.DPL_SNOWFLAKE_ROLE || "DPL_FINANCE_ANALYST";  // for target snowflake: reads the marts only

if (!repo) {
  process.stderr.write("dataplatformlab: set the repository path inside WSL (DPL_REPO_WSL)\n");
  process.exit(1);
}

const child = spawn(
  "wsl.exe",
  [...(distro ? ["-d", distro] : []), "--cd", repo, "--exec", "env", "PATH=/opt/de/bin:/usr/local/bin:/usr/bin:/bin",
   `DPL_SNOWFLAKE_ROLE=${role}`, python, "mcp_server/server.py"],
  { stdio: ["pipe", "pipe", "inherit"], windowsHide: true }
);

process.stdin.pipe(child.stdin);
child.stdout.pipe(process.stdout);
child.on("error", (err) => {
  process.stderr.write(`dataplatformlab: could not start wsl.exe: ${err.message}\n`);
  process.exit(1);
});
child.on("exit", (code) => process.exit(code ?? 0));
process.on("SIGTERM", () => child.kill());
