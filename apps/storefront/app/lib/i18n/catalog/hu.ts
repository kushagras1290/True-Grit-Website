/** Hungarian (Magyar). Keys and structure are defined in `../messages.ts`. */

import type { LocaleMessages } from "../messages";

const hu: LocaleMessages = {
  "common.skipToContent": "Ugrás a tartalomra",
  "common.search": "Keresés",
  "common.searchProducts": "Termékek keresése",
  "common.searchPlaceholder": "Termékek keresése…",
  "common.cart": "Kosár",
  "common.cartWithCount": "Kosár, {count} termék",
  "common.account": "Fiók",
  "common.openMenu": "Menü megnyitása",
  "common.closeMenu": "Menü bezárása",
  "common.home": "Kezdőlap",
  "common.loading": "Betöltés…",
  "common.save": "Mentés",
  "common.cancel": "Mégse",
  "common.remove": "Eltávolítás",
  "common.optional": "opcionális",
  "common.somethingWentWrong": "Valami hiba történt",
  "common.tryAgain": "Kérjük, próbálja újra egy kis idő múlva.",
  "common.backToMarket": "Vissza a piacra",
  "common.notFoundTitle": "Ez a földdarab üres.",
  "common.notFoundBody": "A keresett oldal talán a szezonnal együtt elköltözött.",
  "common.demoMode": "Demó mód — csatlakoztassa az API-t az űrlap használatához.",

  "footer.tagline":
    "Nyomon követhető bio élelmiszerek ellenőrzött gazdaságokból, felelős márkáktól és szezonális termésekből — teljes átláthatósággal szállítva.",
  "footer.market": "Piac",
  "footer.support": "Ügyfélszolgálat",
  "footer.rights": "© 2026 True Grit. Minősített bio, tisztességes kereskedelemmel.",

  "language.label": "Nyelv",
  "language.change": "Nyelv váltása",
  "language.indian": "Indiai nyelvek",
  "language.world": "Világnyelvek",
  "language.apply": "Alkalmaz",

  "auth.signIn": "Bejelentkezés",
  "auth.signOut": "Kijelentkezés",
  "auth.signingOut": "Kijelentkezés…",
  "auth.signUp": "Regisztráció",
  "auth.createAccount": "Fiók létrehozása",
  "auth.yourAccount": "Az Ön fiókja",
  "auth.email": "E-mail",
  "auth.password": "Jelszó",
  "auth.name": "Név",
  "auth.mobile": "Mobil",
  "auth.forgotPassword": "Elfelejtette a jelszavát?",
  "auth.send": "Küldés",
  "auth.resetLinkSent":
    "Ha van fiók ehhez az e-mail-címhez, egy visszaállító hivatkozás már úton van.",
  "auth.pleaseWait": "Kérjük, várjon…",
  "auth.noContact": "Nincs rögzített elérhetőség",
  "auth.unavailable": "A bejelentkezés átmenetileg nem elérhető",

  "contact.name": "Név",
  "contact.email": "E-mail",
  "contact.phone": "Telefon",
  "contact.phoneHint":
    "Hogy visszahívhassuk — Indián kívüli számoknál adja meg az országhívó számot.",
  "contact.subject": "Tárgy",
  "contact.message": "Üzenet",
  "contact.send": "Üzenet küldése",
  "contact.sending": "Küldés…",
  "contact.sent": "Az üzenetet elküldtük. E-mailben válaszolunk.",
  "contact.failed":
    "Az üzenetet nem sikerült elküldeni. Kérjük, ellenőrizze az adatokat, és próbálja újra.",

  "comments.heading": "Hozzászólások",
  "comments.headingWithCount": "Hozzászólások ({count})",
  "comments.none": "Még nincs hozzászólás. Legyen Ön az első.",
  "comments.signInPrompt": "Jelentkezzen be, hogy csatlakozhasson a beszélgetéshez.",
  "comments.placeholder": "Ossza meg a véleményét…",
  "comments.post": "Hozzászólás közzététele",
  "comments.posting": "Közzététel…",
  "comments.closed": "A hozzászólások le vannak zárva ehhez a bejegyzéshez.",
  "comments.failed": "A hozzászólást nem sikerült közzétenni. Próbálja újra.",
  "comments.loading": "Hozzászólások betöltése…",

  "farms.eyebrow": "Az emberek",
  "farms.heading": "Gazdaságok, amelyekért kezeskedünk",
  "farms.since": "{year} óta",
  "farms.partnerHeading": "Növekedjen a True Grittel",
  "farms.partnerBody":
    "Mindig olyan termelőket keresünk, akik pontosan úgy gazdálkodnak, ahogyan a címkén szerepel. Meséljen a gazdaságáról, és beszerzési csapatunk jelentkezik.",
  "farms.partnerButton": "Jelentkezés csatlakozásra",

  "partner.eyebrow": "Termelőknek",
  "partner.title": "Legyen a True Grit partnere",
  "partner.intro":
    "Meséljen a földjéről, a gazdálkodási módszereiről és arról, mit szeretne eladni. Minden jelentkezést egy ember olvas el, és visszahívjuk a megadott számon.",
  "partner.sectionContact": "Hogyan érjük el Önt",
  "partner.sectionFarm": "A gazdaságról",
  "partner.sectionStory": "Termékei és gazdálkodási módszerei",
  "partner.contactName": "Az Ön neve",
  "partner.contactEmail": "E-mail",
  "partner.contactPhone": "Mobilszám",
  "partner.contactPhoneHint":
    "Előbb hívunk, mielőtt írnánk. Indián kívüli számoknál adja meg az országhívó számot.",
  "partner.farmName": "A gazdaság vagy szövetkezet neve",
  "partner.region": "Régió vagy körzet",
  "partner.state": "Állam/tartomány",
  "partner.city": "Város vagy falu",
  "partner.pincode": "Irányítószám",
  "partner.establishedYear": "Alapítás éve",
  "partner.landArea": "Megművelt terület",
  "partner.landAreaHint": "Például: 12 acre vagy 4 hektár.",
  "partner.certification": "Tanúsítvány",
  "partner.certificationHint": "Bio tanúsító szervezet és állapot, vagy még nincs.",
  "partner.primaryProduce": "Mit termeszt",
  "partner.practices": "Hogyan gazdálkodik",
  "partner.website": "Weboldal vagy közösségimédia-oldal",
  "partner.message": "Bármi más, amit tudnunk kellene",
  "partner.messageHint": "Legalább néhány mondat — ezt olvassuk el először.",
  "partner.submit": "Jelentkezés elküldése",
  "partner.submitting": "Küldés…",
  "partner.successTitle": "Jelentkezés beérkezett",
  "partner.successBody":
    "Köszönjük. Beszerzési csapatunk elolvassa, és visszahívjuk a megadott számon.",
  "partner.closedTitle": "A jelentkezés jelenleg zárva",
  "partner.closedBody":
    "Jelenleg nem fogadunk új gazdasági jelentkezéseket. Írjon nekünk, és értesítjük, ha újra megnyílik.",
  "partner.failed":
    "A jelentkezést nem sikerült elküldeni. Kérjük, ellenőrizze az adatokat, és próbálja újra.",

  "submit.phone": "Mobilszám",
  "submit.phoneHint": "Szerkesztőink hívnak, ha kérdésük van az Ön írásával kapcsolatban.",
};

export default hu;
