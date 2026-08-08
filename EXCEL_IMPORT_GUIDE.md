# Yuva Store — Excel Import / Export Guide (for Store Owners)

This guide explains how to use the **Export Excel** and **Import Excel** buttons in your store admin, step by step. No technical knowledge needed.

---

## What is this for?

- **Export Excel** = download a copy of all your store data (categories, brands, products, etc.) into one Excel file. It also acts as the **template** you fill in.
- **Import Excel** = upload a filled-in Excel file to add or update lots of products at once (much faster than adding one by one).

---

## Step 1 — Download the file (to see the structure)

1. Log in to your admin panel.
2. Open **Store → Products**.
3. Click **⬇ Export Excel**.
4. The file `yuva_store_data.xlsx` downloads. Open it.

### How the file is arranged

Every sheet (tab) in the file has the same 3-row layout:

- **Row 1** = help / notes for that column. **Do not delete this row.**
- **Row 2** = the column headings. **Do not rename, delete, or move these.**
- **Row 3 onwards** = where you write your own data. Each new row = one new item.

The file contains **8 sheets (tabs)**, always in this order:

1. **Categories** – product groups (e.g. Laptops, Accessories)
2. **Brands** – manufacturers (e.g. HP, Dell, Apple)
3. **UsageTags** – usage labels (e.g. Gaming, Coding, School)
4. **Products** – the actual products (most important sheet)
5. **ProductVariants** – sizes/configs of a product (e.g. 8GB vs 16GB RAM)
6. **Reviews** – customer reviews shown on the site
7. **Coupons** – discount codes
8. **SiteConfig** – your store settings (shipping fee, tax, COD, WhatsApp number)

---

## Step 2 — Understand the simple rules

| Rule | Meaning |
|---|---|
| Leave **`id` empty** | Creates a **new** item |
| Put an existing **`id`** | **Updates** that item |
| Leave `slug` empty | The website address-name is created automatically for you |
| Empty rows | Are skipped automatically — safe to leave blank space |
| Problem rows | Are skipped with a warning — the rest still import |
| Sheet order matters | Products need Brands & Categories to exist first |

---

## Step 3 — Fill each sheet

### 1. Categories (product groups)

Columns: `id` | `name` | `slug` | `is_featured` | `image_url`

| Column | What to type |
|---|---|
| `name` | **Required.** The category name, e.g. `Laptops` |
| `slug` | Leave blank (auto-created) |
| `is_featured` | `TRUE` (show on homepage) or `FALSE` |
| `image_url` | Optional. A direct image link or Google Drive link |

Example:
```
(blank) | Laptops | (blank) | TRUE | https://...image link... 
```

> You can also create categories by hand in **Store → Categories → Add** — no Excel needed for one category.

---

### 2. Brands (manufacturers)

Columns: `id` | `name` | `slug`

| Column | What to type |
|---|---|
| `name` | **Required.** e.g. `HP` |
| `slug` | Leave blank (auto-created) |

Example: `(blank) | HP | (blank)`

---

### 3. UsageTags (labels)

Columns: `id` | `name` | `slug` | `icon`

| Column | What to type |
|---|---|
| `name` | **Required.** e.g. `Gaming` |
| `slug` | Leave blank (auto-created) |
| `icon` | Optional. A small symbol name, e.g. `gamepad`, `code`, `monitor` |

Example: `(blank) | Gaming | (blank) | gamepad`

---

### 4. Products (the most important sheet)

Columns: `id` | `title` | `slug` | `sku` | `brand_slug` | `category_slug` | `condition` | `price` | `original_price` | then specifications | then description/warranty | then Yes/No toggles | `usage_tag_slugs` | `image_urls`

Plain-English explanation of the tricky ones:

