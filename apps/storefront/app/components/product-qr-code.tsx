/** A scannable link back to this exact product page — printed on packaging
 * or shown on-screen as a portable, verifiable trace-back to where this food
 * came from, alongside the traceability steps on the product page. */

import { QRCodeSVG } from "qrcode.react";

import { LocalizedText, useLocalizeText } from "../lib/i18n/localized-text";

export function ProductQrCode({ url }: { url: string }) {
  const localize = useLocalizeText();
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="rounded-md border border-line bg-surface p-3">
        <QRCodeSVG
          value={url}
          size={112}
          level="M"
          marginSize={0}
          title={localize("Scan to open this product on your phone")}
        />
      </div>
      <p className="max-w-36 text-center text-xs text-ink-muted">
        <LocalizedText>Scan to open this product on your phone</LocalizedText>
      </p>
    </div>
  );
}
