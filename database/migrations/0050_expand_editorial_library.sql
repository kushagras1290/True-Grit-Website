-- 0050_expand_editorial_library: restore the useful scale of the original
-- blog without restoring its three-template filler, distribute articles across
-- transparent editorial-desk bylines, and replace the repetitive generated
-- community prompts with questions that ask for usable evidence and context.
PRAGMA foreign_keys = ON;

-- These are non-login byline profiles, not invented individual people. Keeping
-- them disabled makes that boundary explicit while allowing the existing
-- articles.author_user_id relationship to render honest, distinct authors.
INSERT OR IGNORE INTO users (
  id, email, display_name, user_type, status, created_at, updated_at
) VALUES
  ('usr_author_buying', 'buying-desk@truegrit.invalid', 'True Grit Buying Desk', 'staff', 'disabled', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z'),
  ('usr_author_kitchen', 'kitchen@truegrit.invalid', 'True Grit Kitchen', 'staff', 'disabled', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z'),
  ('usr_author_food_care', 'food-care@truegrit.invalid', 'True Grit Food Care Desk', 'staff', 'disabled', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z'),
  ('usr_author_farms', 'farms-desk@truegrit.invalid', 'True Grit Farms Desk', 'staff', 'disabled', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z'),
  ('usr_author_community', 'community@truegrit.invalid', 'True Grit Community Team', 'staff', 'disabled', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z');

-- Spread the seven long-form guides introduced by 0046 across the desk that
-- owns the subject. Existing databases receive the change here; fresh
-- development seeds use the same mapping in development.sql.
UPDATE articles
SET author_user_id = CASE id
  WHEN 'art_guide_organic_label' THEN 'usr_author_buying'
  WHEN 'art_guide_produce_storage' THEN 'usr_author_food_care'
  WHEN 'art_guide_pantry_sizes' THEN 'usr_author_kitchen'
  WHEN 'art_guide_imperfect_produce' THEN 'usr_author_food_care'
  WHEN 'art_guide_traceability' THEN 'usr_author_farms'
  WHEN 'art_guide_millets' THEN 'usr_author_kitchen'
  WHEN 'art_guide_weekly_plan' THEN 'usr_author_kitchen'
  ELSE author_user_id
END
WHERE id LIKE 'art_guide_%';

DROP TABLE IF EXISTS editorial_topics_0050;
CREATE TABLE editorial_topics_0050 (
  n INTEGER PRIMARY KEY,
  subject TEXT NOT NULL,
  slug TEXT NOT NULL,
  observation TEXT NOT NULL,
  practice TEXT NOT NULL,
  takeaway TEXT NOT NULL
);

-- Each subject appears once. The three articles built from it answer different
-- reader needs: understand the evidence, try a bounded practice, and judge the
-- trade-off. This replaces the old three cosmetic title variants.
INSERT INTO editorial_topics_0050 VALUES
  (1,'morning harvests','morning-harvests','Tender crops hold more moisture before the day becomes hot.','Growers plan cutting, shade and packing as one continuous job.','Freshness depends on handling after harvest as much as the hour of picking.'),
  (2,'seed selection','seed-selection','Saving seed begins by noticing healthy plants long before harvest.','Farmers mark plants with the flavour, vigour and timing they want to keep.','A seed line survives through repeated observation, not nostalgia alone.'),
  (3,'monsoon sowing','monsoon-sowing','The first rain is not always the right rain for sowing.','Farmers check soil depth and the forecast before committing valuable seed.','Timing is a practical judgement shaped by local memory and current weather.'),
  (4,'soil organic matter','soil-organic-matter','Organic matter affects water, nutrients and the way soil holds together.','Compost, roots and retained crop residue rebuild it gradually.','The useful change is steady resilience rather than an overnight transformation.'),
  (5,'farm ponds','farm-ponds','A well-placed pond slows water that would otherwise leave the farm.','Design must account for soil, overflow, safety and downstream users.','Water storage works best as part of a wider landscape plan.'),
  (6,'mixed cropping','mixed-cropping','Different crops can share light, rooting depth and risk.','Useful mixtures are chosen for compatible timing and manageable harvest work.','Diversity in a field should solve a real agronomic or livelihood problem.'),
  (7,'natural pest control','natural-pest-control','Predatory insects need habitat before a pest outbreak begins.','Flowering borders and careful spraying decisions protect useful species.','Ecological pest control is patient management, not the absence of intervention.'),
  (8,'seasonal labour','seasonal-labour','Harvest quality depends on people arriving at the right moment.','Fair planning includes safe hours, drinking water and predictable payment.','The human work behind fresh food belongs in every conversation about quality.'),
  (9,'field mulching','field-mulching','A surface cover can reduce heat and soften the impact of rain.','Farmers choose straw, leaves or living cover according to local risks.','Mulch is most useful when its source and side effects are considered.'),
  (10,'compost maturity','compost-maturity','Finished compost smells earthy and no longer heats dramatically.','Growers watch moisture, air and the breakdown of the original materials.','Applying immature material can move a problem from the pile into the field.'),
  (11,'tomato ripeness','tomato-ripeness','Aroma develops while fruit remains attached to a healthy vine.','Shorter supply routes allow farmers to pick closer to eating ripeness.','Colour alone cannot tell the full story of flavour.'),
  (12,'leafy green storage','leafy-green-storage','Leaves lose moisture quickly and decay when held wet.','Dry cloth, loose packing and prompt cooling create a useful balance.','Good storage begins by removing damaged leaves before they affect the bunch.'),
  (13,'pulse soaking','pulse-soaking','Water reaches the centre of older, denser pulses slowly.','A planned soak shortens cooking and often improves texture.','The age and variety of a pulse matter as much as the clock.'),
  (14,'whole grain milling','whole-grain-milling','Natural oils and aromas begin changing as soon as grain is milled.','Small batches and cool airtight storage protect fresh flour.','Buy at a pace that matches how quickly the kitchen actually cooks.'),
  (15,'cold pressed oils','cold-pressed-oils','The press cannot improve stale or poorly dried seed.','Millers protect raw seed from moisture, heat and contamination.','Fresh oil starts with good agriculture and ends with careful storage.'),
  (16,'market grading','market-grading','Sorting separates damage from harmless differences in shape and size.','Clear grades help match produce to fresh sale, processing or quick use.','Good grading should reduce waste without pretending every crop is identical.'),
  (17,'reusable crates','reusable-crates','Rigid crates prevent crushing better than overfilled sacks.','Cleaning, return routes and ownership must be organised for reuse to work.','Packaging is a system, not simply a material choice.'),
  (18,'cooling fresh produce','cooling-fresh-produce','Harvested vegetables continue to respire and generate heat.','Shade and crop-appropriate cooling slow water loss.','Temperature decisions must suit the crop rather than follow one rule.'),
  (19,'farm traceability','farm-traceability','A useful lot record connects food to place, date and handling.','Labels remain meaningful only when each transfer preserves the link.','Traceability should help answer practical questions, not decorate a package.'),
  (20,'organic inspections','organic-inspections','Certification reviews records, fields, inputs and handling systems.','Farmers maintain evidence throughout the year, not only on inspection day.','A certificate is one part of trust and should be readable by customers.'),
  (21,'rain-fed millets','rain-fed-millets','Millets tolerate conditions that make many grains unreliable.','Variety choice, sowing date and soil cover still decide the harvest.','Resilient crops reduce risk but do not remove it.'),
  (22,'legumes in rotation','legumes-in-rotation','Legume roots work with bacteria that can add nitrogen to the system.','Farmers place them where the following crop can benefit.','Rotation value includes soil cover, income and pest interruption.'),
  (23,'hedgerows','hedgerows','Living boundaries slow wind and provide food for useful insects.','Mixed native species offer more than a single uniform hedge.','Productive land can make room for habitat without becoming unmanaged.'),
  (24,'pollinator seasons','pollinator-seasons','Bees need food before and after the main crop flowers.','Overlapping blooms and nesting places support resident populations.','Pollination depends on year-round habitat, not a rented moment.'),
  (25,'hand weeding','hand-weeding','Young weeds are easier to remove before roots and seed develop.','Timing work after light moisture reduces effort and soil disturbance.','Avoiding herbicide replaces a product with skilled, repeated labour.'),
  (26,'cover crops','cover-crops','Living roots feed soil organisms between cash crops.','Species are chosen for rainfall, duration and the next planting window.','A cover crop must fit the farm calendar to deliver its promise.'),
  (27,'reduced tillage','reduced-tillage','Every pass with machinery changes pores and soil aggregates.','Growers reduce disturbance while managing weeds and crop residue.','The right level of tillage depends on soil, climate and available tools.'),
  (28,'agroforestry','agroforestry','Trees can moderate heat, hold soil and diversify farm income.','Spacing and pruning prevent harmful competition with crops.','A useful tree system is designed for decades as well as seasons.'),
  (29,'shade-grown coffee','shade-grown-coffee','Canopy changes temperature, ripening speed and wildlife habitat.','Farmers adjust shade to balance quality with disease pressure.','The words shade grown describe a spectrum that deserves specifics.'),
  (30,'orchard floor care','orchard-floor-care','Bare orchard soil heats quickly and loses structure under hard rain.','Mown cover, mulch and managed grazing each offer different options.','The ground between trees is part of the crop system.'),
  (31,'mango flowering','mango-flowering','Warmth, humidity and wind affect flowers before fruit is visible.','Orchardists monitor bloom health and avoid unnecessary disturbance.','A mango season begins months before the first crate.'),
  (32,'banana circles','banana-circles','Bananas use steady moisture and abundant organic material.','Circular planting basins can collect biomass and suitable household water when safely designed.','A good design matches water supply, sanitation and available space.'),
  (33,'coconut diversity','coconut-diversity','Tall and dwarf coconut lines differ in timing, stature and use.','Farmers choose material for local wind, water and market needs.','One familiar crop contains more diversity than a shop shelf suggests.'),
  (34,'kitchen herb gardens','kitchen-herb-gardens','Frequently cut herbs earn their place close to the kitchen.','Regular pinching, drainage and morning light keep plants productive.','A small useful garden can matter more than a large neglected one.'),
  (35,'balcony composting','balcony-composting','Small bins turn sour when wet scraps overwhelm dry material.','Chopped browns, airflow and modest portions restore balance.','Successful composting is mostly observation of moisture and smell.'),
  (36,'saving cooking water','saving-cooking-water','Unsalted vegetable and pulse water can carry flavour and starch.','Cooks cool and reuse it promptly in soups, doughs or the next pot of dal.','Reuse is helpful only when food safety and excess salt are considered.'),
  (37,'root-to-leaf cooking','root-to-leaf-cooking','Many tender stems and leaves are ingredients rather than waste.','Separate parts by cooking time and taste before using unfamiliar greens.','Whole-plant cooking begins with judgement, not a rule to eat everything.'),
  (38,'seasonal meal planning','seasonal-meal-planning','Fragile produce should be scheduled before sturdy roots and pumpkins.','A weekly sort makes the order of cooking visible.','Planning around perishability saves more food than collecting recipes.'),
  (39,'pantry turnover','pantry-turnover','Large stores of flour, oil and spices lose quality slowly.','Smaller containers and dated purchases reveal what the kitchen uses.','A useful pantry is active, not merely full.'),
  (40,'safe grain cooling','safe-grain-cooling','Deep pots of cooked grain cool slowly at the centre.','Shallow containers release heat before prompt refrigeration.','Good leftovers begin with safe cooling, not reheating alone.'),
  (41,'fermented batters','fermented-batters','Warmth, grain ratio and grinding texture shape fermentation.','Cooks watch aroma and rise instead of trusting the clock alone.','A living batter needs clean tools and room to expand.'),
  (42,'pickling seasons','pickling-seasons','Preserving starts when produce is abundant, firm and full of flavour.','Salt, acidity, dryness and clean jars each control a different risk.','A reliable pickle method respects both tradition and food safety.'),
  (43,'sun drying','sun-drying','Drying succeeds when moisture leaves faster than spoilage can begin.','Thin even pieces, clean screens and protection from night humidity matter.','Sun is only one part of a controlled drying process.'),
  (44,'jaggery making','jaggery-making','Cane juice changes flavour as it is clarified and concentrated.','Experienced makers judge foam, heat and finishing point by sight and feel.','Colour varies naturally and should not replace questions about process.'),
  (45,'small dairy herds','small-dairy-herds','Milk quality begins with animal health, feed and clean handling.','Cooling and traceable collection protect work done at the farm.','Scale alone does not determine care or quality.'),
  (46,'farm-gate pricing','farm-gate-pricing','The price at the farm must cover more than visible harvest work.','Seed, failed crops, certification, packing and delayed payment all matter.','Fair pricing starts by recognising risk across the season.'),
  (47,'short supply chains','short-supply-chains','Fewer kilometres do not guarantee careful handling.','Clear orders, reusable crates and reliable collection keep local trade fresh.','Distance and logistics must be judged together.'),
  (48,'community seed banks','community-seed-banks','Shared seed collections protect access to locally adapted varieties.','Records, regeneration plots and agreed borrowing rules keep seed viable.','A seed bank succeeds when seed continues to grow in fields.'),
  (49,'farm weather records','farm-weather-records','Local rainfall and temperature can differ from a distant station.','Simple daily notes become useful when kept consistently.','Farm decisions improve when memory is supported by a record.'),
  (50,'eating with the seasons','eating-with-the-seasons','Availability changes with weather, place and the limits of a harvest.','Cooks preserve some abundance and allow other ingredients to disappear.','Seasonality is a practice of attention rather than a purity test.');

DROP TABLE IF EXISTS editorial_angles_0050;
CREATE TABLE editorial_angles_0050 (
  angle INTEGER PRIMARY KEY,
  slug_suffix TEXT NOT NULL
);
INSERT INTO editorial_angles_0050 VALUES
  (1, 'evidence'),
  (2, 'practical-start'),
  (3, 'tradeoffs');

-- Remove only entries owned by this migration so a retry or a development
-- reseed is deterministic without touching CMS/customer-authored articles.
DELETE FROM search_content
WHERE entity_type = 'article'
  AND (entity_id LIKE 'art_field_%' OR entity_id LIKE 'art_case_%');
DELETE FROM articles
WHERE id LIKE 'art_field_%' OR id LIKE 'art_case_%';

-- Forty-eight distinct subjects x three genuinely different reader jobs =
-- 144 focused explainers. Together with 50 community-tested case notes and the
-- seven long guides, seeded environments contain the original 201 stories.
INSERT INTO articles (
  id, internal_name, title, slug, excerpt, author_user_id, hero_media_id,
  reading_minutes, status, published_version_id, published_at, seo_title,
  seo_description, created_at, created_by, updated_at, updated_by, seo_keywords,
  indexing_policy, hero_image_url, hero_image_alt
)
SELECT
  printf('art_field_%03d_%d', topics.n, angles.angle),
  'Editorial field guide: ' || topics.slug || ':' || angles.angle,
  CASE angles.angle
    WHEN 1 THEN CASE topics.n % 8
      WHEN 0 THEN 'What to look for in ' || topics.subject
      WHEN 1 THEN 'The evidence behind ' || topics.subject
      WHEN 2 THEN 'What changes when you use ' || topics.subject
      WHEN 3 THEN 'How to judge ' || topics.subject || ' in context'
      WHEN 4 THEN 'Beyond the label: ' || topics.subject
      WHEN 5 THEN 'The overlooked detail in ' || topics.subject
      WHEN 6 THEN 'Beyond marketing shorthand: ' || topics.subject
      ELSE 'A clearer way to understand ' || topics.subject
    END
    WHEN 2 THEN CASE topics.n % 8
      WHEN 0 THEN 'A workable first step for ' || topics.subject
      WHEN 1 THEN 'How to start with ' || topics.subject || ' without overcomplicating it'
      WHEN 2 THEN 'The small habit that improves ' || topics.subject
      WHEN 3 THEN 'A practical checklist for ' || topics.subject
      WHEN 4 THEN 'How to record and improve ' || topics.subject
      WHEN 5 THEN 'Turning ' || topics.subject || ' into a repeatable practice'
      WHEN 6 THEN 'What to do before changing ' || topics.subject
      ELSE 'A measured way to try ' || topics.subject
    END
    ELSE CASE topics.n % 8
      WHEN 0 THEN 'The trade-off hidden inside ' || topics.subject
      WHEN 1 THEN 'When the work behind ' || topics.subject || ' pays off'
      WHEN 2 THEN 'What can go wrong with ' || topics.subject
      WHEN 3 THEN 'The limits of a simple ' || topics.subject || ' claim'
      WHEN 4 THEN 'Which questions make ' || topics.subject || ' meaningful'
      WHEN 5 THEN 'Why context matters in ' || topics.subject
      WHEN 6 THEN 'What not to assume about ' || topics.subject
      ELSE 'How to compare two approaches to ' || topics.subject
    END
  END,
  topics.slug || '-' || angles.slug_suffix,
  CASE angles.angle
    WHEN 1 THEN topics.observation || ' Learn which evidence makes that observation useful instead of merely persuasive.'
    WHEN 2 THEN topics.practice || ' Use a small, recorded trial before turning it into a rule.'
    ELSE topics.takeaway || ' Compare the outcome, labour and local constraints before deciding.'
  END,
  CASE angles.angle
    WHEN 1 THEN 'usr_author_farms'
    WHEN 2 THEN CASE WHEN topics.n BETWEEN 12 AND 15 OR topics.n BETWEEN 34 AND 43 THEN 'usr_author_kitchen' ELSE 'usr_author_food_care' END
    ELSE 'usr_author_buying'
  END,
  NULL,
  4 + ((topics.n + angles.angle) % 2),
  'published',
  printf('arv_field_%03d_%d_1', topics.n, angles.angle),
  datetime('2025-11-01T09:00:00Z', printf('+%d days', topics.n * 3 + angles.angle)),
  CASE angles.angle
    WHEN 1 THEN 'Evidence guide: ' || topics.subject
    WHEN 2 THEN 'Practical guide: ' || topics.subject
    ELSE 'Trade-offs and questions: ' || topics.subject
  END,
  CASE angles.angle
    WHEN 1 THEN topics.observation || ' Learn what to verify and what the claim cannot prove by itself.'
    WHEN 2 THEN topics.practice || ' Follow a bounded trial, record the result and adjust for local conditions.'
    ELSE topics.takeaway || ' Understand the limits, labour and context before comparing approaches.'
  END,
  '2025-10-20T09:00:00Z',
  CASE angles.angle WHEN 1 THEN 'usr_author_farms' WHEN 2 THEN 'usr_author_food_care' ELSE 'usr_author_buying' END,
  datetime('2025-11-01T09:00:00Z', printf('+%d days', topics.n * 3 + angles.angle)),
  CASE angles.angle WHEN 1 THEN 'usr_author_farms' WHEN 2 THEN 'usr_author_food_care' ELSE 'usr_author_buying' END,
  replace(topics.slug, '-', ' ') || ' practical guide evidence',
  'index',
  '/banners/content/blog-editorial-guides.webp',
  'True Grit field notes and practical checks for ' || topics.subject
FROM editorial_topics_0050 topics
CROSS JOIN editorial_angles_0050 angles
WHERE topics.n <= 48;

INSERT INTO article_versions (
  id, article_id, version_number, content_json, workflow_state, created_at,
  created_by, approved_at, approved_by, published_at
)
SELECT
  printf('arv_field_%03d_%d_1', topics.n, angles.angle),
  printf('art_field_%03d_%d', topics.n, angles.angle),
  1,
  json_object(
    'blocks', json_array(
      json_object(
        'id', printf('blk_field_%03d_%d_context', topics.n, angles.angle),
        'type', 'rich_text', 'version', 1, 'enabled', json('true'),
        'props', json_object('paragraphs', CASE angles.angle
          WHEN 1 THEN json_array(
            topics.observation,
            topics.practice || ' The useful evidence is the record connecting that practice to a place, season and result, not a photograph of the practice in isolation.',
            topics.takeaway || ' Ask what was observed before and after, over what period, and which competing explanation was considered.',
            'A useful record names the crop or ingredient, location, date, starting condition and result. It also keeps failed attempts. Without that context, a true observation can still become a misleading promise when it is repeated somewhere with different weather, equipment, timing or goals.'
          )
          WHEN 2 THEN json_array(
            topics.practice,
            'Begin with one bounded change and write down the starting condition. ' || topics.observation,
            topics.takeaway || ' Keep the part that solves the real problem; change or stop the part that creates a larger one.',
            'Run the smallest trial that can answer the question. Keep everything else as steady as practical, decide in advance what success and failure look like, and set a review date. That discipline turns an interesting suggestion into knowledge you can use again.'
          )
          ELSE json_array(
            topics.takeaway,
            topics.observation || ' That benefit still has to be weighed against labour, timing, cost and the conditions in which it was observed.',
            topics.practice || ' A useful comparison names those constraints instead of declaring one approach universally best.',
            'Compare the same outcome over the same period and include the work needed to maintain it. A cheaper input can demand more labour; a faster method can shorten storage life; a strong result in one season can weaken in another. The honest choice keeps those costs visible.'
          )
        END)
      ),
      json_object(
        'id', printf('blk_field_%03d_%d_questions', topics.n, angles.angle),
        'type', 'faq', 'version', 1, 'enabled', json('true'),
        'props', json_object(
          'heading', CASE angles.angle WHEN 1 THEN 'Three evidence checks' WHEN 2 THEN 'Three steps for a useful trial' ELSE 'Three questions before deciding' END,
          'items', CASE angles.angle
            WHEN 1 THEN json_array(
              json_object('question','What should be observable?','answer',topics.observation || ' Look for a dated, specific observation rather than a broad promise.'),
              json_object('question','What practice produced it?','answer',topics.practice || ' Ask who performed the work, when, and under which conditions.'),
              json_object('question','What does it not prove?','answer',topics.takeaway || ' One good result does not establish that the same approach fits every farm or kitchen.'),
              json_object('question','How long should the record run?','answer','Long enough to include the relevant cycle: several storage checks, repeated cooking attempts, or more than one field observation. A single photograph captures a moment, not reliability.'),
              json_object('question','What should a customer ask for?','answer','Ask for the source, date, method and scope of the claim. A useful answer should identify what was actually checked and where reasonable uncertainty remains.')
            )
            WHEN 2 THEN json_array(
              json_object('question','What should I change first?','answer',topics.practice || ' Change one controllable part so the result remains understandable.'),
              json_object('question','What should I record?','answer',topics.observation || ' Record the starting point, date, conditions and result in plain language.'),
              json_object('question','How should I judge the result?','answer',topics.takeaway || ' Keep usefulness, safety, labour and repeatability in the same decision.'),
              json_object('question','When should I stop the trial?','answer','Stop when food safety, animal welfare, worker safety, plant health or equipment safety is uncertain. A small experiment is not a reason to push through a clear warning sign.'),
              json_object('question','What makes the result reusable?','answer','Write down quantities, timing, temperature or weather, and what you would change next time. Those details let another person adapt the result instead of copying it blindly.')
            )
            ELSE json_array(
              json_object('question','Which benefit is being claimed?','answer',topics.observation || ' Ask for the concrete outcome rather than accepting a category label.'),
              json_object('question','Which work or cost is hidden?','answer',topics.practice || ' Include labour, timing, equipment and maintenance in the comparison.'),
              json_object('question','Which context could change the answer?','answer',topics.takeaway || ' Season, place, scale and the intended outcome can reverse a simple recommendation.'),
              json_object('question','Who carries the extra work or risk?','answer','Include the farmer, worker, processor, cook and customer. A benefit is incomplete when its labour, failed batches, delayed payment or disposal cost is quietly shifted to someone else.'),
              json_object('question','What evidence would change the decision?','answer','Decide which result, cost or failure would make you choose differently. A comparison is more trustworthy when it can be revised by new evidence.')
            )
          END
        )
      )
    ),
    'pullQuote', CASE angles.angle WHEN 1 THEN topics.observation WHEN 2 THEN topics.practice ELSE topics.takeaway END
  ),
  'published',
  '2025-10-20T09:00:00Z',
  CASE angles.angle WHEN 1 THEN 'usr_author_farms' WHEN 2 THEN 'usr_author_food_care' ELSE 'usr_author_buying' END,
  datetime('2025-11-01T08:30:00Z', printf('+%d days', topics.n * 3 + angles.angle)),
  'usr_author_buying',
  datetime('2025-11-01T09:00:00Z', printf('+%d days', topics.n * 3 + angles.angle))
FROM editorial_topics_0050 topics
CROSS JOIN editorial_angles_0050 angles
WHERE topics.n <= 48;

INSERT INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords)
SELECT 'article', id, title, slug, excerpt, seo_keywords
FROM articles
WHERE id LIKE 'art_field_%';

-- Fifty useful community threads already contain a specific problem and a
-- follow-up describing what changed. Turn each pair into a concise case note.
-- This SELECT is intentionally a no-op where development discussions were
-- never seeded; development.sql repeats it after creating those fixtures.
WITH paired_threads AS (
  SELECT
    CAST(substr(question.id, 13, 3) AS INTEGER) AS n,
    question.body AS problem,
    outcome.title AS title,
    outcome.body AS outcome
  FROM discussions question
  JOIN discussions outcome
    ON outcome.id = substr(question.id, 1, length(question.id) - 1) || 'b'
  WHERE question.id LIKE 'dsc_library_%_a'
)
INSERT INTO articles (
  id, internal_name, title, slug, excerpt, author_user_id, hero_media_id,
  reading_minutes, status, published_version_id, published_at, seo_title,
  seo_description, created_at, created_by, updated_at, updated_by, seo_keywords,
  indexing_policy, hero_image_url, hero_image_alt
)
SELECT
  printf('art_case_%03d', n),
  'Community-tested kitchen note ' || n,
  title,
  'community-tested-kitchen-note-' || printf('%03d', n),
  problem,
  CASE n % 5
    WHEN 0 THEN 'usr_author_community'
    WHEN 1 THEN 'usr_author_food_care'
    WHEN 2 THEN 'usr_author_kitchen'
    WHEN 3 THEN 'usr_author_buying'
    ELSE 'usr_author_farms'
  END,
  NULL,
  3,
  'published',
  printf('arv_case_%03d_1', n),
  datetime('2026-02-01T09:00:00Z', printf('+%d days', n)),
  title,
  problem,
  '2026-01-20T09:00:00Z',
  'usr_author_community',
  datetime('2026-02-01T09:00:00Z', printf('+%d days', n)),
  'usr_author_community',
  'community tested kitchen storage cooking troubleshooting',
  'index',
  '/banners/content/blog-editorial-guides.webp',
  'A practical True Grit community kitchen test and its result'
FROM paired_threads;

WITH paired_threads AS (
  SELECT
    CAST(substr(question.id, 13, 3) AS INTEGER) AS n,
    question.body AS problem,
    outcome.body AS outcome
  FROM discussions question
  JOIN discussions outcome
    ON outcome.id = substr(question.id, 1, length(question.id) - 1) || 'b'
  WHERE question.id LIKE 'dsc_library_%_a'
)
INSERT INTO article_versions (
  id, article_id, version_number, content_json, workflow_state, created_at,
  created_by, approved_at, approved_by, published_at
)
SELECT
  printf('arv_case_%03d_1', n),
  printf('art_case_%03d', n),
  1,
  json_object(
    'blocks', json_array(
      json_object(
        'id', printf('blk_case_%03d_story', n), 'type', 'rich_text',
        'version', 1, 'enabled', json('true'),
        'props', json_object('paragraphs', json_array(
          problem,
          outcome,
          'Treat this as a tested starting point, not a universal guarantee. Variety, maturity, room temperature, refrigerator conditions and equipment can change the result. Try the smallest useful batch, record what you changed and keep the part that works in your kitchen.',
          'Before repeating the method, inspect the food and the storage conditions again. Do not use a successful texture result to overrule mould, leaking decay, a rotten smell, unsafe holding time or appliance guidance. Quality experiments are useful only inside clear food-safety boundaries.'
        ))
      ),
      json_object(
        'id', printf('blk_case_%03d_checklist', n), 'type', 'faq',
        'version', 1, 'enabled', json('true'),
        'props', json_object(
          'heading', 'Use the result without losing the context',
          'items', json_array(
            json_object('question','What was the starting problem?','answer',problem),
            json_object('question','What changed in the successful attempt?','answer',outcome),
            json_object('question','How should I test it?','answer','Change one factor, keep the batch small and note the time, temperature and result before repeating it.'),
            json_object('question','When should I discard rather than rescue?','answer','Discard food with mould, leaking rot, an unmistakably rotten smell or a storage history that makes safety uncertain. A useful waste-reduction habit never depends on talking yourself past a warning sign.'),
            json_object('question','Which details help other readers?','answer','Share the ingredient variety or form, approximate quantity, room or refrigerator conditions, timing and the result. Those details explain why two honest attempts may differ.')
          )
        )
      )
    ),
    'pullQuote', outcome
  ),
  'published',
  '2026-01-20T09:00:00Z',
  'usr_author_community',
  datetime('2026-02-01T08:30:00Z', printf('+%d days', n)),
  'usr_author_buying',
  datetime('2026-02-01T09:00:00Z', printf('+%d days', n))
FROM paired_threads;

INSERT INTO search_content (entity_type, entity_id, title, slug, excerpt, keywords)
SELECT 'article', id, title, slug, excerpt, seo_keywords
FROM articles
WHERE id LIKE 'art_case_%';

-- The original expansion discussions repeated two sentence templates one
-- hundred times. Replace only that generated family. The specific, useful
-- dsc_library_* problem/outcome threads and genuine customer posts remain.
DELETE FROM discussions WHERE id LIKE 'dsc_expansion_%';
DELETE FROM discussions WHERE id LIKE 'dsc_editorial_%';

WITH discussion_kinds(kind) AS (VALUES (1), (2))
INSERT INTO discussions (
  id, author_user_id, title, body, status, comment_count, last_activity_at,
  created_at, updated_at
)
SELECT
  printf('dsc_editorial_%03d', ((topics.n - 1) * 2) + kinds.kind),
  CASE (topics.n + kinds.kind) % 5
    WHEN 0 THEN 'usr_author_community'
    WHEN 1 THEN 'usr_author_farms'
    WHEN 2 THEN 'usr_author_food_care'
    WHEN 3 THEN 'usr_author_kitchen'
    ELSE 'usr_author_buying'
  END,
  CASE kinds.kind
    WHEN 1 THEN CASE topics.n % 5
      WHEN 0 THEN 'Where are the weak points in ' || topics.subject || '?'
      WHEN 1 THEN 'What is your first check for ' || topics.subject || '?'
      WHEN 2 THEN 'Which small change improved ' || topics.subject || '?'
      WHEN 3 THEN 'What would you record before changing ' || topics.subject || '?'
      ELSE 'What did the second attempt teach you about ' || topics.subject || '?'
    END
    ELSE CASE topics.n % 5
      WHEN 0 THEN 'What should a seller explain about ' || topics.subject || '?'
      WHEN 1 THEN 'Which trade-off in ' || topics.subject || ' surprised you?'
      WHEN 2 THEN 'How do season and place change the answer for ' || topics.subject || '?'
      WHEN 3 THEN 'Which evidence makes claims about ' || topics.subject || ' useful?'
      ELSE 'What makes the extra effort worthwhile in ' || topics.subject || '?'
    END
  END,
  CASE kinds.kind
    WHEN 1 THEN topics.practice || ' ' || topics.observation || ' Share the starting condition, the one thing you changed, how long you observed it and what you would do differently next time. Specific failures are as useful as successes. If the result changed over time, say when.'
    ELSE topics.takeaway || ' ' || topics.observation || ' Which detail would help you compare two claims or approaches fairly? Please include place, season, scale or kitchen conditions where they affected the answer. A useful reply names what you compared, not only which option you preferred.'
  END,
  'visible',
  0,
  datetime('2026-03-01T09:00:00Z', printf('+%d hours', topics.n * 2 + kinds.kind)),
  datetime('2026-03-01T09:00:00Z', printf('+%d hours', topics.n * 2 + kinds.kind)),
  datetime('2026-03-01T09:00:00Z', printf('+%d hours', topics.n * 2 + kinds.kind))
FROM editorial_topics_0050 topics
CROSS JOIN discussion_kinds kinds;

DROP TABLE editorial_angles_0050;
DROP TABLE editorial_topics_0050;
