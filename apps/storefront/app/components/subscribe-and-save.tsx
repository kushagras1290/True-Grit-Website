/**
 * "Subscribe & Save" -- set up a recurring cash-on-delivery order of this
 * exact variant/quantity. Off entirely unless an owner has switched the
 * sitewide feature on (see migration 0064 / services.subscriptions); the API
 * refuses creation while off regardless, so hiding the widget here is UX,
 * not the enforcement.
 *
 * Shares the quantity the "Add to basket" controls above it are set to
 * (passed in as a prop) rather than tracking a second, easily-desynced copy.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router";

import {
  createAddress,
  createSubscription,
  getSubscriptionDiscountPercent,
  listMyAddresses,
} from "../lib/commerce";
import { useCustomer } from "../lib/customer-auth";
import { useSiteSettings } from "../lib/site-settings";
import type { CustomerAddress, SubscriptionFrequency } from "@truegrit/contracts";

const FREQUENCY_OPTIONS: { value: SubscriptionFrequency; label: string }[] = [
  { value: "weekly", label: "Every week" },
  { value: "biweekly", label: "Every 2 weeks" },
  { value: "monthly", label: "Every month" },
];

interface NewAddressDraft {
  recipientName: string;
  phoneE164: string;
  line1: string;
  line2: string;
  city: string;
  state: string;
  postalCode: string;
}

const EMPTY_ADDRESS: NewAddressDraft = {
  recipientName: "",
  phoneE164: "",
  line1: "",
  line2: "",
  city: "",
  state: "",
  postalCode: "",
};

export function SubscribeAndSave({
  variantId,
  quantity,
  productName,
}: {
  variantId: string;
  quantity: number;
  productName: string;
}) {
  const siteSettings = useSiteSettings();
  const { customer, status } = useCustomer();
  const [discountPercent, setDiscountPercent] = useState<number | null>(null);
  const [addresses, setAddresses] = useState<CustomerAddress[] | null>(null);
  const [addressId, setAddressId] = useState("");
  const [frequency, setFrequency] = useState<SubscriptionFrequency>("weekly");
  const [addingAddress, setAddingAddress] = useState(false);
  const [addressDraft, setAddressDraft] = useState<NewAddressDraft>(EMPTY_ADDRESS);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [subscribed, setSubscribed] = useState(false);

  const enabled = siteSettings.subscriptions.enabled;
  const signedIn = status === "authenticated";

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    getSubscriptionDiscountPercent()
      .then((percent) => active && setDiscountPercent(percent))
      .catch(() => active && setDiscountPercent(0));
    return () => {
      active = false;
    };
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !signedIn) return;
    let active = true;
    listMyAddresses()
      .then((items) => {
        if (!active) return;
        setAddresses(items);
        const preferred = items.find((entry) => entry.isDefaultDelivery) ?? items[0];
        if (preferred) setAddressId(preferred.id);
        else setAddingAddress(true);
      })
      .catch(() => active && setAddresses([]));
    return () => {
      active = false;
    };
  }, [enabled, signedIn]);

  if (!enabled || status === "loading") return null;

  if (!signedIn) {
    return (
      <div className="mt-4 rounded-md border border-dashed border-line bg-canvas px-4 py-3 text-sm text-ink-muted">
        <span className="font-medium text-ink">Subscribe &amp; Save</span> — sign in from the
        account menu to set up recurring delivery of {productName}.
      </div>
    );
  }

  async function handleAddAddress() {
    setError(null);
    if (
      !addressDraft.recipientName.trim() ||
      !addressDraft.line1.trim() ||
      !addressDraft.city.trim() ||
      !addressDraft.state.trim() ||
      !addressDraft.postalCode.trim()
    ) {
      setError("Fill in the recipient name, address, city, state and postal code.");
      return;
    }
    setSaving(true);
    try {
      const created = await createAddress({
        recipientName: addressDraft.recipientName.trim(),
        phoneE164: addressDraft.phoneE164.trim() || undefined,
        line1: addressDraft.line1.trim(),
        line2: addressDraft.line2.trim() || undefined,
        city: addressDraft.city.trim(),
        state: addressDraft.state.trim(),
        postalCode: addressDraft.postalCode.trim(),
      });
      setAddresses((current) => [...(current ?? []), created]);
      setAddressId(created.id);
      setAddingAddress(false);
      setAddressDraft(EMPTY_ADDRESS);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the address.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSubscribe() {
    setError(null);
    if (!addressId) {
      setError("Add a delivery address first.");
      return;
    }
    setSaving(true);
    try {
      await createSubscription({ variantId, quantity, frequency, addressId });
      setSubscribed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set up the subscription.");
    } finally {
      setSaving(false);
    }
  }

  if (subscribed) {
    return (
      <div className="mt-4 rounded-md border border-success/40 bg-success/5 px-4 py-3 text-sm text-success">
        Subscribed. Your first delivery is scheduled based on your chosen frequency — manage it
        anytime from{" "}
        <Link to="/account" className="underline underline-offset-4">
          your account
        </Link>
        .
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-md border border-line bg-canvas px-4 py-4">
      <p className="text-sm font-medium text-ink">
        Subscribe &amp; Save
        {discountPercent !== null && discountPercent > 0 ? ` ${discountPercent}%` : ""}
      </p>
      <p className="mt-1 text-xs text-ink-muted">
        Recurring cash-on-delivery orders of {quantity} × {productName} at your chosen frequency.
        Pause or cancel anytime from your account.
      </p>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="sub-frequency" className="block text-xs font-medium text-ink-muted">
            Deliver
          </label>
          <select
            id="sub-frequency"
            value={frequency}
            onChange={(event) => setFrequency(event.target.value as SubscriptionFrequency)}
            className="mt-1 min-h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink"
          >
            {FREQUENCY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {addresses && addresses.length > 0 && !addingAddress ? (
          <div>
            <label htmlFor="sub-address" className="block text-xs font-medium text-ink-muted">
              Deliver to
            </label>
            <select
              id="sub-address"
              value={addressId}
              onChange={(event) => setAddressId(event.target.value)}
              className="mt-1 min-h-9 max-w-xs rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink"
            >
              {addresses.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.label ? `${entry.label} — ` : ""}
                  {entry.line1}, {entry.city}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="mt-1 block text-xs text-brand hover:underline"
              onClick={() => setAddingAddress(true)}
            >
              Use a different address
            </button>
          </div>
        ) : null}
      </div>

      {addingAddress ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <input
            value={addressDraft.recipientName}
            onChange={(event) =>
              setAddressDraft((current) => ({ ...current, recipientName: event.target.value }))
            }
            placeholder="Recipient name"
            className="min-h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink sm:col-span-2"
          />
          <input
            value={addressDraft.line1}
            onChange={(event) =>
              setAddressDraft((current) => ({ ...current, line1: event.target.value }))
            }
            placeholder="Address line 1"
            className="min-h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink sm:col-span-2"
          />
          <input
            value={addressDraft.line2}
            onChange={(event) =>
              setAddressDraft((current) => ({ ...current, line2: event.target.value }))
            }
            placeholder="Address line 2 (optional)"
            className="min-h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink sm:col-span-2"
          />
          <input
            value={addressDraft.city}
            onChange={(event) =>
              setAddressDraft((current) => ({ ...current, city: event.target.value }))
            }
            placeholder="City"
            className="min-h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink"
          />
          <input
            value={addressDraft.state}
            onChange={(event) =>
              setAddressDraft((current) => ({ ...current, state: event.target.value }))
            }
            placeholder="State"
            className="min-h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink"
          />
          <input
            value={addressDraft.postalCode}
            onChange={(event) =>
              setAddressDraft((current) => ({ ...current, postalCode: event.target.value }))
            }
            placeholder="Postal code"
            className="min-h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink"
          />
          <input
            value={addressDraft.phoneE164}
            onChange={(event) =>
              setAddressDraft((current) => ({ ...current, phoneE164: event.target.value }))
            }
            placeholder="Phone (optional)"
            className="min-h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink"
          />
          <div className="flex gap-2 sm:col-span-2">
            <button
              type="button"
              disabled={saving}
              onClick={handleAddAddress}
              className="min-h-9 rounded-sm border border-line-strong px-3 text-xs font-medium text-ink hover:bg-surface disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save address"}
            </button>
            {addresses && addresses.length > 0 ? (
              <button
                type="button"
                onClick={() => setAddingAddress(false)}
                className="min-h-9 rounded-sm px-3 text-xs text-ink-muted hover:underline"
              >
                Cancel
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {error ? <p className="mt-2 text-xs text-danger">{error}</p> : null}

      {!addingAddress ? (
        <button
          type="button"
          disabled={saving || !addressId}
          onClick={handleSubscribe}
          className="mt-3 min-h-10 rounded-sm border border-brand px-4 text-sm font-medium text-brand hover:bg-subtle disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? "Setting up..." : "Start subscription"}
        </button>
      ) : null}
    </div>
  );
}
