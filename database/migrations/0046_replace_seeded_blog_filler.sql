-- 0043_replace_seeded_blog_filler: retire generated demo posts and publish a
-- small, useful editorial library in seeded environments.
--
-- The old development catalogue crossed 50 subjects with three title templates,
-- producing 150 near-duplicate posts on top of 50 very short library entries.
-- Those records use reserved seed id prefixes, so this cleanup never touches a
-- customer submission or an article created through the CMS.

PRAGMA foreign_keys = ON;

DELETE FROM search_content
WHERE entity_type = 'article'
  AND (
    entity_id = 'art_millets'
    OR entity_id LIKE 'art_library_%'
    OR entity_id LIKE 'art_expansion_%'
    OR entity_id LIKE 'art_guide_%'
  );

DELETE FROM articles
WHERE id = 'art_millets'
   OR id LIKE 'art_library_%'
   OR id LIKE 'art_expansion_%'
   OR id LIKE 'art_guide_%';

-- A plain scratch table, not TEMP: D1 refuses `CREATE TEMP TABLE` outright
-- (`not authorized: SQLITE_AUTH`), which fails the whole migration and blocks
-- every deploy. Local SQLite allows temporary tables, so `pnpm db:validate`
-- passes and the problem only shows up against the real database. It is
-- dropped at the end of this file either way, so nothing is left behind.
CREATE TABLE curated_blog_articles (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  slug TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  reading_minutes INTEGER NOT NULL,
  published_at TEXT NOT NULL,
  seo_title TEXT NOT NULL,
  seo_description TEXT NOT NULL,
  keywords TEXT NOT NULL,
  image_alt TEXT NOT NULL,
  content_json TEXT NOT NULL
);

