-- 0102_replace_templated_discussions: retire the machine-generated community
-- library and replace it with a small hand-written one.
--
-- Migrations 0050 and 0058 built 300 threads by CROSS JOINing a topic table
-- against a fixed set of "kinds" (100 `dsc_editorial_*` from 50 topics x 2,
-- 200 `dsc_practical_*` from 50 topics x 4). Every thread sharing a kind ends
-- in the same boilerplate paragraph verbatim, all 300 carry the same image and
-- alt text, all have `comment_count = 0`, and their timestamps sit one minute
-- apart. That is 45% of the sitemap -- the single largest block of URLs on the
-- domain -- and it matches Google's scaled content abuse pattern closely
-- enough to put indexing of the whole site at risk, including the 31 product
-- pages that actually sell something.
--
-- The replacement is deliberately 30 rather than 300: each one is written for
-- a specific product in the live catalogue, asks a question that has a real
-- answer, and shares no sentence with any other row. Threads open with zero
-- comments because none have been answered yet -- seeding replies would be
-- fabricating community activity, which is the same dishonesty in a smaller
-- package.
--
-- `discussion_comments` cascades on delete (migration 0034), so the DELETE
-- below needs no companion cleanup. Discussions appear in neither
-- `search_content` nor `entity_translations`, so nothing is orphaned there.
PRAGMA foreign_keys = ON;

DELETE FROM discussions
WHERE id LIKE 'dsc_practical_%' OR id LIKE 'dsc_editorial_%';

