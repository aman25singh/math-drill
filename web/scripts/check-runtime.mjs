const [major, minor] = process.versions.node.split(".").map(Number);
if (major !== 24 || minor < 21) {
  throw new Error(
    `Math Drill builds require Node 24.21.0 or a newer Node 24 patch. Running ${process.version}. Select the runtime in .node-version before building.`,
  );
}
console.log(`Building with Node ${process.versions.node}`);