| Column | What it means / what to type |
|---|---|
| `title` | **Required.** Product name, e.g. `HP Pavilion 15` |
| `sku` | **Required.** Your own unique code for this product, e.g. `HP-PAV-15`. Never reuse the same code for two products. |
| `slug` | Leave blank (auto-created). |
| `brand_slug` | **Required.** Must be an existing Brand (use the exact `name` from the Brands sheet in lower-case, e.g. `hp`). |
| `category_slug` | **Required.** Must be an existing Category (e.g. `laptops`). |
| `condition` | **Required.** Pick one of exactly these 4 words: `like_new` (like new) · `excellent` · `good` · `value` (fair/cheap) |
| `price` | **Required.** Selling price, e.g. `27999.00` |
| `original_price` | Optional. The older/higher price (shows a discount on the site). |
| `processor`, `ram`, `storage`, `display`, `graphics`, `operating_system`, `battery`, `weight`, `ports`, `wifi`, `bluetooth` | The product's specifications. Type them in plain words, e.g. `16GB DDR4`, `512GB NVMe SSD`, `Windows 11 Pro`. |
| `description` | A paragraph describing the product. |
| `highlights` | Top selling points, **one per line** (press Enter to make a new line inside the cell). |
| `refurbishment_summary` / `refurbishment_points` | Quality-check text, e.g. `40+ Quality Checks Passed`. |
| `warranty_summary` / `warranty_details` | Warranty text, one point per line. |
| `service_centers`, `warranty_period`, `return_policy` | Small trust texts, e.g. `350+ Service Centers`, `6 Months Warranty`, `14 Days Return`. |
| `is_new_arrival`, `is_best_seller`, `is_trending`, `is_best_deal`, `is_active` | **Yes/No switches.** Type `TRUE` or `FALSE`. (`is_active` = is this product visible on the site?) |
| `usage_tag_slugs` | Existing tags for this product, separated by commas, e.g. `gaming,coding`. |
| `image_urls` | **One or more image links** (direct links, CDN links, or Google Drive share links). Separate multiple links with a **comma**, or put each on its own line. **The first link = the main image shown on the site.** |

Example (single row — type it all on one line in the sheet):
```
(blank) | HP Pavilion 15 | (blank) | HP-PAV-15 | hp | laptops | good | 27999.00 | 34000.00 |
Intel Core i5 11th Gen | 8GB DDR4 | 512GB NVMe SSD | 15.6-inch Full HD | Intel Iris Xe |
Windows 11 Home | 3-Cell 41Wh | 1.75 kg | USB-A x2, Type-C x1, HDMI x1 | Wi-Fi 6 | Bluetooth 5.1 |
Everyday performance laptop in great condition. |
Intel i5 11th Gen
8GB RAM & 512GB SSD |
40+ Quality Checks Passed | Display Checked
Battery Health > 90% |
6 Months Warranty Included | Covers internal components and adapter replacement. |
350+ Service Centers | 6 Months Warranty | 14 Days Return |
FALSE | TRUE | FALSE | FALSE | TRUE | business,coding |
https://drive.google.com/file/d/1W5xzHAfBIWVZRnPNepp7kpBLDJoCiMBe/view?usp=sharing, https://drive.google.com/file/d/1bgGAsruTtcGVU5VTJ-FqHOCaCgZSOhaQ/view?usp=sharing
```

> To **update** an existing product: keep its `id` as it is, or simply reuse its `sku` — the import will update it instead of making a duplicate.

---

### 5. ProductVariants (configs of a product)

Columns: `id` | `product_sku` | `processor` | `ram` | `storage` | `stock` | `price_override`

| Column | What it means |
|---|---|
| `product_sku` | **Required.** The `sku` of the product this variant belongs to (must exist). |
| `processor` | Optional. e.g. `Intel Core i7 10th Gen`. |
| `ram` | **Required.** e.g. `16GB DDR4` |
| `storage` | **Required.** e.g. `512GB NVMe SSD` |
| `stock` | How many pieces you have in stock (a whole number, e.g. `8`). |
| `price_override` | Extra rupees added on top of the base price for this variant. `0.00` = same as base price. |

Example: `(blank) | HP-ELITE-840G7 | Intel Core i7 10th Gen | 16GB DDR4 | 512GB NVMe SSD | 8 | 0.00`

You can add **multiple rows** for the same product (e.g. a 16GB version and a 32GB version).

---

### 6. Reviews

Columns: `id` | `product_sku` | `user_name` | `rating` | `comment` | `location` | `is_featured`

| Column | What it means |
|---|---|
| `product_sku` | **Required.** The product this review is for. |
| `user_name` | **Required.** Customer name. |
| `rating` | A number from `1` to `5`. |
| `comment` | **Required.** The review text. |
| `location` | Optional, e.g. `Bengaluru` |
| `is_featured` | `TRUE` = show this review prominently. |

Example: `(blank) | HP-ELITE-840G7 | Ananya Reddy | 5 | Super lightweight and powerful laptop! | Bengaluru | TRUE`

---

### 7. Coupons (discount codes)