INSERT INTO discussions (
  id, author_user_id, title, body, status, comment_count,
  last_activity_at, created_at, updated_at, image_url, image_alt,
  indexing_policy
) VALUES
  ('dsc_truegrit_001', 'usr_author_kitchen',
   'Kathiya atta rotis turn stiff once they cool - what hydration are you using?',
   'I am using Kathiya atta at roughly seventy percent water and resting the dough twenty minutes. The rotis are soft off the tawa but go leathery within an hour in the casserole. Banshi atta from the same kitchen does not do this. I suspect I am under hydrating, because emmer absorbs more slowly than the flour I grew up with. If you cook with Kathiya regularly, what water ratio and resting time are you landing on, and does a damp cloth actually help past the first thirty minutes?',
   'visible', 0,
   '2026-02-04T08:15:00Z', '2026-02-04T08:15:00Z', '2026-02-04T08:15:00Z',
   '/banners/categories/flours-baking.webp',
   'Stone-ground wheat flour being kneaded for rotis', 'index'),

  ('dsc_truegrit_002', 'usr_author_buying',
   'Banshi or Kathiya semolina for upma - which one stays separate?',
   'Both semolinas cook, but I get different results and I cannot tell whether it is the grain or my roasting. The Banshi version stays separate and slightly firm, while the Kathiya one turns creamier and clumps if I look away. I roast both in ghee until they smell nutty, same water ratio, same standing time. Is that difference genuinely varietal, or am I roasting one longer than the other without noticing? Interested in what people who cook with both have found.',
   'visible', 0,
   '2026-02-11T17:40:00Z', '2026-02-11T17:40:00Z', '2026-02-11T17:40:00Z',
   '/banners/categories/staple-grains.webp',
   'Coarse wheat semolina in a steel bowl', 'index'),

  ('dsc_truegrit_003', 'usr_author_food_care',
   'Paigambari flour for thick bhakri: does it need a hotter tawa?',
   'Paigambari flour behaves differently from the atta I use for chapati. My bhakri cracks at the edges when I pat it out, and the centre stays pale even when the underside has spotted. I am working on a cast iron tawa over a home gas burner. My guess is that the tawa is not hot enough before the dough goes on, and that I am patting it thinner than this flour wants. What thickness and heat are you using, and do you pat with wet palms or dry?',
   'visible', 0,
   '2026-02-19T07:05:00Z', '2026-02-19T07:05:00Z', '2026-02-19T07:05:00Z',
   '/banners/categories/flours-baking.webp',
   'Hand-patted flatbread cooking on a cast iron tawa', 'index'),

  ('dsc_truegrit_004', 'usr_author_farms',
   'Whole wheat pasta from Banshi - how long before it goes past al dente?',
   'Whole wheat pasta seems to have a much shorter window between firm and soft than refined pasta. With the Banshi pasta I get maybe forty seconds between a good bite and something mushy, so I have started pulling it early and finishing it in the sauce. I salt the water properly and do not add oil. Is a narrow window normal for whole grain pasta, or does it point at my water dropping off a rolling boil when the pasta goes in?',
   'visible', 0,
   '2026-02-27T19:25:00Z', '2026-02-27T19:25:00Z', '2026-02-27T19:25:00Z',
   '/banners/categories/pasta-noodles-couscous.webp',
   'Whole wheat pasta draining in a colander', 'index'),

  ('dsc_truegrit_005', 'usr_author_community',
   'Vermicelli clumps every time I make sevai kheer',
   'My sevai kheer keeps ending up as one soft mass instead of separate strands. I dry roast the vermicelli until it colours, then add hot milk, and within a few minutes the strands stick together and swell past what I want. Reducing the milk did not help. I suspect I am roasting unevenly, so some strands go in already softened. How are you roasting yours, and do you add the vermicelli to milk at a full boil or something gentler?',
   'visible', 0,
   '2026-03-05T06:50:00Z', '2026-03-05T06:50:00Z', '2026-03-05T06:50:00Z',
   '/banners/categories/pasta-noodles-couscous.webp',
   'Roasted wheat vermicelli before cooking', 'index'),

  ('dsc_truegrit_006', 'usr_author_kitchen',
   'How coarse should daliya be for a savoury upma versus a milk kheer?',
   'I have been buying one grade of daliya and using it for both a savoury upma and a milk kheer, and neither is quite right. The upma wants some separation and a little chew, while the kheer wants the grain to break down and thicken the milk. Using one coarseness means one of the two is always a compromise. Do you keep two grades on hand, or is there a single middle grind that genuinely works for both?',
   'visible', 0,
   '2026-03-12T13:10:00Z', '2026-03-12T13:10:00Z', '2026-03-12T13:10:00Z',
   '/banners/categories/staple-grains.webp',
   'Broken wheat daliya in a wooden scoop', 'index'),

  ('dsc_truegrit_007', 'usr_author_buying',
   'Storing stone-ground atta through a coastal monsoon',
   'I moved to a coastal town and my stone-ground atta now smells faintly sour within about three weeks, which never happened inland. I keep it in a steel dabba in a cupboard away from the stove. The bran in freshly ground flour presumably picks up moisture faster than refined maida does. I am close to just buying smaller quantities more often instead of solving the storage problem. For anyone in a humid place, what has actually worked, and does refrigerating flour cause condensation trouble when you take it out?',
   'visible', 0,
   '2026-03-20T09:35:00Z', '2026-03-20T09:35:00Z', '2026-03-20T09:35:00Z',
   '/banners/categories/flours-baking.webp',
   'Airtight steel container used for storing flour', 'index'),

  ('dsc_truegrit_008', 'usr_author_food_care',
   'How many days after chakki grinding does atta actually taste different to you?',
   'There is a lot of talk about fresh flour tasting better, and I want to know what people can genuinely detect rather than what they expect. In my kitchen the difference between day one and day five is obvious in the smell, and after that I honestly cannot tell until it starts going stale around week three. I am not measuring anything, only noticing. At what point does the difference stop being noticeable for you, and is it the smell, the finished roti, or both?',
   'visible', 0,
   '2026-03-28T18:05:00Z', '2026-03-28T18:05:00Z', '2026-03-28T18:05:00Z',
   '/banners/categories/flours-baking.webp',
   'Freshly stone-ground wheat flour falling from a chakki', 'index'),

  ('dsc_truegrit_009', 'usr_author_farms',
   'Black gram sattu drink keeps settling into grit at the bottom',
   'When I mix black gram sattu into cold water it looks fine for a minute and then separates into a gritty layer at the bottom of the glass. Whisking harder only delays it. I am using roughly two spoons to a glass, with salt, lemon and a little roasted cumin. A friend says making a thick paste first with a small amount of water and then thinning it fixes this completely. Has that worked for you, and does the water temperature change anything?',
   'visible', 0,
   '2026-04-03T07:20:00Z', '2026-04-03T07:20:00Z', '2026-04-03T07:20:00Z',
   '/banners/categories/pulses-legumes.webp',
   'Roasted black gram sattu flour beside a glass of water', 'index'),

  ('dsc_truegrit_010', 'usr_author_community',
   'Black gram besan versus chickpea besan in chilla - texture differences?',
   'I switched from chickpea besan to black gram besan for chilla and the batter behaves differently. It feels heavier, holds more water, and the finished chilla is softer with less crisp at the edges. The flavour is earthier, which I like. I have not adjusted my ratios at all yet, which is probably the whole problem. If you use black gram besan for chilla, do you thin the batter more, rest it longer, or cook it on lower heat than you would chickpea besan?',
   'visible', 0,
   '2026-04-10T15:45:00Z', '2026-04-10T15:45:00Z', '2026-04-10T15:45:00Z',
   '/banners/categories/pulses-legumes.webp',
   'Besan batter being whisked in a bowl', 'index'),

  ('dsc_truegrit_011', 'usr_author_kitchen',
   'Broken urad dal for dahi vada: soaking time for a light batter',
   'My dahi vada come out dense rather than light, and I think the problem is upstream of the frying. I soak broken urad dal for about four hours, grind with very little water, then beat the batter by hand for a few minutes. It does not float when I drop a little into water. I am unsure whether to soak longer, grind finer, or simply beat far more air in. What soaking time and beating method give you a batter that reliably floats?',
   'visible', 0,
   '2026-04-18T11:30:00Z', '2026-04-18T11:30:00Z', '2026-04-18T11:30:00Z',
   '/banners/categories/pulses-legumes.webp',
   'Soaked split black gram ready for grinding', 'index'),

  ('dsc_truegrit_012', 'usr_author_buying',
   'Whole black gram for dal makhani - overnight soak or pressure cook straight?',
   'For dal makhani I have been soaking whole black gram overnight and then pressure cooking, but I have also seen people skip the soak and cook longer instead. Soaking gives me a cleaner texture, though the skins sometimes separate. Skipping it once left me with uneven cooking and some hard grains in the pot. I would rather not keep guessing. If you make this often, do you soak, and how long after the first pressure are you giving it on low heat?',
   'visible', 0,
   '2026-04-25T20:10:00Z', '2026-04-25T20:10:00Z', '2026-04-25T20:10:00Z',
   '/banners/categories/pulses-legumes.webp',
   'Whole black gram soaking in a bowl of water', 'index'),

  ('dsc_truegrit_013', 'usr_author_food_care',
   'Sattu paratha stuffing dries out and cracks the dough',
   'My sattu paratha stuffing turns powdery and cracks the dough while rolling. I mix the sattu with chopped onion, green chilli, ajwain, mustard oil and salt, and it still does not hold together as a mass. Adding more oil makes it greasy without making it cohesive. I suspect what it needs is moisture rather than fat, perhaps a little water or the liquid drawn out of the onions. What are you adding to bind it, and how long does the filling sit before stuffing?',
   'visible', 0,
   '2026-05-02T08:40:00Z', '2026-05-02T08:40:00Z', '2026-05-02T08:40:00Z',
   '/banners/categories/pulses-legumes.webp',
   'Sattu filling being spooned onto rolled dough', 'index'),

  ('dsc_truegrit_014', 'usr_author_farms',
   'Red lentils whole or broken - does the split really cook faster in practice?',
   'I keep both whole and broken red lentils and the cooking time difference is smaller than I expected, maybe five minutes in an open pot. The broken ones collapse into a smoother dal, which I want for some dishes and not for others. What I cannot work out is whether the whole ones are worth the extra time when I am going to mash them anyway. Do you keep both, and is there a dish where the whole lentil genuinely changes the result?',
   'visible', 0,
   '2026-05-09T16:15:00Z', '2026-05-09T16:15:00Z', '2026-05-09T16:15:00Z',
   '/banners/categories/pulses-legumes.webp',
   'Whole and split red lentils side by side', 'index'),

  ('dsc_truegrit_015', 'usr_author_community',
   'White field pea: how are you using it beyond ghugni?',
   'I bought white field pea mainly for ghugni and now have more than I will use that way. It soaks and cooks reliably and the flavour is mild, so it seems like it should work in more places than one dish. I tried it once in a mixed vegetable curry where it held its shape well. I am wary of treating it as a chickpea substitute without knowing how it behaves. Where else are you using field pea, and does it work in anything that needs a puree?',
   'visible', 0,
   '2026-05-16T06:25:00Z', '2026-05-16T06:25:00Z', '2026-05-16T06:25:00Z',
   '/banners/categories/pulses-legumes.webp',
   'Dried white field peas in a bowl', 'index'),

  ('dsc_truegrit_016', 'usr_author_kitchen',
   'Black mustard oil versus yellow for Bengali fish - pungency comparison',
   'I have both black and yellow mustard oil open and I am trying to use them deliberately rather than reaching for whichever is nearer. The black is noticeably sharper raw and seems to keep more of that bite after smoking, while the yellow settles into something rounder. For fish I currently use the black and for everyday sabzi the yellow. Is that roughly how you split them, or does the choice depend more on whether the dish is eaten hot or at room temperature?',
   'visible', 0,
   '2026-05-23T14:50:00Z', '2026-05-23T14:50:00Z', '2026-05-23T14:50:00Z',
   '/banners/categories/oils-cooking-fats.webp',
   'Two bottles of cold-pressed mustard oil', 'index'),

  ('dsc_truegrit_017', 'usr_author_buying',
   'Smoke point of cold-pressed sesame oil for a regular tadka',
   'I have been treating cold-pressed sesame oil as a finishing oil because I assumed its smoke point was too low for a tadka. Then I watched someone use it for exactly that with no trouble at all. Mine does start to smell sharp fairly quickly on high heat. It may simply be that my pan is hotter than it needs to be for mustard seeds and curry leaves. Do you use cold-pressed sesame for tadka, and are you starting it in a cold pan or a hot one?',
   'visible', 0,
   '2026-05-30T10:05:00Z', '2026-05-30T10:05:00Z', '2026-05-30T10:05:00Z',
   '/banners/categories/oils-cooking-fats.webp',
   'Tempering spices in oil in a small pan', 'index'),

  ('dsc_truegrit_018', 'usr_author_food_care',
   'Flax seed oil - what do you actually do with it if it cannot be heated?',
   'Flax seed oil comes with clear instructions not to heat it, which leaves me with a bottle I use twice a week at most, and it is not cheap. So far it goes on salads and occasionally gets stirred into dal after the flame is off. That does not feel like enough to finish a bottle before it turns. For people who buy it regularly, what does it actually go into in an Indian kitchen, and how quickly are you getting through a bottle?',
   'visible', 0,
   '2026-06-06T19:35:00Z', '2026-06-06T19:35:00Z', '2026-06-06T19:35:00Z',
   '/banners/categories/oils-cooking-fats.webp',
   'Bottle of cold-pressed linseed oil on a counter', 'index'),

  ('dsc_truegrit_019', 'usr_author_farms',
   'Sediment at the bottom of cold-pressed oil bottles: normal or not?',
   'There is a fine sediment settling at the bottom of my cold-pressed oil bottles, more in the sesame than the mustard. I understand that unrefined oils are not filtered the way refined ones are, so some solids are expected. What I do not know is whether that sediment goes rancid faster than the oil above it, and whether I should be pouring off the clear oil or shaking it back in. What have sellers told you, and what do you actually do at home?',
   'visible', 0,
   '2026-06-13T07:55:00Z', '2026-06-13T07:55:00Z', '2026-06-13T07:55:00Z',
   '/banners/categories/oils-cooking-fats.webp',
   'Unfiltered cold-pressed oil showing settled sediment', 'index'),

  ('dsc_truegrit_020', 'usr_author_community',
   'Roasted or plain flax seed for daily grinding - which keeps longer?',
   'I grind flax seed in small batches because ground flax is supposed to turn quickly. I have been buying plain seed and roasting it myself, though the roasted seed is available already done. My assumption is that roasting drives off some moisture and so the whole seed keeps longer, but I have never tested that. If you buy roasted flax seed, how long does it stay good in your kitchen compared to plain, and do you still grind in small batches or make a week at a time?',
   'visible', 0,
   '2026-06-20T12:20:00Z', '2026-06-20T12:20:00Z', '2026-06-20T12:20:00Z',
   '/banners/categories/nuts-seeds-dried-fruit.webp',
   'Roasted flax seeds in a small steel bowl', 'index'),

  ('dsc_truegrit_021', 'usr_author_kitchen',
   'Roasted sesame seeds beyond garnish - where else do you use them?',
   'Roasted sesame seeds mostly end up as a garnish in my cooking, which feels like an underuse given how much flavour they carry. I have started grinding them coarsely into chutney and that works well. I would like to use them somewhere more substantial than a finish. Grinding them into a paste seems the obvious next step, but I am not sure my mixer will get there without adding oil. Where are you using roasted sesame as an actual ingredient?',
   'visible', 0,
   '2026-06-27T17:00:00Z', '2026-06-27T17:00:00Z', '2026-06-27T17:00:00Z',
   '/banners/categories/nuts-seeds-dried-fruit.webp',
   'Roasted sesame seeds on a dark surface', 'index'),

  ('dsc_truegrit_022', 'usr_author_buying',
   'Does anyone track how much flax seed they actually eat in a week?',
   'Every article gives a recommended daily quantity of flax seed and I suspect almost nobody measures it. I started with a level tablespoon a day, then drifted to whenever I remember, which is maybe three times a week. I am curious what real routines look like rather than what is recommended. Do you measure, and have you found a way to attach it to something you already do daily so that it does not depend on remembering?',
   'visible', 0,
   '2026-07-02T09:10:00Z', '2026-07-02T09:10:00Z', '2026-07-02T09:10:00Z',
   '/banners/categories/nuts-seeds-dried-fruit.webp',
   'Measured spoon of ground flax seed', 'index'),

  ('dsc_truegrit_023', 'usr_author_food_care',
   'What do you check on an organic certification label before buying?',
   'Organic labels carry certification marks, licence numbers and sometimes a certifying body I have never heard of. I have started looking for the certification number and confirming the body exists, and that is roughly where my checking stops. It is slow, and I am not confident it tells me very much. For people who buy organic regularly, what do you actually look at on the pack, and has checking ever made you put something back on the shelf?',
   'visible', 0,
   '2026-07-09T15:30:00Z', '2026-07-09T15:30:00Z', '2026-07-09T15:30:00Z',
   '/banners/content/community-useful-conversations.webp',
   'Close view of an organic certification label on a food pack', 'index'),

  ('dsc_truegrit_024', 'usr_author_farms',
   'What farm information would genuinely change your buying decision?',
   'Packs are starting to carry farm names and locations, which I like in principle. In practice I am not sure a village name changes anything for me, because I have no way to verify it. What might change my decision is the harvest date, the specific variety, and whether the pack came from one farm or a pooled group of them. Those feel checkable. What information would genuinely shift your buying, as opposed to simply feeling reassuring on the shelf?',
   'visible', 0,
   '2026-07-16T08:00:00Z', '2026-07-16T08:00:00Z', '2026-07-16T08:00:00Z',
   '/banners/content/community-useful-conversations.webp',
   'Farmer standing in a wheat field at harvest time', 'index'),

  ('dsc_truegrit_025', 'usr_author_community',
   'Bulk five kilo packs versus small ones for a two person household',
   'We are two people and I keep buying five kilo packs of flour and pulses because the per kilo price is clearly better. Then the last kilo sits around long enough that I am not happy using it. The saving is probably being cancelled by waste I am not counting anywhere. Smaller packs cost more per kilo but everything gets used fresh. For small households, where have you landed, and does the answer differ between flour and whole pulses?',
   'visible', 0,
   '2026-07-23T18:45:00Z', '2026-07-23T18:45:00Z', '2026-07-23T18:45:00Z',
   '/banners/categories/bulk-refill-value.webp',
   'Bulk refill sacks of grain and pulses', 'index'),

  ('dsc_truegrit_026', 'usr_author_kitchen',
   'Keeping weevils out of grain without chemical tablets',
   'I have been keeping neem leaves and dried red chilli in my grain containers and still found weevils in a jar of whole wheat this month. The container was steel with a tight lid, kept in a dark cupboard. It is possible the eggs arrived with the grain rather than afterwards, in which case storage was never going to be the fix. Has freezing new grain for a few days before storing worked for you, and how long do you leave it in?',
   'visible', 0,
   '2026-07-30T11:15:00Z', '2026-07-30T11:15:00Z', '2026-07-30T11:15:00Z',
   '/banners/categories/kitchen-dining-storage.webp',
   'Glass storage jars holding whole grains in a pantry', 'index'),

  ('dsc_truegrit_027', 'usr_author_buying',
   'Emmer wheat and blood sugar - has anyone measured rather than assumed?',
   'There are a great many claims about emmer wheat being better for blood sugar than modern wheat, and very little that looks like measurement. If you monitor glucose and have switched from regular atta to Kathiya, did you see a difference in your own readings? I am interested in what you actually recorded, how long after eating you took it, and whether anything else changed at the same time, because that is usually where these comparisons quietly fall apart.',
   'visible', 0,
   '2026-08-03T07:35:00Z', '2026-08-03T07:35:00Z', '2026-08-03T07:35:00Z',
   '/banners/categories/staple-grains.webp',
   'Emmer wheat grains held in an open palm', 'index'),

  ('dsc_truegrit_028', 'usr_author_food_care',
   'Cooking gas cost of whole grains compared to refined - worth it?',
   'Whole grains and whole pulses take noticeably longer to cook than their refined or split versions, and all of that time is gas. Over a month I doubt it amounts to much, but I have never actually estimated it. Pressure cooking closes most of the gap for pulses and rather less for grains like whole wheat daliya. Has anyone worked out roughly what the difference costs, or found that soaking properly removes most of the extra cooking time?',
   'visible', 0,
   '2026-08-06T16:40:00Z', '2026-08-06T16:40:00Z', '2026-08-06T16:40:00Z',
   '/banners/categories/regional-indian-pantry.webp',
   'Pressure cooker on a gas burner in a home kitchen', 'index'),

  ('dsc_truegrit_029', 'usr_author_farms',
   'Grinding your own besan at home versus buying it ready',
   'I have started grinding besan at home from whole gram because the flavour is noticeably fresher for about the first week. The problem is that my mixer leaves it slightly coarser than shop besan, and that shows up in chilla as a grainy texture. Sieving helps but wastes a fair amount of what I just ground. Are you grinding at home, and if so are you passing it through twice, sieving and regrinding the coarse part, or simply accepting the texture?',
   'visible', 0,
   '2026-08-09T10:25:00Z', '2026-08-09T10:25:00Z', '2026-08-09T10:25:00Z',
   '/banners/categories/pulses-legumes.webp',
   'Freshly ground gram flour beside whole black gram', 'index'),

  ('dsc_truegrit_030', 'usr_author_community',
   'Which of the three wheat varieties do you keep stocked year round?',
   'Between Kathiya, Banshi and Paigambari I have ended up keeping all three, which is more flour than a household of three needs and means one of them is always the oldest bag in the cupboard. If I had to keep two, I would probably drop the one I use only for a single dish. I am curious how others have simplified this. Which is your everyday atta, which do you buy only when a recipe calls for it, and did you try all three first?',
   'visible', 0,
   '2026-08-12T13:55:00Z', '2026-08-12T13:55:00Z', '2026-08-12T13:55:00Z',
   '/banners/categories/staple-grains.webp',
   'Three varieties of wheat grain in separate bowls', 'index');
