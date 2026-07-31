/**
 * Revenue page behaviour that protects money or tells the operator the truth.
 *
 * The rendering details are not worth pinning; these are the things that would
 * cause a real mistake if they regressed — paying a farm with nothing owed,
 * showing a payment control to someone who cannot use it, or sending a payout
 * request without the amount the operator actually approved.
 *
 * Uses `fireEvent` rather than `user-event`, which is not a dependency of this
 * workspace; the interactions here are single clicks and value changes, where
 * the two behave the same.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../components/toast";
import { api, type FarmRevenueRow, type FarmRevenueSummary } from "../lib/api";
import { RevenuePage } from "./revenue";

function farmRow(overrides: Partial<FarmRevenueRow> = {}): FarmRevenueRow {
  return {
    farmId: "farm_devika",
    farmName: "Devika Organics",
    farmSlug: "devika-organics",
    farmerName: "Devika Kulkarni",
    region: "Ratnagiri",
    status: "published",
    currencyCode: "INR",
    ownerUserId: "usr_devika",
    ownerName: "Devika Kulkarni",
    ownerEmail: "devika@example.test",
    commissionBps: 1500,
    commissionPercent: 15,
    commissionSource: "default",
    orderCount: 1,
    grossMinor: 89_900,
    refundedMinor: 0,
    netRevenueMinor: 89_900,
    commissionMinor: 13_485,
    farmEarningsMinor: 76_415,
    paidOutMinor: 0,
    payoutCount: 0,
    outstandingItemCount: 1,
    outstandingGrossMinor: 89_900,
    outstandingRefundedMinor: 0,
    outstandingNetMinor: 89_900,
    outstandingCommissionMinor: 13_485,
    outstandingPayoutMinor: 76_415,
    ...overrides,
  };
}

function summary(farms: FarmRevenueRow[]): FarmRevenueSummary {
  return {
    defaultCommissionBps: 1500,
    defaultCommissionPercent: 15,
    farms,
    totals: {
      grossMinor: 89_900,
      refundedMinor: 0,
      netRevenueMinor: 89_900,
      commissionMinor: 13_485,
      farmEarningsMinor: 76_415,
      paidOutMinor: 0,
      outstandingPayoutMinor: 76_415,
    },
  };
}

function renderPage(permissions: string[]) {
  vi.spyOn(api, "me").mockResolvedValue({
    id: "usr_admin",
    displayName: "Owner",
    email: "owner@truegrit.test",
    isSuperAdmin: true,
    permissions,
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <RevenuePage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The farm row's rate editor. Index 0 is the house default above the table. */
async function openFarmRateEditor() {
  await screen.findByText("Devika Organics");
  const editButtons = await screen.findAllByRole("button", { name: "Edit" });
  const farmEditButton = editButtons.at(1);
  if (!farmEditButton) throw new Error("Expected an Edit button on the farm row.");
  fireEvent.click(farmEditButton);
  return screen.getByLabelText(/commission percentage/i);
}

beforeEach(() => {
  vi.spyOn(api, "revenue").mockResolvedValue(summary([farmRow()]));
});

afterEach(() => {
  // This workspace runs vitest with `globals: false`, so Testing Library never
  // registers its own auto-cleanup — without this, each test renders on top of
  // the last one's DOM and every query finds duplicates.
  cleanup();
  vi.restoreAllMocks();
});

