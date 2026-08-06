/** Gift cards (migration 0082): issuable, purchasable stored-value codes
 * redeemable at checkout.
 *
 * Balance is derived from gift_card_redemptions, never stored -- see
 * services.gift_cards' module docstring. The sitewide on/off switch lives on
 * Site Settings, next to the other storefront switches -- this page only
 * manages the cards themselves. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  Button,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  Modal,
  Pagination,
  SearchBox,
  StatusPill,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { formatDateTime, formatMoney } from "../lib/format";
import { usePermissions } from "../lib/permissions";
import { T } from "../lib/i18n";

interface IssueFormState {
  balance: string;
  issuedToEmail: string;
  note: string;
  expiresAt: string;
  code: string;
}

const EMPTY_FORM: IssueFormState = {
  balance: "500",
  issuedToEmail: "",
  note: "",
  expiresAt: "",
  code: "",
};

function IssueGiftCardModal({ onClose, onIssued }: { onClose: () => void; onIssued: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState<IssueFormState>(EMPTY_FORM);

  function update<K extends keyof IssueFormState>(key: K, value: IssueFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  const mutation = useMutation({
    mutationFn: () =>
      api.issueGiftCard({
        balanceMinor: Math.round((Number(form.balance) || 0) * 100),
        issuedToEmail: form.issuedToEmail.trim() || null,
        note: form.note.trim() || null,
        expiresAt: form.expiresAt ? `${form.expiresAt}T00:00:00Z` : null,
        code: form.code.trim() || null,
      }),
    onSuccess: (result) => {
      toast.success(`Gift card ${result.code} issued.`);
      onIssued();
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not issue the gift card."),
  });

  return (
    <Modal title="Issue a gift card" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!form.balance || Number(form.balance) <= 0) {
            toast.error("Set a value for the card.");
            return;
          }
          mutation.mutate();
        }}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Value, ₹" htmlFor="gift-card-balance">
            <Input
              id="gift-card-balance"
              type="number"
              min={100}
              max={50_000}
              step="1"
              value={form.balance}
              onChange={(event) => update("balance", event.target.value)}
            />
          </Field>
          <Field label="Code (optional — generated if left blank)" htmlFor="gift-card-code">
            <Input
              id="gift-card-code"
              value={form.code}
              maxLength={24}
              placeholder="e.g. DIWALI500"
              onChange={(event) => update("code", event.target.value)}
            />
          </Field>
        </div>

        <Field label="Recipient email (optional)" htmlFor="gift-card-email">
          <Input
            id="gift-card-email"
            type="email"
            value={form.issuedToEmail}
            maxLength={254}
            placeholder="customer@example.com"
            onChange={(event) => update("issuedToEmail", event.target.value)}
          />
        </Field>

        <Field label="Internal note (optional)" htmlFor="gift-card-note">
          <Textarea
            id="gift-card-note"
            rows={2}
            value={form.note}
            maxLength={300}
            placeholder="Why this card was issued — a goodwill gesture, a return resolved as store credit, etc."
            onChange={(event) => update("note", event.target.value)}
          />
        </Field>

        <Field label="Expires (optional)" htmlFor="gift-card-expires">
          <Input
            id="gift-card-expires"
            type="date"
            value={form.expiresAt}
            onChange={(event) => update("expiresAt", event.target.value)}
          />
        </Field>

        <div className="flex justify-end gap-2 border-t border-line pt-3">
          <Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            <T>Cancel</T>
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? <T>{"Issuing..."}</T> : <T>{"Issue gift card"}</T>}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function GiftCardDetailModal({
  giftCardId,
  onClose,
  onChanged,
}: {
  giftCardId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data: card, isLoading } = useQuery({
    queryKey: ["admin-gift-card", giftCardId],
    queryFn: () => api.getGiftCard(giftCardId),
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelGiftCard(giftCardId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-gift-card", giftCardId] });
      onChanged();
      toast.success("Gift card cancelled.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not cancel the gift card."),
  });

  return (
    <Modal title="Gift card" onClose={onClose}>
      {isLoading || !card ? (
        <p className="text-sm text-ink-muted">
          <T>Loading...</T>
        </p>
      ) : (
        <div className="space-y-5">
          <div>
            <p className="font-mono font-display text-lg text-ink">{card.code}</p>
            <p className="mt-1 text-sm text-ink-muted">
              {formatMoney(card.balanceMinor, card.currencyCode)} <T>{"remaining of"}</T>{" "}
              {formatMoney(card.initialBalanceMinor, card.currencyCode)}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <StatusPill status={card.status} />
              {card.expiresAt ? (
                <span className="text-xs text-ink-muted">
                  <T>Expires</T> {formatDateTime(card.expiresAt)}
                </span>
              ) : null}
            </div>
            {card.issuedToEmail ? (
              <p className="mt-2 text-sm text-ink">{card.issuedToEmail}</p>
            ) : null}
            {card.note ? <p className="mt-1 text-sm text-ink-muted">{card.note}</p> : null}
          </div>

          <div>
            <h3 className="text-sm font-medium text-ink">
              <T>Redemption history</T>
            </h3>
            {card.redemptions.length === 0 ? (
              <p className="mt-1 text-sm text-ink-muted">
                <T>Not redeemed against any order yet.</T>
              </p>
            ) : (
              <ul className="mt-2 divide-y divide-line rounded-md border border-line">
                {card.redemptions.map((entry) => (
                  <li
                    key={entry.orderId}
                    className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                  >
                    <span className="font-mono text-sm text-ink">{entry.orderReference}</span>
                    <span className="text-sm text-ink-muted">
                      {formatMoney(entry.amountMinor, card.currencyCode)} ·{" "}
                      {formatDateTime(entry.redeemedAt)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex justify-between border-t border-line pt-3">
            {card.status === "active" ? (
              <Button
                type="button"
                variant="destructive"
                disabled={cancelMutation.isPending}
                onClick={() => cancelMutation.mutate()}
              >
                {cancelMutation.isPending ? <T>{"Cancelling..."}</T> : <T>{"Cancel card"}</T>}
              </Button>
            ) : (
              <span />
            )}
            <Button type="button" variant="secondary" onClick={onClose}>
              <T>Close</T>
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

export function GiftCardsListPage() {
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const canManage = permissions.has("gift_cards.manage");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [issuing, setIssuing] = useState(false);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const limit = 25;
  const offset = (page - 1) * limit;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-gift-cards", searchQuery, page],
    queryFn: () => api.giftCards({ search: searchQuery || undefined, limit, offset }),
  });
  const cards = data?.items ?? [];

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["admin-gift-cards"] });
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">
            <T>Gift Cards</T>
          </h1>
          <p className="max-w-2xl text-sm text-ink-muted">
            <T>
              Issue a stored-value code redeemable at checkout, covering part or all of an order
              total. The sitewide on/off switch is on Site Settings, next to the other storefront
              switches.
            </T>
          </p>
        </div>
        {canManage ? (
          <Button variant="primary" onClick={() => setIssuing(true)}>
            <T>Issue gift card</T>
          </Button>
        ) : null}
      </div>

      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by code or email..."
          aria-label="Search gift cards"
        />
      </div>

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>
              <T>Code</T>
            </Th>
            <Th>
              <T>Balance</T>
            </Th>
            <Th>
              <T>Status</T>
            </Th>
            <Th>
              <T>Issued to</T>
            </Th>
            <Th>
              <T>Issued</T>
            </Th>
            <Th>
              <T>Actions</T>
            </Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={6} />
        ) : cards.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={6} className="px-3 py-8">
                <EmptyState
                  title="No gift cards yet"
                  hint="Issue one for a customer goodwill gesture, a returned order's store credit, or as a purchasable gift."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {cards.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <span className="font-mono text-sm text-ink">{entry.code}</span>
                </Td>
                <Td>
                  {formatMoney(entry.balanceMinor, entry.currencyCode)}
                  {entry.balanceMinor !== entry.initialBalanceMinor ? (
                    <span className="ml-1 text-xs text-ink-muted">
                      / {formatMoney(entry.initialBalanceMinor, entry.currencyCode)}
                    </span>
                  ) : null}
                </Td>
                <Td>
                  <StatusPill status={entry.status} />
                </Td>
                <Td>{entry.issuedToEmail ?? "—"}</Td>
                <Td>{formatDateTime(entry.createdAt)}</Td>
                <Td>
                  <Button variant="secondary" onClick={() => setViewingId(entry.id)}>
                    <T>View</T>
                  </Button>
                </Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination page={page} onPageChange={setPage} rowCount={cards.length} limit={limit} />

      {issuing ? (
        <IssueGiftCardModal onClose={() => setIssuing(false)} onIssued={invalidate} />
      ) : null}

      {viewingId ? (
        <GiftCardDetailModal
          giftCardId={viewingId}
          onClose={() => setViewingId(null)}
          onChanged={invalidate}
        />
      ) : null}
    </div>
  );
}