INSERT INTO curated_blog_articles VALUES
  (
    'art_guide_organic_label',
    'How to read an organic food label in India',
    'how-to-read-organic-food-label-india',
    'A five-minute label check that separates verifiable organic certification from attractive but vague packaging.',
    7,
    '2026-07-31T09:00:00Z',
    'How to read an organic food label in India',
    'Learn which marks, licence details, certification scope and batch information make an organic claim useful before you buy.',
    'organic label India Jaivik Bharat NPOP PGS certification buying guide',
    'Certified organic is a claim you should be able to verify, not a mood created by green packaging.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_organic_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'An organic label is useful only when it lets you answer three questions: who is making the claim, which certification system supports it, and whether the specific product you are holding is covered. Words such as natural, clean, farm fresh and residue conscious may describe an intention, but they are not substitutes for certification.',
            'In India, FSSAI recognises the NPOP and PGS-India certification systems for organic food. The official [FSSAI organic food guidance](https://fssai.gov.in/cms/standards-organic-food.php) explains the framework, while the Jaivik Bharat identity helps customers recognise certified products. Here is how to turn those marks into a practical buying check.'
          ))
        ),
        json_object(
          'id', 'blk_guide_organic_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'The five checks that matter',
            'items', json_array(
              json_object(
                'question', '1. Is there a recognised certification mark?',
                'answer', 'Look for the Jaivik Bharat mark and the FSSAI logo with a licence number on packaged certified organic food. Depending on the certification route, you may also see the India Organic mark for NPOP or the PGS-India Organic mark. A leaf illustration designed by the brand is not the same thing. If a marketplace page calls a product organic, the certification details should also be available in text rather than hidden in a lifestyle photograph.'
              ),
              json_object(
                'question', '2. Does the certificate cover this product and this operator?',
                'answer', 'A certificate is not a blanket badge for everything a farm, processor or seller handles. Check the named operator, covered products or scope, certification body or group, and validity period. A farm may have certified mangoes but also trade produce from elsewhere; a processor may be certified for grain handling but not every packaged mix. Ask for the current scope certificate when the listing is unclear.'
              ),
              json_object(
                'question', '3. Can the pack be traced to a batch?',
                'answer', 'Useful labels include a batch or lot number, packed-on or processing date, best-before information where applicable, net quantity and the responsible food business operator. These details do not prove farming practice by themselves, but they connect the pack to records that can be checked. A complaint without a batch number is harder to investigate; a seller that records lots can isolate a problem instead of making guesses about every pack.'
              ),
              json_object(
                'question', '4. Are the marketing claims more precise than the evidence?',
                'answer', 'Treat chemical-free, pesticide-free and 100 percent natural as separate claims that need their own explanation. Organic standards govern a production system; they do not promise that food is nutritionally superior, perfectly shaped or free from every environmental contaminant. Good sellers state what they verified and avoid turning certification into medical advice or an all-purpose purity claim.'
              ),
              json_object(
                'question', '5. What should you ask when buying loose produce?',
                'answer', 'Ask for the farm or producer-group name, certification system, current validity, and how certified stock is kept separate from conventional stock during collection and sale. A direct answer is more valuable than a long farm story. If the seller cannot connect the loose produce to a certified operator or lot, buy it on its visible quality and provenance, but do not pay an organic premium solely on trust.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_organic_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'A sensible check takes less than a minute once you know where to look: recognised mark, licence details, named operator, valid scope and batch identity. Save a photo of the label for pantry products you buy repeatedly. It gives you something concrete to compare when the supplier or packaging changes.',
            'True Grit product pages surface the farm and certification record alongside the food. If any record is missing, expired or too broad to support the product claim, ask us before ordering. The useful answer is evidence, not reassurance.'
          ))
        ),
        json_object(
          'id', 'blk_guide_organic_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Practise the label check', 'source', 'manual',
            'productSlugs', json_array('organic-alphonso-mangoes','organic-baby-spinach','sprouted-ragi-flour','wood-pressed-groundnut-oil'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'Certified organic is a claim you should be able to verify, not a mood created by green packaging.'
    )
  ),
  (
    'art_guide_produce_storage',
    'The 20-minute produce reset that prevents a week of waste',
    '20-minute-produce-storage-reset',
    'What to wash, what to keep dry and what to use first when a fresh produce order reaches your kitchen.',
    7,
    '2026-07-29T09:00:00Z',
    'A practical fresh produce storage reset',
    'Use a 20-minute unpacking routine to store leafy greens, herbs, fruit, roots and damaged produce with less waste.',
    'fresh produce storage leafy greens herbs fruit reduce food waste',
    'The best storage plan begins with an order of use, not a collection of containers.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_storage_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Most produce waste is decided on unpacking day. A wet spinach bunch is pushed behind a cabbage, one bruised mango disappears at the bottom of a bag, and every vegetable is treated as though it wants the same temperature and humidity. By the time a meal plan notices the problem, the most fragile food has already lost.',
            'Set a timer for twenty minutes when the order arrives. You are not meal-prepping the whole week. You are finding damage, removing trapped moisture, giving delicate items the right conditions and deciding what must be cooked first.'
          ))
        ),
        json_object(
          'id', 'blk_guide_storage_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'A five-step unpacking routine',
            'items', json_array(
              json_object(
                'question', '1. Empty every bag and make a use-first group',
                'answer', 'Put bruised fruit, split tomatoes, wilted greens and anything unusually ripe in one visible group. Separate produce with mould, slime, leaking rot or a fermented smell; do not let it touch sound food. A cosmetic mark belongs in tonight''s dinner, not automatically in the bin. The point is to make urgency visible before sturdy roots and pantry items hide it.'
              ),
              json_object(
                'question', '2. Keep leafy greens dry but not exposed',
                'answer', 'Remove ties, damaged leaves and any wet packing. If the leaves are gritty, wash in a bowl of cool water, lift them away from the settled soil and dry them thoroughly; otherwise, washing just before use is simpler. Wrap loosely in a clean dry cloth or absorbent paper and place in a container or bag with a little room. Check the cloth after a day and replace it if it is wet.'
              ),
              json_object(
                'question', '3. Treat herbs by the kind of stem they have',
                'answer', 'Coriander and mint often keep well with trimmed stems in a small jar of water, loosely covered in the refrigerator; remove leaves below the waterline and change cloudy water. Woody herbs prefer to stay dry and loosely wrapped. Whichever method you use, inspect the centre of the bunch. A tight elastic and one decaying stem can spoil leaves that looked fine from the outside.'
              ),
              json_object(
                'question', '4. Give ripening fruit its own zone',
                'answer', 'Mangoes, bananas, tomatoes and similar ripening produce are easier to manage when visible at room temperature until ready, then moved or eaten promptly. Keep them away from delicate greens when possible because ripening fruit releases ethylene, which can speed yellowing and ageing in sensitive produce. Never seal warm or damp fruit in an airtight box; trapped moisture turns a small bruise into decay.'
              ),
              json_object(
                'question', '5. Write a three-line cooking order',
                'answer', 'Line one is today or tomorrow: damaged-but-sound produce, herbs and very ripe fruit. Line two is the next few days: leafy greens, tender vegetables and ripe tomatoes. Line three is later: cabbage, gourds, roots and firm fruit. Put the note on the refrigerator or in the family chat. Planning perishability first is more effective than choosing seven ambitious recipes that use the same sturdy vegetables.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_storage_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Storage advice is never a guarantee because variety, harvest maturity, handling and refrigerator conditions differ. Inspect food instead of trusting a fixed number of days. Clean smell, sound texture and absence of decay matter more than a calendar copied from a generic chart.',
            'If something arrives below standard, photograph the product, label and outer packaging before trimming or cooking it. Keep the batch details and contact support promptly. That evidence helps distinguish delivery damage from normal ripening and lets the affected lot be checked.'
          ))
        ),
        json_object(
          'id', 'blk_guide_storage_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Fresh produce to plan first', 'source', 'manual',
            'productSlugs', json_array('organic-baby-spinach','organic-alphonso-mangoes'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'The best storage plan begins with an order of use, not a collection of containers.'
    )
  ),
  (
    'art_guide_pantry_sizes',
    'Buy less, eat better: a pantry sizing guide for Indian kitchens',
    'pantry-sizing-guide-indian-kitchens',
    'A realistic way to choose pack sizes for flour, pulses and cooking oil based on how your household actually cooks.',
    6,
    '2026-07-27T09:00:00Z',
    'A pantry sizing guide for Indian kitchens',
    'Choose practical pack sizes for flour, pulses and cooking oil using household consumption, climate and storage space.',
    'pantry planning pack size flour pulses cooking oil freshness',
    'The economical pack is the one you finish while the ingredient still tastes the way it should.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_pantry_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'A large pack can lower the price per kilogram and still be the expensive choice. Whole-grain flour loses aroma, cooking oil sits open near a hot stove, and a pulse bought for one recipe occupies the cupboard until nobody remembers its age. The waste is often gradual: food remains edible but becomes harder to cook or less enjoyable to eat.',
            'Instead of stocking an idealised pantry, measure the kitchen you actually run. One week of observation is enough to make a better first estimate, and a marker pen does more useful work than another matching storage jar.'
          ))
        ),
        json_object(
          'id', 'blk_guide_pantry_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Five decisions before choosing a pack size',
            'items', json_array(
              json_object(
                'question', '1. How many meals does this pack represent?',
                'answer', 'Start with your own recipes, not a universal serving chart. Note how much atta, rice, dal or oil goes into a usual meal, then multiply by how often that meal appears. If a 500 g bag of a speciality flour makes four breakfasts and you cook it twice a month, a larger bargain pack is probably not a bargain. Leave room for travel, eating out and the weeks when plans change.'
              ),
              json_object(
                'question', '2. Which foods lose quality fastest after opening?',
                'answer', 'Whole-grain and freshly milled flours deserve smaller, faster-moving packs because bran and natural oils are exposed to air after milling. Unrefined oils also benefit from protection from heat, light and repeated long storage. Whole dry pulses are more forgiving, but older beans can take longer to soften. Buy the smallest pack for slow-use aromatic or oily ingredients; use larger packs for staples with proven turnover.'
              ),
              json_object(
                'question', '3. Is the storage place cooler than the sales shelf?',
                'answer', 'A hot, humid kitchen changes the calculation. Keep dry foods airtight and away from the cooker, sink and direct sun. If refrigerator space is available, it can help protect whole-grain flour in warm weather; use a well-sealed container so the flour does not absorb moisture or odours, and let the amount you need lose its chill while still covered. Do not buy a sack that has no genuinely suitable home.'
              ),
              json_object(
                'question', '4. Can you track two open packs without mixing them?',
                'answer', 'Write the opened date and batch number on the container or keep the original label. Finish the older batch before adding a new one, rather than topping up indefinitely. Mixing makes age, allergens and complaint tracing harder to understand. Decant only when the container is clean and completely dry, and keep the label until the food is finished.'
              ),
              json_object(
                'question', '5. When does bulk buying make sense?',
                'answer', 'Bulk works when consumption is steady, the price difference is meaningful, storage is appropriate and the purchase does not crowd out variety. It can also work when neighbours intentionally split sealed packs at purchase. It makes less sense for a new ingredient, a seasonal enthusiasm or a product you are buying mainly to reach a delivery threshold. Test a smaller pack before committing cupboard space and money.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_pantry_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'For the next four weeks, write the opened date on every flour, pulse and oil pack. When each one finishes, you have your household''s real consumption rate. Choose the next pack to cover that interval with a modest buffer, not six imaginary months.',
            'A smaller active pantry makes changes easier to notice. You smell when a fresh oil is especially good, learn which pulse cooks reliably and buy enough flour to enjoy its aroma. That is a better return than saving a few rupees on food that spends a year fading in the cupboard.'
          ))
        ),
        json_object(
          'id', 'blk_guide_pantry_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Build a faster-moving pantry', 'source', 'manual',
            'productSlugs', json_array('sprouted-ragi-flour','himalayan-red-rajma','wood-pressed-groundnut-oil'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'The economical pack is the one you finish while the ingredient still tastes the way it should.'
    )
  ),
  (
    'art_guide_imperfect_produce',
    'Imperfect, ripe or spoiled? A practical produce triage guide',
    'imperfect-ripe-or-spoiled-produce-guide',
    'How to tell harmless variation from damage that needs quick cooking, a support claim or the compost bin.',
    7,
    '2026-07-25T09:00:00Z',
    'Imperfect, ripe or spoiled produce?',
    'Use sight, smell and texture to sort cosmetic variation, usable damage and clear spoilage in fresh produce deliveries.',
    'imperfect produce ripe spoiled bruised vegetables food waste delivery quality',
    'Ugly is not unsafe, and beautiful is not proof of freshness. Condition matters more than symmetry.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_triage_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Fresh produce is allowed to look alive. A mango can carry a sap mark, spinach leaves vary in size and a carrot may fork around a stone. Rejecting every variation wastes good food; accepting leaking, mouldy or heat-damaged produce excuses poor handling. Customers need a clearer line than supermarket perfection on one side and eat everything on the other.',
            'Use three groups: sound, use first, and do not use. Work with clean hands and good light, and judge the whole item rather than one dramatic photograph of a harmless scar.'
          ))
        ),
        json_object(
          'id', 'blk_guide_triage_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Five ways to make the call',
            'items', json_array(
              json_object(
                'question', '1. What is usually cosmetic?',
                'answer', 'Uneven shape, superficial soil, healed skin scars, colour variation and leaves of different sizes are often cosmetic. So are small pressure marks that remain dry and firm. Wash or trim as the ingredient normally requires, then use it on its own merits. Organic production does not cause every blemish, and a spotless surface does not reveal how something was grown; appearance and certification are separate questions.'
              ),
              json_object(
                'question', '2. What belongs in the use-first group?',
                'answer', 'A soft but clean tomato, a wilted but unslimy bunch, a split root with dry edges or a bruised ripe fruit may still be useful if handled promptly. Cut the item open and inspect it. Use sound portions in cooked dishes where texture is less important. Do not store damaged pieces beside pristine produce, and do not preserve or pickle questionable ingredients in the hope that salt, spice or heat will erase poor quality.'
              ),
              json_object(
                'question', '3. Which signs mean do not use?',
                'answer', 'Visible fuzzy mould, slime, leaking rot, a fermented or putrid smell, extensive internal browning, pest contamination or flesh that has become unexpectedly fizzy are clear reasons to stop. With soft, high-moisture produce, cutting a small margin around mould is not a reliable rescue because growth can extend beyond what is visible. When in doubt about a strongly altered smell or texture, discard the item.'
              ),
              json_object(
                'question', '4. When is the seller responsible?',
                'answer', 'Report produce that arrives crushed, overheated, leaking, mouldy, materially underweight or inconsistent with the listing. Also report repeated premature decay from the same lot. Take one photo showing the full quantity, one close view of the problem, and one of the label or batch details. Include the delivery time and whether the outer packaging was damaged. This is more actionable than a close-up with no scale or order reference.'
              ),
              json_object(
                'question', '5. How should a fair resolution work?',
                'answer', 'The goal is to restore the value of the affected portion, not force a customer to return decaying food through the post. Depending on the issue, a replacement, refund or credit may be appropriate. Keep the product and packaging only until support confirms what evidence is needed. A responsible seller should also check the lot, packing process and route so the next customer does not receive the same problem.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_triage_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'This approach leaves room for normal agricultural variation without lowering the standard for sound food. The test is not whether a vegetable could appear in an advertisement. It is whether it is clean, honestly described, usable for its intended purpose and delivered with reasonable shelf life remaining.',
            'Build one use-first meal into delivery day: tomato base, mixed sabzi, soup, chutney or fruit compote. It turns minor transit damage into dinner while keeping clear spoilage out of the kitchen. Waste less, but never let an anti-waste slogan pressure you into eating food you do not trust.'
          ))
        ),
        json_object(
          'id', 'blk_guide_triage_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Fresh produce with clear provenance', 'source', 'manual',
            'productSlugs', json_array('organic-alphonso-mangoes','organic-baby-spinach'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'Ugly is not unsafe, and beautiful is not proof of freshness. Condition matters more than symmetry.'
    )
  ),
  (
    'art_guide_traceability',
    'What food traceability should tell you before and after a purchase',
    'what-food-traceability-should-tell-you',
    'The records that turn a farm story into something useful when you are choosing a product or reporting a problem.',
    6,
    '2026-07-23T09:00:00Z',
    'What useful food traceability looks like',
    'Learn which farm, lot, harvest, processing and delivery records make food traceability useful to customers.',
    'food traceability farm lot harvest date batch supply chain customer guide',
    'Traceability earns its keep when it can answer a specific question about a specific pack.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_trace_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'A photograph of a farmer is not traceability. Neither is a map pin with no connection to the item in your basket. Traceability is the preserved link between a particular quantity of food and the records created as it moved through growing, harvest or processing, packing and sale.',
            'Customers do not need every internal spreadsheet. They do need enough information to choose intelligently, verify important claims and identify the affected lot when something goes wrong.'
          ))
        ),
        json_object(
          'id', 'blk_guide_trace_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Five records that make provenance useful',
            'items', json_array(
              json_object(
                'question', '1. Who produced it, and where?',
                'answer', 'The record should name the farm, grower group or processor responsible for the product, with a location more meaningful than simply India. For a blended or aggregated product, the seller should say so rather than presenting one photogenic farm as the only source. The producer name helps you connect certification, farming method and previous purchases to the correct operation.'
              ),
              json_object(
                'question', '2. Which lot is this item part of?',
                'answer', 'A lot or batch groups food handled under shared conditions. It may relate to a harvest date, milling run, collection route or packing session. The code does not need to be friendly, but it must remain attached to the item and to internal records. When quality varies, the lot lets a seller investigate the narrowest sensible group instead of blaming the customer or recalling everything.'
              ),
              json_object(
                'question', '3. Which dates actually matter?',
                'answer', 'For fresh produce, harvest and dispatch timing can help explain maturity and expected condition. For flour and oil, milling or pressing and packing dates are often more useful than a romantic harvest season alone. Best-before information serves a different purpose and should not be presented as proof of freshness. Useful pages label each date clearly instead of displaying one unexplained timestamp.'
              ),
              json_object(
                'question', '4. Which claims are connected to documents?',
                'answer', 'Certification, variety, processing method and single-origin claims should point to records that cover the relevant product and period. A certificate for the farm does not automatically prove a separate processor''s handling claim. Good traceability preserves the chain across hand-offs: producer to collector, processor, packer, fulfilment centre and customer.'
              ),
              json_object(
                'question', '5. Can support retrieve the record from your order?',
                'answer', 'The final test happens after purchase. Give support the order reference and product name; the team should be able to identify the dispatched batch without asking you to reconstruct the supply chain. A label photo is still valuable when packaging is damaged or lots were split. If the business collects traceability data but cannot use it during a complaint, it is decoration rather than an operating system.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_trace_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Before buying, look for a named source, meaningful dates, a certification or method record where relevant, and an explanation of mixed sourcing. After buying, retain the batch label until the food has been checked. Those habits take seconds and make provenance far more useful.',
            'Traceability cannot guarantee flavour or prevent every mistake. It shortens the distance between a question and an accountable answer. That is why a plain lot code can matter more than a page of storytelling.'
          ))
        ),
        json_object(
          'id', 'blk_guide_trace_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'See traceability in the catalogue', 'source', 'manual',
            'productSlugs', json_array('organic-alphonso-mangoes','sprouted-ragi-flour','wood-pressed-groundnut-oil','himalayan-red-rajma'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'Traceability earns its keep when it can answer a specific question about a specific pack.'
    )
  ),
  (
    'art_guide_millets',
    'Ragi, jowar, bajra or little millet: choose the grain for the meal',
    'choose-ragi-jowar-bajra-little-millet',
    'A cooking-first guide to four different millets, without treating them as one fashionable substitute for rice and wheat.',
    7,
    '2026-07-21T09:00:00Z',
    'How to choose a millet for the meal',
    'Compare ragi, jowar, bajra and little millet by flavour, form and cooking use so you can choose the right grain for a dish.',
    'ragi jowar bajra little millet cooking guide flour whole grain',
    'Millet is a family of grains, not a single ingredient waiting to replace wheat or rice.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_millet_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Millet advice often begins with a list of health claims and ends by asking one grain to replace every familiar staple. That is a poor introduction. Finger millet, sorghum, pearl millet and the small millets have different flavours, structures and forms. The useful question is not which millet is best, but which one suits the meal you want to cook.',
            'Start with one recurring dish and learn the ingredient there. A grain becomes part of a household through reliable breakfasts and dinners, not through a bag purchased after a headline and forgotten behind the rice.'
          ))
        ),
        json_object(
          'id', 'blk_guide_millet_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Choose by form, flavour and technique',
            'items', json_array(
              json_object(
                'question', '1. When does ragi make sense?',
                'answer', 'Ragi, or finger millet, is commonly sold as flour because the tiny grain is difficult to use like rice at home. Its earthy, gently malty flavour works in dosa, roti blended with other flours, porridge and baked snacks. Ragi contains no gluten, so a 100 percent ragi dough will not stretch like wheat dough. Use a recipe designed for it instead of making a straight swap and blaming the grain for crumbling.'
              ),
              json_object(
                'question', '2. What is jowar good at?',
                'answer', 'Jowar, or sorghum, has a mild flavour that sits comfortably beside vegetables and dal. Its flour is used for bhakri and roti, while pearled or whole forms can be cooked for salads, bowls and pilafs when available. Jowar dough also lacks gluten; warm water, careful patting and practice matter more than adding excess dry flour. Begin with a small roti or a flour blend while learning the feel.'
              ),
              json_object(
                'question', '3. Where does bajra fit?',
                'answer', 'Bajra, or pearl millet, is robust, nutty and especially good with assertive winter foods: greens, garlic, sesame, jaggery and slow-cooked pulses. The flour can develop stale flavours during long storage, so buy an amount you will finish and keep it cool and airtight. Bajra roti is meant to be tender and rustic, not an imitation of a thin elastic wheat phulka.'
              ),
              json_object(
                'question', '4. Can little millet replace rice in a dish?',
                'answer', 'Little millet and other small millets are often the easiest place to start when you want a separate cooked grain. Rinse well, use the package ratio as a starting point and rest the covered pot after cooking. The exact water need changes with polishing and age. Use it first in a familiar lemon rice, pulao or curd-rice style dish so only one part of the meal is new.'
              ),
              json_object(
                'question', '5. How do you make the change last?',
                'answer', 'Choose one millet, one form and one weekly meal. Record the water, resting time and result on the pack. Adjust the next batch instead of switching grains immediately. Keep rice and wheat in the kitchen if they serve you well; variety is a more realistic goal than purity. Repetition builds skill, creates steady demand and tells you whether the family genuinely enjoys the ingredient.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_millet_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'For a first purchase, decide the dish before the pack size. Choose ragi flour for dosa or porridge, jowar flour for bhakri, bajra flour for a robust winter roti, or a small millet for a rice-style preparation. Then buy enough for two or three attempts, because technique rarely becomes comfortable in one meal.',
            'The best grain is the one that earns a regular place at the table. Respecting the differences between millets leads to better food and more durable demand than treating all of them as a single miracle ingredient.'
          ))
        ),
        json_object(
          'id', 'blk_guide_millet_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Start with ragi in a familiar dish', 'source', 'manual',
            'productSlugs', json_array('sprouted-ragi-flour'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'Millet is a family of grains, not a single ingredient waiting to replace wheat or rice.'
    )
  ),
  (
    'art_guide_weekly_plan',
    'Plan five dinners from one seasonal produce order',
    'plan-five-dinners-seasonal-produce-order',
    'A flexible meal-planning method that uses fragile vegetables first, carries prep forward and leaves room for real life.',
    7,
    '2026-07-19T09:00:00Z',
    'Plan five dinners from seasonal produce',
    'Turn one mixed produce order into five flexible dinners by planning perishability, shared preparation and one rescue meal.',
    'seasonal meal planning vegetables weekly dinner plan food waste',
    'A useful meal plan organises perishability and effort; it does not pretend Thursday will obey Monday.',
    json_object(
      'blocks', json_array(
        json_object(
          'id', 'blk_guide_plan_intro', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Seasonal shopping becomes frustrating when the order is treated as a collection of unrelated recipes. Every dish needs a new list, the tender greens wait for inspiration and the cook runs out of energy before the vegetables run out of life. A better plan starts with perishability and shared preparation.',
            'You do not need to predict five exact dinners. Build five meal roles, assign the most fragile produce to the earliest role and prepare one component that can move through the week without making every plate taste the same.'
          ))
        ),
        json_object(
          'id', 'blk_guide_plan_checklist', 'type', 'faq', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Five dinner roles for a mixed order',
            'items', json_array(
              json_object(
                'question', 'Dinner 1: the fragile meal',
                'answer', 'Use spinach, tender herbs, mushrooms, flowers, very ripe tomatoes or any sound item bruised in transit. Keep the method fast: dal with greens, a herb-heavy egg dish, stir-fry or tomato toast beside leftovers. While chopping, wash and dry the remaining herbs and cook one neutral base such as plain dal, beans or grain for later meals.'
              ),
              json_object(
                'question', 'Dinner 2: the two-texture vegetable meal',
                'answer', 'Pair a vegetable that needs longer cooking with one that needs almost none. Roast roots and fold in greens at the end; cook a gourd curry and finish with fresh coriander; make millet or rice and top it with a crisp cucumber salad. This keeps the meal varied without running two elaborate recipes. Prepare double the sturdy component if tomorrow is busy.'
              ),
              json_object(
                'question', 'Dinner 3: the pantry bridge',
                'answer', 'Use pulses, flour or grain to stretch the smaller quantities left in the produce drawer. Rajma can carry roasted pumpkin, ragi dosa can hold a quick spinach filling and khichdi can absorb beans, carrots or gourds. The pantry is not a fallback after fresh food; it is what turns seasonal variation into a complete, repeatable meal.'
              ),
              json_object(
                'question', 'Dinner 4: the planned leftover',
                'answer', 'Transform one prepared component rather than reheating the entire previous plate. Cooked beans become a chaat or wrap filling, roasted vegetables join a grain bowl, and extra dal thickens into a pancake batter or soup base. Cool and refrigerate cooked food promptly in shallow containers, label it and reheat only what you need. If storage was uncertain, do not build a new meal around it.'
              ),
              json_object(
                'question', 'Dinner 5: the rescue meal',
                'answer', 'Reserve a forgiving format for the end of the cycle: mixed sabzi, soup, tray roast, fried rice, khichdi or a clean-out-the-drawer pasta. Inspect every ingredient and keep incompatible flavours separate rather than emptying everything into one pot. The rescue meal is planned capacity for small amounts and changed schedules, not permission to use spoiled food.'
              )
            )
          )
        ),
        json_object(
          'id', 'blk_guide_plan_close', 'type', 'rich_text', 'version', 1,
          'enabled', json('true'),
          'props', json_object('paragraphs', json_array(
            'Keep the plan on one screen: five roles, the produce assigned to each and one component to carry forward. If dinner out appears, move the fragile ingredient into breakfast or lunch and push a sturdy role back. The structure bends because it was never dependent on five perfect evenings.',
            'After a month, notice what repeatedly survives to rescue night. Buy less of it, choose a smaller pack or learn one preparation the household actually requests. A seasonal plan improves by listening to the waste, not by collecting more recipes.'
          ))
        ),
        json_object(
          'id', 'blk_guide_plan_products', 'type', 'product_collection', 'version', 1,
          'enabled', json('true'),
          'props', json_object(
            'heading', 'Build this week''s flexible order', 'source', 'manual',
            'productSlugs', json_array('organic-baby-spinach','himalayan-red-rajma','sprouted-ragi-flour','wood-pressed-groundnut-oil'),
            'limit', 4
          )
        )
      ),
      'pullQuote', 'A useful meal plan organises perishability and effort; it does not pretend Thursday will obey Monday.'
    )
  );

