import RAW_EN_MESSAGES from "./raw-messages";

/**
 * The English source catalogue, and the types every translation is checked
 * against.
 *
 * English lives here — client-safe — rather than alongside the other
 * catalogues, for one reason: it is the guaranteed fallback. A translation that
 * is missing a key, or that ships a blank string, must still render *words*,
 * and the only way to promise that on the client is for English to already be
 * in the bundle. It is roughly 4KB, which is a fair price for "no page can ever
 * render an empty label".
 *
 * Every other catalogue is `Partial`, loaded on the server, and merged over
 * this one. `i18n.test.ts` fails the build if any registered locale is missing
 * a key, so "partial" is a type-level allowance, not a shipping state.
 *
 * SCOPE. These are the storefront's *own* strings: chrome, navigation, forms,
 * buttons, states. Catalogue and editorial content — product names, blog posts,
 * farm descriptions — come from the database in the language the admin wrote
 * them, and are not translated here. Interpolation is `{name}`-style, handled
 * by `translate()`.
 */

export const EN_MESSAGES = {
  ...RAW_EN_MESSAGES,
  // -- Chrome and shared actions --------------------------------------------
  "common.skipToContent": "Skip to content",
  "common.search": "Search",
  "common.searchProducts": "Search products",
  "common.searchPlaceholder": "Search products…",
  "common.cart": "Cart",
  "common.cartWithCount": "Cart, {count} items",
  "common.account": "Account",
  "common.openMenu": "Open menu",
  "common.closeMenu": "Close menu",
  "common.home": "Home",
  "common.loading": "Loading…",
  "common.save": "Save",
  "common.cancel": "Cancel",
  "common.remove": "Remove",
  "common.optional": "optional",
  "common.somethingWentWrong": "Something went wrong",
  "common.tryAgain": "Please try again in a moment.",
  "common.backToMarket": "Back to the market",
  "common.notFoundTitle": "This patch is empty.",
  "common.notFoundBody": "The page you are looking for may have moved with the season.",
  "common.demoMode": "Demo mode — connect the API to use this form.",

  // -- Footer ---------------------------------------------------------------
  "footer.tagline":
    "Traceable organic food from verified farms, responsible brands and seasonal harvests — delivered with complete transparency.",
  "footer.market": "Market",
  "footer.support": "Support",
  "footer.rights": "© 2026 True Grit. Certified organic, honestly traded.",

  // -- Language switcher ----------------------------------------------------
  "language.label": "Language",
  "language.change": "Change language",
  "language.indian": "Indian languages",
  "language.world": "World languages",
  "language.apply": "Apply",

  // -- Account and sign-in --------------------------------------------------
  "auth.signIn": "Sign in",
  "auth.signOut": "Sign out",
  "auth.signingOut": "Signing out…",
  "auth.signUp": "Sign up",
  "auth.createAccount": "Create account",
  "auth.yourAccount": "Your account",
  "auth.email": "Email",
  "auth.password": "Password",
  "auth.name": "Name",
  "auth.mobile": "Mobile",
  "auth.forgotPassword": "Forgot password?",
  "auth.send": "Send",
  "auth.resetLinkSent": "If that email has an account, a reset link is on its way.",
  "auth.pleaseWait": "Please wait…",
  "auth.noContact": "No contact on file",
  "auth.unavailable": "Sign-in is temporarily unavailable",

  // -- Contact form ---------------------------------------------------------
  "contact.name": "Name",
  "contact.email": "Email",
  "contact.phone": "Phone",
  "contact.phoneHint":
    "So we can call you back — include the country code for numbers outside India.",
  "contact.subject": "Subject",
  "contact.message": "Message",
  "contact.send": "Send message",
  "contact.sending": "Sending…",
  "contact.sent": "Your message has been sent. We will reply by email.",
  "contact.failed": "Could not send your message. Please check your details and try again.",

  // -- Comments on blog posts and recipes -----------------------------------
  "comments.heading": "Comments",
  "comments.headingWithCount": "Comments ({count})",
  "comments.none": "No comments yet. Be the first to say something.",
  "comments.signInPrompt": "Sign in to join the conversation.",
  "comments.placeholder": "Share what you thought…",
  "comments.post": "Post comment",
  "comments.posting": "Posting…",
  "comments.closed": "Comments are closed on this post.",
  "comments.failed": "Could not post your comment. Please try again.",
  "comments.loading": "Loading comments…",

  // -- Farms and the partnership call to action -----------------------------
  "farms.eyebrow": "The people",
  "farms.heading": "Farms we can vouch for",
  "farms.since": "Since {year}",
  "farms.partnerHeading": "Grow with True Grit",
  "farms.partnerBody":
    "We are always looking for growers who farm the way we describe on the label. Tell us about your farm and our sourcing team will get in touch.",
  "farms.partnerButton": "Apply to join",

  // -- Farm partnership application form ------------------------------------
  "partner.eyebrow": "For growers",
  "partner.title": "Partner with True Grit",
  "partner.intro":
    "Tell us about your land, how you grow, and what you have to sell. Every application is read by a person, and we call you back on the number you leave.",
  "partner.sectionContact": "How we reach you",
  "partner.sectionFarm": "About the farm",
  "partner.sectionStory": "Your produce and practices",
  "partner.contactName": "Your name",
  "partner.contactEmail": "Email",
  "partner.contactPhone": "Mobile number",
  "partner.contactPhoneHint":
    "We call before we write. Include the country code for numbers outside India.",
  "partner.farmName": "Farm or collective name",
  "partner.region": "Region or district",
  "partner.state": "State",
  "partner.city": "Town or village",
  "partner.pincode": "PIN code",
  "partner.establishedYear": "Year established",
  "partner.landArea": "Land under cultivation",
  "partner.landAreaHint": "For example: 12 acres, or 4 hectares.",
  "partner.certification": "Certification",
  "partner.certificationHint": "Organic certification body and status, or none yet.",
  "partner.primaryProduce": "What you grow",
  "partner.practices": "How you farm",
  "partner.website": "Website or social page",
  "partner.message": "Anything else we should know",
  "partner.messageHint": "At least a couple of sentences — this is what we read first.",
  "partner.submit": "Send application",
  "partner.submitting": "Sending…",
  "partner.successTitle": "Application received",
  "partner.successBody":
    "Thank you. Our sourcing team will read it and call you on the number you gave us.",
  "partner.closedTitle": "Applications are closed",
  "partner.closedBody":
    "We are not taking new farm applications right now. Please write to us and we will let you know when they reopen.",
  "partner.failed": "Could not send your application. Please check your details and try again.",

  // -- Community content submissions ----------------------------------------
  "submit.phone": "Mobile number",
  "submit.phoneHint": "Our editors call if they have a question about your piece.",
} as const;

