import fs from "fs";
import path from "path";
import https from "https";

// Usage: node scripts/fetch-product-images.mjs <UNSPLASH_ACCESS_KEY>
const UNSPLASH_ACCESS_KEY = process.argv[2] || process.env.UNSPLASH_ACCESS_KEY;

if (!UNSPLASH_ACCESS_KEY) {
  console.error("Error: Please provide an Unsplash Access Key.");
  console.error("Usage: node scripts/fetch-product-images.mjs <UNSPLASH_ACCESS_KEY>");
  process.exit(1);
}

const CATALOGUE_PATH = path.join(
  process.cwd(),
  "packages",
  "contracts",
  "src",
  "catalogue.generated.json",
);
const PUBLIC_PRODUCTS_PATH = path.join(process.cwd(), "apps", "storefront", "public", "products");

if (!fs.existsSync(PUBLIC_PRODUCTS_PATH)) {
  fs.mkdirSync(PUBLIC_PRODUCTS_PATH, { recursive: true });
}

console.log("Loading catalogue...");
const catalogue = JSON.parse(fs.readFileSync(CATALOGUE_PATH, "utf8"));
const products = Object.values(catalogue.products);

const missingImages = products.filter((p) => !p.imageUrl);
console.log(
  `Found ${missingImages.length} products missing images out of ${products.length} total.`,
);

// To avoid hitting API rate limits immediately (Unsplash demo allows 50/hour),
// we will just do a batch of 10 for demonstration. You can remove the slice to do more.
const batch = missingImages.slice(0, 10);
console.log(`Processing a batch of ${batch.length} products to respect API limits...`);

const delay = (ms) => new Promise((res) => setTimeout(res, ms));

async function fetchUnsplashImage(query) {
  return new Promise((resolve, reject) => {
    const url = `https://api.unsplash.com/search/photos?query=${encodeURIComponent(query)}&per_page=1&orientation=squarish&client_id=${UNSPLASH_ACCESS_KEY}`;

    https
      .get(url, (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          try {
            if (res.statusCode === 200) {
              const json = JSON.parse(data);
              if (json.results && json.results.length > 0) {
                // Get the raw URL and append size parameters for 1254x1254
                const rawUrl = json.results[0].urls.raw;
                resolve(`${rawUrl}&w=1254&h=1254&fit=crop`);
              } else {
                resolve(null); // No image found
              }
            } else {
              reject(new Error(`API Error: ${res.statusCode} ${data}`));
            }
          } catch (e) {
            reject(e);
          }
        });
      })
      .on("error", reject);
  });
}

async function downloadImage(url, destPath) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(destPath);
    https
      .get(url, (response) => {
        response.pipe(file);
        file.on("finish", () => {
          file.close(resolve);
        });
      })
      .on("error", (err) => {
        fs.unlink(destPath, () => {});
        reject(err);
      });
  });
}

async function main() {
  for (const product of batch) {
    const slug = product.slug;
    const name = product.name;
    const destPath = path.join(PUBLIC_PRODUCTS_PATH, `${slug}.jpg`);

    // Convert slug to a searchable query (e.g., "organic-baby-spinach" -> "organic baby spinach food")
    const query = name + " food ingredients";

    console.log(`Fetching image for: ${name} (${slug})`);
    try {
      const imageUrl = await fetchUnsplashImage(query);
      if (imageUrl) {
        console.log(`  -> Found image, downloading...`);
        await downloadImage(imageUrl, destPath);
        console.log(`  -> Saved to ${destPath}`);
      } else {
        console.log(`  -> No suitable image found on Unsplash for: ${name}`);
      }
    } catch (e) {
      console.error(`  -> Error processing ${name}:`, e.message);
    }

    // Sleep to respect API rate limits (1 request per second)
    await delay(1000);
  }

  console.log(
    "Batch complete! Run the script again to process the next batch (or update the script to process more at once).",
  );
  console.log(
    "Note: Remember to update the 'imageUrl' property in your catalogue data (or regenerate it) if your application relies on it.",
  );
}

main().catch(console.error);