-- Production databases do not necessarily contain the development editor. The
-- SELECT guard makes this a no-op there; seeded environments have usr_editor,
-- and the development seed mirrors this curated set for a fresh database.
INSERT INTO articles (
  id, internal_name, title, slug, excerpt, author_user_id, hero_media_id,
  reading_minutes, status, published_version_id, published_at, seo_title,
  seo_description, created_at, created_by, updated_at, updated_by, seo_keywords,
  indexing_policy, hero_image_url, hero_image_alt
)
SELECT
  id, 'Customer guide: ' || slug, title, slug, excerpt, 'usr_editor', NULL,
  reading_minutes, 'published', 'arv_' || id || '_1', published_at, seo_title,
  seo_description, published_at, 'usr_editor', published_at, 'usr_editor', keywords,
  'index', '/banners/content/blog-editorial-guides.webp', image_alt
FROM curated_blog_articles
WHERE EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO article_versions (
  id, article_id, version_number, content_json, workflow_state, created_at,
  created_by, approved_at, approved_by, published_at
)
SELECT
  'arv_' || id || '_1', id, 1, content_json, 'published', published_at,
  'usr_editor', published_at, 'usr_editor', published_at
FROM curated_blog_articles
WHERE EXISTS (SELECT 1 FROM users WHERE id = 'usr_editor');

INSERT INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords)
SELECT 'article', id, title, slug, excerpt, keywords
FROM curated_blog_articles
WHERE EXISTS (SELECT 1 FROM articles WHERE articles.id = curated_blog_articles.id);

DROP TABLE curated_blog_articles;