describe("RevenuePage", () => {
  it("shows each farm's net revenue, cut and outstanding balance", async () => {
    renderPage(["revenue.view", "revenue.manage"]);
    expect(await screen.findByText("Devika Organics")).toBeInTheDocument();
    // ₹899 net, ₹134.85 platform cut, ₹764.15 payable to the farm.
    // `formatMoney` omits paise when there are none, hence "₹899" not "₹899.00".
    expect(screen.getAllByText(/₹899\b/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("₹134.85").length).toBeGreaterThan(0);
    expect(screen.getAllByText("₹764.15").length).toBeGreaterThan(0);
  });

  it("links to the detailed revenue breakdown for the farm", async () => {
    renderPage(["revenue.view"]);
    const link = await screen.findByRole("link", { name: /detailed revenue/i });
    expect(link).toHaveAttribute("href", "/revenue/farm_devika");
  });

  it("hides the payment control from a viewer who cannot issue payouts", async () => {
    renderPage(["revenue.view"]);
    await screen.findByText("Devika Organics");
    expect(screen.queryByRole("button", { name: /issue payment/i })).not.toBeInTheDocument();
  });

  it("does not offer payment when nothing is outstanding", async () => {
    vi.spyOn(api, "revenue").mockResolvedValue(
      summary([
        farmRow({ outstandingPayoutMinor: 0, outstandingItemCount: 0, paidOutMinor: 76_415 }),
      ]),
    );
    renderPage(["revenue.view", "revenue.manage"]);
    expect(await screen.findByRole("button", { name: /issue payment/i })).toBeDisabled();
  });

  it("sends the amount shown on screen so a moved balance is caught server-side", async () => {
    const issue = vi.spyOn(api, "issueFarmPayout").mockResolvedValue({
      payoutId: "fpo_1",
      farmId: "farm_devika",
      farmName: "Devika Organics",
      currencyCode: "INR",
      payoutMinor: 76_415,
      commissionMinor: 13_485,
      itemCount: 1,
    });
    renderPage(["revenue.view", "revenue.manage"]);

    fireEvent.click(await screen.findByRole("button", { name: /issue payment/i }));
    fireEvent.change(screen.getByLabelText(/transfer reference/i), {
      target: { value: "UTR-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /record payment/i }));

    await waitFor(() =>
      expect(issue).toHaveBeenCalledWith("farm_devika", {
        reference: "UTR-123",
        note: "",
        expectedPayoutMinor: 76_415,
      }),
    );
  });

  it("states that recording a payment does not transfer money", async () => {
    renderPage(["revenue.view", "revenue.manage"]);
    fireEvent.click(await screen.findByRole("button", { name: /issue payment/i }));
    expect(await screen.findByText(/make the transfer to/i)).toBeInTheDocument();
  });

  it("saves a per-farm commission override as a percentage", async () => {
    const setRate = vi
      .spyOn(api, "setFarmCommission")
      .mockResolvedValue({ commissionBps: 1250, commissionSource: "farm" });
    renderPage(["revenue.view", "revenue.manage"]);

    const input = await openFarmRateEditor();
    fireEvent.change(input, { target: { value: "12.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(setRate).toHaveBeenCalledWith("farm_devika", 12.5));
  });

  it("clears a farm override with an empty value, which is not the same as zero", async () => {
    const setRate = vi
      .spyOn(api, "setFarmCommission")
      .mockResolvedValue({ commissionBps: 1500, commissionSource: "default" });
    renderPage(["revenue.view", "revenue.manage"]);

    const input = await openFarmRateEditor();
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(setRate).toHaveBeenCalledWith("farm_devika", null));
  });

  it("treats zero as a real rate, not a cleared one", async () => {
    const setRate = vi
      .spyOn(api, "setFarmCommission")
      .mockResolvedValue({ commissionBps: 0, commissionSource: "farm" });
    renderPage(["revenue.view", "revenue.manage"]);

    const input = await openFarmRateEditor();
    fireEvent.change(input, { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(setRate).toHaveBeenCalledWith("farm_devika", 0));
  });

  it("rejects a rate outside 0-100 without calling the API", async () => {
    const setRate = vi.spyOn(api, "setFarmCommission");
    renderPage(["revenue.view", "revenue.manage"]);

    const input = await openFarmRateEditor();
    fireEvent.change(input, { target: { value: "150" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Enter 0–100.")).toBeInTheDocument();
    expect(setRate).not.toHaveBeenCalled();
  });
});