/** Every key a page may ask for. Derived from English so the source catalogue
 *  is the single definition — adding a string in one place adds it everywhere. */
export type MessageKey = keyof typeof EN_MESSAGES;

/**
 * A translation catalogue. Partial by design: a new English string ships
 * immediately and falls back to English in every other language until it is
 * translated, rather than blocking the release or — far worse — rendering an
 * empty label. `i18n.test.ts` is what stops "temporarily partial" becoming
 * permanent.
 */
export type LocaleMessages = Partial<Record<MessageKey, string>>;

/** A complete catalogue, as handed to the provider. */
export type ResolvedMessages = Record<MessageKey, string>;

/**
 * Look up `key` and substitute `{placeholder}` values.
 *
 * Resolution order is: the locale's own string, then English, then the key
 * itself. That last step is deliberate and never removed — a raw
 * `partner.submit` on screen is ugly but diagnosable, whereas an empty button
 * is a bug nobody can see the shape of.
 *
 * Placeholders left unsupplied are preserved verbatim for the same reason.
 */
export function translate(
  messages: Partial<ResolvedMessages>,
  key: MessageKey,
  values?: Readonly<Record<string, string | number>>,
): string {
  const template = messages[key] ?? EN_MESSAGES[key] ?? key;
  if (!values) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match,
  );
}
