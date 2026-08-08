import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";

import { Button, Field, Input, StatusPill } from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { formatMoney } from "../lib/format";
import { T } from "../lib/i18n";

function Panel({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-md border border-line bg-surface p-5 shadow-card">
      <h2 className="font-display text-xl text-ink">{title}</h2>
      <p className="mt-1 text-sm text-ink-muted">{description}</p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="mt-3 text-sm text-danger">
      {error instanceof ApiError ? error.message : <T>{"Could not load this feature."}</T>}
    </p>
  );
}

export function ExpandedCommercePage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [pickup, setPickup] = useState({ name: "", line1: "", city: "", hours: "" });
  const [harvest, setHarvest] = useState({
    productId: "",
    title: "",
    expectedStart: "",
    expectedEnd: "",
    maxPreorders: "",
  });
  const [zone, setZone] = useState({
    name: "",
    postalCodes: "",
    feeRupees: "",
    leadTimeHours: "24",
  });
  const [business, setBusiness] = useState({
    companyName: "",
    gstNumber: "",
    contactEmail: "",
    creditRupees: "0",
    paymentTermsDays: "30",
  });
  const [adjustment, setAdjustment] = useState({ customerUserId: "", points: "", reason: "" });
  const [businessUser, setBusinessUser] = useState({ accountId: "", userId: "" });
  const [priceBreak, setPriceBreak] = useState({ variantId: "", minQuantity: "", priceRupees: "" });
  const [slot, setSlot] = useState({
    zoneId: "",
    dayOfWeek: "1",
    startTime: "09:00",
    endTime: "12:00",
    maxOrders: "20",
  });

  const loyalty = useQuery({ queryKey: ["expanded", "loyalty"], queryFn: api.loyaltyAccounts });
  const pickupPoints = useQuery({ queryKey: ["expanded", "pickup"], queryFn: api.pickupPoints });
  const harvestWindows = useQuery({
    queryKey: ["expanded", "harvest"],
    queryFn: api.harvestWindows,
  });
  const preorderRows = useQuery({
    queryKey: ["expanded", "preorders"],
    queryFn: api.preorders,
  });
  const deliveryZones = useQuery({ queryKey: ["expanded", "zones"], queryFn: api.deliveryZones });
  const b2bAccounts = useQuery({ queryKey: ["expanded", "b2b"], queryFn: api.b2bAccounts });
  const b2bInvoices = useQuery({
    queryKey: ["expanded", "b2b-invoices"],
    queryFn: api.b2bInvoices,
  });

  const fail = (error: unknown) =>
    toast.error(error instanceof ApiError ? error.message : "The change could not be saved.");

  const adjustMutation = useMutation({
    mutationFn: api.adjustLoyalty,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expanded", "loyalty"] });
      setAdjustment({ customerUserId: "", points: "", reason: "" });
      toast.success("Loyalty balance adjusted.");
    },
    onError: fail,
  });
  const pickupMutation = useMutation({
    mutationFn: api.createPickupPoint,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expanded", "pickup"] });
      setPickup({ name: "", line1: "", city: "", hours: "" });
      toast.success("Pickup point created.");
    },
    onError: fail,
  });
  const harvestMutation = useMutation({
    mutationFn: api.createHarvestWindow,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expanded", "harvest"] });
      setHarvest({
        productId: "",
        title: "",
        expectedStart: "",
        expectedEnd: "",
        maxPreorders: "",
      });
      toast.success("Harvest window created.");
    },
    onError: fail,
  });
  const readyMutation = useMutation({
    mutationFn: api.markHarvestReady,
    onSuccess: async ({ updated }) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["expanded", "harvest"] }),
        queryClient.invalidateQueries({ queryKey: ["expanded", "preorders"] }),
      ]);
      toast.success(`${updated} pre-order${updated === 1 ? "" : "s"} marked ready.`);
    },
    onError: fail,
  });
  const fulfillMutation = useMutation({
    mutationFn: api.fulfillPreorder,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expanded", "preorders"] });
      toast.success("Pre-order fulfilled.");
    },
    onError: fail,
  });
  const zoneMutation = useMutation({
    mutationFn: api.createDeliveryZone,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expanded", "zones"] });
      setZone({ name: "", postalCodes: "", feeRupees: "", leadTimeHours: "24" });
      toast.success("Delivery zone created.");
    },
    onError: fail,
  });
  const slotMutation = useMutation({
    mutationFn: () =>
      api.createDeliverySlot(slot.zoneId.trim(), {
        dayOfWeek: Number(slot.dayOfWeek),
        startTime: slot.startTime,
        endTime: slot.endTime,
        maxOrders: Number(slot.maxOrders),
      }),
    onSuccess: () => {
      setSlot({
        zoneId: "",
        dayOfWeek: "1",
        startTime: "09:00",
        endTime: "12:00",
        maxOrders: "20",
      });
      toast.success("Delivery slot created.");
    },
    onError: fail,
  });
  const b2bMutation = useMutation({
    mutationFn: api.createB2BAccount,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expanded", "b2b"] });
      setBusiness({
        companyName: "",
        gstNumber: "",
        contactEmail: "",
        creditRupees: "0",
        paymentTermsDays: "30",
      });
      toast.success("Business account created.");
    },
    onError: fail,
  });
  const linkMutation = useMutation({
    mutationFn: () => api.linkB2BUser(businessUser.accountId.trim(), businessUser.userId.trim()),
    onSuccess: () => {
      setBusinessUser({ accountId: "", userId: "" });
      toast.success("Customer linked to the business account.");
    },
    onError: fail,
  });
  const priceBreakMutation = useMutation({
    mutationFn: () =>
      api.createB2BPriceBreak({
        variantId: priceBreak.variantId.trim(),
        minQuantity: Number(priceBreak.minQuantity),
        priceMinor: Math.round(Number(priceBreak.priceRupees) * 100),
      }),
    onSuccess: () => {
      setPriceBreak({ variantId: "", minQuantity: "", priceRupees: "" });
      toast.success("Bulk price break created.");
    },
    onError: fail,
  });
  const invoicePaidMutation = useMutation({
    mutationFn: (invoiceId: string) => api.markB2BInvoicePaid(invoiceId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expanded", "b2b-invoices"] });
      toast.success("Invoice marked paid.");
    },
    onError: fail,
  });

  function submit(event: FormEvent, action: () => void) {
    event.preventDefault();
    action();
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold tracking-[0.12em] text-brand uppercase">
          <T>Commerce</T>
        </p>
        <h1 className="mt-1 font-display text-3xl text-ink">
          <T>Expanded commerce</T>
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-ink-muted">
          <T>
            Configure loyalty, pickup, harvest reservations, delivery logistics and wholesale
            accounts. Customer access is controlled independently by the five checkboxes in Site
            Control.
          </T>
        </p>
      </header>

      <Panel
        title="Loyalty & referrals"
        description="Review balances and make audited corrections."
      >
        <form
          className="grid gap-3 md:grid-cols-4"
          onSubmit={(event) =>
            submit(event, () =>
              adjustMutation.mutate({
                customerUserId: adjustment.customerUserId.trim(),
                points: Number(adjustment.points),
                reason: adjustment.reason.trim(),
              }),
            )
          }
        >
          <Field label="Customer user ID" htmlFor="loyalty-user">
            <Input
              id="loyalty-user"
              required
              value={adjustment.customerUserId}
              onChange={(event) =>
                setAdjustment((value) => ({ ...value, customerUserId: event.target.value }))
              }
            />
          </Field>
          <Field label="Points (+ / -)" htmlFor="loyalty-points">
            <Input
              id="loyalty-points"
              required
              type="number"
              value={adjustment.points}
              onChange={(event) =>
                setAdjustment((value) => ({ ...value, points: event.target.value }))
              }
            />
          </Field>
          <Field label="Reason" htmlFor="loyalty-reason">
            <Input
              id="loyalty-reason"
              required
              value={adjustment.reason}
              onChange={(event) =>
                setAdjustment((value) => ({ ...value, reason: event.target.value }))
              }
            />
          </Field>
          <Button
            className="self-end"
            type="submit"
            variant="primary"
            disabled={adjustMutation.isPending}
          >
            <T>Adjust points</T>
          </Button>
        </form>
        <ErrorText error={loyalty.error} />
        <ul className="mt-4 divide-y divide-line">
          {loyalty.data?.items.map((account) => (
            <li
              key={account.id}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <span>
                <strong>{account.customerName || account.customerEmail}</strong>
                <span className="ml-2 text-ink-muted">{account.customerEmail}</span>
              </span>
              <span>
                {account.balance} <T>points ·</T> <code>{account.referralCode}</code>
              </span>
            </li>
          ))}
          {loyalty.data?.items.length === 0 ? (
            <li className="py-3 text-sm text-ink-muted">
              <T>No loyalty accounts yet.</T>
            </li>
          ) : null}
        </ul>
      </Panel>

      <Panel
        title="Local pickup points"
        description="Active points appear as free checkout alternatives."
      >
        <form
          className="grid gap-3 md:grid-cols-5"
          onSubmit={(event) =>
            submit(event, () =>
              pickupMutation.mutate({
                name: pickup.name.trim(),
                address: { line1: pickup.line1.trim(), city: pickup.city.trim() },
                hours: pickup.hours.trim() || undefined,
              }),
            )
          }
        >
          <Field label="Name" htmlFor="pickup-name">
            <Input
              id="pickup-name"
              required
              value={pickup.name}
              onChange={(event) => setPickup((value) => ({ ...value, name: event.target.value }))}
            />
          </Field>
          <Field label="Address" htmlFor="pickup-address">
            <Input
              id="pickup-address"
              required
              value={pickup.line1}
              onChange={(event) => setPickup((value) => ({ ...value, line1: event.target.value }))}
            />
          </Field>
          <Field label="City" htmlFor="pickup-city">
            <Input
              id="pickup-city"
              required
              value={pickup.city}
              onChange={(event) => setPickup((value) => ({ ...value, city: event.target.value }))}
            />
          </Field>
          <Field label="Hours" htmlFor="pickup-hours">
            <Input
              id="pickup-hours"
              value={pickup.hours}
              onChange={(event) => setPickup((value) => ({ ...value, hours: event.target.value }))}
            />
          </Field>
          <Button
            className="self-end"
            type="submit"
            variant="primary"
            disabled={pickupMutation.isPending}
          >
            <T>Add point</T>
          </Button>
        </form>
        <ErrorText error={pickupPoints.error} />
        <ul className="mt-4 divide-y divide-line">
          {pickupPoints.data?.items.map((point) => (
            <li key={point.id} className="flex items-center justify-between py-3 text-sm">
              <span>
                <strong>{point.name}</strong>
                <span className="ml-2 text-ink-muted">{point.hours}</span>
              </span>
              <StatusPill status={point.status} />
            </li>
          ))}
        </ul>
      </Panel>

      <Panel
        title="Harvest calendar"
        description="Reserve future capacity without consuming current inventory."
      >
        <form
          className="grid gap-3 md:grid-cols-6"
          onSubmit={(event) =>
            submit(event, () =>
              harvestMutation.mutate({
                productId: harvest.productId.trim(),
                title: harvest.title.trim() || undefined,
                expectedStart: harvest.expectedStart,
                expectedEnd: harvest.expectedEnd,
                maxPreorders: harvest.maxPreorders ? Number(harvest.maxPreorders) : undefined,
              }),
            )
          }
        >
          <Field label="Product ID" htmlFor="harvest-product">
            <Input
              id="harvest-product"
              required
              value={harvest.productId}
              onChange={(event) =>
                setHarvest((value) => ({ ...value, productId: event.target.value }))
              }
            />
          </Field>
          <Field label="Label" htmlFor="harvest-title">
            <Input
              id="harvest-title"
              value={harvest.title}
              onChange={(event) => setHarvest((value) => ({ ...value, title: event.target.value }))}
            />
          </Field>
          <Field label="Expected start" htmlFor="harvest-start">
            <Input
              id="harvest-start"
              required
              type="date"
              value={harvest.expectedStart}
              onChange={(event) =>
                setHarvest((value) => ({ ...value, expectedStart: event.target.value }))
              }
            />
          </Field>
          <Field label="Expected end" htmlFor="harvest-end">
            <Input
              id="harvest-end"
              required
              type="date"
              value={harvest.expectedEnd}
              onChange={(event) =>
                setHarvest((value) => ({ ...value, expectedEnd: event.target.value }))
              }
            />
          </Field>
          <Field label="Capacity" htmlFor="harvest-cap">
            <Input
              id="harvest-cap"
              type="number"
              min={1}
              value={harvest.maxPreorders}
              onChange={(event) =>
                setHarvest((value) => ({ ...value, maxPreorders: event.target.value }))
              }
            />
          </Field>
          <Button
            className="self-end"
            type="submit"
            variant="primary"
            disabled={harvestMutation.isPending}
          >
            <T>Add window</T>
          </Button>
        </form>
        <ErrorText error={harvestWindows.error} />
        <ul className="mt-4 divide-y divide-line">
          {harvestWindows.data?.items.map((window) => (
            <li
              key={window.id}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <span>
                <strong>{window.title || window.productName}</strong>
                <span className="ml-2 text-ink-muted">
                  {window.expectedStart} – {window.expectedEnd}
                </span>
              </span>
              <span>
                {window.currentPreorders}
                {window.maxPreorders ? ` / ${window.maxPreorders}` : ""} <T>reserved ·</T>{" "}
                <StatusPill status={window.status} />
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
          {harvestWindows.data?.items.map((window) => (
            <Button
              key={window.id}
              type="button"
              disabled={readyMutation.isPending}
              onClick={() => readyMutation.mutate(window.id)}
            >
              <T>Mark</T> {window.title || window.productName} ready
            </Button>
          ))}
        </div>
        <ErrorText error={preorderRows.error} />
        <ul className="mt-4 divide-y divide-line border-t border-line">
          {preorderRows.data?.items.map((preorder) => (
            <li
              key={preorder.id}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <span>
                <strong>{preorder.productName}</strong>
                <span className="ml-2 text-ink-muted">
                  {preorder.orderReference} <T>/ qty</T> {preorder.quantity}
                </span>
              </span>
              <span className="flex items-center gap-2">
                <StatusPill status={preorder.status} />
                {preorder.status === "reserved" || preorder.status === "ready" ? (
                  <Button
                    type="button"
                    disabled={fulfillMutation.isPending}
                    onClick={() => fulfillMutation.mutate(preorder.id)}
                  >
                    <T>Fulfill</T>
                  </Button>
                ) : null}
              </span>
            </li>
          ))}
          {preorderRows.data?.items.length === 0 ? (
            <li className="py-3 text-sm text-ink-muted">
              <T>No pre-orders yet.</T>
            </li>
          ) : null}
        </ul>
      </Panel>

      <Panel
        title="Delivery zones & slots"
        description="PIN patterns accept an exact value or a trailing wildcard, such as 560*."
      >
        <form
          className="grid gap-3 md:grid-cols-5"
          onSubmit={(event) =>
            submit(event, () =>
              zoneMutation.mutate({
                name: zone.name.trim(),
                postalCodes: zone.postalCodes
                  .split(",")
                  .map((value) => value.trim())
                  .filter(Boolean),
                feeOverrideMinor: zone.feeRupees
                  ? Math.round(Number(zone.feeRupees) * 100)
                  : undefined,
                leadTimeHours: Number(zone.leadTimeHours),
              }),
            )
          }
        >
          <Field label="Zone name" htmlFor="zone-name">
            <Input
              id="zone-name"
              required
              value={zone.name}
              onChange={(event) => setZone((value) => ({ ...value, name: event.target.value }))}
            />
          </Field>
          <Field label="PIN patterns" htmlFor="zone-pins">
            <Input
              id="zone-pins"
              required
              placeholder="560*, 561001"
              value={zone.postalCodes}
              onChange={(event) =>
                setZone((value) => ({ ...value, postalCodes: event.target.value }))
              }
            />
          </Field>
          <Field label="Fee, ₹" htmlFor="zone-fee">
            <Input
              id="zone-fee"
              type="number"
              min={0}
              value={zone.feeRupees}
              onChange={(event) =>
                setZone((value) => ({ ...value, feeRupees: event.target.value }))
              }
            />
          </Field>
          <Field label="Lead time, hours" htmlFor="zone-lead">
            <Input
              id="zone-lead"
              required
              type="number"
              min={0}
              value={zone.leadTimeHours}
              onChange={(event) =>
                setZone((value) => ({ ...value, leadTimeHours: event.target.value }))
              }
            />
          </Field>
          <Button
            className="self-end"
            type="submit"
            variant="primary"
            disabled={zoneMutation.isPending}
          >
            <T>Add zone</T>
          </Button>
        </form>
        <form
          className="mt-4 grid gap-3 border-t border-line pt-4 md:grid-cols-6"
          onSubmit={(event) => submit(event, () => slotMutation.mutate())}
        >
          <Field label="Zone ID" htmlFor="slot-zone">
            <Input
              id="slot-zone"
              required
              value={slot.zoneId}
              onChange={(event) => setSlot((value) => ({ ...value, zoneId: event.target.value }))}
            />
          </Field>
          <Field label="Day (0 Sun – 6 Sat)" htmlFor="slot-day">
            <Input
              id="slot-day"
              required
              type="number"
              min={0}
              max={6}
              value={slot.dayOfWeek}
              onChange={(event) =>
                setSlot((value) => ({ ...value, dayOfWeek: event.target.value }))
              }
            />
          </Field>
          <Field label="Starts" htmlFor="slot-start">
            <Input
              id="slot-start"
              required
              type="time"
              value={slot.startTime}
              onChange={(event) =>
                setSlot((value) => ({ ...value, startTime: event.target.value }))
              }
            />
          </Field>
          <Field label="Ends" htmlFor="slot-end">
            <Input
              id="slot-end"
              required
              type="time"
              value={slot.endTime}
              onChange={(event) => setSlot((value) => ({ ...value, endTime: event.target.value }))}
            />
          </Field>
          <Field label="Capacity" htmlFor="slot-cap">
            <Input
              id="slot-cap"
              required
              type="number"
              min={1}
              value={slot.maxOrders}
              onChange={(event) =>
                setSlot((value) => ({ ...value, maxOrders: event.target.value }))
              }
            />
          </Field>
          <Button className="self-end" type="submit" disabled={slotMutation.isPending}>
            <T>Add slot</T>
          </Button>
        </form>
        <ErrorText error={deliveryZones.error} />
        <ul className="mt-4 divide-y divide-line">
          {deliveryZones.data?.items.map((item) => (
            <li
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <span>
                <strong>{item.name}</strong>
                <span className="ml-2 text-ink-muted">{item.postalCodes.join(", ")}</span>
              </span>
              <span>
                {item.feeOverrideMinor == null ? (
                  <T>{"Default fee"}</T>
                ) : (
                  formatMoney(item.feeOverrideMinor)
                )}{" "}
                · {item.leadTimeHours}
                <T>h lead</T>
              </span>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel
        title="B2B / bulk ordering"
        description="Create companies, link customers and configure quantity price breaks."
      >
        <form
          className="grid gap-3 md:grid-cols-6"
          onSubmit={(event) =>
            submit(event, () =>
              b2bMutation.mutate({
                companyName: business.companyName.trim(),
                gstNumber: business.gstNumber.trim() || undefined,
                contactEmail: business.contactEmail.trim() || undefined,
                creditLimitMinor: Math.round(Number(business.creditRupees) * 100),
                paymentTermsDays: Number(business.paymentTermsDays),
              }),
            )
          }
        >
          <Field label="Company" htmlFor="b2b-company">
            <Input
              id="b2b-company"
              required
              value={business.companyName}
              onChange={(event) =>
                setBusiness((value) => ({ ...value, companyName: event.target.value }))
              }
            />
          </Field>
          <Field label="GST number" htmlFor="b2b-gst">
            <Input
              id="b2b-gst"
              value={business.gstNumber}
              onChange={(event) =>
                setBusiness((value) => ({ ...value, gstNumber: event.target.value }))
              }
            />
          </Field>
          <Field label="Contact email" htmlFor="b2b-email">
            <Input
              id="b2b-email"
              type="email"
              value={business.contactEmail}
              onChange={(event) =>
                setBusiness((value) => ({ ...value, contactEmail: event.target.value }))
              }
            />
          </Field>
          <Field label="Credit limit, ₹" htmlFor="b2b-credit">
            <Input
              id="b2b-credit"
              type="number"
              min={0}
              value={business.creditRupees}
              onChange={(event) =>
                setBusiness((value) => ({ ...value, creditRupees: event.target.value }))
              }
            />
          </Field>
          <Field label="Terms, days" htmlFor="b2b-terms">
            <Input
              id="b2b-terms"
              type="number"
              min={0}
              max={365}
              value={business.paymentTermsDays}
              onChange={(event) =>
                setBusiness((value) => ({ ...value, paymentTermsDays: event.target.value }))
              }
            />
          </Field>
          <Button
            className="self-end"
            type="submit"
            variant="primary"
            disabled={b2bMutation.isPending}
          >
            <T>Add business</T>
          </Button>
        </form>
        <div className="mt-4 grid gap-4 border-t border-line pt-4 lg:grid-cols-2">
          <form
            className="grid gap-3 sm:grid-cols-3"
            onSubmit={(event) => submit(event, () => linkMutation.mutate())}
          >
            <Field label="Business account ID" htmlFor="b2b-link-account">
              <Input
                id="b2b-link-account"
                required
                value={businessUser.accountId}
                onChange={(event) =>
                  setBusinessUser((value) => ({ ...value, accountId: event.target.value }))
                }
              />
            </Field>
            <Field label="Customer user ID" htmlFor="b2b-link-user">
              <Input
                id="b2b-link-user"
                required
                value={businessUser.userId}
                onChange={(event) =>
                  setBusinessUser((value) => ({ ...value, userId: event.target.value }))
                }
              />
            </Field>
            <Button className="self-end" type="submit" disabled={linkMutation.isPending}>
              <T>Link customer</T>
            </Button>
          </form>
          <form
            className="grid gap-3 sm:grid-cols-4"
            onSubmit={(event) => submit(event, () => priceBreakMutation.mutate())}
          >
            <Field label="Variant ID" htmlFor="b2b-price-variant">
              <Input
                id="b2b-price-variant"
                required
                value={priceBreak.variantId}
                onChange={(event) =>
                  setPriceBreak((value) => ({ ...value, variantId: event.target.value }))
                }
              />
            </Field>
            <Field label="Minimum qty" htmlFor="b2b-price-qty">
              <Input
                id="b2b-price-qty"
                required
                type="number"
                min={1}
                value={priceBreak.minQuantity}
                onChange={(event) =>
                  setPriceBreak((value) => ({ ...value, minQuantity: event.target.value }))
                }
              />
            </Field>
            <Field label="Unit price, ₹" htmlFor="b2b-price-value">
              <Input
                id="b2b-price-value"
                required
                type="number"
                min={0}
                value={priceBreak.priceRupees}
                onChange={(event) =>
                  setPriceBreak((value) => ({ ...value, priceRupees: event.target.value }))
                }
              />
            </Field>
            <Button className="self-end" type="submit" disabled={priceBreakMutation.isPending}>
              <T>Add price</T>
            </Button>
          </form>
        </div>
        <ErrorText error={b2bAccounts.error} />
        <ul className="mt-4 divide-y divide-line">
          {b2bAccounts.data?.items.map((account) => (
            <li
              key={account.id}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <span>
                <strong>{account.companyName}</strong>
                <span className="ml-2 text-ink-muted">{account.contactEmail}</span>
              </span>
              <span>
                {account.paymentTermsDays}
                <T>-day terms ·</T> <StatusPill status={account.status} />
              </span>
            </li>
          ))}
        </ul>
        <ErrorText error={b2bInvoices.error} />
        <ul className="mt-4 divide-y divide-line border-t border-line">
          {b2bInvoices.data?.items.map((invoice) => (
            <li
              key={invoice.id}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <span>
                <strong>{invoice.invoiceNumber}</strong>
                <span className="ml-2 text-ink-muted">
                  {invoice.companyName} / {invoice.orderReference} <T>/ due</T>{" "}
                  {invoice.dueDate.slice(0, 10)}
                </span>
              </span>
              <span className="flex items-center gap-2">
                {formatMoney(invoice.amountMinor)} / <StatusPill status={invoice.status} />
                {invoice.status === "issued" || invoice.status === "overdue" ? (
                  <Button
                    type="button"
                    disabled={invoicePaidMutation.isPending}
                    onClick={() => invoicePaidMutation.mutate(invoice.id)}
                  >
                    <T>Mark paid</T>
                  </Button>
                ) : null}
              </span>
            </li>
          ))}
          {b2bInvoices.data?.items.length === 0 ? (
            <li className="py-3 text-sm text-ink-muted">
              <T>No B2B invoices yet.</T>
            </li>
          ) : null}
        </ul>
      </Panel>
    </div>
  );
}
