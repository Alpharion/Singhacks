import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const schemasDir = path.join(root, "schemas");
const manifest = JSON.parse(
  fs.readFileSync(path.join(root, "contract-manifest.json"), "utf8"),
);

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);

for (const filename of fs.readdirSync(schemasDir).sort()) {
  if (!filename.endsWith(".schema.json")) continue;
  const schema = JSON.parse(fs.readFileSync(path.join(schemasDir, filename), "utf8"));
  ajv.addSchema(schema);
}

let failures = 0;
const loadedFixtures = new Map();
for (const entry of manifest) {
  const fixturePath = path.join(root, entry.fixture);
  const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
  loadedFixtures.set(entry.fixture, fixture);
  const validate = ajv.getSchema(entry.schema);
  if (!validate) {
    console.error(`MISSING SCHEMA ${entry.schema}`);
    failures += 1;
    continue;
  }
  if (!validate(fixture)) {
    console.error(`INVALID ${entry.fixture}`);
    console.error(ajv.errorsText(validate.errors, { separator: "\n  " }));
    failures += 1;
    continue;
  }
  console.log(`VALID ${entry.fixture}`);
}

function semanticCheck(condition, message) {
  if (condition) {
    console.log(`CONSISTENT ${message}`);
    return;
  }
  console.error(`INCONSISTENT ${message}`);
  failures += 1;
}

const plan = loadedFixtures.get("fixtures/selected-plan.json");
const plannedMeals = plan.foodAllocations.reduce((sum, item) => sum + item.quantity, 0);
const plannedFoodDrops = plan.foodAllocations.reduce(
  (sum, item) => sum + BigInt(item.lineTotalDrops),
  0n,
);
semanticCheck(plannedMeals === plan.totalMeals, "selected plan meal total");
semanticCheck(plannedFoodDrops === BigInt(plan.foodCostDrops), "selected plan food cost");
semanticCheck(
  plannedFoodDrops + BigInt(plan.deliveryCostDrops) === BigInt(plan.totalCostDrops),
  "selected plan grand total",
);

const intent = loadedFixtures.get("fixtures/purchase-intent.json");
const requirement = loadedFixtures.get("fixtures/payment-requirement.json").accepts[0];
semanticCheck(intent.amountDrops === requirement.amount, "purchase intent matches x402 amount");
semanticCheck(intent.payTo === requirement.payTo, "purchase intent matches x402 recipient");
semanticCheck(intent.invoiceId === requirement.extra.invoiceId, "purchase intent matches x402 invoice");
semanticCheck(intent.network === requirement.network, "purchase intent matches x402 network");

const run = loadedFixtures.get("fixtures/agent-run.json");
const reservedMeals = run.reservations.reduce((sum, item) => sum + item.quantity, 0);
const reservationDrops = run.reservations.reduce(
  (sum, item) => sum + BigInt(item.paymentReceipt.amountDrops),
  0n,
);
const deliveryDrops = run.deliveryBookings.reduce(
  (sum, item) => sum + BigInt(item.paymentReceipt.amountDrops),
  0n,
);
semanticCheck(reservedMeals === run.goal.mealCount, "fulfilled run reserves requested meals");
semanticCheck(reservationDrops === BigInt(run.spend.foodDrops), "reservation receipts match food spend");
semanticCheck(deliveryDrops === BigInt(run.spend.deliveryDrops), "booking receipts match delivery spend");
semanticCheck(
  reservationDrops + deliveryDrops === BigInt(run.spend.totalDrops),
  "payment receipts match total spend",
);
semanticCheck(
  BigInt(run.spend.totalDrops) + BigInt(run.spend.remainingDrops) ===
    BigInt(run.goal.maxTotalSpendDrops),
  "spend and remaining budget reconcile",
);
semanticCheck(
  run.events.every((event, index) => event.sequence === index + 1),
  "agent event sequence is contiguous",
);

if (failures > 0) process.exit(1);
console.log(`Validated ${manifest.length} contract fixtures and semantic invariants.`);