Columns: `id` | `code` | `discount_type` | `value` | `min_order_value` | `valid_from` | `valid_to` | `active` | `usage_limit` | `uses_count`

| Column | What it means |
|---|---|
| `code` | **Required.** The code customers type, e.g. `WELCOME10`. Unique. |
| `discount_type` | `percentage` (a % off) or `fixed` (a fixed rupee amount off). |
| `value` | The number: `10` for 10%, or `200` for ₹200 off. |
| `min_order_value` | Minimum order amount to use it. `0` = no minimum. |
| `valid_from` / `valid_to` | Dates in the format `2026-01-01 00:00` |
| `active` | `TRUE` / `FALSE` |
| `usage_limit` | Max number of times it can be used (e.g. `100`). |
| `uses_count` | Read-only — how many times it was used. Don't type anything. |

Example: `(blank) | WELCOME10 | percentage | 10 | 1000 | 2026-01-01 00:00 | 2026-12-31 23:59 | TRUE | 100 | (blank)`

---

### 8. SiteConfig (your store settings)

Columns: `id` | `shipping_fee` | `free_shipping_threshold` | `cod_surcharge_percentage` | `tax_percentage` | `whatsapp_number`

| Column | What it means |
|---|---|
| `shipping_fee` | Flat delivery charge, e.g. `0.00` or `100.00` |
| `free_shipping_threshold` | Order amount above which delivery is free, e.g. `1000.00` (`0.00` = no free shipping). |
| `cod_surcharge_percentage` | The Cash-on-Delivery service fee %, e.g. `2.00`. |
| `tax_percentage` | GST %, e.g. `18.00`. **If you want GST shown, this must not be `0`.** |
| `whatsapp_number` | Your WhatsApp number with country code and **no + sign**, e.g. `919709888456` |

There is only **one** settings row — editing it just updates your settings.

---

## Step 4 — Import the file

1. Go to **Store → Products**.
2. Click **⬆ Import Excel**.
3. Drag your `.xlsx` file into the box (or click to choose it).
4. Click **Start Import**. Wait for the "Importing…" message to finish.

### Reading the result

After importing you'll see a summary at the top, for example:

> Import complete — 3 Product created · 2 Product updated · 1 rows skipped (empty) · 0 error(s)

- **created** = new items added
- **updated** = existing items changed
- **skipped** = rows ignored (usually blank)
- **error(s)** = rows with problems. Each problem is shown as a yellow warning message, e.g. `[Products] SKU='XYZ': brand slug 'abc' not found`. Fix those rows and import again — the good rows won't be duplicated.

---

## Step 5 — Manual vs Excel (when to use which)

- **Excel** is best for **bulk work** — many products, stock levels, prices, or images at once, or when your team uses a spreadsheet.
- **Manual (in the admin)** is easiest for **one-off changes** — Categories, Brands, UsageTags, and individual Products all have Add/Edit forms with image and variant uploads built in.

---

## Bonus — Let an AI assistant build the Excel file for you

You can ask an AI (ChatGPT, Claude, Gemini, etc.) to fill the file. Attach your downloaded `yuva_store_data.xlsx` and paste this:

> You are an e-commerce data assistant. I attached the Excel file `yuva_store_data.xlsx` exported from my store. It has 8 sheets; Row 1 is help text and Row 2 is the column headings.
>
> Strict rules:
> 1. Keep all 8 sheets, their names, Row 1 and Row 2 exactly as they are. Never rename or reorder columns.
> 2. Add my new products as new rows in the **Products** sheet, starting just below the last data row. Do not change other sheets unless I ask.
> 3. Follow the exact column order. Leave `id` and `slug` blank. Create a unique `sku` for each product.
> 4. Use only brand/category/tag names that already exist in my file's Brands, Categories, and UsageTags sheets. If something is missing, tell me — do not invent it.
> 5. `condition` must be one of exactly these words: like_new, excellent, good, value.
> 6. Prices with 2 decimals (e.g. 27999.00). Copy sensible warranty/refurbishment defaults from existing rows.
> 7. Put my image links in `image_urls`, separated by commas — first link is the main image.
> 8. Yes/No columns as TRUE or FALSE.
> 9. Return the finished `.xlsx` file with the same layout so I can import it directly.
>
> New products to add:
> [paste your product details here — names, specs, prices, condition, image links, etc.]

---

*Tip: always keep a copy of the exported file before editing it, so you always have a safe backup.*
